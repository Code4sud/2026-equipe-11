"""Link a free-text job name (report, user question) to a ROME 4.0 code.

Candidates are every ROME appellation (both genders), every ROME label and
every ONISEP job name (ONISEP gives the ROME code). Fuzzy matching only: no
model needed, deterministic, and the score tells us when to say "je ne sais pas".
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from rapidfuzz import fuzz, process

from coach.text import gender_variants, normalize

CONFIDENT = 88  # >= : we trust the link
PLAUSIBLE = 75  # >= : we show it, flagged as uncertain


@dataclass
class Match:
    code: str
    matched_label: str
    source: str
    score: float

    @property
    def confident(self) -> bool:
        return self.score >= CONFIDENT

    def as_dict(self) -> dict:
        return {**asdict(self), "confident": self.confident}


def _score(query: str, choice: str, **_: object) -> float:
    # token_sort is strict on extra words; token_set forgives them.
    # Mixing both favours exact names while still finding "infirmier" in
    # "infirmier en soins generaux".
    return 0.65 * fuzz.token_sort_ratio(query, choice) + 0.35 * fuzz.token_set_ratio(query, choice)


class JobMatcher:
    def __init__(self, entries: list[tuple[str, str, str, str]]):
        # (normalized, display label, rome code, source)
        self.entries = entries
        self._norm = [e[0] for e in entries]

    @classmethod
    def from_sources(cls, rome: dict[str, dict], onisep: list[dict]) -> "JobMatcher":
        seen: set[tuple[str, str]] = set()
        entries: list[tuple[str, str, str, str]] = []

        def add(label: str, code: str, source: str) -> None:
            for variant in gender_variants(label):
                key = (normalize(variant), code)
                if key[0] and key not in seen:
                    seen.add(key)
                    entries.append((key[0], variant, code, source))

        for code, sheet in rome.items():
            add(sheet["label"], code, "ROME")
            for app in sheet["appellations"]:
                add(app, code, "ROME appellation")
        for job in onisep:
            if len(job["rome"]) == 1:  # ambiguous multi-code ONISEP jobs are skipped
                add(job["label"], job["rome"][0], "ONISEP")
        return cls(entries)

    def search(self, query: str, limit: int = 5) -> list[Match]:
        hits = []
        for variant in gender_variants(query):
            q = normalize(variant)
            if q:
                hits += process.extract(q, self._norm, scorer=_score, limit=limit * 4)
        hits.sort(key=lambda h: h[1], reverse=True)
        out: list[Match] = []
        codes: set[str] = set()
        for _, score, idx in hits:
            _, label, code, source = self.entries[idx]
            if code in codes:
                continue
            codes.add(code)
            out.append(Match(code, label, source, round(score, 1)))
            if len(out) == limit:
                break
        return out

    def best(self, query: str) -> Match | None:
        hits = self.search(query, limit=1)
        if hits and hits[0].score >= PLAUSIBLE:
            return hits[0]
        return None

    def name_score(self, query: str, code: str) -> tuple[float, str]:
        """Best fuzzy score of `query` against the names of one ROME code."""
        qs = [normalize(v) for v in gender_variants(query)]
        best, label = 0.0, ""
        for norm, display, c, _ in self.entries:
            if c == code:
                s = max(_score(q, norm) for q in qs)
                if s > best:
                    best, label = s, display
        return best, label


def hybrid_candidates(matcher: JobMatcher, label: str, name_hits: list[Match],
                      semantic: list[tuple[str, float]], limit: int = 3) -> list[dict]:
    """Merge name matching and description similarity into ranked candidates.

    `semantic` is [(rome_code, cosine)] for the job description.
    A link is `confident` only when both signals agree, otherwise the assistant
    must present it as uncertain.
    """
    cos = dict(semantic)
    pool: dict[str, dict] = {}
    for h in name_hits:
        pool[h.code] = {"code": h.code, "name": h.score / 100, "matched_label": h.matched_label}
    for code, _ in semantic:
        if code not in pool:
            s, lab = matcher.name_score(label, code)
            pool[code] = {"code": code, "name": s / 100, "matched_label": lab}
    out = []
    for c in pool.values():
        c["semantic"] = round(float(cos.get(c["code"], 0.0)), 3)
        c["name"] = round(c["name"], 3)
        c["score"] = round(0.5 * c["name"] + 0.5 * c["semantic"], 3)
        c["confident"] = c["name"] >= 0.9 or (c["name"] >= 0.75 and c["semantic"] >= 0.75)
        out.append(c)
    # exact name first, then agreeing signals, then combined score
    out.sort(key=lambda c: (c["confident"], c["name"] >= 0.97, c["score"]), reverse=True)
    return out[:limit]
