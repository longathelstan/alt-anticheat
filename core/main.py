import cv2
import time
import threading
import os
import subprocess
import re # Import re module for regex
import firebase_admin
from core.face_auth import verify_face
from core.yolo_detect import init_yolo, detect_objects
from core.firebase_utils import update_user_field, get_user_doc
from core.proxy_server import start_proxy
from firebase_admin import credentials, firestore
import tkinter as tk
from tkinter import messagebox
import numpy as np

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
proxy_started = False
dns_blocked = False # New flag to track DNS blocking status
# Store original DNS config for each interface for resetting
original_dns_config_interfaces = [] 

def run_netsh_command(command_parts):
    try:
        result = subprocess.run(command_parts, check=True, capture_output=True, text=True, shell=True)
        print(f"✓ netsh output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Lỗi netsh: {e.cmd}")
        print(f"  Stdout: {e.stdout.strip()}")
        print(f"  Stderr: {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        print("✗ Lỗi: Lệnh 'netsh' không tìm thấy. Có thể không phải Windows hoặc PATH sai.")
        return False

def set_system_proxy():
    print("Đang thiết lập proxy hệ thống...")
    success = run_netsh_command(["netsh", "winhttp", "set", "proxy", "127.0.0.1:8899"])
    if success:
        print("✓ Đã thiết lập proxy hệ thống.")
    else:
        print("✗ Không thể thiết lập proxy hệ thống.")

def reset_system_proxy():
    print("Đang đặt lại proxy hệ thống...")
    success = run_netsh_command(["netsh", "winhttp", "reset", "proxy"])
    if success:
        print("✓ Đã đặt lại proxy hệ thống.")
    else:
        print("✗ Không thể đặt lại proxy hệ thống.")

def get_active_network_interfaces():
    interfaces = []
    try:
        result = subprocess.run(["netsh", "interface", "show", "interface"], check=True, capture_output=True, text=True, shell=True)
        output = result.stdout
        # Regex to find interface names. 'Enabled' or 'Connected' status
        # Adapters that start with 'Wi-Fi', 'Ethernet', etc.
        for line in output.splitlines():
            if "Connected" in line or "Enabled" in line:
                match = re.search(r'\s{2,}\w+\s{2,}\w+\s{2,}\w+\s{2,}(.+)$', line) # Matches the Interface Name column
                if match:
                    interface_name = match.group(1).strip()
                    if interface_name and interface_name not in ['Loopback Pseudo-Interface 1']:
                         interfaces.append(interface_name)
    except Exception as e:
        print(f"✗ Lỗi khi lấy danh sách card mạng: {e}")
    return interfaces

def set_system_dns(interface_name, dns_server="127.0.0.1"):
    print(f"Đang thiết lập DNS cho adapter '{interface_name}' thành {dns_server}...")
    success = run_netsh_command(["netsh", "interface", "ipv4", "set", "dns", interface_name, "static", dns_server])
    if success:
        print(f"✓ Đã thiết lập DNS cho '{interface_name}'.")
    else:
        print(f"✗ Không thể thiết lập DNS cho '{interface_name}'.")

def reset_system_dns(interface_name):
    print(f"Đang đặt lại DNS cho adapter '{interface_name}' về DHCP...")
    success = run_netsh_command(["netsh", "interface", "ipv4", "set", "dns", interface_name, "dhcp"])
    if success:
        print(f"✓ Đã đặt lại DNS cho '{interface_name}'.")
    else:
        print(f"✗ Không thể đặt lại DNS cho '{interface_name}'.")

def monitoring_loop():
    global authenticated, registered_face_path, proxy_started, dns_blocked, original_dns_config_interfaces

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

                    if not authenticated:
                        print("👤 Khuôn mặt khớp - xác thực hoàn tất!")
                        authenticated = True
                        # Start proxy and set system proxy
                        if not proxy_started:
                            threading.Thread(target=start_proxy, daemon=True).start()
                            proxy_started = True
                            set_system_proxy()
                        
                        # Set DNS after successful authentication and proxy setup
                        if not dns_blocked:
                            original_dns_config_interfaces = get_active_network_interfaces()
                            if original_dns_config_interfaces:
                                for interface in original_dns_config_interfaces:
                                    set_system_dns(interface)
                                dns_blocked = True
                            else:
                                print("⚠ Không tìm thấy card mạng hoạt động để thiết lập DNS.")

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
            if cv2.waitKey(1) == 27:
                print("👋 Người dùng thoát.")
                break
    finally:
        # Ensure DNS and proxy are reset even if an error occurs
        if proxy_started:
            reset_system_proxy()
        if dns_blocked and original_dns_config_interfaces:
            for interface in original_dns_config_interfaces:
                reset_system_dns(interface)

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
        root.destroy()

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

    try:
        monitoring_loop()
    finally:
        # Ensure DNS and proxy are reset in case monitoring_loop does not complete fully
        if proxy_started:
            reset_system_proxy()
        if dns_blocked and original_dns_config_interfaces:
            for interface in original_dns_config_interfaces:
                reset_system_dns(interface)
