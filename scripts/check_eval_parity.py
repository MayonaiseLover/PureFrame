#!/usr/bin/env python3
"""Gate detection-quality parity against a committed baseline.

Compares the aggregate precision/recall/F1 of a fresh `pureframe evaluate`
report against `eval-baseline.json`. A change that shifts any metric more
than TOLERANCE fails — this is how performance PRs prove they did not trade
accuracy for speed.

Bootstrap mode: if the baseline file is missing, the check passes with a
warning and instructions (a maintainer then commits the generated report as
the new baseline).
"""

import json
import sys
from pathlib import Path

TOLERANCE = 0.02
METRICS = ("precision", "recall", "f1_score")


def load_aggregates(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    agg = data["aggregate_metrics"]
    return {m: float(agg[m]) for m in METRICS}


def main() -> int:
    baseline_path = Path("eval-baseline.json")
    report_path = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path("evaluation_report.json")
    )

    if not report_path.exists():
        print(f"FAIL: evaluation report not found at {report_path}", file=sys.stderr)
        print("Run: pureframe evaluate --output " + str(report_path), file=sys.stderr)
        return 1

    if not baseline_path.exists():
        print(
            "WARNING: eval-baseline.json not found — parity check skipped "
            "(bootstrap mode).\n"
            "To create the baseline, commit the freshly generated report:\n"
            f"  cp {report_path} {baseline_path}",
            file=sys.stderr,
        )
        return 0

    baseline = load_aggregates(baseline_path)
    current = load_aggregates(report_path)

    failed = False
    for metric in METRICS:
        delta = current[metric] - baseline[metric]
        status = "ok"
        if abs(delta) > TOLERANCE:
            status = f"FAIL (drift {delta:+.4f} exceeds ±{TOLERANCE})"
            failed = True
        print(
            f"{metric:>10}: baseline {baseline[metric]:.4f} -> "
            f"current {current[metric]:.4f} [{status}]"
        )

    if failed:
        print(
            "\nDetection quality drifted beyond tolerance. If the change is "
            "intentional, regenerate and commit the baseline with:\n"
            f"  pureframe evaluate --output {baseline_path}",
            file=sys.stderr,
        )
        return 1
    print("\nEval parity: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
