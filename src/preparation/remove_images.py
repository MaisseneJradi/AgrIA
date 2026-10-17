"""Remove bad images (noise, wrong label) from the processed data and log why.
Usage: python src/preparation/remove_images.py "reason" path1 [path2 ...]"""
import csv, os, sys

reason, paths = sys.argv[1], [os.path.normpath(p) for p in sys.argv[2:]]
log = os.path.join("docs", "removed_images.csv")
new_log = not os.path.exists(log)
with open(log, "a", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    if new_log:
        w.writerow(["path", "reason"])
    for task in ["diseases", "deficiency"]:
        man = os.path.join("data", "processed", f"{task}_manifest.csv")
        rows = list(csv.DictReader(open(man, encoding="utf-8")))
        keep = [r for r in rows if os.path.normpath(r["path"]) not in paths]
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
