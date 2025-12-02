import socket
import json
import time

HOST = "0.0.0.0"
PORT = 5000

def main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(1)

    print(f"[TCP] Listening on {HOST}:{PORT} ...")
    conn, addr = server_sock.accept()
    print(f"[TCP] Connected from {addr}")

    try:
        with conn:
            step = 0
            while True:
                # 짝수 step → (1,1), 홀수 step → (10, 5) 로 왔다갔다
                if step % 2 == 0:
                    gx, gy = 1, 1
                else:
                    gx, gy = 10, 5

                payload = {
                    "objects": [
                        {
                            "id": 2,
                            "kind": "building",
                            "label": "Building_02",
                            "marker_board": {"x": 0.0, "y": 0.0},
                            "marker_stud":  {"x": gx, "y": gy},
                            "marker_unity": {"x": gx, "y": gy},
                            "spawn_stud":   {"x": gx, "y": gy},
                            "spawn_unity":  {"x": gx, "y": gy},
                            "yaw_deg": 0
                        }
                    ]
                }

                json_str = json.dumps(payload)
                data = (json_str + "\n").encode("utf-8")

                try:
                    conn.sendall(data)
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                    print(f"[TCP] connection closed by client: {e}")
                    break

                step += 1
                time.sleep(1.0)  # 1초마다 위치 변경
    finally:
        server_sock.close()
        print("[TCP] server closed")

if __name__ == "__main__":
    main()
