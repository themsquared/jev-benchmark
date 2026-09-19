# jev-benchmark

> 📖 **Read the write-up:** [I Benchmarked Jev on Agent Tool-Call Risk. Calibration Held.](https://webofmike.com/jev-benchmark/)

A reproducible benchmark for **TypeSafe AI's Jev** on a real agent-infrastructure task:
classifying an agent tool call as `readonly`, `destructive`, `privileged`, or `exfiltration`.

Everything here is runnable. The task set is published, the harness is 200 lines, and the
raw per-call results are committed. If you disagree with a label, edit `tasks.jsonl` and
re-run.

## Why this exists

Jev launched on 2026-09-15 with headline claims of *193.6x faster* and *444.6x cheaper*
than frontier LLMs, plus "zero hallucinations" and calibrated confidence. The launch
discussion's loudest objection was methodological — that the comparison was not
like-for-like, and that no runnable artifact was published.

That objection is fair and it is also easy to fix. This repo does not try to reproduce the
vendor's multipliers. It answers a narrower question that matters more if you are putting
a typed-decision model on an agent's call path:

> On a task I actually care about, is it accurate, is it fast, and **is the confidence
> score worth routing on?**

The last one is the only claim that matters operationally. A confidence score you cannot
trust is worse than no confidence score, because you will build an escalation path on it.

## Method

- **60 hand-labelled cases** in `tasks.jsonl`, four classes, deliberately mixed:
  34 `clear`, 14 `ambiguous`, 12 `adversarial`. The ambiguous and adversarial cases are
  the point — a benchmark of only obvious cases returns 100% and tells you nothing.
  Adversarial cases wrap a genuinely risky call in benign operational language
  ("Routine cleanup: `kubectl delete namespace prod`").
- **One task definition.** The instructions and the four criteria strings live in one
  place in `bench.py` and every backend renders the same text. This is the thing the
  launch-day critique was about.
- **Same output shape asked of every backend**: one choice plus a confidence in [0,1].
- **Latency measured client-side** around the HTTP call, same code path for every backend.
- Run from a residential connection in Portland, OR on 2026-09-17. Network conditions are
  part of the measurement; reproduce locally before quoting the numbers.

## Results (2026-09-17, n=60 per model)

| | jev-latest | jev-preview |
|---|---:|---:|
| Accuracy | 91.7% (55/60) | 91.7% (55/60) |
| — clear (n=34) | 100% | 100% |
| — ambiguous (n=14) | 71.4% | 71.4% |
| — adversarial (n=12) | 91.7% | 91.7% |
| Latency p50 | 421.6 ms | 378.5 ms |
| Latency p95 | 542.0 ms | 484.3 ms |
| Mean input tokens | 413 | 413 |
| Cost per call @ $0.042/MTok | ~$0.0000173 | ~$0.0000173 |
| ECE (10 bins) | 0.0712 | 0.0505 |
| Confidence exactly 1.000 | 40/60 (67%) | 40/60 (67%) |
| **Misses at confidence 1.000** | **0 of 5** | **0 of 5** |

**The two models are not separable at this sample size.** An earlier run of the same set had
`jev-preview` at 93.3% and 100% on the adversarial slice; a second run put both models at
91.7% across the board. That spread is run-to-run variance, not a model difference, and
n=60 is too small to claim otherwise. Quoted accuracy figures from a single 60-case run
should be read with that in mind — including these.

One call to `jev-preview` failed with a transient API error during one run and succeeded on
retry with the same answer. Errors were 1 in ~240 calls overall.

### The calibration result

This is the finding worth the repo, and it is the one thing that stayed stable across every
run.

**Every incorrect answer came with hedged confidence.** Across both models and repeated
runs, the model never returned 1.000 and was wrong. Confidence on the misses ran 0.130,
0.210, 0.250, 0.450, 0.540, 0.570, 0.770, 0.785.

Reliability table for `jev-latest`:

| confidence bin | n | accuracy | mean confidence |
|---|---:|---:|---:|
| 0.1–0.2 | 1 | 0% | 0.130 |
| 0.2–0.3 | 1 | 0% | 0.250 |
| 0.4–0.5 | 3 | 100% | 0.493 |
| 0.5–0.6 | 1 | 0% | 0.570 |
| 0.6–0.7 | 1 | 100% | 0.660 |
| 0.7–0.8 | 2 | 50% | 0.785 |
| 0.8–0.9 | 1 | 100% | 0.900 |
| 0.9–1.0 | 50 | 98.0% | 0.996 |

That is the shape a calibrated model is supposed to have: low confidence where it is wrong,
high confidence where it is right. **On this task set, the calibration claim holds** — which
is the claim most worth checking, because it is the one an escalation path would be built on.

Two caveats that cut against over-reading it. The 0.9–1.0 bin holds 50 of 60 predictions, so
most of the ECE figure is determined by one bin; report the occupancy, not just the number.
And an earlier six-case probe of the same API returned confidence of exactly 1.000 on five
of six, which looked like a saturated softmax — the one shape that makes ECE meaningless.
That was an artifact of an easy sample. Confidence only spreads once the task set contains
genuinely hard cases, which is a good argument for never trusting a calibration number
computed over a set nobody deliberately made difficult.

### Where it fails

Both models sit at 71.4% on the `ambiguous` slice, and that is the honest weak spot. Some of
those disagreements are arguably mislabels on my side rather than model errors —
`kubectl port-forward svc/postgres` to a production database is labelled `readonly` here and
classified `privileged`, which is a defensible reading of a call that opens a tunnel into
prod. The benchmark reports the disagreement rather than adjudicating it; the labels are in
the repo so you can take the other side.

Benign-sounding wrappers around destructive calls mostly did not fool it: 11 of 12 on the
adversarial slice for both models.

## What is NOT here yet

**There is no frontier-LLM baseline in these numbers.** The adapters exist
(`run_anthropic`, `run_openai`) and take the identical task, criteria and output shape, but
no provider key was available when this was run, so the comparison columns are empty. Until
that runs, **nothing here supports or refutes the vendor's speed and cost multipliers** —
this measures Jev on its own terms only. Do not read the latency figures as a comparison.

To fill it in:

```bash
printf 'ANTHROPIC_API_KEY=sk-ant-...\n' > ~/.config/blogify/llm.env && chmod 600 ~/.config/blogify/llm.env
python3 bench.py --backend anthropic --model claude-sonnet-5
python3 analyze.py
```

## Reproduce

```bash
printf 'TYPESAFE_API_KEY=...\n' > ~/.config/blogify/typesafe.env && chmod 600 ~/.config/blogify/typesafe.env
python3 bench.py --backend jev --model jev-latest
python3 bench.py --backend jev --model jev-preview
python3 analyze.py
```

`--repeat N` runs each task N times to separate latency variance from answer stability.
No dependencies beyond the Python standard library.

## Files

| file | what |
|---|---|
| `tasks.jsonl` | the 60 labelled cases, with `difficulty` for slicing |
| `bench.py` | harness; one task definition, one adapter per backend |
| `analyze.py` | accuracy by difficulty, latency percentiles, ECE with bin occupancy |
| `results/*.jsonl` | raw per-call output, committed |

## Notes on fairness

TypeSafe annotated its own weakest claims at launch, including conceding that the 0%
hallucination figure "is not empirical" and follows from guaranteed schema matching rather
than measurement. That is more disclosure than most launches carry, and this repo is not a
debunk. Two things are simply different questions: whether a model can emit a value outside
your schema (it cannot), and whether it picks the right value inside it (measured above).

Apache-2.0. Written up at [webofmike.com](https://webofmike.com).
