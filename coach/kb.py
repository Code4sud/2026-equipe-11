"""Read-only knowledge base built by scripts/build_data.py."""

from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from rapidfuzz import fuzz, process

from coach.matching import JobMatcher
from coach.text import gender_variants, normalize

DATA = Path(__file__).resolve().parent.parent / "data" / "processed"

ZONES = {
    1: ("Métiers accessibles en 0 à 6 mois",
        "Une courte démonstration ou jusqu'à 6 mois d'apprentissage. "
        "Certains métiers peuvent demander un diplôme de niveau bac."),
    2: ("Métiers accessibles en 3 mois à 2 ans",
        "3 mois à 2 ans d'apprentissage. Certains métiers demandent un CAP, un BEP ou un bac."),
    3: ("Métiers accessibles en 1 à 4 ans",
        "Études supérieures de type BTS ou licence. Certains métiers demandent une licence 3."),
    4: ("Métiers accessibles en 2 à 6 ans",
        "Études supérieures de type master. Certains métiers demandent un master 2, "
        "un bachelor ou un diplôme d'ingénieur."),
    5: ("Métiers accessibles en 4 à 10 ans",
        "Le plus haut niveau d'études : doctorat ou habilitation à diriger des recherches."),
}
CONTEXT_LABELS = {
    "Horaires et durée du travail": "Horaires",
    "Conditions de travail et risques professionnels": "Conditions de travail",
    "Lieux et déplacements": "Lieux et déplacements",
    "Types de structures": "Où on travaille",
    "Publics spécifiques": "Avec qui",
    "Statut d'emploi": "Statut",
}
REPORT_SOURCE = "Rapport des Possibles / table métiers du Centre des Possibles"


@dataclass
class Source:
    """A citable piece of evidence handed to the LLM and shown to the user."""
    title: str
    url: str | None
    text: str


def diploma_label(f: dict) -> str:
    """'certificat d'aptitude professionnelle (CAP)' from the national ONISEP catalogue."""
    t, short = f.get("diploma_type", ""), f.get("diploma_short", "")
    return f"{t} ({short})" if t and short and short.lower() not in t.lower() else t


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class KnowledgeBase:
    def __init__(self, data_dir: Path = DATA):
        def load(name: str):
            return json.loads((data_dir / name).read_text(encoding="utf-8"))

        self.rome: dict[str, dict] = load("rome.json")
        self.onisep: list[dict] = load("onisep.json")
        self.formations: list[dict] = load("formations.json")
        self.jobs: list[dict] = load("jobs.json")
        self.jobs_by_norm = {normalize(j["label"]): j for j in self.jobs}
        self.onisep_by_rome: dict[str, list[dict]] = defaultdict(list)
        for o in self.onisep:
            for code in o["rome"]:
                self.onisep_by_rome[code].append(o)
        self.formations_by_rome: dict[str, list[dict]] = defaultdict(list)
        for f in self.formations:
            for code in f["rome"]:
                self.formations_by_rome[code].append(f)
        self.via_diplomas: set[str] = set()
        self._link_by_diplomas()

    def _link_by_diplomas(self) -> None:
        """A ROME job with no course linked by ONISEP: look for the diplomas France Travail
        cites for it (« Diplôme d'État d'accompagnant éducatif et social ») among the
        Région Sud courses. Strict matching, so it only finds the same diploma."""
        def clean(t: str) -> str:
            return re.sub(r"\s+option\s+.*$", "", normalize(t))
        by_title: dict[str, list[dict]] = defaultdict(list)
        for f in self.formations:
            by_title[clean(f["title"])].append(f)
        titles = list(by_title)
        for code, r in self.rome.items():
            if self.formations_by_rome.get(code) or not r.get("diplomas"):
                continue
            found: dict[str, dict] = {}
            for d in r["diplomas"]:
                cd = clean(d)
                hits = [t for t, _, _ in process.extract(cd, titles, scorer=fuzz.token_sort_ratio,
                                                         score_cutoff=88, limit=10)]
                words = set(cd.split())
                if len(words) >= 5:  # every word of the cited diploma is in the course title
                    hits += [t for t, _, _ in process.extract(
                        cd, titles, scorer=fuzz.token_set_ratio, score_cutoff=100, limit=10)
                        if words <= set(t.split())]
                for t in hits:
                    for f in by_title[t]:
                        found[f["id"]] = f
            if found:
                self.formations_by_rome[code] = list(found.values())
                self.via_diplomas.add(code)

    # ---- jobs -----------------------------------------------------------
    @cached_property
    def matcher(self) -> JobMatcher:
        return JobMatcher.from_sources(self.rome, self.onisep)

    @cached_property
    def _job_labels(self) -> list[str]:
        return list(self.jobs_by_norm)

    def job(self, label: str) -> dict | None:
        """A job of the Centre des Possibles table, by (approximate) name."""
        key = normalize(label)
        if key in self.jobs_by_norm:
            return self.jobs_by_norm[key]
        hit = process.extractOne(key, self._job_labels, scorer=fuzz.token_sort_ratio,
                                 score_cutoff=90)
        return self.jobs_by_norm[hit[0]] if hit else None

    def find_in_text(self, text: str, among: list[str] | None = None) -> list[str]:
        """Job names (from `among`, else the whole table) mentioned in a question."""
        q = normalize(text)
        labels = [normalize(x) for x in among] if among else self._job_labels
        found = []
        for lab in labels:
            if len(lab) >= 4 and fuzz.partial_ratio(lab, q) >= 90:
                found.append(lab)
        # keep the longest names (avoid "agent" inside "agent d accueil")
        found.sort(key=len, reverse=True)
        keep: list[str] = []
        for lab in found:
            if not any(lab in k for k in keep):
                keep.append(lab)
        if among:
            back = {normalize(x): x for x in among}
            return [back[k] for k in keep]
        return [self.jobs_by_norm[k]["label"] for k in keep]

    def rome_for_job(self, job: dict) -> tuple[str | None, list[dict]]:
        """(confident ROME code or None, candidate list) for a table job."""
        return job.get("rome"), job.get("rome_candidates", [])

    def rome_for_name(self, name: str) -> tuple[str | None, list[dict]]:
        """Same as rome_for_job but for any free-text job name."""
        job = self.job(name)
        if job:
            return self.rome_for_job(job)
        hits = self.matcher.search(name, limit=3)
        cands = [{"code": h.code, "name": h.score / 100, "matched_label": h.matched_label,
                  "confident": h.score >= 90} for h in hits]
        best = cands[0]["code"] if cands and cands[0]["confident"] else None
        return best, cands

    # ---- trainings ------------------------------------------------------
    @cached_property
    def cities(self) -> dict[str, tuple[float, float, str]]:
        """normalized city -> (lat, lon, display) from the training offer itself."""
        acc: dict[str, list] = defaultdict(list)
        for f in self.formations:
            if f["lat"] and f["city"]:
                acc[normalize(f["city"])].append((f["lat"], f["lon"], f["city"]))
        return {k: (sum(p[0] for p in v) / len(v), sum(p[1] for p in v) / len(v), v[0][2])
                for k, v in acc.items()}

    def locate(self, city: str) -> tuple[float, float, str] | None:
        if not city:
            return None
        hit = process.extractOne(normalize(city), list(self.cities),
                                 scorer=fuzz.ratio, score_cutoff=85)
        return self.cities[hit[0]] if hit else None

    def trainings(self, rome_code: str, near: tuple[float, float] | None = None,
                  no_bac: bool | None = None, limit: int = 6) -> list[dict]:
        rows = self.formations_by_rome.get(rome_code, [])
        if no_bac is not None:
            rows = [f for f in rows if f["no_bac"] == no_bac]
        out = []
        for f in rows:
            d = None
            if near and f["lat"]:
                d = _haversine(near[0], near[1], f["lat"], f["lon"])
            out.append({**f, "distance_km": round(d, 1) if d is not None else None})
        out.sort(key=lambda f: (f["distance_km"] is None, f["distance_km"] or 0, f["title"]))
        # one line per (title, school): the offer repeats per year of the cycle
        seen, uniq = set(), []
        for f in out:
            key = (f["title"], f["school"])
            if key not in seen:
                seen.add(key)
                uniq.append(f)
        return uniq[:limit]

    # ---- evidence -------------------------------------------------------
    def sources_for_job(self, name: str, near: tuple[float, float] | None = None,
                        has_bac: bool | None = None,
                        report_zone: int | None = None,
                        situation: int | None = None) -> tuple[list[Source], dict]:
        """Everything we know about one job, as citable sources + a summary dict."""
        sources: list[Source] = []
        job = self.job(name)
        code, cands = (self.rome_for_job(job) if job else self.rome_for_name(name))
        info = {"name": job["label"] if job else name, "rome": code,
                "candidates": cands, "zone": job["zone"] if job else None}

        if job:  # (the report's « zones » are not shown: the jeune picks jobs directly)
            sources.append(Source(
                f"Fiche métier du Centre des Possibles : {job['label']}", None,
                job["description"].strip()))

        if code:
            r = self.rome[code]
            text = f"Code ROME {code} - {r['label']}.\nDéfinition : {r['definition']}"
            if r["access"]:
                text += f"\nAccès au métier (diplômes, conditions) : {r['access']}"
            if r["regulated"]:
                text += "\nC'est un emploi réglementé (diplôme ou autorisation obligatoire)."
            sources.append(Source(f"France Travail - fiche ROME {code} {r['label']}",
                                  r["url"], text))
            daily = self.daily_life_text(code)
            if daily:
                sources.append(Source(f"France Travail - ROME {code} : au quotidien, "
                                      "compétences et conditions de travail", r["url"], daily))
            for o in self.onisep_by_rome.get(code, [])[:1]:
                sources.append(Source(f"ONISEP - fiche métier « {o['label']} »", o["url"],
                                      f"Fiche ONISEP du métier {o['label']} "
                                      f"(domaine : {o['domains']})."))
            summary = self.training_summary(code, near)
            if summary:
                sources.append(summary)
                road = self.route_source(info["name"], code, near, situation)
                if road:
                    sources.append(road)
                # the 3 closest trainings, the no-bac ones first for a jeune without bac
                pool = self.trainings(code, near=near, limit=50)
                if has_bac is False:
                    pool.sort(key=lambda f: not f["no_bac"])
                for f in pool[:3]:
                    sources.append(self._training_source(f))
        return sources, info

    def daily_life_text(self, code: str) -> str:
        """« C'est quoi concrètement ? » from ROME 4.0 skills and work context."""
        r = self.rome[code]
        lines = []
        if r.get("tasks"):
            lines.append("Au quotidien : " + " ; ".join(r["tasks"][:6]) + ".")
        if r.get("qualities"):
            lines.append("Qualités attendues : " + " ; ".join(r["qualities"]) + ".")
        ctx = r.get("context", {})
        for key, label in CONTEXT_LABELS.items():
            if ctx.get(key):
                lines.append(f"{label} : " + " ; ".join(ctx[key][:6]) + ".")
        if r.get("knowledge"):
            lines.append("Connaissances à acquérir : " + " ; ".join(r["knowledge"][:5]) + ".")
        if r.get("diplomas"):
            lines.append("Diplômes et titres cités par France Travail : "
                         + " ; ".join(r["diplomas"][:6]) + ".")
        return "\n".join(lines)

    def training_summary(self, code: str, near: tuple[float, float] | None) -> Source | None:
        """Deterministic facts (counts, with/without bac) so the LLM has nothing to guess."""
        rows = self.trainings(code, near=near, limit=500)
        if not rows:
            return None
        no_bac = [f for f in rows if f["no_bac"]]
        lines = [f"{len(rows)} formation(s) reliée(s) à ce métier dans l'offre ONISEP "
                 "de la Région Sud."]
        if code in self.via_diplomas:
            lines.append("Ces formations ont été trouvées à partir des diplômes que France "
                         "Travail cite pour ce métier (fiche ROME).")
        if no_bac:
            titles = sorted({f["title"] for f in no_bac})[:4]
            lines.append(f"Accès sans le bac : oui, {len(no_bac)} formation(s) accessible(s) sans "
                         f"le bac, par exemple : {', '.join(titles)}.")
        else:
            lines.append("Accès sans le bac : non, aucune de ces formations n'est accessible sans "
                         "le bac (toutes demandent au minimum le bac).")
        levels = sorted({f["level"] for f in rows if f["level"]})
        if levels:
            lines.append(f"Niveaux de diplôme obtenus : {', '.join(levels)}.")
        types = sorted({diploma_label(f) for f in rows if f["diploma_type"]})
        if types:
            lines.append(f"Types de diplômes qui y mènent : {', '.join(types[:6])}.")
        durations = sorted({f["duration"] for f in rows if f["duration"]})
        if durations:
            lines.append(f"Durées de formation : {', '.join(durations)}.")
        public = sum(1 for f in rows if f["status"] == "public")
        lines.append(f"Établissements publics : {public} sur {len(rows)} "
                     "(le public est en général gratuit ou peu coûteux, le privé peut être payant).")
        if near and rows[0]["distance_km"] is not None:
            lines.append(f"La plus proche : {rows[0]['title']} à {rows[0]['city']} "
                         f"({rows[0]['distance_km']:.0f} km).")
        return Source("ONISEP - offre de formation Région Sud (synthèse)",
                      "https://www.onisep.fr", "\n".join(lines))

    @staticmethod
    def _training_source(f: dict) -> Source:
        where = f"{f['school']} ({f['city']})"
        if f["distance_km"] is not None:
            where += f", à {f['distance_km']:.0f} km"
        text = (f"Formation : {f['title']}. "
                f"Type de diplôme : {diploma_label(f) or 'non précisé'}. "
                f"Niveau obtenu : {f['level'] or 'non précisé'}. Entrée : {f['entry']}"
                f"{' (accessible sans le bac)' if f['no_bac'] else ' (bac ou plus demandé)'}. "
                f"Durée : {f['duration'] or 'non précisée'}. Lieu : {where}. "
                f"Établissement {f['status'] or 'statut non précisé'} ({f['school_type']}).")
        if f["rncp"]:
            text += (f" Diplôme reconnu par l'État (RNCP {f['rncp']}, {f['cert_level']}"
                     f"{', ' + f['ministry'] if f['ministry'] else ''}).")
        elif f["cert_level"] == "non inscrit au RNCP":
            text += " Attention : diplôme non inscrit au RNCP (pas reconnu par l'État)."
        return Source(f"ONISEP - formation « {f['title']} » - {f['city']}", f["url"], text)

    def rome_name(self, code: str) -> str:
        """A young-friendly name: the ONISEP job name (« aide-soignant ») over the ROME label."""
        o = self.onisep_by_rome.get(code)
        if o:
            return o[0]["label"].split(" / ")[0].capitalize()
        label = self.rome[code]["label"]  # « Chef / Cheffe d'équipe » -> « Chef d'équipe »
        return gender_variants(label)[-1] if " / " in label else label

    def detours(self, code: str, near: tuple[float, float] | None = None,
                limit: int = 2) -> list[tuple[str, list]]:
        """Jobs France Travail lists as a way into `code` (ROME mobility) that have a
        course without the bac in Région Sud: the « passerelle » route."""
        from coach.roadmap import diplomas
        out = []
        for src in self.rome[code].get("mobility_from", []):
            rows = self.trainings(src, near=near, no_bac=True, limit=200)
            if rows:
                out.append((self.rome_name(src), diplomas(rows)))
            if len(out) >= limit:
                break
        return out

    def plan(self, name: str, code: str, near: tuple[float, float] | None,
             situation: int | None) -> tuple[list, list]:
        """(diplomas, routes) for one job: the « Ton chemin » page."""
        from coach.roadmap import diplomas, routes
        dips = diplomas(self.trainings(code, near=near, limit=500))
        rts = routes(name, dips, situation, self.detours(code, near))
        by_name = {self.rome_name(c): c for c in self.rome[code].get("mobility_from", [])}
        by_name[name] = code
        for r in rts:
            for st in r.steps:
                c = by_name.get(st.title)
                if st.kind != "job" or not c or st.lines:
                    continue
                rome = self.rome[c]
                tasks = [t[:1].lower() + t[1:] for t in rome.get("tasks", [])[:2]]
                if tasks and len(" ; ".join(tasks)) > 130:
                    tasks = tasks[:1]
                if tasks:
                    st.lines.append("Au quotidien : " + " ; ".join(tasks) + ".")
                if c == code:
                    nxt = [self.rome_name(x) for x in rome.get("mobility_to", [])[:3]]
                    if nxt:
                        st.lines.append("Et après ? Tu pourras évoluer vers : "
                                        + ", ".join(nxt) + ".")
                    if rome.get("regulated"):
                        st.facts.append("⚖️ diplôme obligatoire")
        return dips, rts

    def route_source(self, name: str, code: str, near: tuple[float, float] | None,
                     situation: int | None) -> Source | None:
        _, rts = self.plan(name, code, near, situation)
        if not rts:
            return None
        lines = []
        for r in rts:
            steps = " → ".join(s.title for s in r.steps[1:])
            lines.append(f"{r.name} ({r.duration_text}) : {steps}."
                         + (f" {r.note}" if r.note else ""))
        return Source(f"Chemin vers {name} (calculé depuis l'offre ONISEP Région Sud et les "
                      "mobilités ROME de France Travail)", None, "\n".join(lines))

    # ---- deterministic facts (UI cards, comparison) ------------------------
    def facts(self, name: str, near: tuple[float, float] | None = None,
              report_zone: int | None = None) -> dict:
        job = self.job(name)
        code, cands = self.rome_for_job(job) if job else self.rome_for_name(name)
        rows = self.trainings(code, near=near, limit=500) if code else []
        zone = report_zone or (job["zone"] if job else None)
        rome = self.rome.get(code) if code else None
        onisep = self.onisep_by_rome.get(code, [])[:1] if code else []
        return {
            "name": job["label"] if job else name,
            "zone": zone,
            "zone_title": ZONES[zone][0] if zone in ZONES else None,
            "rome_code": code,
            "rome_label": rome["label"] if rome else None,
            "rome_url": rome["url"] if rome else None,
            "definition": rome["definition"] if rome else "",
            "regulated": bool(rome and rome["regulated"]),
            "riasec": rome["riasec"] if rome else "",
            "tasks": rome.get("tasks", []) if rome else [],
            "qualities": rome.get("qualities", []) if rome else [],
            "context": rome.get("context", {}) if rome else {},
            "diplomas": rome.get("diplomas", []) if rome else [],
            "candidates": [] if code else [
                {"code": c["code"], "label": self.rome[c["code"]]["label"],
                 "matched": c.get("matched_label") or self.rome[c["code"]]["label"],
                 "url": self.rome[c["code"]]["url"]}
                for c in cands[:3] if c.get("score", c.get("name", 0)) >= 0.6],
            "onisep_url": onisep[0]["url"] if onisep else None,
            "n_trainings": len(rows),
            "via_diplomas": bool(code and code in self.via_diplomas),
            "n_no_bac": sum(1 for f in rows if f["no_bac"]),
            "nearest": rows[0] if rows and rows[0]["distance_km"] is not None else None,
            "trainings": rows,
        }
