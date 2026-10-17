"""Pushes tracker updates to open web pages over Server-Sent Events.

Runs inside the tracker process on a background thread; nginx proxies /events to it.
New subscribers immediately get the latest message of each event type.
"""

import json
import logging
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KEEPALIVE_S = 15

log = logging.getLogger("live")


class Hub:
    def __init__(self):
        self._lock = threading.Lock()
        self._clients = set()
        self._latest = {}

    def publish(self, event, data):
        msg = f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()
        with self._lock:
            self._latest[event] = msg
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait(msg)
            except queue.Full:  # a stalled client misses updates rather than blocking the tracker
                pass

    def subscribe(self):
        q = queue.Queue(maxsize=64)
        with self._lock:
            self._clients.add(q)
            for msg in self._latest.values():
                q.put_nowait(msg)
        return q

    def unsubscribe(self, q):
        with self._lock:
            self._clients.discard(q)


def serve(hub, port):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.split("?")[0] != "/events":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            q = hub.subscribe()
            try:
                self.wfile.write(b"retry: 3000\n\n")
                while True:
                    try:
                        msg = q.get(timeout=KEEPALIVE_S)
                    except queue.Empty:
                        msg = b": keepalive\n\n"
                    self.wfile.write(msg)
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            finally:
                hub.unsubscribe(q)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, name="live", daemon=True).start()
    log.info("live updates on 127.0.0.1:%d/events", port)
