# vision-python/src/network/tcp_server.py

import socket
import json
import time
import math
import os
import sys

import cv2
import numpy as np

# ======================================================================
# sys.path 설정: src/ 를 PYTHONPATH에 추가해서
# vision, config, mapping 패키지를 절대 import 로 사용
# ======================================================================

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))   # .../src/network
SRC_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..")) # .../src
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# src/ 를 루트로 하는 패키지 import
from vision.camera import open_camera, read_frame, release_camera
from vision.aruco_detector import (
    detect_markers,
    extract_marker_info,
    draw_markers_with_centers,
)
from config.marker_config import (
    BOARD_CORNER_IDS,
    BUILDING_MARKERS,
    EXPECTED_BUILDING_IDS,
    IDEAL_BOARD_CORNERS,
    CORNER_ANCHOR_INDEX,
)
from mapping.grid_mapping import BoardCoord, board_to_stud
from mapping.homography import compute_board_homography, image_to_board_point

# ======================================================================
# 상수 설정
# ======================================================================

# 기준 마커(보드 모서리)가 이상 위치와 얼마나 가까워야 하는지 (보드좌표 거리)
CORNER_FREEZE_THRESHOLD = 1.0

# 기준 마커가 안정적으로 유지되어야 하는 프레임 수
CORNER_STABLE_FRAMES = 10

# 건물 스폰 위치: 마커에서 스터드 몇 칸 떨어진 곳에 건물을 둘지
SPAWN_OFFSET_STUDS = 5

# 스터드 범위
STUD_MIN = 1
STUD_MAX = 32

# Unity 격자 변환: 1 stud = 2 unity cell
UNITY_PER_STUD = 2

# TCP 설정
HOST = "0.0.0.0"
PORT = 5000
SEND_FPS = 10
SEND_INTERVAL = 1.0 / SEND_FPS


# ======================================================================
# 유틸 함수들
# ======================================================================

def stud_to_unity_grid(sx: int, sy: int):
    """
    스터드(1~32) → 유니티 그리드(0~63)
    stud 1 → unity 0
    stud 32 → unity 62
    """
    ux = (sx - 1) * UNITY_PER_STUD
    uy = (sy - 1) * UNITY_PER_STUD
    return ux, uy


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
    건물 스폰 스터드 좌표를 계산.
    (보드 좌표계 기준: X 오른쪽, Y 위쪽이라고 가정)
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
        # 이론상 0/90/180/270만 오지만 방어 코드
        rad = math.radians(yaw_snapped - 90.0)  # top->front 회전
        dx = round(offset * math.cos(rad))
        dy = round(offset * math.sin(rad))

    sx = stud_x + dx
    sy = stud_y + dy

    sx = max(STUD_MIN, min(STUD_MAX, sx))
    sy = max(STUD_MIN, min(STUD_MAX, sy))

    return sx, sy


def are_corners_stable(markers, H):
    """
    기준 마커 4개가 각자의 IDEAL_BOARD_CORNERS 위치에서
    CORNER_FREEZE_THRESHOLD 이내이면 True
    """
    if H is None:
        return False

    corner_positions = {}

    for m in markers:
        mid = m["id"]
        if mid not in BOARD_CORNER_IDS:
            continue

        # 각 기준 마커에서 "보드와 닿는" anchor 코너
        corner_idx = CORNER_ANCHOR_INDEX[mid]
        acx, acy = m["corners"][corner_idx]
        bx, by = image_to_board_point((acx, acy), H)
        corner_positions[mid] = (bx, by)

    # 4개 다 있어야 함
    if set(corner_positions.keys()) != set(BOARD_CORNER_IDS):
        return False

    # 각 기준 마커가 이상 위치 근처인지 확인
    for mid, (bx, by) in corner_positions.items():
        tx, ty = IDEAL_BOARD_CORNERS[mid]
        dist = math.sqrt((bx - tx) ** 2 + (by - ty) ** 2)
        if dist > CORNER_FREEZE_THRESHOLD:
            return False

    return True


# ======================================================================
# 1단계: 카메라로 기준 마커/건물 마커 캡처 → 최종 payload 동결
# ======================================================================

def capture_and_freeze_payload():
    """
    1) 기준 마커 4개가 보드 좌표에서 안정되면 homography 고정
    2) 그 이후에 건물 4개의 마커가 한 번 이상 모두 기록되면,
       그 시점의 정보를 payload로 동결
    3) 카메라/창 모두 닫고, 동결된 payload 반환
    """
    print("[CAPTURE] Opening camera...")
    cap = open_camera()
    print("[CAPTURE] Camera opened. Press ESC to abort.")

    board_frozen = False
    homography = None
    frozen_payload = None

    stable_frame_count = 0

    # board_frozen 이후에만 건물 기록
    seen_building_ids = set()
    latest_building_info = {}  # {id: payload_obj}

    try:
        while True:
            ok, frame = read_frame(cap)
            if not ok:
                print("[CAPTURE] Failed to read frame.")
                break

            corners, ids = detect_markers(frame)
            markers = extract_marker_info(corners, ids)

            # 마커 시각화 (격자 X)
            debug_frame = draw_markers_with_centers(frame.copy(), markers)
            cv2.imshow("Lego VR Capture (Markers Only)", debug_frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                print("[CAPTURE] ESC pressed. Aborting capture.")
                break

            if not markers:
                stable_frame_count = 0
                continue

            # ----------------------------------------------------------
            # 1) 기준 마커 4개 안정화 → homography freeze
            # ----------------------------------------------------------
            if not board_frozen:
                # 기준 마커 4개가 모두 보이는지 먼저 확인
                corner_ids_in_frame = {m["id"] for m in markers if m["id"] in BOARD_CORNER_IDS}
                if not set(BOARD_CORNER_IDS).issubset(corner_ids_in_frame):
                    stable_frame_count = 0
                    continue

                H = compute_board_homography(markers)
                if H is None:
                    stable_frame_count = 0
                    continue

                if are_corners_stable(markers, H):
                    stable_frame_count += 1
                else:
                    stable_frame_count = 0

                if stable_frame_count >= CORNER_STABLE_FRAMES:
                    homography = H
                    board_frozen = True
                    print(f"[CAPTURE] Board homography frozen after {stable_frame_count} stable frames.")
                continue  # 아직 건물 기록은 안 함

            # ----------------------------------------------------------
            # 2) homography가 고정된 이후: 건물 4개가 한 번씩 다 보일 때까지 기록
            # ----------------------------------------------------------
            if homography is None:
                continue

            # 이번 프레임에서 보이는 "기대하는" 건물 마커들
            building_markers = [m for m in markers if m["id"] in EXPECTED_BUILDING_IDS]
            building_ids_in_frame = {m["id"] for m in building_markers}

            if building_ids_in_frame:
                print("[CAPTURE] Buildings in this frame:", sorted(list(building_ids_in_frame)))

            for m in building_markers:
                mid = m["id"]
                label = BUILDING_MARKERS.get(mid, f"Building_{mid}")

                # 마커 중심 → 보드 좌표
                cx, cy = m["center"]
                bx, by = image_to_board_point((cx, cy), homography)
                board_coord = BoardCoord(bx, by)
                stud_idx = board_to_stud(board_coord)

                # 회전 (0/90/180/270)
                yaw_deg = compute_snapped_yaw_deg(m, homography)

                # 스폰 스터드 좌표 (마커에서 offset 떨어진 위치)
                spawn_sx, spawn_sy = compute_spawn_stud_from_marker(
                    stud_idx.x, stud_idx.y, yaw_deg, offset=SPAWN_OFFSET_STUDS
                )
                spawn_ux, spawn_uy = stud_to_unity_grid(spawn_sx, spawn_sy)

                # Unity에서 쓰기 위한 ObjectPayload 형태로 저장
                latest_building_info[mid] = {
                    "id": mid,
                    "kind": "building",   # Unity ObjectPayload.kind
                    "label": label,
                    "marker_board": {"x": bx, "y": by},
                    "marker_stud": {"x": stud_idx.x, "y": stud_idx.y},
                    "marker_unity": {"x": 0, "y": 0},  # 필요 없으면 0으로 두거나 계산 생략 가능
                    "spawn_stud": {"x": spawn_sx, "y": spawn_sy},
                    "spawn_unity": {"x": spawn_ux, "y": spawn_uy},
                    "yaw_deg": yaw_deg,
                }
                seen_building_ids.add(mid)

            # EXPECTED_BUILDING_IDS 가 전부 한 번 이상 등장했으면 동결
            if set(EXPECTED_BUILDING_IDS).issubset(seen_building_ids):
                print("[CAPTURE] All 4 building markers have been seen at least once AFTER board stabilized.")

                # 정렬된 순서로 objects 배열 구성
                objects_payload = [
                    latest_building_info[mid] for mid in EXPECTED_BUILDING_IDS
                    if mid in latest_building_info
                ]

                if len(objects_payload) != len(EXPECTED_BUILDING_IDS):
                    print("[CAPTURE] Warning: some building IDs missing in latest_building_info.")
                else:
                    print("[CAPTURE] All building infos are present.")

                # Unity 쪽 PayloadRoot 구조에 맞게 루트 키는 "objects"
                frozen_payload = {
                    "objects": objects_payload
                }

                print("[CAPTURE] Frozen payload:")
                print(json.dumps(frozen_payload, indent=2, ensure_ascii=False))
                break

    finally:
        try:
            release_camera(cap)
        except Exception:
            pass
        cv2.destroyAllWindows()
        print("[CAPTURE] Camera released and windows closed.")

    return frozen_payload


# ======================================================================
# 2단계: 동결된 payload를 TCP로 Unity에 전송
#       Unity가 끊기면 파이썬도 바로 종료
# ======================================================================

def run_tcp_server_with_payload(payload):
    """
    이미 동결된 payload(JSON)를 일정 간격으로 Unity에 전송.
    클라이언트가 연결을 끊으면 전체 프로그램도 종료.
    """
    print("[MAIN] Capture phase done. Starting TCP server to send frozen payload.")
    print(f"[TCP] Starting TCP server on {HOST}:{PORT}")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(1)

    conn = None
    addr = None
    last_send_time = 0.0
    running = True

    try:
        # 1) Unity 접속 기다리기
        print("[TCP] Waiting for Unity connection...")
        conn, addr = server_socket.accept()
        print(f"[TCP] Connected by {addr}")
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        # 2) 연결 된 동안 payload 전송
        while running:
            now = time.time()
            if (now - last_send_time) >= SEND_INTERVAL:
                try:
                    json_str = json.dumps(payload)
                    conn.sendall((json_str + "\n").encode("utf-8"))
                    last_send_time = now
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                    print(f"[TCP] Client disconnected: {e}")
                    running = False
                except Exception as e:
                    print(f"[TCP] Send error: {e}")
                    running = False

            # 너무 쓸데없이 바쁘게 돌지 않게 살짝 쉼
            time.sleep(0.001)

    except KeyboardInterrupt:
        print("[MAIN] KeyboardInterrupt received. Exiting TCP server.")

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
        print("[MAIN] TCP server closed. Program exiting.")


# ======================================================================
# main entry
# ======================================================================

def main():
    print("[MAIN] Lego VR tcp_server starting.")
    print("       1) 기준 마커 4개가 좌표로 안정되면 보드 좌표계 고정")
    print("       2) 그 다음 건물 4개가 한 번 이상 기록되면 데이터 고정 + Unity로 송신")

    frozen_payload = capture_and_freeze_payload()
    if frozen_payload is None:
        print("[MAIN] No payload captured. Exiting.")
        return

    run_tcp_server_with_payload(frozen_payload)


if __name__ == "__main__":
    main()
