#!/usr/bin/env python3
"""
Summarise every results/*.jsonl file: accuracy (overall and by difficulty),
latency percentiles, cost, and calibration.

The calibration section is the load-bearing part. "Calibrated" means that among
predictions made at confidence p, about p of them are correct. The standard
summary statistic is Expected Calibration Error: bin predictions by confidence,
take |accuracy - mean confidence| in each bin, and average weighted by bin size.

ECE has a well-known failure mode that matters here: if every prediction lands in
one bin, ECE collapses to a single |accuracy - confidence| difference and tells
you almost nothing about the shape of the distribution. This script therefore
reports bin occupancy alongside ECE and refuses to print ECE alone.
"""
import glob, json, pathlib, statistics, sys

HERE = pathlib.Path(__file__).parent
# Published per-token prices, verified against each vendor's own pricing page/docs.
# jev: TypeSafe homepage, 2026-09-17, output tokens free ("too cheap to meter").
# claude-sonnet-5: Anthropic API pricing, cached 2026-06-24 (current as of this run).
PRICE_PER_MTOK = {
    "jev":       {"input": 0.042, "output": 0.0},
    "anthropic": {"input": 2.00,  "output": 10.00},
}


def pct(sorted_vals, q):
    if not sorted_vals:
        return float("nan")
    return sorted_vals[max(0, min(len(sorted_vals) - 1, int(len(sorted_vals) * q) - 1))]


def ece(rows, bins=10):
    """Expected Calibration Error plus the bin table it was computed from."""
    usable = [r for r in rows if isinstance(r.get("confidence"), (int, float))
              and r["confidence"] == r["confidence"]]
    if not usable:
        return None, []
    table = []
    total = len(usable)
    err = 0.0
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        sel = [r for r in usable
               if (r["confidence"] > lo or (i == 0 and r["confidence"] >= lo))
               and r["confidence"] <= hi]
        if not sel:
            continue
        acc = sum(r["correct"] for r in sel) / len(sel)
        conf = sum(r["confidence"] for r in sel) / len(sel)
        err += (len(sel) / total) * abs(acc - conf)
        table.append((f"{lo:.1f}-{hi:.1f}", len(sel), acc, conf))
    return err, table


def main():
    files = sorted(glob.glob(str(HERE / "results" / "*.jsonl")))
    if not files:
        sys.exit("no results/*.jsonl — run bench.py first")

    for f in files:
        rows = [json.loads(l) for l in open(f) if l.strip()]
        if not rows:
            continue
        name = f"{rows[0]['backend']}/{rows[0]['model']}"
        n = len(rows)
        lat = sorted(r["latency_ms"] for r in rows)
        acc = sum(r["correct"] for r in rows) / n

        print(f"\n{'=' * 66}\n{name}   n={n}\n{'=' * 66}")
        print(f"  accuracy        {acc:.1%}  ({sum(r['correct'] for r in rows)}/{n})")
        for d in ("clear", "ambiguous", "adversarial"):
            sel = [r for r in rows if r.get("difficulty") == d]
            if sel:
                print(f"    {d:<12}  {sum(r['correct'] for r in sel) / len(sel):.1%}"
                      f"  ({sum(r['correct'] for r in sel)}/{len(sel)})")
        print(f"  latency  p50 {statistics.median(lat):.1f}ms   p95 {pct(lat, .95):.1f}ms"
              f"   min {lat[0]:.1f}   max {lat[-1]:.1f}")

        tin = [r["usage"].get("input_tokens") for r in rows if r.get("usage")]
        tin = [t for t in tin if isinstance(t, int)]
        tout = [r["usage"].get("output_tokens") for r in rows if r.get("usage")]
        tout = [t for t in tout if isinstance(t, int)]
        if tin:
            price = PRICE_PER_MTOK.get(rows[0]["backend"])
            avg_in = statistics.mean(tin)
            avg_out = statistics.mean(tout) if tout else 0
            line = f"  tokens   mean input {avg_in:.0f}"
            if avg_out:
                line += f"  mean output {avg_out:.1f}"
            if price:
                cost = avg_in * price["input"] / 1e6 + avg_out * price["output"] / 1e6
                line += f"   ~${cost:.7f}/call (${price['input']}/${price['output']} per MTok in/out)"
            print(line)

        e, table = ece(rows)
        if e is None:
            print("  calibration     no usable confidence values")
            continue
        print(f"  calibration     ECE {e:.4f} over {len(table)} occupied bin(s)")
        for label, cnt, a, c in table:
            print(f"    conf {label}  n={cnt:<4} accuracy={a:.1%}  mean_conf={c:.3f}")
        if len(table) == 1:
            print("    ^ ALL predictions in ONE bin. ECE here is a single difference,")
            print("      not a calibration curve. Report the occupancy, not just the number.")

        conf_vals = [r["confidence"] for r in rows
                     if isinstance(r.get("confidence"), (int, float))]
        if conf_vals:
            at_one = sum(1 for c in conf_vals if c >= 0.9995)
            print(f"  confidence      exactly 1.000 on {at_one}/{len(conf_vals)}"
                  f" ({at_one / len(conf_vals):.0%}); median {statistics.median(conf_vals):.3f}")
            wrong = [r for r in rows if not r["correct"]
                     and isinstance(r.get("confidence"), (int, float))]
            if wrong:
                hi = sum(1 for r in wrong if r["confidence"] >= 0.9995)
                print(f"  WRONG AT conf=1.000: {hi}/{len(wrong)} of the misses"
                      f" — this is the number that decides whether 'calibrated' holds")


if __name__ == "__main__":
    main()
