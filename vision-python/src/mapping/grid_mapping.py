# vision-python/src/mapping/grid_mapping.py

from dataclasses import dataclass

BOARD_EXTENT_X = 33.0
BOARD_EXTENT_Y = 33.0

NUM_STUDS_X = 32
NUM_STUDS_Y = 32

UNITY_GRID_X = 64
UNITY_GRID_Y = 64

UNITY_PER_STUD = 2  # 1 stud = 2 unity cells


@dataclass
class BoardCoord:
    x: float
    y: float


@dataclass
class StudIndex:
    x: int
    y: int


@dataclass
class UnityCoord:
    x: int
    y: int


def clamp(val, lo, hi):
    return max(lo, min(hi, val))


def board_to_stud(board: BoardCoord) -> StudIndex:
    bx = clamp(board.x, 0, BOARD_EXTENT_X - 1e-3)
    by = clamp(board.y, 0, BOARD_EXTENT_Y - 1e-3)

    sx = int((bx / BOARD_EXTENT_X) * NUM_STUDS_X) + 1
    sy = int((by / BOARD_EXTENT_Y) * NUM_STUDS_Y) + 1

    sx = clamp(sx, 1, NUM_STUDS_X)
    sy = clamp(sy, 1, NUM_STUDS_Y)

    return StudIndex(sx, sy)


def stud_to_unity(stud: StudIndex) -> UnityCoord:
    ux = (stud.x - 1) * UNITY_PER_STUD
    uy = (stud.y - 1) * UNITY_PER_STUD
    return UnityCoord(ux, uy)


def board_to_unity(board: BoardCoord) -> UnityCoord:
    stud = board_to_stud(board)
    return stud_to_unity(stud)
