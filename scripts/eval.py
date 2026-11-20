"""Tiny behavioural evaluation of the assistant (run it to compare models).

    uv run python scripts/eval.py                 # model from .env
    LLM_MODEL=qwen2.5:7b uv run python scripts/eval.py
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coach.assistant import Assistant, Profile  # noqa: E402

REPORT = [("Infirmier", 4), ("Auxiliaire de puériculture", 2), ("Plongeur", 1),
          ("Musicothérapeute", 4), ("Coach sportif", 3)]

DONT_KNOW = re.compile(r"(je ne sais pas|pas dans mes sources|n'ai pas (cette|d')info)", re.I)
CITES = re.compile(r"\[\d+\]")
EURO = re.compile(r"\d[\d  ]*\s?(€|euros?)", re.I)
SAYS_NO = re.compile(r"\b(non|pas possible|impossible|faut (avoir )?le bac|"
                     r"(demande|exige|nécessite)\w* (au minimum |d'avoir )?le bac)\b", re.I)
SAYS_YES = re.compile(r"\b(oui|sans le bac,? (c'est )?possible|accessible(s)? sans le bac)\b", re.I)

CASES = [
    # (question, has_bac, checks)
    ("C'est quoi concrètement un musicothérapeute ?", None, ["cites"]),
    ("Infirmier, je peux le faire sans le bac ?", False, ["cites", "says_no"]),
    ("Auxiliaire de puériculture, je peux le faire sans le bac ?", False, ["cites", "says_yes"]),
    ("Combien gagne un infirmier ?", None, ["dont_know", "no_euro"]),
    ("Plongeur, il y a quelles formations près de chez moi ?", None, ["uncertain"]),
    ("Quel est le meilleur club de foot de Marseille ?", None, ["dont_know"]),
    # the roadmap: computed route, with the « passerelle » for a jeune without the bac
    ("Comment je deviens infirmier ?", False, ["cites", "route"]),
    # no course in Région Sud: must not invent access or schools (it did with a few-shot)
    ("C'est quoi concrètement un musicothérapeute ?", False, ["no_course_claim"]),
    ("Musicothérapeute, il faut quel diplôme ?", False, ["dont_know"]),
]


def check(name: str, answer: str) -> bool:
    return {
        "cites": bool(CITES.search(answer)),
        "dont_know": bool(DONT_KNOW.search(answer)),
        "no_euro": not EURO.search(answer),
        "says_no": bool(SAYS_NO.search(answer)),
        "says_yes": bool(SAYS_YES.search(answer)) and not re.search(r"\bnon\b", answer, re.I),
        "route": bool(re.search(r"passerelle", answer, re.I)
                      and re.search(r"aide-soignant", answer, re.I)),
        "no_course_claim": not re.search(r"(sans (le )?bac\s*:?\s*(oui|possible)|près de chez toi"
                                         r"|[ée]coles? (sp[ée]cialis|d'|de ))", answer, re.I),
        "uncertain": bool(re.search(r"(incertain|pas (trouvé|de correspondance)|"
                                    r"ne (sais|peux) pas|vérifier)", answer, re.I)),
    }[name]


def main() -> int:
    bot = Assistant()
    print(f"model: {bot.llm.model}\n")
    passed = total = 0
    t0 = time.time()
    for q, has_bac, checks in CASES:
        profile = Profile(report_jobs=REPORT, city="Nice", has_bac=has_bac)
        _, stream = bot.answer(q, profile, [])
        t = time.time()
        answer = "".join(stream)
        results = {c: check(c, answer) for c in checks}
        passed += sum(results.values())
        total += len(results)
        status = " ".join(f"{'✅' if ok else '❌'}{c}" for c, ok in results.items())
        print(f"Q: {q}\n   {status}  ({time.time() - t:.0f}s)")
        print("   " + answer.replace("\n", " ")[:400] + "\n")
    print(f"SCORE {passed}/{total}  in {time.time() - t0:.0f}s  ({bot.llm.model})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
