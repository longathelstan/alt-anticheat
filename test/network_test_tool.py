import subprocess
import socket
import requests
import time
import threading
import json
from urllib.parse import urlparse

class NetworkTester:
    def __init__(self):
        self.test_domains = [
            "facebook.com",
            "google.com", 
            "youtube.com",
            "github.com",
            "stackoverflow.com"
        ]
        self.test_results = {}
        
    def test_system_dns(self, domain):
        """Test DNS resolution qua system resolver"""
        try:
            ip = socket.gethostbyname(domain)
            return {"success": True, "ip": ip, "method": "system_dns"}
        except Exception as e:
            return {"success": False, "error": str(e), "method": "system_dns"}
    
    def test_direct_dns(self, domain, dns_server="127.0.0.1"):
        """Test DNS resolution trực tiếp đến DNS server"""
        try:
            import dns.resolver
            resolver = dns.resolver.Resolver()
            resolver.nameservers = [dns_server]
            resolver.timeout = 2
            
            answers = resolver.resolve(domain, 'A')
            ips = [str(answer) for answer in answers]
            return {"success": True, "ips": ips, "method": f"direct_dns_{dns_server}"}
        except Exception as e:
            return {"success": False, "error": str(e), "method": f"direct_dns_{dns_server}"}
    
    def test_nslookup(self, domain):
        """Test DNS bằng nslookup command"""
        try:
            result = subprocess.run(
                ["nslookup", domain], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "method": "nslookup"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "method": "nslookup"}
    
    def test_http_direct(self, url):
        """Test HTTP request trực tiếp (không qua proxy)"""
        try:
            response = requests.get(
                f"http://{url}", 
                timeout=5,
                proxies={"http": None, "https": None}  # Bypass proxy
            )
            return {
                "success": True,
                "status_code": response.status_code,
                "method": "http_direct"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "method": "http_direct"}
    
    def test_http_system_proxy(self, url):
        """Test HTTP request qua system proxy"""
        try:
            response = requests.get(
                f"http://{url}", 
                timeout=5
                # Sử dụng system proxy settings
            )
            return {
                "success": True,
                "status_code": response.status_code,
                "method": "http_system_proxy"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "method": "http_system_proxy"}
    
    def test_https_direct(self, url):
        """Test HTTPS request trực tiếp"""
        try:
            response = requests.get(
                f"https://{url}", 
                timeout=5,
                proxies={"http": None, "https": None},
                verify=False  # Skip SSL verification for testing
            )
            return {
                "success": True,
                "status_code": response.status_code,
                "method": "https_direct"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "method": "https_direct"}
    
    def test_https_system_proxy(self, url):
        """Test HTTPS request qua system proxy"""
        try:
            response = requests.get(
                f"https://{url}", 
                timeout=5,
                verify=False
            )
            return {
                "success": True,
                "status_code": response.status_code,
                "method": "https_system_proxy"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "method": "https_system_proxy"}
    
    def test_proxy_server_running(self, proxy_host="127.0.0.1", proxy_port=8899):
        """Test xem proxy server có đang chạy không"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((proxy_host, proxy_port))
            sock.close()
            return {
                "success": result == 0,
                "method": "proxy_port_check",
                "port": proxy_port
            }
        except Exception as e:
            return {"success": False, "error": str(e), "method": "proxy_port_check"}
    
    def test_dns_server_running(self, dns_host="127.0.0.1", dns_port=53):
        """Test xem DNS server có đang chạy không"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            sock.sendto(b"test", (dns_host, dns_port))
            sock.close()
            return {
                "success": True,
                "method": "dns_port_check",
                "port": dns_port
            }
        except Exception as e:
            return {"success": False, "error": str(e), "method": "dns_port_check"}
    
    def get_system_proxy_settings(self):
        """Lấy proxy settings hiện tại của hệ thống"""
        try:
            result = subprocess.run(
                ["netsh", "winhttp", "show", "proxy"], 
                capture_output=True, 
                text=True
            )
            return {
                "success": True,
                "output": result.stdout,
                "method": "system_proxy_check"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "method": "system_proxy_check"}
    
    def get_system_dns_settings(self):
        """Lấy DNS settings hiện tại"""
        try:
            result = subprocess.run(
                ["ipconfig", "/all"], 
                capture_output=True, 
                text=True
            )
            return {
                "success": True,
                "output": result.stdout,
                "method": "system_dns_check"
            }
        except Exception as e:
            return {"success": False, "error": str(e), "method": "system_dns_check"}
    
    def run_comprehensive_test(self):
        """Chạy tất cả các test"""
        print("🧪 Bắt đầu comprehensive network test...")
        print("=" * 60)
        
        # Test infrastructure
        print("\n📡 INFRASTRUCTURE TESTS:")
        print("-" * 30)
        
        # Check if servers are running
        proxy_test = self.test_proxy_server_running()
        print(f"Proxy Server (8899): {'✅' if proxy_test['success'] else '❌'}")
        
        dns_test = self.test_dns_server_running()
        print(f"DNS Server (53): {'✅' if dns_test['success'] else '❌'}")
        
        # Check system settings
        proxy_settings = self.get_system_proxy_settings()
        if proxy_settings['success']:
            print(f"System Proxy: {proxy_settings['output'].strip()}")
        
        # Test each domain
        print(f"\n🌐 DOMAIN TESTS:")
        print("-" * 30)
        
        for domain in self.test_domains:
            print(f"\n🔍 Testing {domain}:")
            
            # DNS Tests
            dns_system = self.test_system_dns(domain)
            print(f"  DNS (System): {'✅' if dns_system['success'] else '❌'} {dns_system.get('ip', dns_system.get('error', ''))}")
            
            dns_local = self.test_direct_dns(domain, "127.0.0.1")
            if 'dns.resolver' in str(type(dns_local.get('error', ''))):
                print(f"  DNS (Local): ⚠️  Need 'pip install dnspython'")
            else:
                print(f"  DNS (Local): {'✅' if dns_local['success'] else '❌'} {dns_local.get('ips', dns_local.get('error', ''))}")
            
            nslookup_test = self.test_nslookup(domain)
            print(f"  nslookup: {'✅' if nslookup_test['success'] else '❌'}")
            
            # HTTP Tests
            http_direct = self.test_http_direct(domain)
            print(f"  HTTP (Direct): {'✅' if http_direct['success'] else '❌'} {http_direct.get('status_code', http_direct.get('error', ''))}")
            
            http_proxy = self.test_http_system_proxy(domain)
            print(f"  HTTP (Proxy): {'✅' if http_proxy['success'] else '❌'} {http_proxy.get('status_code', http_proxy.get('error', ''))}")
            
            # HTTPS Tests
            https_direct = self.test_https_direct(domain)
            print(f"  HTTPS (Direct): {'✅' if https_direct['success'] else '❌'} {https_direct.get('status_code', https_direct.get('error', ''))}")
            
            https_proxy = self.test_https_system_proxy(domain)
            print(f"  HTTPS (Proxy): {'✅' if https_proxy['success'] else '❌'} {https_proxy.get('status_code', https_proxy.get('error', ''))}")
    
    def run_quick_test(self):
        """Test nhanh chỉ một số điểm chính"""
        print("⚡ Quick Network Test")
        print("=" * 30)
        
        # Test infrastructure
        proxy_running = self.test_proxy_server_running()['success']
        dns_running = self.test_dns_server_running()['success']
        
        print(f"Proxy Server: {'✅ Running' if proxy_running else '❌ Not running'}")
        print(f"DNS Server: {'✅ Running' if dns_running else '❌ Not running'}")
        
        # Test one blocked domain
        test_domain = "facebook.com"
        dns_result = self.test_system_dns(test_domain)
        http_result = self.test_http_system_proxy(test_domain)
        
        print(f"\nTest {test_domain}:")
        print(f"  DNS: {'❌ Blocked' if not dns_result['success'] else '⚠️  Allowed'}")
        print(f"  HTTP: {'❌ Blocked' if not http_result['success'] else '⚠️  Allowed'}")
        
        if dns_result['success'] or http_result['success']:
            print("\n⚠️  WARNING: Blocking may not be working properly!")
        else:
            print("\n✅ Blocking appears to be working!")

def main():
    tester = NetworkTester()
    
    while True:
        print("\n" + "="*50)
        print("NETWORK TESTING TOOL")
        print("="*50)
        print("1. Quick Test")
        print("2. Comprehensive Test")
        print("3. Test Single Domain")
        print("4. Check System Settings")
        print("5. Exit")
        
        choice = input("\nChọn option (1-5): ").strip()
        
        if choice == "1":
            tester.run_quick_test()
            
        elif choice == "2":
            tester.run_comprehensive_test()
            
        elif choice == "3":
            domain = input("Nhập domain để test: ").strip()
            if domain:
                print(f"\n🔍 Testing {domain}:")
                dns_result = tester.test_system_dns(domain)
                http_result = tester.test_http_system_proxy(domain)
                print(f"DNS: {'✅' if dns_result['success'] else '❌'} {dns_result.get('ip', dns_result.get('error', ''))}")
                print(f"HTTP: {'✅' if http_result['success'] else '❌'} {http_result.get('status_code', http_result.get('error', ''))}")
                
        elif choice == "4":
            proxy_settings = tester.get_system_proxy_settings()
            print(f"\nProxy Settings:\n{proxy_settings.get('output', 'Error getting settings')}")
            
        elif choice == "5":
            print("👋 Goodbye!")
            break
            
        else:
            print("❌ Invalid choice!")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()