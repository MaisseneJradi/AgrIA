"""Remove the duplicates found by check_duplicates.py, through remove_images.py (logged in docs/removed_images.csv).

Rules, per task, on the union of exact and near (pixel-confirmed) groups:
  - label conflict (same picture, several classes): every copy is removed, the true label is unknown;
  - same class: one copy is kept, in priority test_field > train > val > test (the field test set is the
    scarcest; otherwise the copy goes to train, so val/test stay unseen), the others are removed.

Usage: python src/preparation/clean_duplicates.py            # dry run: prints what would be removed
       python src/preparation/clean_duplicates.py --apply
"""
import os
import subprocess
import sys

import pandas as pd

KEEP_ORDER = {"test_field": 0, "train": 1, "val": 2, "test": 3}
LIST = os.path.join("data", "processed", "duplicates_to_remove.txt")


def clusters(d):
    """Merge exact and near groups that share an image into one cluster per task (union-find on paths)."""
    parent = {}

    def root(x):
        while parent.setdefault(x, x) != x:
            x = parent[x]
        return x
    for (task, kind, group), g in d.groupby(["task", "kind", "group"]):
        first = root(g["path"].iloc[0])
        for p in g["path"].iloc[1:]:
            parent[root(p)] = first
    rows = d.drop_duplicates(["task", "path"]).copy()
    rows["cluster"] = rows["task"] + ":" + rows["path"].map(root)
    return rows


def main(apply):
    rows = clusters(pd.read_csv(os.path.join("docs", "duplicates.csv")))
    conflict, extra = [], []
    for _, g in rows.groupby("cluster"):
        if g["class"].nunique() > 1:
            conflict += g["path"].tolist()
        else:
            g = g.sort_values("split", key=lambda s: s.map(KEEP_ORDER))
            extra += g["path"].iloc[1:].tolist()
    rows["action"] = "keep"
    rows.loc[rows["path"].isin(conflict), "action"] = "conflict"
    rows.loc[rows["path"].isin(extra), "action"] = "copy"
    print(f"{rows['cluster'].nunique()} clusters, {len(rows)} images: "
          f"{len(conflict)} label conflicts + {len(extra)} extra copies to remove")
    print(rows[rows["action"] != "keep"].groupby(["task", "source", "action"]).size().unstack(fill_value=0).to_string())
    if not apply:
        print("\nDry run: nothing removed. Add --apply to remove.")
        return
    for reason, paths in [("duplicate: same picture with different labels", conflict),
                          ("duplicate: extra copy of the same picture (leakage between splits)", extra)]:
        if paths:
            with open(LIST, "w", encoding="utf-8") as f:
                f.write("\n".join(paths))
            subprocess.run([sys.executable, os.path.join("src", "preparation", "remove_images.py"), reason, "@" + LIST],
                           check=True, stdout=subprocess.DEVNULL)
    os.remove(LIST)
    print("Done. Rerun check_duplicates.py to confirm.")


if __name__ == "__main__":
    main("--apply" in sys.argv)
