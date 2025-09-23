import cv2
import time
import threading
import os
import subprocess # Import subprocess module
import firebase_admin
from core.face_auth import verify_face
from core.yolo_detect import init_yolo, detect_objects
from core.firebase_utils import update_user_field, get_user_doc
from core.proxy_server import start_proxy
from firebase_admin import credentials, firestore
import tkinter as tk
from tkinter import messagebox
import numpy as np # Import numpy

# ================= CONFIG =================
REGISTERED_FACES_DIR = "data/registered_faces"
YOLO_WEIGHTS = "config/yolov7-tiny.weights"
YOLO_CFG = "config/yolov7-tiny.cfg"
COCO_NAMES = "config/coco.names"

# ================= GLOBAL VARS =================
examId = None
studentId = None
authenticated = False
registered_face_path = None
proxy_started = False # New flag to track proxy status

def set_system_proxy():
    try:
        # For Windows: Set system-wide proxy for WinHTTP services
        # Many applications and services respect this, including some browsers if configured to use system proxy.
        subprocess.run(["netsh", "winhttp", "set", "proxy", "127.0.0.1:8899"], check=True)
        print("✓ Đã thiết lập proxy hệ thống.")
    except subprocess.CalledProcessError as e:
        print(f"✗ Lỗi khi thiết lập proxy hệ thống: {e}")
    except FileNotFoundError:
        print("✗ Lỗi: Lệnh 'netsh' không tìm thấy. Có thể không phải Windows hoặc PATH sai.")

def reset_system_proxy():
    try:
        # For Windows: Reset system-wide proxy for WinHTTP services
        subprocess.run(["netsh", "winhttp", "reset", "proxy"], check=True)
        print("✓ Đã đặt lại proxy hệ thống.")
    except subprocess.CalledProcessError as e:
        print(f"✗ Lỗi khi đặt lại proxy hệ thống: {e}")
    except FileNotFoundError:
        print("✗ Lỗi: Lệnh 'netsh' không tìm thấy. Có thể không phải Windows hoặc PATH sai.")

def monitoring_loop():
    global authenticated, registered_face_path, proxy_started

    # Load YOLO
    net, classes, output_layers = init_yolo(YOLO_WEIGHTS, YOLO_CFG, COCO_NAMES)
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("✗ Không thể mở camera!")
        return

    count, frame_count = 0, 0
    last_check_time, check_interval = time.time(), 5

    print("🔍 Bắt đầu giám sát... (ESC để thoát)")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("✗ Không thể đọc frame từ camera!")
                break

            frame_count += 1

            # ---- Face verification (only runs if not yet authenticated) ----
            if not authenticated and registered_face_path and os.path.exists(registered_face_path) and frame_count % 10 == 0:
                verified = verify_face(frame, registered_face_path)
                if verified is True:
                    cv2.putText(frame, "Face: VERIFIED", (50, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    update_user_field(examId, studentId, {
                        "faceVerified": True,
                        "lastVerifiedTime": firestore.SERVER_TIMESTAMP
                    })

                    if not authenticated: # This check is redundant but harmless here
                        print("👤 Khuôn mặt khớp - xác thực hoàn tất!")
                        authenticated = True
                        # Start proxy only after successful face authentication
                        if not proxy_started:
                            threading.Thread(target=start_proxy, daemon=True).start()
                            proxy_started = True
                            set_system_proxy() # Set system proxy after our proxy starts

                elif verified is False:
                    cv2.putText(frame, "Face: NOT VERIFIED", (50, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                    update_user_field(examId, studentId, {
                        "faceVerified": False,
                        "lastFailedTime": firestore.SERVER_TIMESTAMP
                    })
                else:
                    cv2.putText(frame, "Face: ERROR", (50, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 100, 255), 2)
            elif authenticated: # Display verified message if already authenticated
                cv2.putText(frame, "Face: VERIFIED (Authenticated)", (50, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            else: # Display no reference if not authenticated and no registered face path
                cv2.putText(frame, "Face: NO REFERENCE", (50, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (128, 128, 128), 2)


            # ---- YOLO chỉ chạy khi authenticated ----
            if authenticated and net is not None:
                indices, boxes, confidences, class_ids = detect_objects(frame, net, output_layers, classes)
                if len(indices) > 0: # Check if any objects were detected
                    for i in indices.flatten(): # Flatten the indices for robust iteration
                        x, y, w, h = boxes[i]
                        label, conf = classes[class_ids[i]], confidences[i]

                        color = (0, 0, 255) if label == "cell phone" else (128, 0, 128)
                        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                        cv2.putText(frame, f"{label} {conf:.2f}", (x, y - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                        if label == "cell phone":
                            count += 1
                            print(f"📱 Phát hiện điện thoại lần {count}")

                            if count == 3:
                                update_user_field(examId, studentId, {
                                    "cheatSuspicion": "true",
                                    "suspicionTime": firestore.SERVER_TIMESTAMP
                                })
                            if count == 7:
                                update_user_field(examId, studentId, {
                                    "cheatDetected": "true",
                                    "detectionTime": firestore.SERVER_TIMESTAMP
                                })

            # ---- Overlay info ----
            cv2.putText(frame, f"Student: {studentId}", (50, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Phone detections: {count}", (50, 130),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # ---- Remote stop ----
            if time.time() - last_check_time >= check_interval:
                doc = get_user_doc(examId, studentId)
                if doc.exists and doc.to_dict().get("antiCheat", False):
                    print("🛑 Tắt giám sát do yêu cầu từ xa.")
                    break
                last_check_time = time.time()

            # ---- Show frame ----
            cv2.imshow("Exam Monitoring System", frame)
            if cv2.waitKey(1) == 27:  # ESC
                print("👋 Người dùng thoát.")
                break
    finally:
        # Ensure proxy is reset even if an error occurs
        if proxy_started:
            reset_system_proxy()

    cap.release()
    cv2.destroyAllWindows()
    print("✓ Hoàn tất giám sát!")

def run_app():
    global examId, studentId, registered_face_path

    def start_exam():
        global examId, studentId, registered_face_path
        examId = entry_exam.get().strip()
        studentId = entry_student.get().strip()
        if not examId or not studentId:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập đầy đủ Exam ID và Student ID")
            return
        registered_face_path = os.path.join(REGISTERED_FACES_DIR, f"{studentId}.jpg")
        root.destroy()  # đóng form -> bắt đầu giám sát

    root = tk.Tk()
    root.title("Exam Login")

    tk.Label(root, text="Exam ID").pack()
    entry_exam = tk.Entry(root)
    entry_exam.pack()

    tk.Label(root, text="Student ID").pack()
    entry_student = tk.Entry(root)
    entry_student.pack()

    tk.Button(root, text="Bắt đầu", command=start_exam).pack()

    root.mainloop()

    if not os.path.exists(registered_face_path):
        print(f"⚠ Không tìm thấy ảnh gốc: {registered_face_path}")
        return

    # The main monitoring loop should also be in a try-finally block to ensure proxy reset
    try:
        monitoring_loop()
    finally:
        # In case monitoring_loop does not always call reset_system_proxy due to early exit
        if proxy_started:
            reset_system_proxy()

