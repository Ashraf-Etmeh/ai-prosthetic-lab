"""Download the Figshare data files for the AI Prosthetic Lab datasets (S002, D01, S001).

Safe to re-run at any time:
- files already in place with the right size and MD5 are skipped,
- half-finished downloads are resumed.

Each file is first downloaded to TEMP_DIR (outside OneDrive, so OneDrive never
syncs half-finished files), checked against the MD5 that Figshare publishes,
and only then moved into data/sources/05_datasets/<dataset>/data/.
Data files are never unzipped or changed.

When every file of a dataset is verified, its row in sources_manifest.csv is
set to "downloaded". Progress is written to figshare_download_log.txt.

Run:  python fetch_figshare_data.py
"""
import csv
import datetime
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))  # data/sources/00_registry
SOURCE = os.path.dirname(HERE)  # data/sources
MANIFEST = os.path.join(HERE, "sources_manifest.csv")
LOG = os.path.join(HERE, "figshare_download_log.txt")
# Temporary download folder. Any folder outside OneDrive works.
TEMP_DIR = r"C:\Users\LEGION\AppData\Local\Temp\claude\C--Users-LEGION-OneDrive-Desktop-prosthetic-prototype-ai-prosthetic-lab\5487079a-9681-4e4b-9698-a6d8cb768da2\scratchpad\figdl"
CURL = r"C:\Windows\System32\curl.exe"

# (manifest row, target folder, Figshare items). Smallest dataset first.
DATASETS = [
    ("S002-DATA", "05_datasets/S002_Samala2024_Transtibial_IMU_Optical/data", [("article", 25698006)]),
    ("D01-DATA", "05_datasets/D01_GaitRec_Pathological_Gait/data", [("collection", 4788012)]),
    ("S001-ZIPS", "05_datasets/S001_Hood2020_AboveKnee_Amputee_Gait/data", [("article", 10308443)]),
]


def log(msg):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_json(url):
    """Fetch a Figshare API page, retrying for up to an hour if the network is down."""
    for attempt in range(60):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            return json.load(urllib.request.urlopen(req, timeout=60))
        except OSError as e:  # URLError, timeouts and connection resets are all OSError
            if attempt == 0:
                log(f"   Figshare API not reachable ({e}), retrying every minute")
            time.sleep(60)
    raise RuntimeError(f"Figshare API still not reachable after an hour: {url}")


def list_files(kind, item_id):
    """Return the Figshare file records (name, size, computed_md5, download_url) for an article or collection."""
    if kind == "article":
        article_ids = [item_id]
    else:
        articles = get_json(f"https://api.figshare.com/v2/collections/{item_id}/articles?page_size=100")
        article_ids = [a["id"] for a in articles]
    files = []
    for aid in article_ids:
        for f in get_json(f"https://api.figshare.com/v2/articles/{aid}")["files"]:
            f["article_id"] = aid
            files.append(f)
    return files


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def is_verified(path, f):
    return os.path.exists(path) and os.path.getsize(path) == f["size"] and md5(path) == f["computed_md5"]


def fetch(f, dest):
    """Download one file with resume + retries; move it to dest only if size and MD5 match."""
    tmp = os.path.join(TEMP_DIR, f"{f['article_id']}_{f['name']}.part")
    stalls = 0
    while stalls < 30:  # give up on this run after ~30 minutes with no progress
        before = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        if before >= f["size"]:
            break
        r = subprocess.run(
            [CURL, "-sS", "-L", "--ssl-revoke-best-effort", "-A", "Mozilla/5.0", "-C", "-",
             "--speed-limit", "2000", "--speed-time", "60", "-o", tmp, f["download_url"]],
            capture_output=True, text=True)
        after = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        if after >= f["size"]:
            break
        if r.returncode:
            log(f"   curl stopped at {after / 1e6:.1f} MB ({r.stderr.strip()[:120]}), retrying")
        stalls = 0 if after > before else stalls + 1
        time.sleep(60)
    if is_verified(tmp, f):
        shutil.move(tmp, dest)
        return True
    if os.path.exists(tmp) and os.path.getsize(tmp) >= f["size"]:
        os.remove(tmp)  # complete but wrong MD5: start this file again on the next run
    return False


def mark_downloaded(row_id):
    try:
        with open(MANIFEST, encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        for row in rows:
            if row["file_id"] == row_id:
                row["status"] = "downloaded"
                row["date_downloaded"] = f"{datetime.date.today():%Y-%m-%d}"
        with open(MANIFEST, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        log(f"manifest: {row_id} set to downloaded")
    except PermissionError:
        log(f"manifest is locked (open in Excel?) - set {row_id} to downloaded by hand")


def main():
    os.makedirs(TEMP_DIR, exist_ok=True)
    log("=== start ===")
    for row_id, folder, items in DATASETS:
        out = os.path.join(SOURCE, folder)
        os.makedirs(out, exist_ok=True)
        files = [f for kind, item_id in items for f in list_files(kind, item_id)]
        log(f"{row_id}: {len(files)} files, {sum(f['size'] for f in files) / 1e9:.2f} GB")
        done = 0
        for f in files:
            dest = os.path.join(out, f["name"])
            if is_verified(dest, f):
                done += 1
                continue
            log(f"   downloading {f['name']} ({f['size'] / 1e6:.1f} MB)")
            if fetch(f, dest):
                done += 1
                log(f"   OK {f['name']} (MD5 verified) [{done}/{len(files)}]")
            else:
                log(f"   FAILED {f['name']} - run the script again to resume")
        if done == len(files):
            mark_downloaded(row_id)
        else:
            log(f"{row_id}: {done}/{len(files)} files done")
    log("=== finished ===")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # the script runs hidden, so make sure a crash reaches the log
        log(f"=== stopped by an error: {e!r} - run the script again to resume ===")
        raise
