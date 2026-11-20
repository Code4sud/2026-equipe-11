"""Terminal version of the Coach des Possibles (quick tests without the web UI).

    uv run python main.py --report docs/rapport.pdf --city Nice --no-bac
    uv run python main.py -q "c'est quoi un plongeur ?"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from coach.assistant import Assistant, Profile
from coach.llm import LLMError


def main() -> int:
    ap = argparse.ArgumentParser(description="Coach des Possibles (terminal)")
    ap.add_argument("--report", type=Path, help="Rapport des Possibles (PDF)")
    ap.add_argument("--city", default="", help="ville du jeune (Région Sud)")
    bac = ap.add_mutually_exclusive_group()
    bac.add_argument("--bac", dest="has_bac", action="store_true", default=None)
    bac.add_argument("--no-bac", dest="has_bac", action="store_false")
    ap.add_argument("--riasec", default="", help="lettres dominantes, ex. SA")
    ap.add_argument("-q", "--question", help="une seule question puis quitter")
    args = ap.parse_args()

    bot = Assistant()
    profile = Profile(city=args.city, has_bac=args.has_bac, riasec=args.riasec.upper())
    if args.report:
        from coach.report import read_report
        res = read_report(args.report.read_bytes(), bot.kb)
        profile.results = res
        profile.report_jobs = res.jobs
        profile.riasec = profile.riasec or res.riasec
        print(f"Rapport lu : {len(res.jobs)} métiers, intérêts {list(res.interests)[:2]}, "
              f"{len(res.aptitudes)} aptitudes, {len(res.personality)} traits de personnalité.")

    history: list[dict] = []
    focus = None
    questions = [args.question] if args.question else None
    while True:
        if questions is not None:
            if not questions:
                return 0
            q = questions.pop()
            print(f"> {q}")
        else:
            try:
                q = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                return 0
            if not q:
                continue
        turn, stream = bot.answer(q, profile, history, focus)
        answer = ""
        try:
            for chunk in stream:
                answer += chunk
                print(chunk, end="", flush=True)
        except LLMError as exc:
            print(f"[erreur modèle] {exc}", file=sys.stderr)
            continue
        print("\n\nSources :")
        for i, s in enumerate(turn.sources, 1):
            print(f"  [{i}] {s.title}" + (f" - {s.url}" if s.url else ""))
        history += [{"role": "user", "content": q}, {"role": "assistant", "content": answer}]
        focus = turn.jobs[0] if turn.jobs else focus


if __name__ == "__main__":
    sys.exit(main())
