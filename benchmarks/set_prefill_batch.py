#!/usr/bin/env python3
"""Set one bounded prefill-batch experiment on an isolated worker."""
import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ubatch", type=int, choices=(2048, 4096))
    parser.add_argument("--runtime", type=Path, default=Path("/workspace/qwen38/runtime.env"))
    args = parser.parse_args()
    lines = args.runtime.read_text().splitlines(keepends=True)
    for name, value in {"QWEN38_BATCH_SIZE": args.ubatch * 4, "QWEN38_UBATCH_SIZE": args.ubatch}.items():
        indexes = [i for i, line in enumerate(lines) if line.startswith(name + "=")]
        if len(indexes) != 1:
            raise ValueError("runtime must contain exactly one " + name)
        lines[indexes[0]] = f"{name}={value}\n"
    temporary = args.runtime.with_suffix(".env.prefill-tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        handle.write("".join(lines))
    os.replace(temporary, args.runtime)
    print(f"Prefill batch={args.ubatch * 4}, ubatch={args.ubatch}")


if __name__ == "__main__":
    main()
