#!/usr/bin/env python3
"""Change only draft precision in an isolated worker's runtime configuration."""
import argparse
import hashlib
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("quant", choices=("Q4_0", "Q8_0"))
    parser.add_argument("--runtime", type=Path, default=Path("/workspace/qwen38/runtime.env"))
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()
    data = args.runtime.read_text()
    lines = data.splitlines(keepends=True)
    indexes = [index for index, line in enumerate(lines) if line.startswith("QWEN38_DRAFT_QUANT=")]
    if len(indexes) != 1:
        raise ValueError("runtime must contain one draft precision setting")
    model = args.runtime.parent / "models" / f"Qwen3.8-27B-DFlash2-{args.quant}.gguf"
    if not model.is_file() or model.stat().st_size == 0:
        raise ValueError("requested draft file is missing")
    lines[indexes[0]] = f"QWEN38_DRAFT_QUANT={args.quant}\n"
    temporary = args.runtime.with_suffix(".env.precision-tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write("".join(lines))
    os.replace(temporary, args.runtime)
    print(f"Draft precision: {args.quant}; runtime SHA256: {hashlib.sha256(args.runtime.read_bytes()).hexdigest()}")
    if args.restart:
        subprocess.run(["supervisorctl", "restart", "qwen38-cloud"], check=True, timeout=30)
        request = urllib.request.Request("http://127.0.0.1:17070/health", headers={
            "Authorization": "Bearer " + (args.runtime.parent / "api_key").read_text().strip()})
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(request, timeout=2) as response:
                    if response.status == 200:
                        print("Model ready")
                        return
            except (urllib.error.URLError, OSError):
                time.sleep(1)
        raise RuntimeError("Model did not become ready after draft change")


if __name__ == "__main__":
    main()
