# Baseline, 2026-10-13

The state of `main` at `a8cf888` ("Save current project progress"), working
tree clean before the run. Run without the Claude API (no key on this
machine), with the real local search (bge-m3 on the GPU, `HF_HUB_OFFLINE=1`).
Environment: `environment.txt`. Total wall time about 2 minutes.

| # | Command | Result | Log |
|---|---|---|---|
| 1 | `python -m unittest` | **368 tests, OK, 0 skipped** (17.5 s) | `01_unittest.log` |
| 2 | `python -m knowledge.evaluate` | identical to the 2026-10-06 figures (below) | `02_knowledge_evaluate.log` |
| 3a | `python scripts/verify_all.py --with-model`, prompts 0-2 checks | PASS 20, **FAIL 3** (0.3, 0.5, 1.8: repo state, not code; below), MANUAL 1 (1.7b) | `03_verify_all_with_model.log` |
| 3b | same, golden cases with the real search | **13 cases: 80 PASS, 0 WARN/FAIL/SKIP/ERROR** | `03_verify_all_with_model.log` |
| 4 | one case end to end (`e2e_one_case.py`) | **OK**: golden-01 through the Flask app, 6/6 golden checks PASS | `04_e2e.log`, `04_e2e/` |
| - | `python -m intake.golden_cases --rag` | **not run**: no API key, and it costs money (ask the owner) | - |

## Search quality (`knowledge.evaluate`)

| queries | hit@1 | hit@5 | hit@5 without German |
|---|---|---|---|
| English (10) | 5/10 | 10/10 | 10/10 |
| Arabic (8) | 3/8 | 6/8 | 7/8 |
| German (5) | 5/5 | 5/5 | - |
| Cross-language (4) | 3/4 | 4/4 | 3/3 |

Not in the top 5: ar-04 (microprocessor knee) and ar-05 (peer support).
Correct answers score 0.58 to 0.71 (lowest to median); the best off-topic
match scores 0.44 (`MIN_RELEVANCE_SCORE` 0.50). Same as FUTURE_WORK.md,
2026-10-06.

## Prompts 0-2 checks: the three FAILs

None of them is a code regression. On 2026-10-11 only 0.3 failed.

- **0.3, git status clean:** fails because this folder is untracked. The
  tree was clean before the run, so 0.3 would pass without these files.
- **0.5, "nothing pushed":** `main` = `origin/main` = `a8cf888` (pushed
  2026-10-13 01:06 -07:00). The check was written to confirm that nothing
  had been pushed when prompts 0-2 were verified, so it now fails by design.
- **1.8, log split:** expects `data/review_log.jsonl` to be empty. It has
  1 line: log version 5, case `db7a20c8262e`, "approve", Arabic interface,
  logged 2026-10-13T14:53:42Z (its case file is in `data/cases/`). Whether
  that line is a trial decision or a try-out is the owner's call. The log is
  append-only, so it was not touched.

Also from 3a: the 15 trial cases with the real search gave 117 gaps, 93 of
them citing a source (2.3m). The analysis matches SYSTEM_DESCRIPTION §4.5
for all 13 levels (0.6). Protected paths were unchanged (S.1).

## End-to-end case (`e2e_one_case.py`)

golden-01 (transtibial, left, K3) filled into the intake form, then
`POST /intake` (302), `GET /review/<id>` (200, 78 KB, saved as
`04_e2e/review_page.html`), then an "approve" decision (302, then 200). The
case store and review log were redirected into `04_e2e/`, and the script
checked that `data/cases/` and `data/review_log.jsonl` stayed unchanged
(true).

- Time: 12.7 s for the first case (model load), 0.14 s for the second.
- Gaps: 4, of which 3 cite a passage (volume stability: socket shape
  capture review p. 2; pain: VA/DoD 2024 p. 101; functional goals: VA/DoD
  2024 p. 107; prior devices: none). These match golden-01's expected gaps.
- Passages found: 59 distinct (5 per gap field, 6 per RAG topic, 10 topics).
- Without the AI: all three AI parts show "unavailable", there are no
  summary sentences or statements (0 shown), and each section lists its
  passages. This is the documented fallback.

## Not covered by this baseline

The RAG itself: coverage of the answer key, misquote rate, time and cost per
case. FUTURE_WORK.md records that no live `--rag` run has been done yet.
Measured without the API, the search caps coverage at 129 of 359 expected
statements (36%) at `RAG_TOP_K` 6. Running `--rag` needs `ANTHROPIC_API_KEY`
and the owner's go-ahead (3 calls per case × 13 cases).

## Reproduced (second run, same day, `rerun/`)

All four steps were run again from scratch. The results are the same: 368
tests OK, the evaluation log identical, PASS 20 / FAIL 3 (0.3, 0.5, 1.8) /
MANUAL 1, golden cases 80 PASS, and the end-to-end case with the same 4
gaps, the same cited passages, 59 passages and 6/6 PASS. Only the
timestamps, timings (first case 9.9 s instead of 12.7 s), generated case ids
and the list of untracked files in check 0.3 differ.

## Re-running

```
$env:PYTHONIOENCODING="utf-8"; $env:HF_HUB_OFFLINE="1"
python -m unittest
python -m knowledge.evaluate
python scripts/verify_all.py --with-model
python data/eval/baseline/2026-10-13/e2e_one_case.py
```
