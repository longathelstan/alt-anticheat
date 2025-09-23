import cv2
import time
import threading
import os
import subprocess
import re
import firebase_admin
import tkinter as tk
from tkinter import messagebox
import numpy as np
from firebase_admin import credentials, firestore

from core.face_auth import verify_face
from core.yolo_detect import init_yolo, detect_objects
from core.firebase_utils import update_user_field, get_user_doc
from core.proxy_server import start_proxy, stop_proxy
from core.network_utils import (
    set_system_proxy, reset_system_proxy,
    get_active_network_interfaces, set_system_dns, reset_system_dns,
    start_dns_server, stop_dns_server, flush_dns_cache
)

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

proxy_active = False
dns_blocked_interfaces = [] # Lưu trữ các interface đã được thay đổi DNS
dns_server_active = False

def apply_network_restrictions():
    """
    Áp dụng các hạn chế mạng: khởi động DNS và Proxy server cục bộ,
    đặt DNS và Proxy của hệ thống trỏ về cục bộ, và xóa cache DNS.
    """
    global proxy_active, dns_blocked_interfaces, dns_server_active
    print("⚙️ Áp dụng các hạn chế mạng...")

    # 0. Xóa bộ nhớ cache DNS của hệ điều hành
    flush_dns_cache()

    # 1. Khởi động DNS Server cục bộ
    if not dns_server_active:
        start_dns_server()
        dns_server_active = True
        print("✓ DNS Server cục bộ đã khởi động.")

    # 2. Đặt DNS hệ thống trỏ về DNS Server cục bộ
    active_interfaces = get_active_network_interfaces()
    if active_interfaces:
        for interface in active_interfaces:
            if set_system_dns(interface):
                dns_blocked_interfaces.append(interface)
        print("✓ DNS hệ thống đã trỏ về DNS Server cục bộ.")
    else:
        print("⚠ Không tìm thấy card mạng hoạt động để thiết lập DNS.")

    # 3. Khởi động Proxy Server và thiết lập Proxy hệ thống
    if not proxy_active:
        threading.Thread(target=start_proxy, daemon=True).start()
        proxy_active = True
        # Chờ một chút để proxy server khởi động
        time.sleep(1)
        if set_system_proxy():
            print("✓ Proxy hệ thống đã thiết lập.")
        else:
            print("✗ Không thể thiết lập proxy hệ thống.")

def remove_network_restrictions():
    """
    Gỡ bỏ tất cả các hạn chế mạng đã áp dụng và khôi phục cài đặt gốc.
    """
    global proxy_active, dns_blocked_interfaces, dns_server_active
    print("⚙️ Gỡ bỏ các hạn chế mạng...")

    # 1. Đặt lại Proxy hệ thống
    if proxy_active:
        reset_system_proxy()
        stop_proxy()
        proxy_active = False
        print("✓ Proxy hệ thống đã đặt lại.")

    # 2. Đặt lại DNS hệ thống
    if dns_blocked_interfaces:
        for interface in dns_blocked_interfaces:
            reset_system_dns(interface)
        dns_blocked_interfaces = []
        print("✓ DNS hệ thống đã đặt lại.")

    # 3. Dừng DNS Server cục bộ
    if dns_server_active:
        stop_dns_server()
        dns_server_active = False
        print("✓ DNS Server cục bộ đã dừng.")
    
    # 4. Xóa bộ nhớ cache DNS một lần nữa để đảm bảo sạch sẽ
    flush_dns_cache()


def monitoring_loop():
    """
    Vòng lặp chính để giám sát kỳ thi, bao gồm xác thực khuôn mặt, phát hiện đối tượng
    và kiểm soát mạng.
    """
    global authenticated, registered_face_path

    net, classes, output_layers = init_yolo(YOLO_WEIGHTS, YOLO_CFG, COCO_NAMES)
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("✗ Không thể mở camera! Đảm bảo không có ứng dụng nào khác đang sử dụng camera.")
        return

    phone_detection_count, frame_count = 0, 0
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

                    if not authenticated:
                        print("👤 Khuôn mặt khớp - xác thực hoàn tất!")
                        authenticated = True
                        apply_network_restrictions() # Áp dụng hạn chế mạng sau xác thực

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


            # ---- YOLO chỉ chạy khi authenticated ----
            if authenticated and net is not None:
                indices, boxes, confidences, class_ids = detect_objects(frame, net, output_layers, classes)
                if len(indices) > 0:
                    for i in indices.flatten():
                        x, y, w, h = boxes[i]
                        label, conf = classes[class_ids[i]], confidences[i]

                        color = (0, 0, 255) if label == "cell phone" else (128, 0, 128)
                        cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
                        cv2.putText(frame, f"{label} {conf:.2f}", (x, y - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                        if label == "cell phone":
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

            # ---- Overlay info ----
            cv2.putText(frame, f"Student: {studentId}", (50, 100),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.putText(frame, f"Phone detections: {phone_detection_count}", (50, 130),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # ---- Remote stop ----
            if time.time() - last_check_time >= check_interval:
                doc = get_user_doc(examId, studentId)
                # Giám sát sẽ dừng nếu trường 'monitoringEnabled' trong Firebase được đặt thành False
                if doc.exists and not doc.to_dict().get("monitoringEnabled", True):
                    print("🛑 Tắt giám sát do yêu cầu từ xa.")
                    break
                last_check_time = time.time()

            # ---- Show frame ----
            cv2.imshow("Exam Monitoring System", frame)
            if cv2.waitKey(1) == 27:
                print("👋 Người dùng thoát.")
                break
    finally:
        print("Clean up after monitoring loop...")
        remove_network_restrictions() # Đảm bảo gỡ bỏ hạn chế mạng khi thoát

    cap.release()
    cv2.destroyAllWindows()
    print("✓ Hoàn tất giám sát!")

def run_app():
    """
    Khởi chạy ứng dụng giám sát kỳ thi, bao gồm giao diện đăng nhập
    và vòng lặp giám sát chính.
    """
    global examId, studentId, registered_face_path

    def start_exam_action():
        """Xử lý hành động "Bắt đầu" từ giao diện đăng nhập."""
        nonlocal examId, studentId, registered_face_path
        examId = entry_exam.get().strip()
        studentId = entry_student.get().strip()
        if not examId or not studentId:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập đầy đủ Exam ID và Student ID")
            return
        registered_face_path = os.path.join(REGISTERED_FACES_DIR, f"{studentId}.jpg")
        root.destroy()

    root = tk.Tk()
    root.title("Exam Login")
    root.geometry("300x200") # Kích thước cửa sổ mặc định

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
    
    # Đảm bảo gỡ bỏ hạn chế mạng nếu có bất kỳ lỗi nào xảy ra trước hoặc sau monitoring_loop
    try:
        monitoring_loop()
    finally:
        # Đây là khối finally cuối cùng, đảm bảo mọi thứ được reset. 
        # monitoring_loop() cũng đã có finally riêng, nhưng đây là một lớp bảo vệ bổ sung.
        if proxy_active or dns_server_active or dns_blocked_interfaces:
            print("Chạy clean up cuối cùng từ run_app...")
            remove_network_restrictions()
