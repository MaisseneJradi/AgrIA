"""Summary of the analyses kept in test mode (data/journal/, AGRIA_JOURNAL=1): where the models go wrong.

Usage: python src/api/journal_report.py
For each analysis: photo, what the router saw, the model used, its class and confidence, the agent's issue, the
tester's verdict and the true answer. Then: share of correct answers, and the confidence of right vs wrong answers
(if the wrong ones are confident, raising the threshold will not be enough).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOURNAL = ROOT / "data" / "journal"


def main():
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(JOURNAL.glob("*.json"))]
    if not rows:
        sys.exit(f"aucune analyse dans {JOURNAL} (lancer l'API avec AGRIA_JOURNAL=1)")
    print(f"{len(rows)} analyses dans {JOURNAL.relative_to(ROOT)}\n")
    right, wrong = [], []
    for r in rows:
        d = r.get("diagnostic") or {}
        avis = r.get("avis") or {}
        verdict = "?" if not avis else ("juste" if avis["correct"] else "FAUX")
        conf = d.get("confiance")
        print(f"{r['id']}  {str(r['entree'].get('fichier'))[:28]:28s} {str(d.get('routing')):6s} "
              f"{str(d.get('task')):10s} {str(d.get('classe')):34s} {str(conf):>4s} %  {r['issue']:11s} "
              f"{verdict:5s} {avis.get('vraie_reponse') or ''}")
        if avis and conf is not None:
            (right if avis["correct"] else wrong).append(conf)
    judged = len(right) + len(wrong)
    if judged:
        print(f"\njugées : {judged} ; justes : {len(right)} ({100 * len(right) / judged:.0f} %)")
        if right:
            print(f"confiance moyenne des justes : {sum(right) / len(right):.0f} %")
        if wrong:
            print(f"confiance moyenne des fausses : {sum(wrong) / len(wrong):.0f} %")


if __name__ == "__main__":
    main()
