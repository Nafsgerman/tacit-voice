#!/usr/bin/env python3
"""Print p50/p95 latency percentiles from metrics/turns.jsonl, grouped by run label."""

import json
import pathlib
import sys
from collections import defaultdict

METRICS_FILE = pathlib.Path("metrics/turns.jsonl")

LATENCY_FIELDS = [
    "end_of_utterance_delay_s",
    "transcription_delay_s",
    "llm_ttft_s",
    "tts_ttfb_s",
    "e2e_latency_s",
]

FIELD_LABELS = {
    "end_of_utterance_delay_s": "EOU delay",
    "transcription_delay_s": "STT / transcription delay",
    "llm_ttft_s": "LLM time-to-first-token",
    "tts_ttfb_s": "TTS time-to-first-byte",
    "e2e_latency_s": "Total response latency",
}


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return float("nan")
    sv = sorted(values)
    idx = (p / 100) * (len(sv) - 1)
    lo = int(idx)
    hi = lo + 1
    frac = idx - lo
    if hi >= len(sv):
        return sv[-1]
    return sv[lo] + frac * (sv[hi] - sv[lo])


def main() -> None:
    if not METRICS_FILE.exists():
        print(f"No metrics file at {METRICS_FILE}", file=sys.stderr)
        sys.exit(1)

    # label -> field -> [values in seconds]
    by_label: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    with METRICS_FILE.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            label = rec.get("run_label", "?")
            for field in LATENCY_FIELDS:
                val = rec.get(field)
                if val is not None:
                    by_label[label][field].append(float(val))

    if not by_label:
        print("No data found in metrics file.")
        return

    for label in sorted(by_label):
        # Collect model names seen for this label
        models: dict[str, set[str]] = defaultdict(set)
        with METRICS_FILE.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec.get("run_label") != label:
                    continue
                for key in ("stt_model", "llm_model", "tts_model"):
                    val = rec.get(key)
                    if val:
                        models[key].add(val)

        print(f"\n{'=' * 62}")
        print(f" Run label : {label}")
        for key, name in [
            ("stt_model", "STT"),
            ("llm_model", "LLM"),
            ("tts_model", "TTS"),
        ]:
            names = ", ".join(sorted(models[key])) or "unknown"
            print(f" {name:<4}       : {names}")
        print(f"{'=' * 62}")
        print(f"  {'Metric':<30}  {'n':>5}  {'p50 ms':>8}  {'p95 ms':>8}")
        print(f"  {'-' * 30}  {'-' * 5}  {'-' * 8}  {'-' * 8}")
        for field in LATENCY_FIELDS:
            vals = by_label[label][field]
            if not vals:
                print(f"  {FIELD_LABELS[field]:<30}  {'—':>5}  {'—':>8}  {'—':>8}")
                continue
            p50_ms = _percentile(vals, 50) * 1000
            p95_ms = _percentile(vals, 95) * 1000
            print(
                f"  {FIELD_LABELS[field]:<30}  {len(vals):>5}  {p50_ms:>8.1f}  {p95_ms:>8.1f}"
            )
    print()


if __name__ == "__main__":
    main()
