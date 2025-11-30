import cv2

def find_available_cameras(max_index=10):
    print("🔍 Searching for available cameras...")
    available = []

    for idx in range(max_index):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap is not None and cap.isOpened():
            print(f"📷 Camera found at index {idx}")
            available.append(idx)
            cap.release()

    if not available:
        print("❌ No cameras detected.")
    else:
        print("✅ Available cameras:", available)

    return available

if __name__ == "__main__":
    find_available_cameras()
