import subprocess
import re
import socket
import threading
from dnslib import DNSRecord, RR, A, QTYPE # Cần cài đặt dnslib: pip install dnslib

# ================= CONFIG =================
# Đường dẫn tới whitelist cho DNS (ví dụ: các domain được phép truy cập)
DNS_WHITELIST_PATH = "config/dns_whitelist.txt"
WHITELISTED_DOMAINS = []

def load_dns_whitelist():
    global WHITELISTED_DOMAINS
    try:
        with open(DNS_WHITELIST_PATH, "r") as f:
            WHITELISTED_DOMAINS = [line.strip().lower() for line in f if line.strip() and not line.startswith('#')]
        print(f"✓ Đã tải DNS Whitelist: {WHITELISTED_DOMAINS}")
    except FileNotFoundError:
        print(f"✗ Không tìm thấy tệp DNS Whitelist: {DNS_WHITELIST_PATH}. Tất cả DNS sẽ bị chặn.")
        WHITELISTED_DOMAINS = [] # Nếu không tìm thấy whitelist, chặn tất cả
    except Exception as e:
        print(f"✗ Lỗi khi tải DNS Whitelist: {e}. Tất cả DNS sẽ bị chặn.")
        WHITELISTED_DOMAINS = []

# ================= DNS SERVER =================
DNS_SERVER_IP = "127.0.0.1"
DNS_SERVER_PORT = 53
dns_server_socket = None
dns_server_thread = None
dns_server_running = False

def handle_dns_request(data, addr, sock):
    try:
        request = DNSRecord.parse(data)
        qname = str(request.q.qname).lower().rstrip('.')
        
        response = DNSRecord(request.header)
        response.add_question(request.q)

        is_whitelisted = False
        for domain in WHITELISTED_DOMAINS:
            if qname == domain or qname.endswith('.' + domain):
                is_whitelisted = True
                break

        if is_whitelisted:
            # Chuyển tiếp yêu cầu đến một DNS công cộng (ví dụ: Google DNS)
            # Hoặc, nếu bạn muốn chặn luôn nhưng cho phép một số IP cụ thể (ít dùng cho whitelist DNS)
            try:
                # Sử dụng DNS của Google để phân giải cho các domain trong whitelist
                upstream_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                upstream_sock.settimeout(2)
                upstream_sock.sendto(data, ("8.8.8.8", 53)) # Google Public DNS
                upstream_response, _ = upstream_sock.recvfrom(512)
                sock.sendto(upstream_response, addr)
            except Exception as e:
                print(f"✗ Lỗi khi chuyển tiếp DNS cho {qname}: {e}")
                # Trả về NXDOMAIN nếu chuyển tiếp thất bại
                response.header.ra = 1
                response.header.rcode = QTYPE.NXDOMAIN
                sock.sendto(response.pack(), addr)
            finally:
                if upstream_sock:
                    upstream_sock.close()
        else:
            # Chặn: Trả về NXDOMAIN (tên miền không tồn tại)
            print(f"🚫 Chặn truy vấn DNS cho: {qname} (không có trong whitelist)")
            response.header.ra = 1
            response.header.rcode = QTYPE.NXDOMAIN
            sock.sendto(response.pack(), addr)

    except Exception as e:
        print(f"✗ Lỗi xử lý DNS request từ {addr}: {e}")

def dns_server_loop():
    global dns_server_socket, dns_server_running
    load_dns_whitelist()
    try:
        dns_server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        dns_server_socket.bind((DNS_SERVER_IP, DNS_SERVER_PORT))
        dns_server_socket.settimeout(1) # Timeout để có thể kiểm tra dns_server_running
        print(f"✓ DNS Server đang chạy trên {DNS_SERVER_IP}:{DNS_SERVER_PORT}")
        dns_server_running = True
        while dns_server_running:
            try:
                data, addr = dns_server_socket.recvfrom(512)
                threading.Thread(target=handle_dns_request, args=(data, addr, dns_server_socket)).start()
            except socket.timeout:
                pass # Tiếp tục vòng lặp nếu timeout
            except Exception as e:
                print(f"✗ Lỗi trong vòng lặp DNS server: {e}")
    except Exception as e:
        print(f"✗ Không thể khởi động DNS Server trên {DNS_SERVER_IP}:{DNS_SERVER_PORT}: {e}")
        dns_server_running = False
    finally:
        if dns_server_socket:
            dns_server_socket.close()
            print("✓ DNS Server đã dừng.")

def start_dns_server():
    global dns_server_thread
    if not dns_server_running:
        dns_server_thread = threading.Thread(target=dns_server_loop, daemon=True)
        dns_server_thread.start()
        # Chờ một chút để server có thể khởi động
        import time
        time.sleep(0.5)

def stop_dns_server():
    global dns_server_running
    if dns_server_running:
        dns_server_running = False
        # thread sẽ tự đóng socket khi vòng lặp kết thúc
        print("Đang yêu cầu dừng DNS Server...")

# ================= NETSH COMMANDS =================
def run_netsh_command(command_parts):
    try:
        result = subprocess.run(command_parts, check=True, capture_output=True, text=True, shell=True)
        print(f"✓ netsh output: {command_parts[2]} {command_parts[3]} succeeded") # Rút gọn output
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Lỗi netsh: {e.cmd}")
        print(f"  Stdout: {e.stdout.strip()}")
        print(f"  Stderr: {e.stderr.strip()}")
        return False
    except FileNotFoundError:
        print("✗ Lỗi: Lệnh 'netsh' không tìm thấy. Có thể không phải Windows hoặc PATH sai.")
        return False

def set_system_proxy(proxy_address="127.0.0.1:8899"):
    print(f"Đang thiết lập proxy hệ thống thành {proxy_address}...")
    success = run_netsh_command(["netsh", "winhttp", "set", "proxy", proxy_address])
    if success:
        print("✓ Đã thiết lập proxy hệ thống.")
    else:
        print("✗ Không thể thiết lập proxy hệ thống.")
    return success

def reset_system_proxy():
    print("Đang đặt lại proxy hệ thống...")
    success = run_netsh_command(["netsh", "winhttp", "reset", "proxy"])
    if success:
        print("✓ Đã đặt lại proxy hệ thống.")
    else:
        print("✗ Không thể đặt lại proxy hệ thống.")
    return success

def get_active_network_interfaces():
    interfaces = []
    try:
        # Lệnh để lấy thông tin interface chi tiết hơn
        result = subprocess.run(["netsh", "interface", "ipv4", "show", "config"], check=True, capture_output=True, text=True, shell=True)
        output = result.stdout
        
        current_interface = None
        for line in output.splitlines():
            if "Cấu hình cho giao diện" in line or "Configuration for interface" in line: # Dòng bắt đầu của một interface mới
                match = re.search(r"Cấu hình cho giao diện "(.+)"", line) or re.search(r"Configuration for interface "(.+)"", line)
                if match:
                    current_interface = match.group(1).strip()
                    if current_interface and current_interface not in ['Loopback Pseudo-Interface 1']:
                        interfaces.append(current_interface)
            # Có thể thêm logic để kiểm tra trạng thái "Connected" hoặc "Enabled" nếu cần
            # Tuy nhiên, "show config" thường chỉ hiển thị các interface đang cấu hình IP
    except Exception as e:
        print(f"✗ Lỗi khi lấy danh sách card mạng: {e}")
    # Đôi khi netsh interface show interface cung cấp thông tin "Connected" rõ ràng hơn
    try:
        result = subprocess.run(["netsh", "interface", "show", "interface"], check=True, capture_output=True, text=True, shell=True)
        output = result.stdout
        for line in output.splitlines():
            if "Connected" in line or "Enabled" in line:
                match = re.search(r'\s{2,}\w+\s{2,}\w+\s{2,}\w+\s{2,}(.+)$', line)
                if match:
                    interface_name = match.group(1).strip()
                    if interface_name and interface_name not in ['Loopback Pseudo-Interface 1'] and interface_name not in interfaces:
                         interfaces.append(interface_name)
    except Exception as e:
        print(f"✗ Lỗi khi lấy danh sách card mạng từ 'show interface': {e}")

    return list(set(interfaces)) # Đảm bảo không có trùng lặp


def set_system_dns(interface_name, dns_server="127.0.0.1"):
    print(f"Đang thiết lập DNS cho adapter '{interface_name}' thành {dns_server}...")
    success = run_netsh_command(["netsh", "interface", "ipv4", "set", "dns", interface_name, "static", dns_server, "primary"])
    if success:
        print(f"✓ Đã thiết lập DNS chính cho '{interface_name}'.")
    else:
        print(f"✗ Không thể thiết lập DNS chính cho '{interface_name}'.")
    return success

def reset_system_dns(interface_name):
    print(f"Đang đặt lại DNS cho adapter '{interface_name}' về DHCP...")
    success = run_netsh_command(["netsh", "interface", "ipv4", "set", "dns", interface_name, "dhcp"])
    if success:
        print(f"✓ Đã đặt lại DNS cho '{interface_name}'.")
    else:
        print(f"✗ Không thể đặt lại DNS cho '{interface_name}'.")
    return success
