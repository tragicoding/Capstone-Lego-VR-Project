# vision-python/src/config/marker_config.py

"""
마커 관련 설정값 모음

- BOARD_CORNER_IDS:
    보드 네 모서리를 정의하는 기준 마커 ID 목록

- IDEAL_BOARD_CORNERS:
    각 기준 마커가 보드 평면(0~33 좌표계)에서 가지는 이상적인 위치

- CORNER_ANCHOR_INDEX:
    각 기준 마커에서 "보드와 실제로 닿아 있는 ArUco 코너"의 인덱스
    OpenCV ArUco 코너 인덱스 규칙:
        corners[0] = top-left
        corners[1] = top-right
        corners[2] = bottom-right
        corners[3] = bottom-left

- BUILDING_MARKERS:
    건물 마커 ID → 라벨

- CHARACTER_MARKERS:
    캐릭터 마커 ID → 라벨

- EXPECTED_*:
    최종 freeze를 위해 "반드시 있어야 하는" 건물/캐릭터 ID 목록
"""

# ----------------------------------
#  기준 마커 (보드 모서리 4개)
# ----------------------------------

# 보드 모서리 역할을 하는 기준 마커 ID들
BOARD_CORNER_IDS = [0, 1, 2, 3]

# 보드 평면 좌표계에서 이상적인 위치 (0~33 범위)
# 레고 스터드는 1~32를 쓰고, 0과 33은 바깥쪽 여유
IDEAL_BOARD_CORNERS = {
    0: (0.0, 33.0),   # 좌상단 기준 마커
    1: (33.0, 33.0),  # 우상단 기준 마커
    2: (0.0, 0.0),    # 좌하단 기준 마커
    3: (33.0, 0.0),   # 우하단 기준 마커
}

# 각 기준 마커에서 "보드와 맞닿는" ArUco 코너 인덱스
#   0: top-left, 1: top-right, 2: bottom-right, 3: bottom-left
#
# 이 값은 실제 마커를 어떻게 붙였는지에 따라 달라질 수 있음.
# 실행해 보고 기준 마커의 board 좌표가 (0,0), (33,0), (0,33), (33,33)에
# 잘 맞지 않으면, 아래 인덱스들만 0~3 사이에서 바꿔주면 됨.
CORNER_ANCHOR_INDEX = {
    0: 3,  # ID 0: bottom-left가 보드 모서리에 닿아있다고 가정
    1: 2,  # ID 1: bottom-right
    2: 0,  # ID 2: top-left
    3: 1,  # ID 3: top-right
}

# ----------------------------------
#  건물 & 캐릭터 마커
# ----------------------------------

# 건물 마커 (ID 4~7) → 총 4개
BUILDING_MARKERS = {
    4: "Building_01",
    5: "Building_02",
    6: "Building_03",
    7: "Building_04",
    # 8 은 사용 안 함
}

# 캐릭터 마커 (ID 9~10) → 총 2개
CHARACTER_MARKERS = {
    9: "Character_01",
    10: "Character_02",
    # 11 은 사용 안 함
}

# 최종 freeze 조건에 필요한 "반드시 있어야 하는" ID들
EXPECTED_BUILDING_IDS = list(BUILDING_MARKERS.keys())   # [4,5,6,7]
EXPECTED_CHARACTER_IDS = list(CHARACTER_MARKERS.keys()) # [9,10]
EXPECTED_OBJECT_IDS = EXPECTED_BUILDING_IDS + EXPECTED_CHARACTER_IDS
