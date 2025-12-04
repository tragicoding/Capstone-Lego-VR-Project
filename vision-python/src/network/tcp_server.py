# vision-python/src/network/tcp_server.py

import socket
import json
import time
import math
import os
import sys

import cv2
import numpy as np

from vision.aruco_detector import draw_markers_with_centers
from vision.grid_overlay import draw_grid


# ======================================================================
# sys.path 설정: src/ 를 PYTHONPATH에 추가해서
# config, mapping 패키지를 절대 import 로 사용
# ======================================================================

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from config.marker_config import (
    BOARD_CORNER_IDS,
    BUILDING_MARKERS,
    CHARACTER_MARKERS,
    IDEAL_BOARD_CORNERS,
    CORNER_ANCHOR_INDEX,
    EXPECTED_OBJECT_IDS,
)
from mapping.grid_mapping import BoardCoord, board_to_stud, board_to_unity

try:
    from config.camera_config import CAMERA_INDEX
except Exception:
    CAMERA_INDEX = 0  # fallback


# ======================================================================
# TCP 설정
# ======================================================================

HOST = "0.0.0.0"     # Unity는 127.0.0.1로 접속
PORT = 5000          # Unity NetworkManager 포트와 동일하게
SEND_FPS = 10        # 초당 전송 횟수 (Unity로 보내는 주기)
SEND_INTERVAL = 1.0 / SEND_FPS


# ======================================================================
# Smoothing & Freeze 설정 (main.py와 동일)
# ======================================================================

POS_SMOOTH = 0.25          # 위치 스무딩
ROT_SMOOTH = 0.25          # 회전 스무딩
FREEZE_THRESHOLD = 1.0     # 기준 마커 안정성 기준 (보드좌표 오차)
DATA_STABLE_FRAMES = 10    # 건물/캐릭터가 같은 칸+회전으로 유지되어야 하는 프레임 수
SPAWN_OFFSET_STUDS = 5     # 마커에서 건물/캐릭터가 떨어져 생성될 스터드 거리

homography_frozen = False      # 기준 마커 안정화 여부 (보드 좌표계 고정)
data_frozen = False            # 전체 데이터(건물/캐릭터)까지 안정화 여부

pos_cache = {}                 # {id : (bx, by)}   - 위치 스무딩용
rot_cache = {}                 # {id : yaw_deg}    - 회전 스무딩용

last_state = {}                # {id : (spawn_sx, spawn_sy, yaw_snapped)}
stable_count = {}              # {id : 연속 동일 상태 프레임 수}

final_payload = None           # data_frozen 시점의 최종 데이터 (Unity로 넘길 데이터)

# 스터드/유니티 범위
STUD_MIN = 1
STUD_MAX = 32
UNITY_PER_STUD = 2  # 1 stud = 2 unity grid
BOARD_EXTENT_X = 33.0
BOARD_EXTENT_Y = 33.0
NUM_STUDS_X = 32
NUM_STUDS_Y = 32

# Homography 전역
homography = None
_prev_H = None  # smooth_homography용


# ======================================================================
# ArUco 설정 (OpenCV 4.7+ 완전 호환 버전)
# ======================================================================

ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)

# OpenCV 버전에 따라 DetectorParameters 생성 방식이 다름
try:
    # 최신 버전 (4.7+) 스타일
    ARUCO_PARAMS = cv2.aruco.DetectorParameters()
except Exception:
    ARUCO_PARAMS = cv2.aruco.DetectorParameters_create()

# OpenCV 4.7+: ArucoDetector 클래스 사용
try:
    ARUCO_DETECTOR = cv2.aruco.ArucoDetector(ARUCO_DICT, ARUCO_PARAMS)
    USE_ARUCO_DETECTOR = True
    print("[ARUCO] Using ArucoDetector API.")
except Exception:
    USE_ARUCO_DETECTOR = False
    print("[ARUCO] Using legacy detectMarkers API.")


def detect_markers(frame):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    if USE_ARUCO_DETECTOR:
        corners, ids, _ = ARUCO_DETECTOR.detectMarkers(gray)
        return corners, ids
    else:
        corners, ids, _ = cv2.aruco.detectMarkers(
            gray, ARUCO_DICT, parameters=ARUCO_PARAMS
        )
        return corners, ids


def extract_marker_info(corners, ids):
    """
    main.py가 기대하는 포맷:
    [
      {
        "id": int,
        "corners": np.ndarray (4,2),
        "center": (cx, cy)
      },
      ...
    ]
    """
    markers = []
    if ids is None or len(corners) == 0:
        return markers

    ids = ids.flatten()
    for mid, c in zip(ids, corners):
        pts = c[0]  # (4,2)
        cx = float(pts[:, 0].mean())
        cy = float(pts[:, 1].mean())
        markers.append({
            "id": int(mid),
            "corners": pts,
            "center": (cx, cy),
        })
    return markers


# ======================================================================
# Homography 관련 함수 (homography.py 내용 inline)
# ======================================================================

def compute_board_homography(markers):
    """
    기준 마커 4개의 "보드와 맞닿는 코너"를 이용해
    이미지 좌표 → 보드 평면 좌표(0~33)의 Homography 행렬 H를 계산한다.
    """
    src_pts = []
    dst_pts = []

    for m in markers:
        mid = m["id"]
        if mid in BOARD_CORNER_IDS:
            corners = m["corners"]  # (4,2)

            corner_idx = CORNER_ANCHOR_INDEX[mid]
            corner = corners[corner_idx]  # (x, y)

            src_pts.append([corner[0], corner[1]])

            bx, by = IDEAL_BOARD_CORNERS[mid]
            dst_pts.append([bx, by])

    if len(src_pts) < 4:
        return None

    src_pts = np.array(src_pts, dtype=np.float32)
    dst_pts = np.array(dst_pts, dtype=np.float32)

    H, _ = cv2.findHomography(src_pts, dst_pts, method=0)
    return H


def image_to_board_point(point, H):
    """
    Homography H를 이용해 이미지 좌표 (x, y)를 보드 평면 좌표 (bx, by)로 변환.
    """
    x, y = point
    vec = np.array([x, y, 1.0], dtype=np.float32)
    out = H @ vec
    if out[2] == 0:
        return 0.0, 0.0
    out /= out[2]
    return float(out[0]), float(out[1])


def smooth_homography(H_new, alpha=0.2):
    """
    간단한 지수 스무딩을 이용해 Homography를 안정화한다.
    """
    global _prev_H

    if H_new is None:
        return _prev_H

    if _prev_H is None:
        _prev_H = H_new
        return H_new

    H_smooth = alpha * H_new + (1.0 - alpha) * _prev_H
    _prev_H = H_smooth
    return H_smooth


# ======================================================================
# main.py 에서 쓰던 헬퍼 함수들
# ======================================================================

def smooth_value(prev, new, factor):
    if prev is None:
        return new
    return prev * (1 - factor) + new * factor


def classify_marker(mid):
    if mid in BUILDING_MARKERS:
        return "building", BUILDING_MARKERS[mid]
    if mid in CHARACTER_MARKERS:
        return "character", CHARACTER_MARKERS[mid]
    if mid in BOARD_CORNER_IDS:
        return "corner", "BoardCorner"
    return "unknown", None


def is_homography_stable(corner_positions):
    """
    corner_positions: {id: (bx,by)}
    4개 기준 마커가 각자의 이상 위치에서 FREEZE_THRESHOLD 이내이면 True
    """
    for mid, (bx, by) in corner_positions.items():
        tx, ty = IDEAL_BOARD_CORNERS[mid]
        dist = math.sqrt((bx - tx) ** 2 + (by - ty) ** 2)
        if dist > FREEZE_THRESHOLD:
            return False
    return True


def compute_snapped_yaw_deg(marker, H):
    """
    rotation 0/90/180/270 계산
    corners[0] -> corners[1] 방향 벡터 이용 (top edge 방향)
    """
    c = marker["corners"]
    p0 = (c[0][0], c[0][1])
    p1 = (c[1][0], c[1][1])

    bx0, by0 = image_to_board_point(p0, H)
    bx1, by1 = image_to_board_point(p1, H)

    dx = bx1 - bx0
    dy = by1 - by0

    angle = math.degrees(math.atan2(dy, dx))
    angle = (angle + 360) % 360

    snapped = round(angle / 90) * 90
    snapped %= 360
    return snapped


def compute_spawn_stud_from_marker(stud_x, stud_y, yaw_snapped, offset=SPAWN_OFFSET_STUDS):
    """
    마커의 스터드 좌표(stud_x, stud_y)와 yaw_snapped(0/90/180/270)를 이용해서
    '정자세의 아랫변(건물 앞면)' 방향으로 offset만큼 떨어진
    건물/캐릭터 스폰 스터드 좌표를 계산한다.
    (main.py와 같은 규칙)
    """
    if yaw_snapped == 0:
        dx, dy = 0, -offset
    elif yaw_snapped == 90:
        dx, dy = offset, 0
    elif yaw_snapped == 180:
        dx, dy = 0, offset
    elif yaw_snapped == 270:
        dx, dy = -offset, 0
    else:
        rad = math.radians(yaw_snapped - 90.0)  # top->front 회전
        dx = round(offset * math.cos(rad))
        dy = round(offset * math.sin(rad))

    sx = stud_x + dx
    sy = stud_y + dy

    sx = max(STUD_MIN, min(STUD_MAX, sx))
    sy = max(STUD_MIN, min(STUD_MAX, sy))

    return sx, sy


def stud_to_unity_grid(sx, sy):
    """
    스터드(1~32) → 유니티 그리드(0~63)
    stud 1 → unity 0
    stud 32 → unity 62
    """
    ux = (sx - 1) * UNITY_PER_STUD
    uy = (sy - 1) * UNITY_PER_STUD
    return ux, uy


def update_stability(mid, spawn_sx, spawn_sy, yaw_snapped):
    """
    각 건물/캐릭터 마커의 (스폰 스터드, yaw_snapped)이
    연속으로 몇 프레임 유지되는지 카운트.
    """
    global last_state, stable_count

    state = (spawn_sx, spawn_sy, yaw_snapped)
    prev = last_state.get(mid)

    if prev == state:
        stable_count[mid] = stable_count.get(mid, 0) + 1
    else:
        stable_count[mid] = 1
        last_state[mid] = state


def are_all_expected_objects_stable(visible_ids):
    """
    EXPECTED_OBJECT_IDS(건물 4개 + 캐릭터 2개)가
    1) 이번 프레임에 모두 인식되고 있고
    2) 각자의 stable_count가 DATA_STABLE_FRAMES 이상인지 확인
    """
    visible_ids = set(visible_ids)
    if not set(EXPECTED_OBJECT_IDS).issubset(visible_ids):
        return False

    for mid in EXPECTED_OBJECT_IDS:
        if stable_count.get(mid, 0) < DATA_STABLE_FRAMES:
            return False

    return True


# ======================================================================
# 한 프레임 처리 → payload 생성 (main.py 로직 압축)
# ======================================================================

def process_frame_and_build_payload(frame):
    """
    main.py의 run_aruco_with_all_features()에서 하던 일을
    'payload 생성' 관점으로만 정리한 함수.

    반환값:
        payload_dict  ({"objects": [...]})
    """
    global homography, homography_frozen, data_frozen, final_payload
    global pos_cache, rot_cache


    
    corners, ids = detect_markers(frame)
    markers = extract_marker_info(corners, ids)
    frame = draw_markers_with_centers(frame, markers)

    # 1) homography 계산/업데이트 (freeze 전까지만)
    if markers and not homography_frozen:
        H_new = compute_board_homography(markers)
        if H_new is not None:
            homography = smooth_homography(H_new)

            corner_positions = {}
            for m in markers:
                mid = m["id"]
                if mid in BOARD_CORNER_IDS:
                    corner_idx = CORNER_ANCHOR_INDEX[mid]
                    acx, acy = m["corners"][corner_idx]
                    bx, by = image_to_board_point((acx, acy), homography)
                    corner_positions[mid] = (bx, by)

            if len(corner_positions) == 4 and is_homography_stable(corner_positions):
                homography_frozen = True
                print("[INFO] Homography frozen (board corners stable).")

    if homography is None:
        return {"objects": []}

    objects_for_payload = []
    visible_object_ids = []

    # 2) 각 마커에 대해 board/stud/unity/yaw/spawn 계산
    if markers:
        if homography_frozen:
            H_inv = np.linalg.inv(homography)
            frame = draw_grid(frame, H_inv, step=1)
        for m in markers:
            mid = m["id"]
            cx, cy = m["center"]
            kind, label = classify_marker(mid)

            # 기준 마커는 homography 용으로만 사용
            if kind == "corner":
                continue

            # center → board 좌표
            bx, by = image_to_board_point((cx, cy), homography)

            # 위치 스무딩
            prev_pos = pos_cache.get(mid)
            if prev_pos is None:
                pos_cache[mid] = (bx, by)
            else:
                bx = smooth_value(prev_pos[0], bx, POS_SMOOTH)
                by = smooth_value(prev_pos[1], by, POS_SMOOTH)
                pos_cache[mid] = (bx, by)

            board = BoardCoord(bx, by)
            stud = board_to_stud(board)
            unity = board_to_unity(board)

            if kind in ("building", "character"):
                visible_object_ids.append(mid)

                # 회전
                yaw_snapped = compute_snapped_yaw_deg(m, homography)

                prev_yaw = rot_cache.get(mid)
                if prev_yaw is None:
                    rot_cache[mid] = yaw_snapped
                    yaw_for_output = yaw_snapped
                else:
                    yaw_smoothed = smooth_value(prev_yaw, yaw_snapped, ROT_SMOOTH)
                    rot_cache[mid] = yaw_smoothed
                    yaw_for_output = round(yaw_smoothed / 90) * 90
                    yaw_for_output %= 360

                # 스폰 스터드 (마커에서 offset 떨어진 위치)
                spawn_sx, spawn_sy = compute_spawn_stud_from_marker(
                    stud.x, stud.y, yaw_snapped, offset=SPAWN_OFFSET_STUDS
                )
                spawn_ux, spawn_uy = stud_to_unity_grid(spawn_sx, spawn_sy)

                # 안정성 체크
                update_stability(mid, spawn_sx, spawn_sy, yaw_snapped)

                obj_info = {
                    "id": mid,
                    "kind": kind,
                    "label": label,
                    "marker_board": {"x": bx, "y": by},
                    "marker_stud": {"x": stud.x, "y": stud.y},
                    "marker_unity": {"x": unity.x, "y": unity.y},
                    "spawn_stud": {"x": spawn_sx, "y": spawn_sy},
                    "spawn_unity": {"x": spawn_ux, "y": spawn_uy},
                    "yaw_deg": yaw_for_output,
                }
                objects_for_payload.append(obj_info)

    # 3) freeze 조건 체크
    if not data_frozen:
        if homography_frozen and are_all_expected_objects_stable(visible_object_ids):
            data_frozen = True
            final_payload = {"objects": objects_for_payload}
            print("[INFO] All expected objects stable. Data frozen for Unity.")
            print("[INFO] Final payload:", final_payload)

    if data_frozen and final_payload is not None:
        return final_payload

    return {"objects": objects_for_payload}


# ======================================================================
# 메인 루프 (카메라 프리뷰 + TCP를 하나의 루프로 처리)
# ======================================================================

def main():
    # 1) 카메라 열기
    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera index {CAMERA_INDEX}")
    print(f"[CAM] Camera opened (index={CAMERA_INDEX}).")

    # 2) TCP 서버 소켓 준비
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)
    server_socket.settimeout(0.001)  # accept가 블로킹되지 않게
    print(f"[TCP] Listening on {HOST}:{PORT} ...")

    conn = None
    addr = None
    last_send_time = 0.0

    try:
        while True:
            # (1) Unity 연결 시도 (연결 안 되어 있으면 계속 시도)
            if conn is None:
                try:
                    conn, addr = server_socket.accept()
                    print(f"[TCP] Connected from {addr}")
                    # 끊어졌을 때 재사용 가능하게
                    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except socket.timeout:
                    # 아직 아무도 안 붙은 상태
                    pass
                except Exception as e:
                    print(f"[TCP] Accept error: {e}")
                    conn = None
                    addr = None

            # (2) 카메라 프레임 읽기
            ok, frame = cap.read()
            if not ok:
                print("[WARN] Frame read failed")
                break

            # (3) 카메라 프리뷰 (항상)
            cv2.imshow("Lego VR TCP Preview", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                print("[CAM] ESC pressed. Exiting.")
                break

            # (4) Unity로 보낼 payload 생성 & 전송 (연결된 경우에만)
            now = time.time()
            if conn is not None and (now - last_send_time) >= SEND_INTERVAL:
                try:
                    payload = process_frame_and_build_payload(frame)
                    json_str = json.dumps(payload)
                    conn.sendall((json_str + "\n").encode("utf-8"))
                    last_send_time = now
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                    print(f"[TCP] Client disconnected: {e}")
                    conn.close()
                    conn = None
                    addr = None
                    print("[TCP] Waiting for new connection...")
                except Exception as e:
                    print(f"[TCP] Send error: {e}")
                    conn.close()
                    conn = None
                    addr = None
                    print("[TCP] Waiting for new connection...")

    except KeyboardInterrupt:
        print("[MAIN] KeyboardInterrupt received. Exiting.")

    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        try:
            server_socket.close()
        except Exception:
            pass
        cap.release()
        cv2.destroyAllWindows()
        print("[MAIN] Closed all resources.")


# ======================================================================
# main entry
# ======================================================================

if __name__ == "__main__":
    print("[TCP] Vision→Unity TCP server starting. Ctrl+C or ESC to exit.")
    main()
