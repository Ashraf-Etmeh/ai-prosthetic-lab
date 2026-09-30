"""Review decision logging.

v1 thin-slice status: STUBBED. record_decision() is called but does not yet
write anywhere durable. Step 5 replaces this with real JSON-lines logging to
shared.config.REVIEW_LOG_PATH. See FUTURE_WORK.md.
"""


def record_decision(case_id: str, decision: str, note: str | None = None) -> None:
    """Record a reviewer's approve/edit/reject decision for a case.

    STUB (step 2): prints to the console only. Real implementation (step 5)
    appends a JSON line to disk: {case_id, decision, note, timestamp}.
    """
    print(f"[stub review log] case_id={case_id} decision={decision} note={note!r}")
