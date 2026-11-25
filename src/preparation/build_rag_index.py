"""Phyto plan, step 11: the local vectors of the passages of the knowledge sheets (src/tools/rag.py).

    python src/preparation/build_rag_index.py                 both models found in the local cache
    python src/preparation/build_rag_index.py --model e5-small

-> data/processed/knowledge/vectors_<model>.npz (vectors + key of the passages: rag.py ignores stale vectors).
Run after build_sections.py and build_db.py. The models are read from the local Hugging Face cache only.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import embed  # noqa: E402
import rag  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=sorted(embed.MODELS), action="append")
    args = ap.parse_args()
    for name in args.model or sorted(embed.MODELS):
        if not embed.available(name):
            print(f"{name}: absent du cache local, ignoré")
            continue
        t0 = time.time()
        v = rag.build_vectors(name)
        print(f"{name}: {v.shape[0]} passages x {v.shape[1]} -> {rag.vector_path(name)} ({time.time() - t0:.0f} s, "
              f"{embed.device()})")


if __name__ == "__main__":
    sys.exit(main())
