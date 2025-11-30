# vision-python/src/vision/camera.py

import cv2
import numpy as np
from ..config.camera_config import CAMERA_INDEX


# ---------------------------------------------------
# 카메라 캘리브레이션 파일 로드 (있으면 사용)
# ---------------------------------------------------
try:
    CAMERA_MATRIX = np.load("camera_matrix.npy")
    DIST_COEFFS = np.load("dist_coeffs.npy")
    USE_UNDISTORT = True
    print("[INFO] Camera calibration loaded. Undistort enabled.")
except:
    CAMERA_MATRIX = None
    DIST_COEFFS = None
    USE_UNDISTORT = False
    print("[WARN] No camera calibration found. Undistort disabled.")


def undistort_frame(frame):
    """렌즈 왜곡 보정"""
    if USE_UNDISTORT:
        return cv2.undistort(frame, CAMERA_MATRIX, DIST_COEFFS)
    return frame


def open_camera(index=CAMERA_INDEX):
    cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        raise RuntimeError(f"[ERROR] Cannot open camera index {index}")
    return cap


def read_frame(cap):
    ok, frame = cap.read()
    if not ok:
        return False, None

    # Why? --> 안정화 효과 매우 큼
    frame = undistort_frame(frame)
    return True, frame


def release_camera(cap):
    cap.release()
    cv2.destroyAllWindows()
