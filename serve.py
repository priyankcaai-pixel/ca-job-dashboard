from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock

from jobs import ROOT, refresh


class PortalHandler(SimpleHTTPRequestHandler):
    refresh_lock = Lock()

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_POST(self):
        if self.path != "/refresh":
            self.send_error(404)
            return
        if self.headers.get("Host") != "127.0.0.1:8765" or self.headers.get("Origin") != "http://127.0.0.1:8765":
            self.send_error(403)
            return
        if not self.refresh_lock.acquire(blocking=False):
            self.send_error(409, "Refresh already running")
            return
        try:
            refresh()
            self.send_response(204)
            self.end_headers()
        except Exception as exc:
            print(f"Refresh failed: {type(exc).__name__}", flush=True)
            self.send_error(500, "Refresh failed")
        finally:
            self.refresh_lock.release()


if __name__ == "__main__":
    handler = partial(PortalHandler, directory=ROOT / "site")
    with ThreadingHTTPServer(("127.0.0.1", 8765), handler) as server:
        print("CA Job Dashboard at http://127.0.0.1:8765/", flush=True)
        server.serve_forever()
