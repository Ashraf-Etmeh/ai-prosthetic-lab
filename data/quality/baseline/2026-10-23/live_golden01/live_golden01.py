"""Live RAG run on golden-01 (owner's decision 2026-10-23): real search, real Gemini, the --rag measurements.
Saves the full record to the scratchpad; writes nothing under data/."""
import json, sys, time
from pathlib import Path
from intake.golden_cases import GOLDEN_CASES_DIR, check_case, read_golden_case
from intake.routes import analyse_case
from reasoning.writer import provider_writer
from shared.store import record_to_dict

out = Path(sys.argv[1])
golden = read_golden_case(GOLDEN_CASES_DIR / "golden-01.json")
writer = provider_writer()
print("writer:", writer.name, flush=True)
started = time.perf_counter()
record = analyse_case(golden.case, writer=writer)
print(f"analysis: {time.perf_counter() - started:.1f} s; knowledge warning: {record.knowledge_warning}", flush=True)
out.write_text(json.dumps(record_to_dict(record), ensure_ascii=False, indent=1), encoding="utf-8")
for name, part in record.generation.parts.items():
    print(f"part {name}: {part.status} {part.reason or ''} model={part.model} {part.seconds}s "
          f"usage={part.usage} topics={len(part.topics)} kept={len(part.items)} removed={len(part.removed)}")
for finding in check_case(golden, record, None, rag=True):
    print(f"  {finding.status:5} {finding.check:18} {finding.lines[0]}")
    for line in finding.lines[1:]:
        print(f"  {'':5} {'':18} - {line}")
