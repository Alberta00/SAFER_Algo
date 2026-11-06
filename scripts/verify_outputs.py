"""Compare measured artifacts from two runs, excluding only wall-clock metadata."""

import argparse
import hashlib
from pathlib import Path

ARTIFACTS = (
    "metrics.json",
    "trace.json",
    "series.json",
    "messages.csv",
    "attempts.csv",
    "backlog.csv",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    args = parser.parse_args()
    for name in ARTIFACTS:
        first = (args.first / name).read_bytes()
        second = (args.second / name).read_bytes()
        if first != second:
            raise SystemExit(f"Mismatch: {name}")
        print(f"identical {name}: sha256={hashlib.sha256(first).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
