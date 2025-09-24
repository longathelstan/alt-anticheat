import pyaudio
import speech_recognition as sr
import threading
import time

# ================= CONFIG =================
CHUNK = 1024  # Kích thước mỗi khối âm thanh
FORMAT = pyaudio.paInt16  # Định dạng âm thanh
CHANNELS = 1  # Số kênh âm thanh
RATE = 16000  # Tốc độ lấy mẫu (Hz)

FORBIDDEN_KEYWORDS = [
    "đáp án", "quay cóp", "gian lận", "tài liệu", "trợ giúp",
    "câu hỏi", "bài làm", "kết quả"
] # Từ khóa cấm

class AudioMonitor:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.recognizer = sr.Recognizer()
        self.audio_thread = None
        self.running = False
        self.speech_detected_callback = None
        self.keyword_detected_callback = None

    def start_monitoring(self, speech_callback=None, keyword_callback=None):
        if self.running:
            print("Audio monitoring already running.")
            return
        
        self.speech_detected_callback = speech_callback
        self.keyword_detected_callback = keyword_callback

        try:
            self.stream = self.p.open(format=FORMAT,
                                      channels=CHANNELS,
                                      rate=RATE,
                                      input=True,
                                      frames_per_buffer=CHUNK)
            self.running = True
            self.audio_thread = threading.Thread(target=self._audio_loop, daemon=True)
            self.audio_thread.start()
            print("✓ Bắt đầu giám sát âm thanh.")
        except Exception as e:
            print(f"✗ Lỗi khi khởi động giám sát âm thanh: {e}")
            self.running = False

    def stop_monitoring(self):
        if self.running:
            self.running = False
            if self.audio_thread and self.audio_thread.is_alive():
                self.audio_thread.join(timeout=2)  # Chờ thread kết thúc
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            print("✓ Đã dừng giám sát âm thanh.")

    def _audio_loop(self):
        while self.running:
            try:
                data = self.stream.read(CHUNK, exception_on_overflow=False)
                audio_data = sr.AudioData(data, RATE, 2) # 2 bytes per sample (paInt16)

                try:
                    text = self.recognizer.recognize_google(audio_data, language="vi-VN")
                    if text:
                        print(f"🎤 Phát hiện tiếng nói: \"{text}\"")
                        if self.speech_detected_callback:
                            self.speech_detected_callback(text)

                        for keyword in FORBIDDEN_KEYWORDS:
                            if keyword in text.lower():
                                print(f"🚨 Phát hiện từ khóa cấm: \"{keyword}\" trong \"{text}\"")
                                if self.keyword_detected_callback:
                                    self.keyword_detected_callback(keyword, text)
                                break

                except sr.UnknownValueError:
                    pass # Không phát hiện tiếng nói
                except sr.RequestError as e:
                    # Lỗi API của Google Speech Recognition (ví dụ: không có mạng)
                    print(f"✗ Lỗi Speech Recognition: {e}")
                    time.sleep(1) # Chờ trước khi thử lại

            except Exception as e:
                print(f"✗ Lỗi trong vòng lặp ghi âm: {e}")
                self.running = False # Dừng giám sát nếu có lỗi nghiêm trọng

    def __del__(self):
        self.stop_monitoring()
        self.p.terminate()
