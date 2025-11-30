# vision-python/src/app/main.py

import cv2
import math
import numpy as np
import os
import json

from ..vision.camera import open_camera, read_frame, release_camera
from ..vision.aruco_detector import (
    detect_markers,
    extract_marker_info,
    draw_markers_with_centers,
)
from ..vision.grid_overlay import draw_grid

from ..mapping.homography import (
    compute_board_homography,
    image_to_board_point,
    smooth_homography,
)
from ..mapping.grid_mapping import BoardCoord, board_to_stud, board_to_unity
from ..config.marker_config import (
    BOARD_CORNER_IDS,
    BUILDING_MARKERS,
    CHARACTER_MARKERS,
    IDEAL_BOARD_CORNERS,
    CORNER_ANCHOR_INDEX,
    EXPECTED_OBJECT_IDS,
)

# =========================
# Smoothing & Freeze
# =========================

POS_SMOOTH = 0.25          # 위치 스무딩
ROT_SMOOTH = 0.25          # 회전 스무딩
FREEZE_THRESHOLD = 1.0     # 기준 마커 안정성 기준 (보드좌표 오차)
DATA_STABLE_FRAMES = 10    # 건물/캐릭터가 같은 칸+회전으로 유지되어야 하는 프레임 수
SPAWN_OFFSET_STUDS = 5     # 마커에서 건물/캐릭터가 떨어져 생성될 스터드 거리

homography_frozen = False      # 기준 마커 안정화 여부 (보드 좌표계 고정)
data_frozen = False            # 전체 데이터(건물/캐릭터)까지 안정화 여부
grid_generated = False         # homography가 freeze된 이후 격자 표시 시작 여부

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


# ======================================================================
# 헬퍼 함수들
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

    yaw_snapped는 marker의 "윗변(top edge)" 방향이라고 가정했고,
    건물 앞면(정자세 아랫변)은 그에 수직인 '아래쪽' 방향이다.

    여기서는 다음 규칙으로 정의한다:
      - yaw =   0도: top edge가 +X → 앞면은 -Y  → (0, -offset)
      - yaw =  90도: top edge가 +Y → 앞면은 +X  → (+offset, 0)
      - yaw = 180도: top edge가 -X → 앞면은 +Y  → (0, +offset)
      - yaw = 270도: top edge가 -Y → 앞면은 -X  → (-offset, 0)
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
        # 이론상 0/90/180/270만 오지만, 혹시 대비해서 일반 처리
        rad = math.radians(yaw_snapped - 90.0)  # top->front 회전
        dx = round(offset * math.cos(rad))
        dy = round(offset * math.sin(rad))

    sx = stud_x + dx
    sy = stud_y + dy

    # 보드 밖으로 나가지 않도록 클램프
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


def board_center_of_stud(sx, sy):
    """
    스터드 인덱스(sx,sy)가 차지하는 칸의 보드 좌표계 중심값을 대략 계산.
    → spawn 위치를 카메라 화면에 그릴 때 사용.
    """
    fx = (sx - 0.5) / NUM_STUDS_X
    fy = (sy - 0.5) / NUM_STUDS_Y
    bx = fx * BOARD_EXTENT_X
    by = fy * BOARD_EXTENT_Y
    return bx, by


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
    # 1) 이번 프레임에 전부 보이는지 확인
    visible_ids = set(visible_ids)
    if not set(EXPECTED_OBJECT_IDS).issubset(visible_ids):
        return False

    # 2) 각 ID가 충분히 안정화되었는지 확인
    for mid in EXPECTED_OBJECT_IDS:
        if stable_count.get(mid, 0) < DATA_STABLE_FRAMES:
            return False

    return True


# ======================================================================
# Main Loop
# ======================================================================

def run_aruco_with_all_features():
    global homography_frozen, data_frozen, final_payload, grid_generated

    cap = open_camera()
    homography = None

    print("[INFO] Press ESC to exit, 'r' to reset.")

    while True:
        ok, frame = read_frame(cap)
        if not ok:
            print("[WARN] Frame read failed")
            break

        # 1) ArUco detect
        corners, ids = detect_markers(frame)
        markers = extract_marker_info(corners, ids)

        # 2) Homography 계산 (freeze 상태 아닐 때만)
        if markers and not homography_frozen:
            H_new = compute_board_homography(markers)

            if H_new is not None:
                homography = smooth_homography(H_new)

                # 기준 마커들의 현재 board좌표 확인 (anchor 코너 기준)
                corner_positions = {}
                for m in markers:
                    mid = m["id"]
                    if mid in BOARD_CORNER_IDS:
                        corner_idx = CORNER_ANCHOR_INDEX[mid]
                        acx, acy = m["corners"][corner_idx]
                        bx, by = image_to_board_point((acx, acy), homography)
                        corner_positions[mid] = (bx, by)

                # 기준조건 만족하면 Freeze
                if len(corner_positions) == 4 and is_homography_stable(corner_positions):
                    homography_frozen = True
                    print("[INFO] Homography frozen (board corners stable).")

        # 3) 마커 박스 + center + ID 디버그 표시
        frame = draw_markers_with_centers(frame, markers)

        # 4) homography가 없으면 좌표/격자 연산 불가
        if homography is None:
            key = cv2.waitKey(1) & 0xFF
            cv2.imshow("Lego VR", frame)
            if key == 27:
                break
            elif key == ord('r'):
                print("[INFO] Reset homography/data state.")
                homography_frozen = False
                data_frozen = False
                final_payload = None
                grid_generated = False
                pos_cache.clear()
                rot_cache.clear()
                last_state.clear()
                stable_count.clear()
            continue

        # 5) 격자 그리기
        #    - homography가 freeze되기 전에는 격자 안 그림
        #    - freeze된 이후부터 H는 고정이라, 이 H 기반으로 격자가 "보드 모서리"에 딱 맞게 고정됨
        if homography_frozen:
            if not grid_generated:
                print("[INFO] Grid overlay enabled (using frozen homography).")
                grid_generated = True

            H_inv = np.linalg.inv(homography)
            frame = draw_grid(frame, H_inv, step=1)

        # 6) 마커 위치/회전/스폰좌표 계산
        objects_for_payload = []   # 이번 프레임의 건물/캐릭터 정보
        visible_object_ids = []    # 이번 프레임에 실제로 보인 건물/캐릭터 ID들

        if markers:
            corner_logs = []
            object_logs = []

            for m in markers:
                mid = m["id"]
                cx, cy = m["center"]
                kind, label = classify_marker(mid)

                # 기준 마커일 때는 anchor 코너 기준 좌표도 같이 로깅
                if kind == "corner":
                    corner_idx = CORNER_ANCHOR_INDEX[mid]
                    acx, acy = m["corners"][corner_idx]
                    bx, by = image_to_board_point((acx, acy), homography)

                    if not data_frozen:
                        corner_logs.append(
                            f"ID {mid} corner_anchor: board=({bx:.2f},{by:.2f})"
                        )
                    continue

                # 그 외(건물/캐릭터/unknown)는 center 기준으로 board 좌표 변환
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

                    # 회전 (raw snapped)
                    yaw_snapped = compute_snapped_yaw_deg(m, homography)

                    # 회전 스무딩 (표시/전달용)
                    prev_yaw = rot_cache.get(mid)
                    if prev_yaw is None:
                        rot_cache[mid] = yaw_snapped
                        yaw_for_output = yaw_snapped
                    else:
                        yaw_smoothed = smooth_value(prev_yaw, yaw_snapped, ROT_SMOOTH)
                        rot_cache[mid] = yaw_smoothed
                        yaw_for_output = round(yaw_smoothed / 90) * 90
                        yaw_for_output %= 360

                    # 🔥 건물/캐릭터 스폰 좌표 (마커에서 5칸 떨어진 지점)
                    spawn_sx, spawn_sy = compute_spawn_stud_from_marker(
                        stud.x, stud.y, yaw_snapped, offset=SPAWN_OFFSET_STUDS
                    )
                    spawn_ux, spawn_uy = stud_to_unity_grid(spawn_sx, spawn_sy)

                    # 🔵 화면에 스폰 위치를 시각적으로 표시 (카메라 이미지 상)
                    spawn_bx, spawn_by = board_center_of_stud(spawn_sx, spawn_sy)
                    p = np.array([spawn_bx, spawn_by, 1.0], dtype=np.float32)
                    H_inv = np.linalg.inv(homography)
                    p_img = H_inv @ p
                    p_img /= p_img[2]
                    ix, iy = int(p_img[0]), int(p_img[1])
                    cv2.circle(frame, (ix, iy), 6, (255, 0, 0), -1)
                    cv2.putText(
                        frame,
                        f"{label}",
                        (ix + 5, iy - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,
                        (255, 0, 0),
                        1,
                    )

                    # 안정성 체크용
                    update_stability(mid, spawn_sx, spawn_sy, yaw_snapped)

                    # Unity로 넘길 한 오브젝트 데이터 구조
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

                    if not data_frozen:  # freeze 이후엔 로그 출력 X
                        object_logs.append(
                            f"[{kind.upper()}] ID {mid} ({label}) "
                            f"board=({bx:.2f},{by:.2f}) "
                            f"stud=({stud.x},{stud.y}) "
                            f"spawn_stud=({spawn_sx},{spawn_sy}) "
                            f"spawn_unity=({spawn_ux},{spawn_uy}) "
                            f"yaw={yaw_for_output:.0f}"
                        )

                else:
                    if not data_frozen:
                        object_logs.append(f"[UNKNOWN] ID {mid}")

            # 콘솔 로그 출력 (data_frozen 이전에만)
            if not data_frozen:
                if corner_logs:
                    print("CORNERS | " + " | ".join(corner_logs))
                if object_logs:
                    print("OBJECTS | " + " | ".join(object_logs))

        # 7) 전체 데이터 안정화 체크
        #   - homography_frozen == True (기준 마커/격자 확정)
        #   - EXPECTED_OBJECT_IDS(건물 4개 + 캐릭터 2개)가
        #     이번 프레임에 모두 보이고 + stable_count도 충분히 크면 freeze
        if not data_frozen:
            if homography_frozen and are_all_expected_objects_stable(visible_object_ids):
                data_frozen = True
                final_payload = {
                    "objects": objects_for_payload,
                }
                print("[INFO] All expected objects stable. Data frozen for Unity.")
                print("[INFO] Final payload:", final_payload)

                # 🔥 out/ 폴더에 JSON + 스냅샷 저장
                out_dir = os.path.join(os.path.dirname(__file__), "..", "..", "out")
                out_dir = os.path.abspath(out_dir)
                os.makedirs(out_dir, exist_ok=True)

                img_path = os.path.join(out_dir, "final_frame.png")
                cv2.imwrite(img_path, frame)
                print(f"[INFO] Final frame saved to: {img_path}")

                out_path = os.path.join(out_dir, "final_payload.json")
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(final_payload, f, ensure_ascii=False, indent=2)
                print(f"[INFO] Final payload saved to: {out_path}")

        # 8) 화면 출력 + 키 입력 처리
        cv2.imshow("Lego VR", frame)
        key = cv2.waitKey(1) & 0xFF

        if key == 27:  # ESC
            break
        elif key == ord('r'):
            print("[INFO] Reset homography/data state.")
            homography_frozen = False
            data_frozen = False
            final_payload = None
            grid_generated = False
            pos_cache.clear()
            rot_cache.clear()
            last_state.clear()
            stable_count.clear()

    release_camera(cap)


if __name__ == "__main__":
    run_aruco_with_all_features()
