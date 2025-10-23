import cv2
import time
import threading
import os
import firebase_admin
import tkinter as tk
from tkinter import messagebox
from firebase_admin import credentials, firestore

from core.face_auth import verify_face
from core.object_detection import ObjectDetector  # UPDATED: Import ObjectDetector instead of YOLO
from core.firebase_utils import update_user_field, get_user_doc
from core.proxy_server import start_proxy, stop_proxy
from core.network_utils import (
    set_system_proxy, reset_system_proxy,
    get_active_network_interfaces, set_system_dns, reset_system_dns,
    start_dns_server, stop_dns_server, flush_dns_cache
)
from core.face_tracking import FaceTracker
from core.audio_monitoring import AudioMonitor

REGISTERED_FACES_DIR = "data/registered_faces"
# REMOVED: YOLO constants are no longer needed

examId = None
studentId = None
authenticated = False
registered_face_path = None

proxy_active = False
dns_blocked_interfaces = []
dns_server_active = False

def apply_network_restrictions():
    global proxy_active, dns_blocked_interfaces, dns_server_active
    print("⚙️ Áp dụng các hạn chế mạng...")

    flush_dns_cache()

    if not dns_server_active:
        start_dns_server()
        dns_server_active = True
        print("✓ DNS Server cục bộ đã khởi động.")

    active_interfaces = get_active_network_interfaces()
    if active_interfaces:
        for interface in active_interfaces:
            if set_system_dns(interface):
                dns_blocked_interfaces.append(interface)
        print("✓ DNS hệ thống đã trỏ về DNS Server cục bộ.")
    else:
        print("⚠ Không tìm thấy card mạng hoạt động để thiết lập DNS.")

    if not proxy_active:
        threading.Thread(target=start_proxy, daemon=True).start()
        proxy_active = True
        time.sleep(1)
        if set_system_proxy():
            print("✓ Proxy hệ thống đã thiết lập.")
        else:
            print("✗ Không thể thiết lập proxy hệ thống.")

def remove_network_restrictions():
    global proxy_active, dns_blocked_interfaces, dns_server_active
    print("⚙️ Gỡ bỏ các hạn chế mạng...")

    if proxy_active:
        reset_system_proxy()
        stop_proxy()
        proxy_active = False
        print("✓ Proxy hệ thống đã đặt lại.")

    if dns_blocked_interfaces:
        for interface in dns_blocked_interfaces:
            reset_system_dns(interface)
        dns_blocked_interfaces = []
        print("✓ DNS hệ thống đã đặt lại.")

    if dns_server_active:
        stop_dns_server()
        dns_server_active = False
        print("✓ DNS Server cục bộ đã dừng.")
    
    flush_dns_cache()

def monitoring_loop():
    global examId, studentId, authenticated, registered_face_path

    # UPDATED: Initialize MediaPipe ObjectDetector
    object_detector = ObjectDetector()
    face_tracker = FaceTracker()
    audio_monitor = AudioMonitor()
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("✗ Không thể mở camera! Đảm bảo không có ứng dụng nào khác đang sử dụng camera.")
        return

    phone_detection_count, frame_count = 0, 0
    last_check_time, check_interval = time.time(), 5

    def handle_speech_detected(text):
        print(f"Callback: Speech detected: {text}")
        update_user_field(examId, studentId, {
            "speechDetected": True,
            "lastSpeechTime": firestore.SERVER_TIMESTAMP,
            "lastSpeechText": text
        })

    def handle_keyword_detected(keyword, text):
        print(f"Callback: Forbidden keyword detected: {keyword} in {text}")
        update_user_field(examId, studentId, {
            "forbiddenKeywordDetected": True,
            "lastKeywordTime": firestore.SERVER_TIMESTAMP,
            "lastKeyword": keyword,
            "fullSpeechWithKeyword": text
        })

    print("🔍 Bắt đầu giám sát... (ESC để thoát)")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("✗ Không thể đọc frame từ camera!")
                break

            frame_count += 1

            frame, gaze_direction, head_pose = face_tracker.process_frame(frame)

            # Face authentication logic (remains the same)
            if not authenticated and registered_face_path and os.path.exists(registered_face_path) and frame_count % 10 == 0:
                verified = verify_face(frame, registered_face_path)
                if verified is True:
                    cv2.putText(frame, "Face: VERIFIED", (50, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    update_user_field(examId, studentId, {
                        "faceVerified": True,
                        "lastVerifiedTime": firestore.SERVER_TIMESTAMP
                    })

                    if not authenticated:
                        print("👤 Khuôn mặt khớp - xác thực hoàn tất!")
                        authenticated = True
                        apply_network_restrictions()
                        audio_monitor.start_monitoring(
                            speech_callback=handle_speech_detected,
                            keyword_callback=handle_keyword_detected
                        )

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
            elif authenticated:
                cv2.putText(frame, "Face: VERIFIED (Authenticated)", (50, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            else:
                cv2.putText(frame, "Face: NO REFERENCE", (50, 50),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (128, 128, 128), 2)

            # --- UPDATED: Object Detection Block ---
            if authenticated and object_detector.detector:
                detections = object_detector.detect(frame)
                
                for detection in detections:
                    label = detection['label']
                    score = detection['score']
                    x, y, w, h = detection['bbox']

                    # MediaPipe might detect 'mobile phone' instead of 'cell phone'
                    # so we check if 'phone' is in the label.
                    is_phone = 'phone' in label.lower()

                    color = (0, 0, 255) if is_phone else (128, 0, 128)
                    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                    cv2.putText(frame, f"{label} {score:.2f}", (x, y - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                    if is_phone:
                        phone_detection_count += 1
                        print(f"📱 Phát hiện điện thoại lần {phone_detection_count}")

                        if phone_detection_count == 3:
                            update_user_field(examId, studentId, {
                                "cheatSuspicion": "true",
                                "suspicionTime": firestore.SERVER_TIMESTAMP
                            })
                        if phone_detection_count == 7:
                            update_user_field(examId, studentId, {
                                "cheatDetected": "true",
                                "detectionTime": firestore.SERVER_TIMESTAMP
                            })
            # --- END OF UPDATED BLOCK ---

            cv2.putText(frame, f"Student: {studentId}", (50, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Phone detections: {phone_detection_count}", (50, 130),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Gaze: {gaze_direction}", (50, 160),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Head Pose: {head_pose}", (50, 190),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            if time.time() - last_check_time >= check_interval:
                doc = get_user_doc(examId, studentId)
                if doc.exists and not doc.to_dict().get("monitoringEnabled", True):
                    print("🛑 Tắt giám sát do yêu cầu từ xa.")
                    break
                last_check_time = time.time()

            cv2.imshow("Exam Monitoring System", frame)
            if cv2.waitKey(1) == 27:
                print("👋 Người dùng thoát.")
                break
    finally:
        print("Clean up after monitoring loop...")
        remove_network_restrictions()
        if audio_monitor.running:
            audio_monitor.stop_monitoring()

    cap.release()
    cv2.destroyAllWindows()
    print("✓ Hoàn tất giám sát!")

def run_app():
    global examId, studentId, registered_face_path

    def start_exam_action():
        global examId, studentId, registered_face_path
        examId = entry_exam.get().strip()
        studentId = entry_student.get().strip()
        if not examId or not studentId:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập đầy đủ Exam ID và Student ID")
            return
        registered_face_path = os.path.join(REGISTERED_FACES_DIR, f"{studentId}.jpg")
        root.destroy()

    root = tk.Tk()
    root.title("Exam Login")
    root.geometry("300x200")

    tk.Label(root, text="Exam ID").pack(pady=5)
    entry_exam = tk.Entry(root, width=30)
    entry_exam.pack(pady=5)

    tk.Label(root, text="Student ID").pack(pady=5)
    entry_student = tk.Entry(root, width=30)
    entry_student.pack(pady=5)

    tk.Button(root, text="Bắt đầu", command=start_exam_action).pack(pady=10)

    root.mainloop()

    if not examId or not studentId:
        print("✗ Người dùng đã hủy hoặc không nhập thông tin. Thoát ứng dụng.")
        return

    if not os.path.exists(registered_face_path):
        print(f"⚠ Không tìm thấy ảnh gốc cho Student ID {studentId} tại: {registered_face_path}")
        messagebox.showerror("Lỗi", f"Không tìm thấy ảnh gốc cho Student ID {studentId}. Vui lòng đảm bảo ảnh đã được đăng ký.")
        return
    
    try:
        monitoring_loop()
    finally:
        if proxy_active or dns_server_active or dns_blocked_interfaces:
            print("Chạy clean up cuối cùng từ run_app...")
            remove_network_restrictions()
