"""Remove bad images (noise, wrong label, duplicates) from the processed data and log why.
Usage: python src/preparation/remove_images.py "reason" path1 [path2 ...]
       python src/preparation/remove_images.py "reason" @list.txt      (one path per line)
Every manifest in data/processed (diseases, deficiency, fruits, routing...) drops the removed paths."""
import csv, glob, os, sys

reason, paths = sys.argv[1], set()
for a in sys.argv[2:]:
    if a.startswith("@"):
        paths |= {os.path.normpath(l.strip()) for l in open(a[1:], encoding="utf-8") if l.strip()}
    else:
        paths.add(os.path.normpath(a))
log = os.path.join("docs", "removed_images.csv")
new_log = not os.path.exists(log)
with open(log, "a", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    if new_log:
        w.writerow(["path", "reason"])
    for man in sorted(glob.glob(os.path.join("data", "processed", "*_manifest.csv"))):
        rows = list(csv.DictReader(open(man, encoding="utf-8")))
        keep = [r for r in rows if os.path.normpath(r["path"]) not in paths]
        if len(keep) == len(rows):
            continue
        for r in rows:
            if os.path.normpath(r["path"]) in paths:
                if os.path.exists(r["path"]):
                    os.remove(r["path"])
                    w.writerow([r["path"], reason])
                print("removed:", r["path"])
        with open(man, "w", newline="", encoding="utf-8") as g:
            dw = csv.DictWriter(g, fieldnames=rows[0].keys())
            dw.writeheader()
            dw.writerows(keep)
        print(f"{os.path.basename(man)}: {len(rows)} -> {len(keep)}")
