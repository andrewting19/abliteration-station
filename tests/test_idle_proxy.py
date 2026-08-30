from __future__ import annotations

import concurrent.futures
import json
import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).parents[1]
PROXY = ROOT / "scripts" / "idle-proxy.mjs"
SERVICE = ROOT / "scripts" / "abliteration-station-proxy.service"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class UpstreamHandler(BaseHTTPRequestHandler):
    cancelled = threading.Event()

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        self.rfile.read(length)
        body = b'{"ok":true}'
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path != "/slow":
            self.send_error(404)
            return
        self.connection.settimeout(3)
        try:
            while self.connection.recv(1):
                pass
        except (ConnectionError, OSError):
            pass
        finally:
            type(self).cancelled.set()

    def log_message(self, _format: str, *_args: object) -> None:
        return


@unittest.skipUnless(shutil.which("node"), "Node.js is required")
class IdleProxyTest(unittest.TestCase):
    def test_service_has_writable_temporary_directory(self) -> None:
        unit = SERVICE.read_text(encoding="utf-8")
        self.assertIn("Environment=TMPDIR=/run/abliteration-station", unit)
        self.assertIn("RuntimeDirectory=abliteration-station", unit)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.proxy_port = free_port()
        self.upstream = ThreadingHTTPServer(("127.0.0.1", 0), UpstreamHandler)
        self.upstream_thread = threading.Thread(target=self.upstream.serve_forever, daemon=True)
        self.upstream_thread.start()
        self.process: subprocess.Popen[str] | None = None

    def tearDown(self) -> None:
        if self.process is not None:
            self.process.terminate()
            self.process.wait(timeout=5)
        self.upstream.shutdown()
        self.upstream.server_close()
        self.temp.cleanup()

    def start_proxy(self, ensure_exit: int = 0, *, idle_seconds: int = 60) -> tuple[Path, Path]:
        route = self.root / "route.json"
        count = self.root / "ensure-count"
        ensure = self.root / "ensure"
        ensure.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f"printf x >>'{count}'\n"
            "sleep 0.4\n"
            + (
                f"printf '%s\\n' '{{\"provider\":\"fake\",\"upstream\":\"http://127.0.0.1:{self.upstream.server_port}\",\"identity\":{{}}}}' >'{route}'\n"
                if ensure_exit == 0
                else f"exit {ensure_exit}\n"
            ),
            encoding="utf-8",
        )
        ensure.chmod(0o700)
        stop = self.root / "stop"
        stop_count = self.root / "stop-count"
        stop.write_text(f"#!/usr/bin/env bash\nprintf x >>'{stop_count}'\n", encoding="utf-8")
        stop.chmod(0o700)
        environment = os.environ.copy()
        environment.update(
            {
                "ABLITERATION_STATION_PROXY_HOST": "127.0.0.1",
                "ABLITERATION_STATION_PROXY_PORT": str(self.proxy_port),
                "ABLITERATION_STATION_IDLE_SECONDS": str(idle_seconds),
                "ABLITERATION_STATION_IDLE_POLL_MS": "100",
                "ABLITERATION_STATION_TEST_MODE": "1",
                "ABLITERATION_STATION_ROUTE_FILE": str(route),
                "ABLITERATION_STATION_ACTIVITY_FILE": str(self.root / "activity.json"),
                "ABLITERATION_STATION_ENSURE_COMMAND": str(ensure),
                "ABLITERATION_STATION_STOP_COMMAND": str(stop),
                "ABLITERATION_STATION_CONFIG": str(self.root / "config.json"),
                "ABLITERATION_STATION_METRICS_FILE": str(self.root / "metrics.jsonl"),
            }
        )
        self.process = subprocess.Popen(
            [shutil.which("node") or "node", str(PROXY)],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{self.proxy_port}/healthz", timeout=0.2)
                return count, stop_count
            except Exception:
                time.sleep(0.05)
        self.fail("proxy did not become ready")

    def request(self) -> dict:
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.proxy_port}/v1/chat/completions",
            data=b'{"model":"qwen38-cloud"}',
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_concurrent_requests_share_one_wake(self) -> None:
        count, _stop_count = self.start_proxy()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _index: self.request(), range(2)))
        self.assertEqual(results, [{"ok": True}, {"ok": True}])
        self.assertEqual(count.read_text(encoding="utf-8"), "x")

    def test_wake_failure_is_clear_and_does_not_forward(self) -> None:
        self.start_proxy(ensure_exit=7)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request()
        self.assertEqual(caught.exception.code, 503)
        body = json.loads(caught.exception.read())
        self.assertIn("model wake failed", body["error"]["message"])

    def test_metrics_record_timing_without_request_or_response_content(self) -> None:
        self.start_proxy()
        self.assertEqual(self.request(), {"ok": True})
        metrics = self.root / "metrics.jsonl"
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and not metrics.exists():
            time.sleep(0.01)
        record = json.loads(metrics.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(record["endpoint"], "/v1/chat/completions")
        self.assertEqual(record["status"], 200)
        self.assertGreater(record["total_seconds"], 0)
        self.assertGreater(record["response_bytes"], 0)
        serialized = json.dumps(record)
        self.assertNotIn("qwen38-cloud", serialized)
        self.assertNotIn("ok", serialized)

    def test_idle_route_is_stopped_once(self) -> None:
        _count, stop_count = self.start_proxy(idle_seconds=1)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not stop_count.exists():
            time.sleep(0.05)
        self.assertTrue(stop_count.exists())
        time.sleep(0.4)
        self.assertEqual(stop_count.read_text(encoding="utf-8"), "x")

    def test_client_cancellation_closes_upstream(self) -> None:
        route = self.root / "route.json"
        route.write_text(
            json.dumps({"provider": "fake", "upstream": f"http://127.0.0.1:{self.upstream.server_port}", "identity": {}}),
            encoding="utf-8",
        )
        self.start_proxy()
        UpstreamHandler.cancelled.clear()
        sock = socket.create_connection(("127.0.0.1", self.proxy_port), timeout=2)
        sock.sendall(b"GET /slow HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\n\r\n")
        sock.close()
        self.assertTrue(UpstreamHandler.cancelled.wait(3))


if __name__ == "__main__":
    unittest.main()
