#!/usr/bin/env python3
"""
本地文件服务 —— 用于绕过内置浏览器不支持文件选择器的限制。

原理：在页面里 fetch 本机文件，构造 File 对象注入 input[type=file]。

⚠️ 必须返回 Access-Control-Allow-Origin: *
   HTTPS 页面 fetch http://127.0.0.1 时，混合内容在 Chrome 里是允许的，
   但 CORS 仍然强制 —— 没有 ACAO 头会直接抛 TypeError: Failed to fetch。

用法：
    python3 cors-upload-server.py                      # 默认 8731 端口，服务 /tmp
    python3 cors-upload-server.py --port 9000 --dir ~/resumes
    curl -sI http://127.0.0.1:8731/resume.pdf | grep -i access-control

页面侧注入代码：
    const res  = await fetch('http://127.0.0.1:8731/resume.pdf');
    const buf  = await res.arrayBuffer();
    const file = new File([buf], 'resume.pdf', { type: 'application/pdf' });
    const dt = new DataTransfer();
    dt.items.add(file);
    const input = document.querySelector('input[type=file]');
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));

用完记得关掉：Ctrl-C（别让一个开放的本地 HTTP 服务一直挂着）
"""
import argparse
import functools
import http.server


class CORSHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self):          # 预检请求
        self.send_response(204)
        self.end_headers()

    def log_message(self, *args):  # 静音
        pass


def main():
    ap = argparse.ArgumentParser(description="带 CORS 头的本地文件服务")
    ap.add_argument("--port", type=int, default=8731)
    ap.add_argument("--dir", default="/tmp", help="要服务的目录")
    ap.add_argument("--bind", default="127.0.0.1")
    args = ap.parse_args()

    handler = functools.partial(CORSHandler, directory=args.dir)
    with http.server.ThreadingHTTPServer((args.bind, args.port), handler) as httpd:
        print(f"serving {args.dir} at http://{args.bind}:{args.port}/  (Ctrl-C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")


if __name__ == "__main__":
    main()
