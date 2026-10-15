"""Extract PlantDoc images on Windows: sanitize forbidden characters and shorten over-long file names."""
import os
import re
import subprocess
import sys

REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "raw", "plantdoc")
MAX_NAME = 80  # max characters for a file name (Windows path limit is 260)


def safe_name(name, sha):
    name = re.sub(r'[<>:"|?*]', "_", name)
    stem, ext = os.path.splitext(name)
    if len(name) > MAX_NAME:
        name = stem[:60] + "_" + sha[:8] + ext
    return name


listing = subprocess.run(["git", "-C", REPO, "ls-tree", "-r", "-z", "HEAD"],
                         capture_output=True, check=True).stdout

written, renamed = 0, 0
for entry in listing.split(b"\0"):
    if not entry:
        continue
    meta, path = entry.split(b"\t", 1)
    _, obj_type, sha = meta.split()
    if obj_type != b"blob":
        continue
    path = path.decode("utf-8")
    sha = sha.decode()
    parts = path.split("/")
    parts[-1] = safe_name(parts[-1], sha)
    dest = os.path.join(REPO, *parts)
    if os.path.exists(dest):
        continue
    folder = os.path.dirname(dest)
    if folder:
        os.makedirs(folder, exist_ok=True)
    blob = subprocess.run(["git", "-C", REPO, "cat-file", "blob", sha],
                          capture_output=True, check=True).stdout
    with open(dest, "wb") as f:
        f.write(blob)
    written += 1
    renamed += "/".join(parts) != path

print(f"Done: {written} files written, {renamed} renamed.")
