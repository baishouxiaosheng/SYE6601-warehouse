"""可选：本机 HTTP 接口（SPEC §9）。只绑定 127.0.0.1。python -m user_sim.server --port 8765"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .generator import generate_question


class _Handler(BaseHTTPRequestHandler):
    def _json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/generate":
            self._json(404, {"error": "路径不存在"})
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16_384:
                raise ValueError
            params = json.loads(self.rfile.read(size).decode("utf-8"))
            if not isinstance(params, dict) or params.keys() - {"domain", "persona", "intent", "seed", "offline"}:
                raise ValueError
            record = generate_question(**params)
        except (ValueError, TypeError):
            self._json(400, {"error": "请求须为有效的生成参数 JSON 对象"})
            return
        self._json(200, record)

    def log_message(self, format, *args):
        # 请求路径可能包含调用方误填的凭据。
        pass


def _make_server(port):
    return ThreadingHTTPServer(("127.0.0.1", port), _Handler)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="本机用户问题生成服务")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    with _make_server(args.port) as server:
        print(f"用户模拟服务 http://127.0.0.1:{server.server_port}/generate", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
