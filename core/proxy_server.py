from proxy.http.proxy import HttpProxyPlugin
from proxy.http.parser import HttpParser
from proxy import main as proxy_main # Import the correct main function
import sys

with open("config/whitelist.txt") as f:
    WHITELIST = [line.strip().lower() for line in f if line.strip()]

class WhitelistPlugin(HttpProxyPlugin):
    def before_upstream_connection(self, request: HttpParser):
        host = request.host.decode("utf-8").lower() if request.host else ""
        if not any(allowed in host for allowed in WHITELIST):
            raise Exception(f"Blocked by whitelist: {host}")
        return request

def start_proxy():
    # Store original argv
    original_argv = sys.argv
    try:
        # Set sys.argv to simulate command line arguments
        sys.argv = [
            "proxy_server.py", # First argument is usually the script name
            "--hostname", "127.0.0.1",
            "--port", "8899",
            "--plugins", __name__ + ".WhitelistPlugin"
        ]
        proxy_main() # Call the correct main function
    finally:
        # Restore original argv
        sys.argv = original_argv
