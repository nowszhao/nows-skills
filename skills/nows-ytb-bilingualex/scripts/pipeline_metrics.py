#!/usr/bin/env python3
"""Record and report stage durations/retries in <workdir>/pipeline_metrics.json."""
import argparse
import json
import os
import time


def load(path):
    if not os.path.exists(path):
        return {"stages": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["start", "end", "retry", "report"])
    ap.add_argument("--stage")
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--status", default="ok")
    args = ap.parse_args()
    path = os.path.join(args.workdir, "pipeline_metrics.json")
    data = load(path)
    stages = data.setdefault("stages", {})
    if args.action != "report" and not args.stage:
        raise SystemExit("--stage is required for start/end/retry")
    if args.action == "start":
        stage = stages.setdefault(args.stage, {})
        stage["started_at_epoch"] = time.time()
        stage.setdefault("retries", 0)
    elif args.action == "retry":
        stage = stages.setdefault(args.stage, {})
        stage["retries"] = int(stage.get("retries", 0)) + 1
    elif args.action == "end":
        stage = stages.setdefault(args.stage, {})
        now = time.time()
        stage["ended_at_epoch"] = now
        stage["elapsed_seconds"] = round(now - stage.get("started_at_epoch", now), 3)
        stage["status"] = args.status
    else:
        total = 0.0
        for name, stage in stages.items():
            elapsed = float(stage.get("elapsed_seconds", 0))
            total += elapsed
            print(f"{name}: {elapsed:.1f}s, retries={stage.get('retries', 0)}, "
                  f"status={stage.get('status', 'running')}")
        print(f"total recorded: {total:.1f}s")
        return 0
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
