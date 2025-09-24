# Hệ thống giám sát kỳ thi tự động

Hệ thống này được thiết kế để hỗ trợ giám sát các kỳ thi trực tuyến hoặc ngoại tuyến, sử dụng kết hợp nhận diện khuôn mặt, phát hiện đối tượng và kiểm soát mạng để đảm bảo tính công bằng.

## Các tính năng chính

*   **Xác thực khuôn mặt**: Sử dụng thư viện DeepFace để xác thực khuôn mặt của thí sinh dựa trên ảnh đã đăng ký.
*   **Phát hiện đối tượng**: Tích hợp mô hình YOLOv7-tiny để phát hiện các vật thể gian lận tiềm năng, đặc biệt là điện thoại di động, trong thời gian thực.
*   **Hạn chế mạng**:
    *   Triển khai một DNS server cục bộ với danh sách trắng (whitelist) các miền được phép truy cập.
    *   Thiết lập một proxy server cục bộ, chỉ cho phép truy cập HTTP/HTTPS đến các miền trong danh sách trắng.
    *   Tự động áp dụng và gỡ bỏ các hạn chế mạng của hệ thống (DNS và Proxy) khi bắt đầu và kết thúc giám sát.
*   **Tích hợp Firebase**: Ghi lại trạng thái xác thực, các sự kiện phát hiện gian lận và có thể dừng giám sát từ xa thông qua Firebase.
*   **Giao diện người dùng đơn giản**: Sử dụng Tkinter để nhập Exam ID và Student ID khi bắt đầu.
*   **Công cụ kiểm tra mạng**: Cung cấp một công cụ riêng biệt để kiểm tra các cài đặt mạng và chức năng chặn.

## Cách hoạt động

1.  **Đăng nhập**: Thí sinh nhập Exam ID và Student ID thông qua giao diện Tkinter.
2.  **Xác thực khuôn mặt**: Hệ thống liên tục quét khuôn mặt của thí sinh qua camera và so sánh với ảnh đã đăng ký. Chỉ khi khuôn mặt được xác thực, quá trình giám sát đầy đủ mới bắt đầu.
3.  **Áp dụng hạn chế mạng**: Sau khi xác thực thành công, hệ thống sẽ:
    *   Khởi động DNS server cục bộ và proxy server cục bộ.
    *   Cấu hình DNS và Proxy của hệ thống để trỏ về các server cục bộ này.
    *   Xóa bộ nhớ cache DNS của hệ điều hành.
4.  **Giám sát liên tục**:
    *   Tiếp tục xác thực khuôn mặt định kỳ.
    *   Sử dụng YOLO để phát hiện "điện thoại di động". Nếu phát hiện quá nhiều lần, hệ thống sẽ ghi lại trạng thái "cheatSuspicion" hoặc "cheatDetected" lên Firebase.
    *   Hiển thị thông tin giám sát trên màn hình camera.
5.  **Dừng giám sát**:
    *   Người dùng có thể thoát bằng phím ESC.
    *   Hệ thống có thể dừng từ xa thông qua việc thay đổi trường `monitoringEnabled` trên Firebase.
    *   Khi dừng, tất cả các hạn chế mạng sẽ được gỡ bỏ và cài đặt gốc được khôi phục.

## Cài đặt

1.  **Cài đặt các thư viện Python**:
    ```bash
    pip install opencv-python deepface dnslib requests firebase-admin dnspython mediapipe pyaudio SpeechRecognition
    ```
2.  **Cấu hình Firebase**:
    *   Tải xuống tệp `key.json` từ Firebase Project Settings -> Service accounts và đặt nó vào thư mục `config/`.
3.  **Ảnh khuôn mặt đã đăng ký**:
    *   Đặt ảnh khuôn mặt tham chiếu của thí sinh vào thư mục `data/registered_faces/` với tên tệp là `[Student ID].jpg` (ví dụ: `12345.jpg`).
4.  **Cấu hình YOLO**:
    *   Đảm bảo các tệp `yolov7-tiny.weights`, `yolov7-tiny.cfg` và `coco.names` nằm trong thư mục `config/`.
5.  **Danh sách trắng (Whitelist)**:
    *   Chỉnh sửa `config/whitelist.txt` cho proxy server (các domain được phép truy cập HTTP/HTTPS).
    *   Chỉnh sửa `config/dns_whitelist.txt` cho DNS server (các domain được phép phân giải DNS).

## Cách sử dụng

Để chạy hệ thống giám sát:

```bash
python main.py
```

Một cửa sổ đăng nhập sẽ xuất hiện. Nhập Exam ID và Student ID, sau đó nhấp "Bắt đầu".

### Công cụ kiểm tra mạng

Để chạy công cụ kiểm tra mạng độc lập (hữu ích cho việc gỡ lỗi):

```bash
python test/network_test_tool.py
```

Công cụ này cung cấp các tùy chọn để kiểm tra DNS, HTTP/HTTPS trực tiếp và qua proxy, cũng như kiểm tra trạng thái của các server cục bộ.

## Lưu ý quan trọng

*   Hệ thống này được thiết kế cho môi trường Windows do sử dụng lệnh `netsh` và `ipconfig`.
*   Cần có quyền quản trị để thay đổi cài đặt mạng của hệ thống.
*   Đối với HTTPS, thư viện `requests` bỏ qua xác minh SSL (`verify=False`) trong các thử nghiệm proxy.

## Cấu trúc thư mục

```
.
├── main.py                     # Điểm khởi chạy chính của ứng dụng
├── config/
│   ├── alt-vpn.ovpn
│   ├── coco.names              # Tên lớp cho YOLO
│   ├── dns_whitelist.txt       # Danh sách trắng cho DNS server cục bộ
│   ├── key.json                # Khóa dịch vụ Firebase
│   ├── whitelist.txt           # Danh sách trắng cho proxy server cục bộ
│   ├── yolov7-tiny.cfg         # Cấu hình mô hình YOLO
│   └── yolov7-tiny.weights     # Trọng số mô hình YOLO
├── core/
│   ├── __init__.py
│   ├── face_auth.py            # Logic xác thực khuôn mặt (DeepFace)
│   ├── firebase_utils.py       # Các hàm tương tác với Firebase
│   ├── main.py                 # Logic chính của ứng dụng giám sát
│   ├── network_utils.py        # Các hàm điều khiển mạng (DNS, Proxy)
│   ├── proxy_server.py         # Triển khai proxy server cục bộ
│   └── yolo_detect.py          # Logic phát hiện đối tượng (YOLO)
├── data/
│   └── registered_faces/       # Thư mục chứa ảnh khuôn mặt đã đăng ký
│       └── [student_id].jpg    # Ảnh khuôn mặt của thí sinh
└── test/
    ├── main.py                 # Tệp thử nghiệm nhận diện khuôn mặt độc lập
    └── network_test_tool.py    # Công cụ kiểm tra các chức năng mạng
```

## Các tính năng được đề xuất và cải tiến trong tương lai

| **Lớp** | **Tính năng** | **Mô tả** | **Công cụ/Gợi ý triển khai** |
|---|---|---|---|
| **Xác thực & Nhận diện** | Xác thực khuôn mặt | So sánh với ảnh đã đăng ký trước khi thi | DeepFace, dlib |
| | Phát hiện nhiều khuôn mặt | Cảnh báo khi có thêm người xuất hiện | MTCNN, Mediapipe |
| | Xác thực môi trường | Yêu cầu quay camera 360° trước khi thi | OpenCV + UI hướng dẫn |
| **Giám sát Webcam** | Phát hiện đối tượng gian lận | Nhận diện điện thoại, sách, tai nghe… | YOLOv7-tiny, Mediapipe |
| | Theo dõi ánh mắt & đầu | Phát hiện nhìn ra ngoài màn hình hoặc cúi xuống | Mediapipe Face Mesh, OpenFace |
| **Giám sát Âm thanh** | Phát hiện tiếng nói | Cảnh báo khi có tiếng người/âm thanh lạ | PyAudio, SpeechRecognition |
| | Nhận diện từ khóa cấm | Phát hiện “nói đáp án” hoặc trao đổi | Keyword Spotting |
| **Môi trường Máy tính** | Khóa toàn màn hình | Bắt buộc chế độ full-screen, phát hiện Alt+Tab | Electron / PyQt fullscreen API |
| | Phát hiện nhiều màn hình | Ngăn dùng 2 màn hình khi thi | Windows API (\`wmic\`) / Xrandr (Linux) |
| | Chụp màn hình định kỳ | Lưu lại hoạt động máy tính để so sánh | PyAutoGUI / mss |
| | Chặn phần mềm gian lận | Ngăn mở TeamViewer, OBS, Discord… | Liệt kê process (\`psutil\`) |
| **Bàn phím & Chuột** | Theo dõi hành vi gõ phím | Phát hiện copy/paste hoặc gõ bất thường | PyHook / pynput |
| | Log chuột | Ghi lại thao tác chuột để phát hiện hành vi lạ | pynput.mouse |
| **Mạng** | DNS + Proxy whitelist | Chỉ cho phép truy cập miền trong danh sách | dnslib + proxy server |
| | Phát hiện VPN/proxy ngoài | Đánh dấu khi user cố lách luật | Kiểm tra IP public, traceroute |
| | Ghi log mất kết nối | Nếu ngắt mạng nhiều lần → nghi vấn | Firebase logging |
| **Hậu kiểm** | Ghi log toàn bộ | Video + ảnh + log sự kiện | Firebase storage + local backup |
| | Phân tích gian lận tự động | Tính điểm rủi ro gian lận (cheatScore) | Rule-based + AI model |