# vision-python/src/mapping/homography.py

import numpy as np
import cv2

from ..config.marker_config import (
    BOARD_CORNER_IDS,
    IDEAL_BOARD_CORNERS,
    CORNER_ANCHOR_INDEX,
)

# 이전 프레임 Homography(스무딩용)
_prev_H = None


def compute_board_homography(markers):
    """
    기준 마커 4개의 "보드와 맞닿는 코너"를 이용해
    이미지 좌표 → 보드 평면 좌표(0~33)의 Homography 행렬 H를 계산한다.

    markers: extract_marker_info() 결과 리스트
        각 원소: {"id": int, "corners": np.ndarray(shape=(4,2)), "center": (cx, cy)}

    반환값:
        H: 3x3 homography matrix (np.ndarray) 또는 None
    """
    src_pts = []
    dst_pts = []

    for m in markers:
        mid = m["id"]
        if mid in BOARD_CORNER_IDS:
            corners = m["corners"]  # shape (4, 2)

            # 기준 마커에서 "보드와 닿는" 코너 인덱스
            corner_idx = CORNER_ANCHOR_INDEX[mid]
            corner = corners[corner_idx]  # (x, y)

            # 이미지 좌표 (픽셀)
            src_pts.append([corner[0], corner[1]])

            # 보드 평면에서의 이상적인 좌표
            bx, by = IDEAL_BOARD_CORNERS[mid]
            dst_pts.append([bx, by])

    if len(src_pts) < 4:
        # 모서리 4개를 다 못 찾으면 Homography 계산 불가
        return None

    src_pts = np.array(src_pts, dtype=np.float32)
    dst_pts = np.array(dst_pts, dtype=np.float32)

    H, _ = cv2.findHomography(src_pts, dst_pts, method=0)
    return H


def image_to_board_point(point, H):
    """
    Homography H를 이용해 이미지 좌표 (x, y)를 보드 평면 좌표 (bx, by)로 변환.

    point: (x, y)
    H: 3x3 homography matrix
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

    H_smooth = alpha * H_new + (1 - alpha) * H_prev
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
