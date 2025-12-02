import socket
import json
import time
import threading

# =============================================================
# 설정
# =============================================================
HOST = "0.0.0.0"   # Unity에서 127.0.0.1로 접속할 거니까 이대로 두면 됨
PORT = 5000        # Unity NetworkManager랑 포트 번호 반드시 동일
SEND_FPS = 10      # 초당 10번 정도 전송 (원하면 바꿔도 됨)


# =============================================================
# 목업: 카메라로 마커 인식해서 좌표 찍었다고 "가정"한 데이터
#  - stud 좌표(1~64,1~64) 기준
#  - spawn_unity = stud 좌표 그대로 사용
# =============================================================

def get_mock_building_states():
    """
    마치 카메라/마커 인식해서 계산된 결과라고 가정한 목업 데이터.
    각 튜플은 (label, x, y, yaw_deg) 의미.
    x, y : 유니티 GridMapper에 들어갈 격자 좌표 (1-based)
    yaw_deg : Y축 회전 (도 단위)
    """

    # 🔹 이전보다 더 멀리 떨어뜨린 배치
    #   - 보드 왼쪽 아래 쪽에 4개를 사각형으로 배치
    #   - 겹치지 않게 x,y 간격을 크게 잡음
    return [
        ("Building_01", 8,  8,  0),    # 왼쪽 아래
        ("Building_02", 24, 8,  90),   # 오른쪽 아래
        ("Building_03", 8,  24, 180),  # 왼쪽 위
        ("Building_04", 24, 24, 270),  # 오른쪽 위
    ]


# =============================================================
# TCP 서버 구현
# =============================================================

class UnityTCPServer:
    def __init__(self):
        self.server_socket = None
        self.client_conn = None
        self.client_addr = None
        self.running = False

    def start(self):
        """별도 스레드에서 서버 루프 시작."""
        t = threading.Thread(target=self.server_loop, daemon=True)
        t.start()

    def server_loop(self):
        self.running = True

        while self.running:
            try:
                print(f"[TCP] Listening on {HOST}:{PORT} ...")
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self.server_socket.bind((HOST, PORT))
                self.server_socket.listen(1)

                conn, addr = self.server_socket.accept()
                self.client_conn = conn
                self.client_addr = addr
                print(f"[TCP] Connected from {addr}")

                self.handle_client(conn)

            except Exception as e:
                print(f"[TCP] Server error: {e}")

            finally:
                try:
                    if self.client_conn:
                        self.client_conn.close()
                except Exception:
                    pass
                self.client_conn = None
                self.client_addr = None

                try:
                    if self.server_socket:
                        self.server_socket.close()
                except Exception:
                    pass
                self.server_socket = None

                if self.running:
                    print("[TCP] Reconnecting in 1 sec...")
                    time.sleep(1)

    def handle_client(self, conn):
        """Unity와 연결된 동안 목업 payload를 계속 보내는 루프."""
        interval = 1.0 / SEND_FPS

        while True:
            try:
                mock_buildings = get_mock_building_states()

                payload = {
                    "objects": []
                }

                for label, gx, gy, yaw in mock_buildings:
                    obj = {
                        "id": 0,
                        "kind": "building",
                        "label": label,

                        # 구조 맞추기용 필드들
                        "marker_board": {
                            "x": float(gx),
                            "y": float(gy)
                        },
                        "marker_stud": {
                            "x": gx,
                            "y": gy
                        },
                        "marker_unity": {
                            "x": gx,
                            "y": gy
                        },
                        "spawn_stud": {
                            "x": gx,
                            "y": gy
                        },
                        # 🔥 GameStateManager에서 실제로 사용하는 좌표
                        "spawn_unity": {
                            "x": gx,
                            "y": gy
                        },

                        "yaw_deg": float(yaw)
                    }

                    payload["objects"].append(obj)

                json_str = json.dumps(payload)
                conn.sendall((json_str + "\n").encode("utf-8"))

                time.sleep(interval)

            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                print(f"[TCP] Client disconnected: {e}")
                break
            except Exception as e:
                print(f"[TCP] Send error: {e}")
                break


# =============================================================
# main
# =============================================================

if __name__ == "__main__":
    server = UnityTCPServer()
    server.start()

    print("[TCP] Mock server running. Ctrl+C to exit.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("[TCP] Bye.")
