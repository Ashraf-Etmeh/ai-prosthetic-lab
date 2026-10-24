"""Baseline 2026-10-13: one case end to end through the real Flask app.

  python data/eval/baseline/2026-10-13/e2e_one_case.py [OUTPUT_DIR]   (default: 04_e2e/ here)

golden-01 (transtibial, left, K3; "reviewed") is filled into the intake form
and submitted with POST /intake, using the real search (bge-m3 and
data/vector_store/). Its review page is fetched and saved, an "approve"
decision is posted, and the stored record is checked against golden-01's
expected gaps (intake/golden_cases.py check_case).

Nothing reaches data/cases/ or data/review_log.jsonl: the case store and the
review log point into 04_e2e/ next to this file, and the script checks that
the real ones are unchanged. The Claude API is never called (OfflineWriter),
so the page shows the no-AI fallback: gaps from the topic-word check and the
passages found per section, without summaries.
"""

import hashlib
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from intake import routes as intake_routes  # noqa: E402
from intake.golden_cases import check_case, intake_form, read_golden_case  # noqa: E402
from reasoning.writer import OfflineWriter  # noqa: E402
from review import decision_log  # noqa: E402
from review import routes as review_routes  # noqa: E402
from shared.config import CASES_DIR, GOLDEN_CASES_DIR, REVIEW_LOG_PATH  # noqa: E402
from shared.store import CaseStore  # noqa: E402

OUT = HERE / "04_e2e"
CASE = GOLDEN_CASES_DIR / "golden-01.json"


def fingerprint() -> dict:
    """The real review log's hash and the real case folder's file list."""
    log = hashlib.sha256(REVIEW_LOG_PATH.read_bytes()).hexdigest() if REVIEW_LOG_PATH.is_file() else None
    cases = sorted(p.name for p in CASES_DIR.glob("*")) if CASES_DIR.is_dir() else []
    return {"review_log_sha256": log, "cases_dir_files": cases}


def main() -> int:
    global OUT
    sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1:
        OUT = Path(sys.argv[1]).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    log = OUT / "review_log.e2e.jsonl"
    log.unlink(missing_ok=True)  # this script's own output from an earlier run
    before = fingerprint()

    golden = read_golden_case(CASE)
    store = CaseStore(folder=OUT / "cases")
    intake_routes.store = review_routes.store = store
    decision_log.REVIEW_LOG_PATH = log
    app = create_app()
    app.config["RAG_WRITER"] = OfflineWriter("baseline run: the Claude API is not called")
    client = app.test_client()

    started = time.perf_counter()
    response = client.post("/intake", data=intake_form(golden.data["question"], "en"))
    intake_seconds = time.perf_counter() - started
    if response.status_code != 302:
        print(f"POST /intake answered {response.status_code}, not 302")
        return 1
    case_id = response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
    record = store.get(case_id)

    page = client.get(f"/review/{case_id}")
    (OUT / "review_page.html").write_bytes(page.data)

    started = time.perf_counter()
    second = client.post("/intake", data=intake_form(golden.data["question"], "en"))
    second_seconds = time.perf_counter() - started  # model already loaded

    form = {"decision": "approve", "note": "baseline e2e run, fake case golden-01"}
    if record.gaps:
        form[f"gap:{record.gaps[0].field}"] = "needed"
    decision = client.post(f"/review/{case_id}/decision", data=form)
    after_page = client.get(f"/review/{case_id}")

    findings = check_case(golden, record)
    generation = record.generation.to_dict() if record.generation else None
    summary = {
        "case_file": CASE.relative_to(ROOT).as_posix(),
        "case_id_assigned": case_id,
        "post_intake": {"status": response.status_code, "seconds_first": round(intake_seconds, 2),
                        "seconds_second_model_loaded": round(second_seconds, 2),
                        "second_status": second.status_code},
        "get_review": {"status": page.status_code, "bytes": len(page.data)},
        "post_decision": {"status": decision.status_code, "location": decision.headers.get("Location")},
        "review_after_decision": {"status": after_page.status_code},
        "knowledge_warning": record.knowledge_warning,
        "gaps": [{"field": gap.field, "status": gap.status,
                  "cited": f"{gap.evidence.chunk_id} (p. {gap.evidence.page})" if gap.evidence else None}
                 for gap in record.gaps],
        "passages_per_topic": {topic: len(chunks) for topic, chunks in record.retrieved_chunks.items()},
        "distinct_passages": len({c.chunk_id for chunks in record.retrieved_chunks.values() for c in chunks}),
        "statements_shown": len(record.shown_statements()),
        "generation_parts": ({kind: {"status": part.get("status"), "reason": part.get("reason")}
                              for kind, part in generation.get("parts", {}).items()} if generation else None),
        "golden_checks": [{"check": f.check, "status": f.status, "lines": f.lines} for f in findings],
        "log_lines_written": len(log.read_text(encoding="utf-8").splitlines()) if log.is_file() else 0,
        "real_data_untouched": fingerprint() == before,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    ok = (response.status_code == 302 and page.status_code == 200 and decision.status_code == 302
          and summary["real_data_untouched"] and all(f.status in ("PASS", "INFO") for f in findings))
    print("\nE2E:", "OK" if ok else "PROBLEM")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
