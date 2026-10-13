# Handoff prompt: AI Prosthetic Lab, state on 2026-10-11

You are continuing work on **AI Prosthetic Lab**, a local Flask prototype of
a decision-support tool for prosthetics specialists, in this repository. The
owner (git user Ashraf-Etmeh) is learning Python while building it. This
prompt tells you what has changed so far, what is unfinished, and how the
owner works. The repository documents are the authority on details; read
them before changing anything:

1. `CLAUDE.md`: principles, working rules, roadmap, commands. It was
   reworded on 2026-10-11; see section 3 below.
2. `SYSTEM_DESCRIPTION.md`: what the system does and how. **§4.8 describes
   the RAG**; §4.4 and §4.5 are now "the answer key".
3. `FUTURE_WORK.md`: every decision with its date and measurements. Read the
   section "RAG: retrieval plus Claude with checked quotes (decided
   2026-10-11)".
4. `README.md`: how to run it, including the API key.
5. The plan for the current work:
   `C:\Users\LEGION\.claude\plans\make-an-overall-simple-sharded-eclipse.md`
   (steps R0 to R5).

## 1. What the product is

It follows an Arabic visual brief ("AI Prosthetic LAB", 09/2026):
- **The full brief:** four domains (prosthetics, orthotics, gait analysis,
  rehabilitation), a six-step pathway (case data → information analysis →
  reasoning → assistive output → specialist review → documented outcome)
  and seven use cases.
- **Built so far:** only the prosthetics domain:
  - use case 01: which intake information is missing, and why the sources
    say it matters;
  - use case 02: functional level (K-level) and what the sources say per
    prosthetic component;
  - design and fitting: readiness, preparatory or definitive prosthesis,
    fitting, alignment.

The user enters a fake case on an intake form (English or Arabic, right to
left). They then see a review page, mark each item, and approve, edit or
reject. Every decision is appended to `data/review_log.jsonl`. The tool must
never diagnose, prescribe, choose or rank components, or say whether a
patient is ready for fitting: the specialist decides.

## 2. History until 2026-10-10 (all committed)

| Commit | What |
|---|---|
| `2ec7b49` … `5537733` | Prototype, knowledge retrieval with the local bge-m3 model, rule-based gap analysis |
| `667ce07`, `6a864d2` | First working version; Arabic interface (why Arabic sources are never cited is in FUTURE_WORK) |
| `a7ff631` | Component selection support and functional level (use case 02): hand-written statements quoted word for word |
| `fdc0078` | 33 more sources recorded in the manifest |
| `988f13f` | Design and fitting support |
| `053a190` "step 1+2 p" | Stabilised for a trial; trial tooling (Arabic term sheet, 15 trial cases, trial report). **Last pushed commit** |
| `5f45499`, `c9d8326` | Knowledge items for the 59 curated statements; the owner's evidence rule table applied (steps 3a-3c) |
| `ce8846d`, `2001508` | Golden-case benchmark: 13 cases, 3 reviewed; `scripts/verify_all.py` (steps 4a-4b) |

`main` is 4 commits ahead of `origin/main`. Until 2026-10-11 the system was
rule-based: the "no language model, no cloud" decision dated 2026-10-06.

## 3. The turning point: 2026-10-11, from rules to a RAG

- **What happened in the conversation:** the owner asked for a simple
  explanation of the system, then asked how it would cope with many more
  sources. Then they said: **"I told you from the start I want a RAG not a
  rule based."** The project records said the opposite, so this was a
  misunderstanding of the owner's intent, and it is now corrected.
- **The owner's four choices (all recommended options):**
  1. **Model:** the Claude API (cloud), behind one swap point so a local
     model can replace it later.
  2. **Answers:** "checked quotes". Claude writes short sentences in English
     and Arabic, each with an exact quote and the passage id. Code checks
     every quote word for word and removes sentences that fail.
  3. **Scope:** the review page's sections come from retrieval plus Claude.
     The 59 hand-written statements stop producing the page and become the
     **answer key** the RAG is measured against.
  4. **Principle 1 stays:** the model reports what the sources say for the
     case; it never advises.
- **CLAUDE.md, reworded the same day with the owner's approval:**
  - Principle 2 is now "Every sentence is backed by the source's own words".
  - Principle 3 is now "Search stays local; one cloud language model writes
    the summaries".
  - Principle 4 adds that the case is sent to the Claude API.
  - The rule "Every new quote gets a word-for-word test" became "Every quote
    is checked word for word".
  - An unnumbered "RAG" paragraph opens the roadmap.

## 4. What was built on 2026-10-11 (NOT committed: 29 modified files, 7 new)

**New modules:**
- `reasoning/rag_topics.py`: the case's topics in three parts.
  - Gaps: one topic per missing field, with the field guide's query.
  - Components: the functional level (lower limb only) and each component of
    `COMPONENTS`. The pylon is searched for any lower limb, but listed only
    when the model reports something.
  - Fitting: each section of `SECTIONS`.
  - Queries name the level, side and K-level.
- `reasoning/writer.py`: the only code that calls a model.
  - `Writer` protocol and `WriterUnavailable(reason)`.
  - `OfflineWriter`.
  - `ClaudeWriter`:
    - calls `client.beta.messages.stream(...)` with model
      `claude-opus-5-5`, `output_config={"effort": "medium", "format":
      json_schema}`, `max_tokens` 32000 and a 300 s timeout;
    - uses server-side fallbacks (`betas=["server-side-fallback-2026-07-01"]`,
      `fallbacks="default"`);
    - checks `stop_reason` (refusal, max_tokens) before parsing;
    - turns every SDK error into a readable reason.
  - `default_writer()` returns `OfflineWriter` when the environment variable
    `AI_PROSTHETIC_LAB_OFFLINE` is set.
- `reasoning/quote_check.py`:
  - `find_quote` normalises text (NFKC, flattened whitespace; curly and
    straight quotation marks and dashes treated as the same). It returns the
    passage's own words, or raises `QuoteRefused`.
  - `grade_after`: the grade must be printed within 300 characters after
    the quote.
  - `locate_pages`: finds the quote's page in `data/extracted/<doc_id>.txt`.
- `reasoning/rag.py`:
  - `SYSTEM_PROMPT` (with `PROMPT_VERSION` "rag-v1"), `TASKS` per part,
    `answer_schema` (topic and passage id limited to enums of what was
    given) and `user_message` (the case without id or time, the topics, the
    passages with ids).
  - `generate()` runs the three parts (gaps / components / fitting) in a
    thread pool. A part with no passages makes no call (status "no
    passages").
  - `check_items()` keeps an item only if all of these hold:
    - the topic is known and the passage id was given;
    - the quote is found and is at least 5 words;
    - there is an English sentence and an Arabic sentence;
    - it isn't a repeat;
    - it is within the limit: 1 per gap field, 4 per section.

    An invalid grade is dropped while the item is kept. Every removal is
    recorded with its reason.
  - Data shapes: `Item`, `Part(kind, status, reason, model, usage, seconds,
    topics, items, removed)` and `Generation(prompt_version, writer, effort,
    parts)`.
  - `gaps_from` / `components_from` / `fitting_from` map items onto the
    existing page shapes. RAG statements are `CitedStatement` with
    `origin="rag"`, `summary_en`, `summary_ar`, `chunk_id`, and id
    `rag-<topic>-<10 hex of sha1(doc_id|quote)>`, which is the same in every
    case, so the trial report can add marks up per quote.
  - When a part is unavailable, the gaps fall back to the old topic-word
    check (`reasoning/gap_analysis.py`) and the sections list the passages
    found.

**Changed:**
- `knowledge/retrieval.py`: `retrieve_relevant_chunks(case, ..., topics=True)`
  also searches the RAG topics in the same embed call, with `RAG_TOP_K` 6
  and `RAG_TOPIC_EXCLUDED_DOCUMENTS` () (the ICRC manual is allowed here but
  still excluded from the gap search).
- `reasoning/models.py`: AI-summary fields on `Gap` and `CitedStatement`;
  `FUNCTIONAL_LEVEL` section; `ComponentSupport.component_sections` and
  `.functional_section`.
- `intake/routes.py`: `analyse_case(case, retrieve=None, writer=None)`. The
  route takes the writer from `app.config["RAG_WRITER"]`.
- `shared/store.py`: case file version 2 stores `generation` (the AI's
  answer cannot be reproduced). Version 1 files open with components and
  fitting set to None.
- `review/decision_log.py`: `LOG_VERSION` 5.
  - Per statement: `origin`, `summary_en`/`summary_ar`, `chunk_id`,
    `passage`.
  - Per gap: the summaries.
  - A `generation` block (status, reason, model, usage, seconds, topics,
    items kept, removed per part) and the RAG settings.
  - Older lines are still read.
- `review/templates/review.html` and `review/routes.py`:
  - every gap and statement shows the "AI summary — check it against the
    quote below" label over the checked quote;
  - an unavailable banner with the reason;
  - a removed-items note;
  - passages listed without summaries as the fallback;
  - the functional-level section;
  - a "made before the AI" note for version 1 files.
- `shared/config.py`: `RAG_TOP_K`, `RAG_TOPIC_EXCLUDED_DOCUMENTS`,
  `MIN_QUOTE_WORDS`, `MAX_ITEMS_PER_TOPIC`, `LLM_MODEL`, `LLM_EFFORT`,
  `LLM_MAX_TOKENS`, `LLM_TIMEOUT_SECONDS`, `LLM_FALLBACKS`, `PROMPT_VERSION`,
  `OFFLINE_ENV`, and a new `DISCLAIMER`.
- `shared/i18n.py`:
  - new keys `ai.*`, `ai_part.*` (built at runtime, listed in
    `tests/test_i18n.py`), `functional.from_sources`,
    `functional.no_statement`, `review.made_before_ai`, `intake.ai_note`,
    and three more grades;
  - reworded disclaimer, intake banner and component/fitting intros.
  - **The Arabic was written by Claude and has not yet been checked by an
    Arabic-reading prosthetist.**
- `intake/golden_cases.py`:
  - the statement and functional-level checks now test the answer key
    (`reference(case)` = the rule engine);
  - without `--rag` the AI is switched off (`NO_AI`);
  - `--rag` uses `ClaudeWriter` and reports INFO/WARN findings (they never
    fail): coverage, must-not-show statements, gap sources, the quote
    check, tokens and estimated cost. A RAG quote covers a statement when it
    is from the same document and shares a run of 6 words; cost is
    estimated at $4/$20 per million input/output tokens.
- `intake/load_trial_cases.py`: docstring warns that it calls the paid API.
- `requirements.txt`: `anthropic>=1.13,<2`. SDK 1.13.0 is installed; it
  was 0.75.0 and unlisted.
- `scripts/verify_prompts_0_2.py`:
  - sets `AI_PROSTHETIC_LAB_OFFLINE` at the top;
  - check 0.2 looks for the new CLAUDE.md wording;
  - check 0.6 compares SYSTEM_DESCRIPTION §4.5 with the answer key;
  - check 1.3 flagged a key `name` and a date in the case file, so the
    field became `Part.kind` and the prompt version "rag-v1".
- `data/trial/arabic_terms.csv`: re-exported, now 225 rows. It had no
  corrections, so none were lost.
- Docs updated: CLAUDE.md, README.md, SYSTEM_DESCRIPTION.md, FUTURE_WORK.md.

**Tests:**
- `tests/__init__.py` sets `AI_PROSTHETIC_LAB_OFFLINE`, so **no test can
  call the API**.
- `tests/helpers.py` has `FakeWriter` and `quote_every_topic`, which quote
  the first 8 words of a passage found for each topic.
- New files: `tests/test_rag.py` and `tests/test_quote_check.py`.
- Rewritten: route, store, log, retrieval, golden and i18n tests.

## 5. Verified results (real runs on 2026-10-11)

- `python -m unittest`: **368 tests OK** (326 before).
- `python scripts/verify_all.py`: everything passes except check 0.3 "git
  status clean". That is expected while the work is uncommitted. All 13
  golden cases pass.
- **A free measurement with the real local search (no API).** It answers:
  are the answer key's expected statements inside any passage the topic
  search finds for the 13 golden cases? This is the ceiling for what the
  RAG can cover.

  | Passages per topic | Statements found |
  |---|---|
  | 6 (current) | 129/359 (36%) |
  | 10 | 40% |
  | 15 | 41% |
  | 20 | 47% |
  | 30 | 51% |

  - Weakest: alignment 10/66, socket 2/23, suspension 4/26, fitting 14/54.
  - The four WHO statements are never found: the WHO manual is searched,
    but never ranks in the top 6.
  - Scratch scripts were used; the numbers are recorded in FUTURE_WORK and
    SYSTEM_DESCRIPTION §4.8.
- **Not yet measured**, because there is no API key on this machine
  (`ANTHROPIC_API_KEY` unset, and the `ant` CLI is not installed):
  - the live answers;
  - the misquote rate;
  - time per case;
  - cost;
  - whether structured output and fallbacks are accepted together.

## 6. Waiting on the owner (ask; don't decide)

1. **An API key.** The owner sets `$env:ANTHROPIC_API_KEY` in PowerShell,
   never in a project file.
2. **The retrieval ceiling.** Options: more passages per topic, several
   queries per topic, or try it as it is. Caution: tuning queries while
   looking at the golden cases weakens them as a test; say so.
3. **Paid runs, each only after an explicit OK.**
   - R3: one live case (about $0.50, estimated), with screenshots in English
     and Arabic. Use a scratchpad launcher so `data/cases` and the real
     review log stay clean. Then stop and report the real numbers.
   - R4: `python -m intake.golden_cases --rag` on 13 cases (about $7,
     estimated).
4. **Committing and pushing.** Only when the owner asks.

**Other open items:**
- Latency per case (three parallel calls) is unknown. If it's too slow:
  effort "low" or a background job; the owner chooses.
- The quote check proves a quote is in its passage, not that the AI's
  sentence says only what the quote says.
- The AI's Arabic sentences are unreviewed.
- The evidence values (step 3e) belong to the hand-written statements and
  are not shown next to RAG statements.
- Older open points:
  - `cms_power_assist_ankle` is `ambulators_only` though its quote doesn't
    say so;
  - the owner never answered option A or B for `pass1.csv`;
  - golden cases 04-13 are unreviewed;
  - the trial with a real prosthetist and the Arabic term check have not
    happened.

## 7. How to work with this owner

- **Gated steps.** The owner works in gated steps ("STOP and wait for my
  OK"). Ask before committing, pushing, adding a dependency, deleting data,
  starting a roadmap item, or **any command that calls the Claude API**
  (it costs money and sends the case out).
- **Keep the RAG.** It is the product direction; don't bring back rule-only
  output. The hand-written statements stay as the answer key and keep their
  word-for-word tests.
- **Project rules:**
  - every new interface text gets its Arabic entry;
  - the review log is append-only, and a shape change raises `LOG_VERSION`;
  - clinical evidence values come only from the owner;
  - fake data only.
- **Explaining.** The owner is learning Python: explain step by step, from
  the purpose down, with one concrete example and real command output.
  Report measured numbers, not guesses.
- **Environment:**
  - Windows 11 with PowerShell and Git Bash; the project is under OneDrive;
    Python 3.14; RTX 5060 8 GB.
  - The network is slow; the bge-m3 model is in the local Hugging Face
    cache. Loading it takes 10-30 s, and a search over the 13 golden cases
    takes about 40 s.
  - Write git commit messages to a scratchpad file (`git commit -F`).

## 8. First steps in a new session

1. Run `python -m unittest`; expect 368 OK.
2. Run `git status`; expect 29 modified files and 7 new ones (the four
   `reasoning/` modules, two test files and this file).
3. Read CLAUDE.md, SYSTEM_DESCRIPTION.md §4.8 and the FUTURE_WORK.md RAG
   section.
4. Ask the owner which of the decisions in section 6 to take first.
