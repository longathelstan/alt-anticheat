from proxy.http.proxy import HttpProxyPlugin
from proxy.http.parser import HttpParser
from proxy import main as proxy_main
import sys
import os
import threading

WHITELIST_PATH = "config/whitelist.txt"
WHITELIST = []
proxy_thread = None
proxy_running_flag = threading.Event()

def load_proxy_whitelist():
    global WHITELIST
    try:
        with open(WHITELIST_PATH, "r") as f:
            WHITELIST = [line.strip().lower() for line in f if line.strip() and not line.startswith('#')]
        print(f"✓ Đã tải Proxy Whitelist: {WHITELIST}")
    except FileNotFoundError:
        print(f"✗ Không tìm thấy tệp Proxy Whitelist: {WHITELIST_PATH}. Tất cả HTTP/HTTPS sẽ bị chặn.")
        WHITELIST = []
    except Exception as e:
        print(f"✗ Lỗi khi tải Proxy Whitelist: {e}. Tất cả HTTP/HTTPS sẽ bị chặn.")
        WHITELIST = []

class WhitelistPlugin(HttpProxyPlugin):
    def before_upstream_connection(self, request: HttpParser):
        host = request.host.decode("utf-8").lower() if request.host else ""
        
        is_whitelisted = False
        for allowed_domain in WHITELIST:
            if host == allowed_domain or host.endswith('.' + allowed_domain):
                is_whitelisted = True
                break

        if not is_whitelisted:
            print(f"🚫 Chặn truy cập HTTP/HTTPS tới: {host} (không có trong whitelist)")
            raise Exception(f"Blocked by whitelist: {host}")
        return request

def _run_proxy_main():
    original_argv = sys.argv
    try:
        sys.argv = [
            "proxy_server.py",
            "--hostname", "127.0.0.1",
            "--port", "8899",
            "--plugins", __name__ + ".WhitelistPlugin"
        ]
        proxy_running_flag.set()
        proxy_main()
    except SystemExit as e:
        if str(e) != "0":
            print(f"✗ Proxy server exited with error: {e}")
    except Exception as e:
        print(f"✗ Lỗi khi chạy proxy server: {e}")
    finally:
        sys.argv = original_argv
        proxy_running_flag.clear()

def start_proxy():
    global proxy_thread
    if not proxy_running_flag.is_set():
        load_proxy_whitelist()
        proxy_thread = threading.Thread(target=_run_proxy_main, daemon=True)
        proxy_thread.start()
        proxy_running_flag.wait(timeout=5)
        if proxy_running_flag.is_set():
            print("✓ Proxy Server cục bộ đã khởi động.")
        else:
            print("✗ Không thể xác nhận Proxy Server đã khởi động.")

def stop_proxy():
    if proxy_running_flag.is_set():
        print("Đang yêu cầu dừng Proxy Server. (Sẽ tự dừng khi ứng dụng chính thoát)")
        proxy_running_flag.clear()
    else:
        print("Proxy Server không hoạt động.")