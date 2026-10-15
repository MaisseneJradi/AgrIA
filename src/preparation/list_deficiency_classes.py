"""List every class folder of the deficiency datasets into a CSV, to map them to unified classes."""
import os
import csv

ROOT = os.path.join("data", "raw", "deficiency")
EXT = (".jpg", ".jpeg", ".png")
OUT = os.path.join("docs", "deficiency_class_mapping.csv")

rows = []
for dataset in sorted(os.listdir(ROOT)):
    ds_path = os.path.join(ROOT, dataset)
    if not os.path.isdir(ds_path):
        continue
    for folder, _, files in os.walk(ds_path):
        n = sum(f.lower().endswith(EXT) for f in files)
        if n:
            rows.append({
                "dataset": dataset,
                "original_class": os.path.relpath(folder, ds_path),
                "n_images": n,
                "unified_class": "",
            })

with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["dataset", "original_class", "n_images", "unified_class"])
    w.writeheader()
    w.writerows(rows)

print(f"{len(rows)} classes written to {OUT}")
for r in rows:
    print(f"  {r['dataset']:<8} {r['original_class']:<60} {r['n_images']}")
