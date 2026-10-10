# Manual checks for Prompts 0-2

Run the automated checks first:

```
python scripts/verify_prompts_0_2.py               # about 20 s, no search model
python scripts/verify_prompts_0_2.py --with-model  # also searches the trial cases with bge-m3
```

The five checks below need a person. Each has steps and what "pass" looks
like. Note the date, who checked, and the result next to each one.

## Before you start: the practice server

Checks 2, 3 and 5 use the app. Run it on practice data, so nothing is
written to `data/cases/` or `data/review_log.jsonl`:

```
python scripts/verify_prompts_0_2.py --practice-server
```

It makes a new temporary folder and loads the 15 trial cases into it with
the real search. The first time, the model takes 10-30 s to load. Then it
prints the folder's path and serves the app at http://127.0.0.1:5001. Stop
it with Ctrl+C.

To carry on later with the same cases and decisions, add
`--practice-dir "<the folder it printed>"`. The folder is outside the repo;
delete it when you have finished.

Do not use `python app.py` for these checks: it writes to the real
`data/cases/` and `data/review_log.jsonl`.

## 1. A fresh Claude Code session knows the repo's rules

Steps
1. Start a new Claude Code session in the repo folder: either run `claude`
   in a new terminal there, or open a new chat in the VS Code extension
   with this folder open.
2. As the first message, without pasting anything, ask: *"What rules must
   you follow when changing this repo?"*

Pass: it answers straight away from CLAUDE.md, which every session loads
at start. You don't explain anything, and it doesn't need to search the
code. The answer covers:
- **Decision support only:** it never diagnoses, prescribes, chooses or
  ranks components, or judges whether a patient is ready for fitting.
- **Only the sources speak:** quotes word for word, with their page.
- **Runtime:** no language model and no cloud service.
- **Data:** fake test data only, no patient identifiers.
- **Languages:** English and Arabic pages; quotes stay in their source's
  language.
- **The working rules:**
  - all tests keep passing;
  - every new quote gets a word-for-word test;
  - every new interface text gets an Arabic entry;
  - the review log is append-only, and `LOG_VERSION` is raised when an
    entry's shape changes;
  - clinical judgements are left to the team;
  - it asks before committing, pushing, adding a dependency, deleting
    data, or starting the next roadmap item.
- **The roadmap:** items 1-7, in order.

Fail: it gives generic rules, asks what the rules are, or has to go
looking for them.

## 2. Intake and review pages look right in English and Arabic

Steps
1. Start the practice server.
2. Open http://127.0.0.1:5001/intake in a normal browser (Edge or Chrome),
   then switch to Arabic with the link at the top.
3. Open these review pages, first in English and then in Arabic, and
   scroll each from top to bottom:
   - http://127.0.0.1:5001/review/trial-03: transfemoral K2, barely
     filled, many gaps.
   - http://127.0.0.1:5001/review/trial-01: transtibial, nearly complete.
   - http://127.0.0.1:5001/review/trial-12: transradial, upper limb.

   The sections are the gaps, the functional level, the components,
   design and fitting, and the decision form.
4. Repeat steps 2 and 3 at phone width: press F12, then Ctrl+Shift+M.

Pass
- **Arabic layout:** the page reads right to left. Headings, labels and
  the form are aligned right, drop-downs show Arabic choices, and radio
  buttons and checkboxes sit at the right of their labels.
- **Nothing broken, in either language, at either width:**
  - no overlapping or cut-off text;
  - no raw keys such as `review.approve` or `{n}`;
  - no boxes or question marks where Arabic letters should be.
- **Quotes and citations keep their own language and order:**
  - On the Arabic page, quotes and citations stay in English and read
    left to right.
  - A citation keeps its order, with the year in brackets and the page at
    the end, for example *Prosthetic Gait Analysis for Physiotherapists.
    ICRC Physiotherapy Reference Manual (2014), p. 49*. Nothing jumps to
    the start of the line.
  - A list quote keeps its items in order under its heading, for example
    *Those who are ready for fitting: Free of pain and infection; No
    oedema; …*.
- **Numbers inside Arabic sentences are in their place**, for example the
  count in "ما تقوله المصادر عن التصميم والتركيب (23 بيانات)" on
  trial-03.

Fail: note the page, the language, the width and the section, and take a
screenshot.

## 3. Switching language in a real browser keeps unsent input

Steps
1. Start the practice server and open http://127.0.0.1:5001/intake in
   English.
2. Without submitting, fill in:
   - Amputation level: Transfemoral (leave Side unchosen; it is required)
   - Age: 58
   - Pain: ألم شبحي
   - Comorbidities: Diabetes and Hypertension, on two lines
   - K-level: K2
   - Prior device 1, description: socket
3. Click the language link at the top (العربية).
4. Click the link again (English).
5. Choose a Side, put the cursor in the Age box and press Enter.

Pass
- **After step 3:**
  - The form is in Arabic, right to left, with every value still in it:
    the level shown in Arabic, the Arabic and English text unchanged, and
    both comorbidity lines.
  - There is no "Case not saved" message.
  - The browser did not stop the switch to ask for the empty Side.
- **After step 4:** the values are all still there, in English.
- **Step 5:** Enter sends the case and the review page opens. Enter does
  not switch the language. The case goes to the practice folder only.
- **Remembered:** reopening /intake later shows the language chosen last.

Fail: a value is lost, the browser asks for Side when you switch, or Enter
switches the language.

## 4. arabic_terms.csv opens with readable Arabic

Steps
1. Copy `data/trial/arabic_terms.csv` to your desktop and open the copy,
   so the original in the repo is never saved over by accident.
2. Open the copy:
   - **Excel:** double-click it.
   - **LibreOffice Calc:** open it, and in the import window choose
     character set "Unicode (UTF-8)" and separator "Comma".

Pass
- There are six columns: key, English, Arabic, where it appears,
  corrected Arabic, comment.
- There are 209 rows under the header.
- The Arabic column shows Arabic words, not strings like "Ø§Ø¹": the row
  `review.approve` shows اعتماد.
- The last two columns are empty.

For the prosthetist who fills in the sheet:
- **Saving:** in Excel, save as "CSV UTF-8 (Comma delimited)". Plain "CSV"
  loses the Arabic. In LibreOffice, keep "Unicode (UTF-8)".
- **Applying:** `python -m shared.arabic_terms apply <file>` shows every
  change and asks before it writes anything.

## 5. Dry run of the trial with a teammate

Goal: someone who didn't build the app can go through the trial path, and
the report's counts match what they clicked.

Steps
1. Start the practice server and note the folder it prints.
2. The teammate reviews 4 trial cases end to end, keeping their own tally
   on paper as they go. A suggested set:
   - trial-01
   - trial-03
   - trial-07
   - trial-12, with the page switched to Arabic

   For each case they open http://127.0.0.1:5001/review/trial-XX and:
   - mark some gaps Needed or Not needed, including at least one gap that
     shows "No source cited", marked Needed;
   - mark some statements Relevant or Not relevant;
   - choose approve, edit (with a note) or reject, and save. Use each
     decision at least once across the cases.

   For each case they write down the decision, how many gaps they marked
   Needed and Not needed, how many statements they marked Relevant and Not
   relevant, and the note, if any.
3. Stop the server (Ctrl+C) and run the report command it printed:
   ```
   python -m review.trial_report --log "<folder>\review_log.jsonl" --out "<folder>\report.csv"
   ```
4. Compare the printed summary, or `report.csv` opened in Excel, with the
   tally.

Pass
- **Decisions:** "N decisions on M cases" and the approve, edit and reject
  counts match the tally.
- **Gaps:** the Needed and Not needed totals (add up those columns under
  "Gap fields") match.
- **Gaps without a source:** every gap marked Needed while it showed "No
  source cited" is listed under "Gaps shown without a source and marked
  Needed", with its case id.
- **Statements:** the Relevant and Not relevant totals match.
- **Notes:** every edit note appears word for word, Arabic included.
- **Usability:** the teammate managed without help. Write down anything
  that confused them; that is input for the trial.

Afterwards, make sure the real trial starts with an empty log:
- **If you used the practice server:** there is nothing to move, because
  the real log was never touched. Delete the practice folder.
- **If the dry run was done in the real app (`python app.py`) instead:**
  stop the app first. Then, in PowerShell, move the log aside under a
  dated name and start an empty one:
  ```
  Move-Item data\review_log.jsonl data\review_log.practice-<date>.jsonl
  New-Item data\review_log.jsonl -ItemType File
  ```
  Never edit or delete lines in either file. Both stay out of git
  (`data/review_log*.jsonl`).

Pass, before the first real trial session:
- `(Get-Item data\review_log.jsonl).Length` in PowerShell prints 0.
- `python -m review.trial_report` prints "No decisions logged yet."

To set up the real trial: `python -m intake.load_trial_cases`, then
`python app.py`.
