"""Leakage check run BEFORE every training (rule 3 of the improvement plan): no training image may also be a
validation or test image, as the same file (MD5) or as the same picture saved again (dHash, confirmed pixel by pixel
like src/preparation/check_duplicates.py, because the hash alone gives false alarms on thin leaves over black).

The sets are the ones train.py will read: train (raw split, minus val_field when --field-val), val, val_field, test,
test_field, after --exclude-source. Hashes come from data/processed/hash_cache.csv; missing ones are computed in
memory (the cache file is never written here). Nothing is deleted: a leak stops the training, and the images are
removed only with remove_images.py after review.

Usage:
  python src/evaluation/leakage.py --task diseases --field-val
  python src/evaluation/leakage.py --task leaf --field-val --exclude-source plantwild
In train.py: called automatically (stops when a training image is also in an evaluation set).
"""
import argparse
import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
for sub in ("vision", "preparation"):
    sys.path.insert(0, os.path.join(ROOT, "src", sub))
from check_duplicates import hashes, same_picture, small  # noqa: E402
from dataset import PROC, load_split, local_path  # noqa: E402

EVAL_SPLITS = ("val", "val_field", "test", "test_field", "field_tn")


def _hash_table(paths):
    cache = pd.read_csv(PROC / "hash_cache.csv", dtype=str)
    cache["path"] = cache["path"].map(local_path)
    cache = cache.drop_duplicates("path").set_index("path")
    known = cache.reindex(list(dict.fromkeys(paths)))
    for p in known.index[known["md5"].isna()]:
        known.loc[p, ["md5", "dhash"]] = hashes(p)
    return known


def find_leaks(sets, confirm=True):
    """sets: {name: list of image paths}. Returns a DataFrame of (train path, eval path, eval set, kind) where a
    training image is also in an evaluation set: kind "exact" (same MD5) or "near" (same dHash, same pixels)."""
    train = list(dict.fromkeys(sets.get("train", [])))
    evals = {k: list(dict.fromkeys(v)) for k, v in sets.items() if k != "train" and len(v)}
    h = _hash_table(train + [p for v in evals.values() for p in v])
    th = h.loc[train]
    by_md5 = th.reset_index().groupby("md5")["path"].apply(list).to_dict()
    by_dh = th.reset_index().groupby("dhash")["path"].apply(list).to_dict()
    rows, train_set = [], set(train)
    for name, paths in evals.items():
        for p in paths:
            if p in train_set:
                rows.append({"train": p, "eval": p, "set": name, "kind": "same path"})
                continue
            for t in by_md5.get(h.at[p, "md5"], []):
                rows.append({"train": t, "eval": p, "set": name, "kind": "exact"})
            for t in by_dh.get(h.at[p, "dhash"], []):
                if h.at[t, "md5"] == h.at[p, "md5"]:
                    continue
                if not confirm or same_picture(small(t), small(p)):
                    rows.append({"train": t, "eval": p, "set": name, "kind": "near"})
    return pd.DataFrame(rows, columns=["train", "eval", "set", "kind"])


def task_sets(task, field_val=True, exclude_sources=()):
    sets = {"train": load_split(task, "train", balanced=False, field_holdout=field_val,
                                exclude_sources=exclude_sources)["path"].tolist()}
    for s in EVAL_SPLITS:
        if s == "val_field" and not field_val:
            continue
        sets[s] = load_split(task, s, exclude_sources=exclude_sources)["path"].tolist()
    return sets


def check(task, field_val=True, exclude_sources=(), verbose=True):
    """Leaks between the train set of `task` and its evaluation sets (empty DataFrame = clean)."""
    sets = task_sets(task, field_val, exclude_sources)
    leaks = find_leaks(sets)
    if verbose:
        sizes = ", ".join(f"{k} {len(v)}" for k, v in sets.items())
        print(f"contrôle des fuites {task} ({sizes}) : "
              + ("aucune image d'entraînement dans les jeux d'évaluation" if leaks.empty else
                 f"{len(leaks)} FUITES " + str(leaks.groupby(['set', 'kind']).size().to_dict())), flush=True)
    return leaks


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task", required=True)
    ap.add_argument("--field-val", action="store_true")
    ap.add_argument("--exclude-source", nargs="*", default=[])
    ap.add_argument("--out", default=None, help="CSV of the leaks found")
    a = ap.parse_args()
    leaks = check(a.task, a.field_val, a.exclude_source)
    if a.out and not leaks.empty:
        leaks.to_csv(a.out, index=False)
    sys.exit(1 if len(leaks) else 0)


if __name__ == "__main__":
    main()
