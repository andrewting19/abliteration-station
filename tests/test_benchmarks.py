from __future__ import annotations

import importlib.util
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MEASURE = load("measure_openai", ROOT / "benchmarks" / "measure_openai.py")
ANALYZE = load("analyze_results", ROOT / "benchmarks" / "analyze_results.py")
PROXY_SUMMARY = load("summarize_proxy_metrics", ROOT / "benchmarks" / "summarize_proxy_metrics.py")


class StreamHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        events = [
            {"choices": [{"delta": {"reasoning_content": "The sum is "}}]},
            {"choices": [{"delta": {"content": "110"}}]},
            {
                "choices": [],
                "usage": {"prompt_tokens": 20, "completion_tokens": 10},
                "timings": {
                    "prompt_per_second": 1000.0,
                    "predicted_per_second": 100.0,
                    "draft_n": 20,
                    "draft_n_accepted": 15,
                },
            },
        ]
        body = b"".join(f"data: {json.dumps(event)}\n\n".encode() for event in events) + b"data: [DONE]\n\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class BenchmarkTest(unittest.TestCase):
    def test_measurement_captures_speed_cost_quality_and_acceptance(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), StreamHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        manifest = {
            "experiment_id": "test",
            "variant": "baseline",
            "workload_class": "novel-agentic",
            "hourly_compute_usd": 0.36,
            "request": {"model": "test", "messages": [], "stream": True},
            "quality": {"required_substrings": ["110"], "minimum_output_chars": 3},
        }
        try:
            result = MEASURE.run(manifest, f"http://127.0.0.1:{server.server_port}", "test-key")
        finally:
            server.shutdown()
            server.server_close()
        self.assertTrue(result["success"])
        self.assertTrue(result["quality_pass"])
        self.assertEqual(result["tokens"]["prompt"], 20)
        self.assertEqual(result["latency"]["decode_tokens_per_second"], 100.0)
        self.assertEqual(result["tokens"]["acceptance_rate"], 0.75)
        self.assertGreater(result["cost"]["turn_compute_usd"], 0)

    def test_summary_uses_token_weighted_decode_and_quality_pareto(self) -> None:
        records = []
        for variant, rate, hourly in (("fast", 100.0, 0.4), ("cheap", 80.0, 0.2)):
            records.append({
                "variant": variant,
                "workload_class": "novel-agentic",
                "success": True,
                "quality_pass": True,
                "latency": {"total_seconds": 10.0, "time_to_first_token_seconds": 1.0, "decode_tokens_per_second": rate},
                "tokens": {"completion": 100},
                "cost": {"turn_compute_usd": hourly * 10 / 3600},
            })
        summaries = ANALYZE.summarize(records)
        self.assertEqual(len(summaries), 2)
        self.assertEqual(
            set(ANALYZE.pareto(summaries)),
            {"fast:novel-agentic", "cheap:novel-agentic"},
        )

    def test_proxy_summary_uses_server_token_weights(self) -> None:
        records = [{
            "status": 200,
            "error": None,
            "cancelled": False,
            "wake_required": True,
            "wake_seconds": 40.0,
            "first_response_byte_seconds": 41.0,
            "total_seconds": 50.0,
            "usage": {"completion_tokens": 100},
            "timings": {"prompt_n": 1000, "prompt_per_second": 500, "predicted_n": 100, "predicted_per_second": 100},
        }]
        summary = PROXY_SUMMARY.summarize(records, 0.36)
        self.assertEqual(summary["decode_tps_token_weighted"], 100)
        self.assertEqual(summary["wake_seconds_median"], 40)
        self.assertGreater(summary["measured_request_compute_usd"], 0)


if __name__ == "__main__":
    unittest.main()
