"""Remove whole crops from the processed datasets and from the class mapping, and log why.

Usage: python src/preparation/remove_crops.py "reason" crop1 [crop2 ...]
Example: python src/preparation/remove_crops.py "not grown in Tunisia" soybean blueberry raspberry

- Deletes the images of these crops in both tasks (diseases, and the PlantVillage "healthy" leaves
  added to the deficiency task), updates both manifests, logs every file in docs/removed_images.csv.
- Removes the crops from docs/disease_class_mapping.csv, so prepare_images.py will not bring them back.
"""
import csv
import os
import sys

reason, crops = sys.argv[1], {c.lower() for c in sys.argv[2:]}
if not crops:
    sys.exit("Give at least one crop name.")

log = os.path.join("docs", "removed_images.csv")
new_log = not os.path.exists(log)
with open(log, "a", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    if new_log:
        w.writerow(["path", "reason"])
    for task in ["diseases", "deficiency"]:
        man = os.path.join("data", "processed", f"{task}_manifest.csv")
        with open(man, encoding="utf-8") as g:
            rows = list(csv.DictReader(g))
        keep, n = [], 0
        for r in rows:
            if r["crop"].lower() in crops:
                if os.path.exists(r["path"]):
                    os.remove(r["path"])
                w.writerow([r["path"], reason])
                n += 1
            else:
                keep.append(r)
        with open(man, "w", newline="", encoding="utf-8") as g:
            dw = csv.DictWriter(g, fieldnames=rows[0].keys())
            dw.writeheader()
            dw.writerows(keep)
        print(f"{task}: removed {n} images, {len(keep)} left")

# Delete the now-empty class folders
for root, dirs, files in os.walk(os.path.join("data", "processed"), topdown=False):
    if not dirs and not files and root != os.path.join("data", "processed"):
        os.rmdir(root)

# Remove the crops from the mapping so a future prepare_images.py run does not restore them
mp = os.path.join("docs", "disease_class_mapping.csv")
with open(mp, encoding="utf-8-sig") as g:
    rows = list(csv.DictReader(g))
kept = [r for r in rows if r["crop"].lower() not in crops]
with open(mp, "w", newline="", encoding="utf-8") as g:
    dw = csv.DictWriter(g, fieldnames=rows[0].keys())
    dw.writeheader()
    dw.writerows(kept)
print(f"disease_class_mapping.csv: {len(rows) - len(kept)} classes removed, {len(kept)} left")
