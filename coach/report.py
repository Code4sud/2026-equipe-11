"""Read a « Rapport des Possibles » PDF: proposed jobs by zone + the young person's results.

The scores are not text in the PDF, they are vector charts. We read them from the
geometry: the pink polygon of each radar chart (interests, personality) and the pink
bars of the aptitude chart. The PDF is read in memory only: nothing is stored or sent.
"""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass, field

import pdfplumber
from rapidfuzz import fuzz, process

from coach.kb import KnowledgeBase
from coach.text import normalize

_ZONE = re.compile(r"(\d)\s*(?:ère|er|ème|e)\s+ZONE DE M[ÉE]TIERS", re.IGNORECASE)
PINK = (0.878, 0.204, 0.608)

RIASEC_AXES = {"Réaliste": "R", "Investigateur": "I", "Artistique": "A",
               "Social": "S", "Entreprenant": "E", "Conventionnel": "C"}
PERSONALITY_AXES = ["Emotivité", "Caractère consciencieux", "Extraversion",
                    "Humilité-honnêteté", "Agréabilité", "Ouvert à l'expérience"]
APTITUDES = ["Originalité", "Raisonnement déductif", "Raisonnement inductif",
             "Flexibilité des catégories", "Facilité avec les nombres", "Mémorisation",
             "Visualisation", "Attention sélective", "Partage du temps"]


@dataclass
class ReportResults:
    jobs: list[tuple[str, int]] = field(default_factory=list)
    interests: dict[str, float] = field(default_factory=dict)    # 0..1, ranked
    aptitudes: dict[str, float] = field(default_factory=dict)    # 0..8
    personality: dict[str, float] = field(default_factory=dict)  # 0..1, ranked

    @property
    def riasec(self) -> str:
        """Dominant interest letters (top 2, or 1 if the second is weak)."""
        ranked = [k for k, v in self.interests.items() if v > 0]
        if not ranked:
            return ""
        top = [ranked[0]]
        if len(ranked) > 1 and self.interests[ranked[1]] >= 0.5 * self.interests[ranked[0]]:
            top.append(ranked[1])
        return "".join(RIASEC_AXES[k] for k in top)


def _is_pink(color) -> bool:
    return (isinstance(color, (tuple, list)) and len(color) == 3
            and all(abs(a - b) < 0.05 for a, b in zip(color, PINK)))


def _first_chart(pdf, words: tuple[str, ...], read) -> dict:
    """Run `read` on each page containing `words`; keep the first page with a chart
    (the overview page also mentions every measure, but has no chart)."""
    for page in pdf.pages:
        text = page.extract_text() or ""
        if all(w in text for w in words):
            values = read(page)
            if values:
                return values
    return {}


def _radar(page, labels: list[str]) -> dict[str, float]:
    """Values (0..1) of a hexagonal radar chart, from the pink data polygon."""
    grid = [c for c in page.curves if len(c["pts"]) >= 6 and not _is_pink(c.get("stroking_color"))
            and not c.get("fill")]
    data = [c for c in page.curves if _is_pink(c.get("stroking_color")) and not c.get("fill")]
    if not grid or not data:
        return {}
    outer = max(grid, key=lambda c: max(p[1] for p in c["pts"]) - min(p[1] for p in c["pts"]))
    xs = [p[0] for p in outer["pts"]]
    ys = [p[1] for p in outer["pts"]]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    radius = (max(ys) - min(ys)) / 2

    # angle of each axis = angle of its label around the centre
    words = page.extract_words()
    axes: dict[str, float] = {}
    for label in labels:
        first = label.split()[0].replace("'", "’")
        cands = [w for w in words if w["text"].replace("'", "’").startswith(first[:6])
                 and abs(w["top"] - cy) < radius * 1.6]
        if cands:
            w = min(cands, key=lambda w: w["top"])
            wx, wy = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
            axes[label] = math.atan2(wy - cy, wx - cx)
    values = {label: 0.0 for label in axes}
    for x, y in data[0]["pts"]:
        r = math.hypot(x - cx, y - cy)
        if r < radius * 0.02:
            continue
        ang = math.atan2(y - cy, x - cx)
        label = min(axes, key=lambda a: abs(math.remainder(ang - axes[a], math.tau)))
        values[label] = max(values[label], round(min(r / radius, 1.0), 2))
    return dict(sorted(values.items(), key=lambda kv: kv[1], reverse=True))


def _bars(page) -> dict[str, float]:
    """Aptitude scores (0..8) from the pink bars, scaled with the y-axis tick labels."""
    bars = [r for r in page.rects if _is_pink(r.get("non_stroking_color"))]
    if not bars:
        return {}
    base = max(r["bottom"] for r in bars)
    ticks = {}
    for w in page.extract_words():
        if w["text"].isdigit() and len(w["text"]) == 1 and w["x0"] < min(r["x0"] for r in bars):
            ticks[int(w["text"])] = (w["top"] + w["bottom"]) / 2
    unit = ((ticks[0] - ticks[max(ticks)]) / max(ticks)) if 0 in ticks and len(ticks) > 2 else None
    if not unit:
        return {}
    frame = [r for r in page.rects if not _is_pink(r.get("non_stroking_color"))
             and r["x0"] < min(b["x0"] for b in bars) and r["x1"] > max(b["x1"] for b in bars)]
    x0, width = (frame[0]["x0"], frame[0]["width"]) if frame else (
        min(b["x0"] for b in bars) - 30, max(b["x1"] for b in bars) - min(b["x0"] for b in bars) + 60)
    slot = width / len(APTITUDES)
    scores = {a: 0.0 for a in APTITUDES}
    for r in bars:
        i = min(int(((r["x0"] + r["x1"]) / 2 - x0) // slot), len(APTITUDES) - 1)
        scores[APTITUDES[i]] = round((base - r["top"]) / unit, 1)
    return scores


def _jobs(text: str, kb: KnowledgeBase) -> list[tuple[str, int]]:
    labels = list(kb.jobs_by_norm)
    found: list[tuple[str, int]] = []
    zone = None
    for raw in text.splitlines():
        line = raw.strip()
        m = _ZONE.search(line)
        if m:
            zone = int(m.group(1))
            continue
        # job titles are short standalone lines inside a zone section
        if zone is None or not line or len(line) > 60 or line.endswith((".", ",")):
            continue
        hit = process.extractOne(normalize(line), labels, scorer=fuzz.ratio, score_cutoff=92)
        if hit:
            name = kb.jobs_by_norm[hit[0]]["label"]
            if all(name != n for n, _ in found):
                found.append((name, zone))
    return found


def read_report(pdf_bytes: bytes, kb: KnowledgeBase) -> ReportResults:
    res = ReportResults()
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
        res.jobs = _jobs(text, kb)
        res.interests = _first_chart(pdf, ("INTÉRÊTS", "PROFESSIONNELS"),
                                     lambda p: _radar(p, list(RIASEC_AXES)))
        res.aptitudes = _first_chart(pdf, ("APTITUDES", "COGNITIVES"), _bars)
        res.personality = _first_chart(pdf, ("PERSONNALITE",),
                                       lambda p: _radar(p, PERSONALITY_AXES))
    return res


def extract_jobs(pdf_bytes: bytes, kb: KnowledgeBase) -> list[tuple[str, int]]:
    """Backward-compatible helper: only the jobs."""
    return read_report(pdf_bytes, kb).jobs
