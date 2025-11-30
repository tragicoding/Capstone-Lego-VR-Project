# vision-python/src/vision/aruco_detector.py

import cv2
import numpy as np

ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
DETECT_PARAMS = cv2.aruco.DetectorParameters()


def detect_markers(frame):
    """
    detectMarkers 반환값:
      - corners: [(4,2), (4,2), ...]
      - ids: (N,1)
    """
    corners, ids, _ = cv2.aruco.detectMarkers(
        frame,
        ARUCO_DICT,
        parameters=DETECT_PARAMS
    )

    if ids is None or len(corners) == 0:
        return [], []   # <= ids도 빈 리스트로

    ids = ids.flatten().tolist()
    return corners, ids


def extract_marker_info(corners, ids):
    """
    ArUco 마커 정보 구성
    - id
    - center
    - corners
    """
    if ids is None or len(ids) == 0:
        return []
    
    markers = []

    for i, cid in enumerate(ids):
        c = corners[i][0]  # shape (4,2)
        cx = float(np.mean(c[:, 0]))
        cy = float(np.mean(c[:, 1]))
        markers.append({
            "id": cid,
            "center": (cx, cy),
            "corners": c
        })

    return markers


def draw_markers_with_centers(frame, markers):
    """
    디버그용 표시(코너 박스 + 중심 + ID)
    """
    if not markers:
        return frame

    for m in markers:
        c = m["corners"]
        p0, p1, p2, p3 = c

        cv2.line(frame, tuple(p0.astype(int)), tuple(p1.astype(int)), (0,255,0), 2)
        cv2.line(frame, tuple(p1.astype(int)), tuple(p2.astype(int)), (0,255,0), 2)
        cv2.line(frame, tuple(p2.astype(int)), tuple(p3.astype(int)), (0,255,0), 2)
        cv2.line(frame, tuple(p3.astype(int)), tuple(p0.astype(int)), (0,255,0), 2)

        cx, cy = m["center"]
        cv2.circle(frame, (int(cx), int(cy)), 4, (0,0,255), -1)

        cv2.putText(frame, str(m["id"]), (int(cx)+5, int(cy)+5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 2)

    return frame
