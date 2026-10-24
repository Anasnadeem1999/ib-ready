# Evaluation history

Each run uses the same labeled answers. Plain gpt-6-luna is not deterministic, so its numbers vary from run to run. Tick & Tie's numbers didn't change, because code makes the grading call.

| Run | Set | System | Verdict accuracy | Wrong caught | Misconception named | False alarms on correct |
|---|---|---|---|---|---|---|
| 1 (code frozen, 2026-10-23) | Held-out (30) | Tick & Tie | 100% | 100% | 100% | 0% |
| 1 | Held-out (30) | Plain gpt-6-luna | 87% | 93% | 93% | 20% |
| 1 | Development (65) | Tick & Tie | 100% | 100% | 100% | 0% |
| 1 | Development (65) | Plain gpt-6-luna | 85% | 98% | 95% | 36% |
| 2 (regression after redesign, 2026-10-24) | Held-out (30) | Tick & Tie | 100% | 100% | 100% | 0% |
| 2 | Held-out (30) | Plain gpt-6-luna | 77% | 93% | 93% | 40% |
| 2 | Development (65) | Tick & Tie | 100% | 100% | 100% | 0% |
| 2 | Development (65) | Plain gpt-6-luna | 89% | 100% | 98% | 28% |

Across both runs, the plain model marked **20–40%** of correct answers wrong. Tick & Tie marked **0%** wrong.

The red-team suite stopped 14 of 14 attacks on both runs.
