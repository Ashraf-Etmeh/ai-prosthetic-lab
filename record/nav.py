"""What the shared header shows for the patient record and governance (shared/templates/ui_header.html;
SYSTEM_DESIGN.md §7.4; docs/design/09-patient-record/; plan Part 8, 2026-10-27).

A shared part (shared/domains.py SHARED_PARTS). Its two tabs open one person's pages when a person is open (the
page passes part_args with the person's code), else the list of records and the governance settings.
"""

MAP = "record.person"  # the part's first page: the records on this machine
# Its pages as numbered tabs: (key, endpoint, anchor); the tab's label is the interface text LABELS + key.
MODULES = (("record", "record.person", ""), ("governance", "record.governance", ""))
LABELS = "recmod."
