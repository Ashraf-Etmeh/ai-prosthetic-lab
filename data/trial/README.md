# Trial material

For the two human reviews before and during the specialist trial.

## arabic_terms.csv — Arabic term check

Every interface text (page texts, gap field names, drop-down choices) with
its English, its current Arabic and where it appears. An Arabic-reading
prosthetist fills in **corrected Arabic** and **comment** only where needed
and leaves the other columns as they are. Opens in Excel (UTF-8 with BOM).

```
python -m shared.arabic_terms export                         # (re)write the sheet
python -m shared.arabic_terms apply data/trial/arabic_terms.csv   # corrections -> shared/i18n.py
```

`apply` changes only rows with a corrected Arabic text, shows the
difference and asks before writing. It refuses the whole sheet if a row has
an unknown key, Arabic that changed since the export, or a `{placeholder}`
the English doesn't have (placeholders such as `{n}` must stay as they
are). `export` never overwrites a sheet that has corrections or comments.
After applying, run `python -m unittest`.

## cases/ — prepared trial cases

15 fake cases (`trial-01` … `trial-15`), no patient identifiers: every
amputation level, left/right/bilateral, K0-K4 and unknown, from nearly
complete to barely filled intakes, some free text in Arabic. To put them in
the app (with the app stopped):

```
python -m intake.load_trial_cases
python app.py
```

Each is then at http://127.0.0.1:5000/review/trial-01 etc. They are analysed
exactly like a typed-in case. Loading again re-analyses them; the review log
is not touched.

## report.csv — counts from the review log

```
python -m review.trial_report
```

Reads `data/review_log.jsonl` and writes `report.csv` (not in git): per gap
field, Needed / Not needed / not marked, split by whether a source passage
was shown; gaps without a source marked Needed; Relevant / Not relevant per
statement; decisions and every edit note. Counts only.
