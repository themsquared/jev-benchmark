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

That objection is fair and it is also easy to fix. This repo puts a real frontier LLM
(Claude Sonnet 5) through the identical task, criteria, and output shape, and answers
three questions:

> On a task I actually care about: is Jev accurate, is it fast and cheap relative to a
> frontier LLM doing the same job, and **is the confidence score worth routing on?**

The last one is the claim that matters operationally. A confidence score you cannot
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

## Results (2026-09-17 / 2026-09-24, n=60 per backend)

| | jev-latest | jev-preview | claude-sonnet-5 |
|---|---:|---:|---:|
| Accuracy | 91.7% (55/60) | 91.7% (55/60) | **91.7% (55/60)** |
| — clear (n=34) | 100% | 100% | 100% |
| — ambiguous (n=14) | 71.4% | 71.4% | 71.4% |
| — adversarial (n=12) | 91.7% | 91.7% | 91.7% |
| Latency p50 | 421.6 ms | 378.5 ms | **1371.0 ms** |
| Latency p95 | 542.0 ms | 484.3 ms | 2719.1 ms |
| Mean input / output tokens | 413 / 53.6 | 413 / 53.6 | 240 / 22.4 |
| Cost per call | ~$0.0000173 | ~$0.0000173 | ~$0.0007035 |
| ECE (10 bins) | 0.0712 | 0.0505 | 0.0633 |
| Confidence exactly 1.000 | 40/60 (67%) | 40/60 (67%) | **0/60 (0%)** |
| Misses at confidence 1.000 | 0 of 5 | 0 of 5 | 0 of 5 |

**The headline result: all three tied on accuracy, exactly.** 55/60 on every backend, and
the same 100% / 71.4% / 91.7% split by difficulty on all three — the task's difficulty
determined the outcome, not which model answered it. That is a striking result on its own:
a narrow, structured decision does not obviously need a frontier LLM at all.

**Measured speed and cost, against the claimed 193.6x / 444.6x:**

- **Latency: Jev is 3.25x–3.62x faster** than Claude Sonnet 5 on this task (421.6ms /
  378.5ms vs 1371.0ms, all p50). Real, worth having, and roughly **50x smaller** than the
  vendor's 193.6x claim.
- **Cost: Jev is ~40.6x cheaper** per call (~$0.0000173 vs ~$0.0007035, at Anthropic's
  published $2/$10 per-MTok in/out rate and TypeSafe's published $0.042/MTok input, free
  output). About **11x smaller** than the vendor's 444.6x claim.

Both multipliers are real and both are far short of the launch numbers. The likely
reconciliation, not verified here: the vendor's figures are described as "based on
workflows for System One tasks," which may compare a multi-step agentic pipeline against
a single classification call, not the one-shot comparison this repo runs. That is a
different, harder-to-reproduce measurement — this repo measures the one-shot case,
states the multiplier plainly, and does not extrapolate to workflows it did not run.

**The two Jev variants are not separable at n=60.** An earlier run of the same set had
`jev-preview` at 93.3% and 100% on the adversarial slice; the run reported above ties both
models across every slice. That spread is run-to-run variance, not a model difference.

One call to `jev-preview` and one to `claude-sonnet-5` each failed transiently during
development runs and succeeded on retry with the same answer; the final n=60 runs above
completed with zero errors.

### The calibration result

This is the finding worth the repo, and the one that stayed stable across every run.

**Every incorrect answer, on every backend, came with hedged confidence.** Across three
backends and 180 total calls, nothing ever said 1.000 (or Claude's practical ceiling,
~0.97-0.99) and was wrong. Jev's misses ran 0.130, 0.210, 0.250, 0.450, 0.540, 0.570,
0.770, 0.785. Claude's misses ran 0.55-0.73, and — worth reporting plainly — **Claude
never expressed confidence below 0.5 on anything in this set**, hedged or not; Jev's
confidence floor reaches 0.13. Jev's calibration is finer-grained on this task, not just
present.

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

That is the shape a calibrated model is supposed to have: low confidence where it is
wrong, high confidence where it is right. **On this task set, the calibration claim
holds** — which is the claim most worth checking, because it is the one an escalation
path would be built on.

Two caveats against over-reading it. The 0.9–1.0 bin holds 50 of 60 predictions, so most
of the ECE figure is determined by one bin; report the occupancy, not just the number.
And an earlier six-case probe of the same API returned confidence of exactly 1.000 on
five of six, which looked like a saturated softmax — the one shape that makes ECE
meaningless. That was an artifact of an easy sample. Confidence only spreads once the
task set contains genuinely hard cases, which is a good argument for never trusting a
calibration number computed over a set nobody deliberately made difficult.

### Where it fails

All three backends sit at 71.4% on the `ambiguous` slice — identically, which is the
strongest evidence in this repo that the difficulty of the *task*, not the model, set the
ceiling here. Some of those disagreements are arguably mislabels on my side rather than
model errors — `kubectl port-forward svc/postgres` to a production database is labelled
`readonly` here and classified `privileged` by every backend, which is a defensible
reading of a call that opens a tunnel into prod. The benchmark reports the disagreement
rather than adjudicating it; the labels are in the repo so you can take the other side.

Benign-sounding wrappers around destructive calls mostly did not fool any backend: 11 of
12 on the adversarial slice, across the board.

## What this does NOT show

This repo measures **one-shot classification latency and cost**, not the vendor's
"workflow" comparison, which may chain multiple steps and is not reproduced here. It also
does not test cardinality above 4 choices, the `noul` or `score` question types, or any
task where Jev's 255-option ceiling would matter. Extending to those is a good next PR.

## Reproduce

```bash
printf 'TYPESAFE_API_KEY=...\n' > ~/.config/blogify/typesafe.env && chmod 600 ~/.config/blogify/typesafe.env
printf 'ANTHROPIC_API_KEY=sk-ant-...\n' > ~/.config/blogify/llm.env && chmod 600 ~/.config/blogify/llm.env
python3 bench.py --backend jev --model jev-latest
python3 bench.py --backend jev --model jev-preview
python3 bench.py --backend anthropic --model claude-sonnet-5
python3 analyze.py
```

The Anthropic adapter explicitly disables extended thinking (`thinking: {"type":
"disabled"}`) for a fair fast-path comparison — this is a single-step classification task
with no need for multi-step reasoning, and Jev does not think before answering either.
Worth knowing if you adapt this for OpenAI or another provider: with thinking left on
defaults and a low `max_tokens`, one case in early testing here burned its entire token
budget on an empty thinking block and returned no answer at all. Prices are current as of
this run (Anthropic $2/$10 per-MTok in/out for Sonnet 5, TypeSafe $0.042/MTok input, output
free) — re-verify against each vendor's pricing page before quoting a cost multiplier from
an old run.

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
