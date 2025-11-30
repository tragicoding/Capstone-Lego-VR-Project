# vision-python/src/vision/grid_overlay.py

import cv2
import numpy as np


def draw_grid(frame, H_inv, step=1):
    """
    homography 역행렬(H_inv)을 이용하여
    보드 좌표(0~33)의 격자를 이미지 좌표에 그린다.
    """
    if H_inv is None:
        return frame

    for x in range(0, 34, step):
        p1 = np.array([x, 0, 1])
        p2 = np.array([x, 33, 1])
        p1 = H_inv @ p1; p1 /= p1[2]
        p2 = H_inv @ p2; p2 /= p2[2]
        cv2.line(frame, (int(p1[0]), int(p1[1])),
                        (int(p2[0]), int(p2[1])),
                        (0,255,0), 1)

    for y in range(0, 34, step):
        p1 = np.array([0, y, 1])
        p2 = np.array([33, y, 1])
        p1 = H_inv @ p1; p1 /= p1[2]
        p2 = H_inv @ p2; p2 /= p2[2]
        cv2.line(frame, (int(p1[0]), int(p1[1])),
                        (int(p2[0]), int(p2[1])),
                        (0,255,0), 1)

    return frame
