#!/usr/bin/env python3
"""Create a balanced, deterministic three-worker assignment for model chunks."""
import argparse
import json
import os
import re


def numeric_key(path: str) -> int:
    m = re.search(r"_(\d+)\.txt$", path)
    return int(m.group(1)) if m else 10**9


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workdir", default=".")
    ap.add_argument("--stage", required=True, choices=["refine", "translate"])
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")

    subdir = "refine_parts" if args.stage == "refine" else "parts"
    manifest_path = os.path.join(
        args.workdir,
        "refine_plan.json" if args.stage == "refine" else "parts/manifest.json",
    )
    if not os.path.exists(manifest_path):
        raise SystemExit(f"manifest not found: {manifest_path}")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    files = [os.path.join(args.workdir, subdir, item["file"])
             for item in manifest.get("parts", [])]
    missing = [path for path in files if not os.path.exists(path)]
    if missing:
        raise SystemExit(f"manifest references missing chunks: {missing}")
    if not files:
        raise SystemExit(f"no {args.stage} chunks listed in {manifest_path}")

    worker_count = min(args.workers, len(files))
    queues = [[] for _ in range(worker_count)]
    loads = [0] * worker_count
    sized = []
    for path in files:
        text = open(path, encoding="utf-8").read()
        weight = len(re.findall(r"\b[\w']+\b", text))
        sized.append((path, weight))
    # Keep assignments contiguous so each long-lived worker retains local topic
    # and terminology continuity. Word-budget chunking already makes weights
    # similar; choose each boundary near the remaining average load.
    sized.sort(key=lambda x: numeric_key(x[0]))
    cursor = 0
    for worker in range(worker_count):
        remaining_workers = worker_count - worker
        remaining_items = len(sized) - cursor
        if remaining_workers == 1:
            take = remaining_items
        else:
            target = sum(w for _, w in sized[cursor:]) / remaining_workers
            take, running = 0, 0
            max_take = remaining_items - (remaining_workers - 1)
            while take < max_take:
                next_weight = sized[cursor + take][1]
                if take > 0 and abs(running - target) <= abs(running + next_weight - target):
                    break
                running += next_weight
                take += 1
            take = max(1, take)
        for path, weight in sized[cursor:cursor + take]:
            queues[worker].append({"file": os.path.abspath(path), "weight": weight})
            loads[worker] += weight
        cursor += take

    plan = {
        "stage": args.stage,
        "workers": worker_count,
        "assignments": [
            {"worker": i + 1, "estimated_words": loads[i], "chunks": queues[i]}
            for i in range(worker_count)
        ],
    }
    out = os.path.join(args.workdir, f"{args.stage}_worker_plan.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    for item in plan["assignments"]:
        names = ", ".join(os.path.basename(x["file"]) for x in item["chunks"])
        print(f"worker {item['worker']}: {item['estimated_words']} est. words — {names}")
    print(f"plan: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
