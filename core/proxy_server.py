from proxy.http.proxy import HttpProxyPlugin
from proxy.http.parser import HttpParser
from proxy import main

with open("config/whitelist.txt") as f:
    WHITELIST = [line.strip().lower() for line in f if line.strip()]

class WhitelistPlugin(HttpProxyPlugin):
    def before_upstream_connection(self, request: HttpParser):
        host = request.host.decode("utf-8").lower() if request.host else ""
        if not any(allowed in host for allowed in WHITELIST):
            raise Exception(f"Blocked by whitelist: {host}")
        return request

def start_proxy():
    main([
        "--hostname", "127.0.0.1",
        "--port", "8899",
        "--plugins", __name__ + ".WhitelistPlugin"
    ])
