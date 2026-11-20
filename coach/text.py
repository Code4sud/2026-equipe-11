"""Small text helpers shared by the data build and the runtime."""

from __future__ import annotations

import re
import unicodedata

_PARENS = re.compile(r"\([^)]*\)")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    """Lowercase, strip accents, parentheses and punctuation."""
    text = _PARENS.sub(" ", text or "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace("'", " ").replace("’", " ")
    return _NON_ALNUM.sub(" ", text).strip()


def gender_variants(label: str) -> list[str]:
    """Expand French gendered labels.

    "Infirmier / Infirmière"                     -> ["Infirmier", "Infirmière"]
    "accompagnant / accompagnante d'élèves ..."  -> ["accompagnant d'élèves ...",
                                                     "accompagnante d'élèves ..."]
    "Hôtesse de l'air / Steward"                 -> ["Hôtesse de l'air", "Steward"]
    """
    if " / " not in label:
        return [label]
    left, right = label.split(" / ", 1)
    left_n = len(left.split())
    right_tokens = right.split()
    variants = [right]
    if len(right_tokens) > left_n:
        variants.append(" ".join([left, *right_tokens[left_n:]]))
    else:
        variants.append(left)
    return variants
