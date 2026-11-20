"""Build the compact JSON knowledge base used at runtime (data/processed/).

Inputs  : data/raw/ (run scripts/download_data.py first) + docs/table-metiers-onet-fr-jobzones.xlsx
Outputs : data/processed/rome.json        ROME 4.0 job sheets (definition, access, RIASEC, appellations)
          data/processed/onisep.json      ONISEP job sheets (name, link, ROME codes)
          data/processed/formations.json  geolocated initial training offer in Région Sud (PACA)
          data/processed/jobs.json        the Centre des Possibles job table, linked to ROME
"""

from __future__ import annotations

import csv
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import openpyxl  # noqa: E402

from coach.matching import JobMatcher, hybrid_candidates  # noqa: E402

RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
ROME_DIR = RAW / "rome"
JOB_TABLE = ROOT / "docs" / "table-metiers-onet-fr-jobzones.xlsx"
LHEO = "{http://lheo.gouv.fr/2.3}"

METIERSCOPE = "https://candidat.francetravail.fr/metierscope/fiche-metier/{code}"

# ONISEP/LHEO entry level codes, decoded from the dataset itself
ENTRY_LEVELS = {
    "0": "non renseigné",
    "1": "sans niveau spécifique",
    "12": "après la 3e",
    "13": "après une 2de ou un CAP",
    "14": "après le bac",
    "15": "après un bac + 2",
    "16": "après un bac + 3",
    "17": "après un bac + 5",
}
NO_BAC_ENTRY = {"1", "12", "13"}


def rome_csv(name: str) -> list[dict[str, str]]:
    path = ROME_DIR / f"unix_{name}_v462_utf8.csv"
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def build_rome() -> dict[str, dict]:
    rome: dict[str, dict] = {}
    for row in rome_csv("referentiel_code_rome"):
        code = row["code_rome"]
        rome[code] = {
            "code": code,
            "label": row["libelle_rome"],
            "regulated": row["emploi_reglemente"] == "O",
            "definition": "",
            "access": "",
            "riasec": "",
            "appellations": [],
            "url": METIERSCOPE.format(code=code),
        }
    texts: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    for row in rome_csv("texte"):
        texts[(row["code_rome"], row["libelle_type_texte"])].append(
            (int(row["position_phrase"] or 0), row["libelle_texte"]))
    for (code, kind), parts in texts.items():
        if code in rome:
            field = "definition" if kind == "definition" else "access"
            rome[code][field] = "\n".join(t.replace("''", "'") for _, t in sorted(parts))
    for row in rome_csv("referentiel_code_rome_riasec"):
        if row["code_rome"] in rome:
            rome[row["code_rome"]]["riasec"] = row["riasec_majeur"] + row["riasec_mineur"]
    for row in rome_csv("referentiel_appellation"):
        code = row["code_rome"]
        if code in rome and row.get("peu_usite") != "O":
            rome[code]["appellations"].append(row["libelle_appellation_long"])
    add_skills_and_context(rome)
    add_mobility(rome)
    return rome


def add_mobility(rome: dict[str, dict]) -> None:
    """Official ROME career moves: 'from' = jobs people come from to reach this one
    (used for the « passerelle » route), 'to' = where one can evolve next."""
    for code in rome:
        rome[code]["mobility_from"], rome[code]["mobility_to"] = [], []
    moves = sorted(rome_csv("rubrique_mobilite"), key=lambda r: int(r["numero_ordre"] or 99))
    for row in moves:
        src, dst = row["code_rome"], row["code_rome_cible"]
        if src in rome and dst in rome and src != dst:
            rome[dst]["mobility_from"].append(src)
            rome[src]["mobility_to"].append(dst)


DIPLOMA = re.compile(r"^(CAP|BEP|Bac|BP|BTS|BUT|DUT|Licence|Master|Mastère|Dipl[ôo]me|Titre|"
                     r"Certificat|DE |DEAES|Doctorat|Brevet|Mention compl)", re.IGNORECASE)


def add_skills_and_context(rome: dict[str, dict]) -> None:
    """ROME 4.0 « compétences » and « contextes de travail » for each job sheet.

    tasks        : savoir-faire, core ones (« Principale ») first
    qualities    : savoir-être professionnels
    knowledge    : savoirs (core first), without the diplomas
    diplomas     : diplomas/titles cited by France Travail in the « savoirs »
    context      : {type: [labels]} - schedules, working conditions, places, employers...
    """
    items = {r["code_ogr"]: r for r in rome_csv("item")}
    contexts = {r["code_ogr"]: r for r in rome_csv("referentiel_contexte_travail")}
    for sheet in rome.values():
        sheet.update(tasks=[], qualities=[], knowledge=[], diplomas=[], context={})
    for row in rome_csv("coherence_item"):
        sheet = rome.get(row["code_rome"])
        ogr = row["code_ogr"]
        if sheet is None:
            continue
        core = row["coeur_metier"] == "Principale"
        if ogr in contexts:
            c = contexts[ogr]
            sheet["context"].setdefault(c["libelle_type_cont_trav"], []).append(
                c["libelle_cont_travail"])
            continue
        it = items.get(ogr)
        if it is None:
            continue
        label, rubric = it["libelle"].strip(), it["code_rubrique"]
        if rubric == "1":
            sheet["tasks"].append((not core, label))
        elif rubric == "2":
            sheet["qualities"].append(label)
        elif rubric == "3":
            if DIPLOMA.match(label):
                sheet["diplomas"].append(label)
            else:
                sheet["knowledge"].append((not core, label))
    for sheet in rome.values():
        # stable order: core items first, then the order of the ROME file
        sheet["tasks"] = [lab for _, lab in sorted(sheet["tasks"], key=lambda t: t[0])][:10]
        knowledge = sorted(sheet["knowledge"], key=lambda t: t[0])
        sheet["knowledge"] = [lab for _, lab in knowledge][:8]
        sheet["qualities"] = sheet["qualities"][:6]
        sheet["diplomas"] = sheet["diplomas"][:8]


def build_onisep() -> list[dict]:
    jobs: dict[str, dict] = {}
    with (RAW / "onisep_metiers.csv").open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            url = row["lien site onisep.fr"]
            job = jobs.setdefault(url, {
                "label": row["libellé métier"],
                "url": url,
                "rome": [],
                "domains": row["domaine/sous-domaine"],
            })
            code = row["code ROME"].strip()
            if code and code not in job["rome"]:
                job["rome"].append(code)
    return list(jobs.values())


def _text(el: ET.Element | None, path: str) -> str:
    if el is None:
        return ""
    return (el.findtext(LHEO + path.replace("/", "/" + LHEO)) or "").strip()


def load_catalogue() -> dict[str, dict]:
    """ONISEP Idéo-Formations initiales en France, keyed by ONISEP id (FOR.xxxx).

    It has no location and no ROME code, but it completes the regional offer with the
    diploma type, the official duration, the RNCP level and the supervising ministry."""
    out: dict[str, dict] = {}
    with (RAW / "onisep_formations.csv").open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            m = re.search(r"FOR\.\d+", row["URL et ID Onisep"])
            if not m:
                continue
            ministry = row["tutelle"].strip()
            out[m.group()] = {
                "diploma_type": row["libellé type formation"].strip(),
                "diploma_short": row["sigle type formation"].strip(),
                "duration": row["durée"].strip(),
                "rncp": row["code RNCP"].strip(),
                "cert_level": row["libellé niveau de certification"].strip(),
                "ministry": "" if ministry == "non renseigné" else ministry,
            }
    return out


def build_formations() -> list[dict]:
    catalogue = load_catalogue()
    xml_path = next((RAW / "actions").glob("*.xml"))
    root = ET.parse(xml_path).getroot()
    out = []
    for f in root.iter(LHEO + "formation"):
        dom = f.find(LHEO + "domaine-formation")
        romes = [c.text for c in dom.iter(LHEO + "code-ROME")] if dom is not None else []
        action = f.find(LHEO + "action")
        if action is None:
            continue
        extras = {x.get("info"): (x.text or "") for x in action.iter(LHEO + "extra")}
        place = action.find(f"{LHEO}lieu-de-formation/{LHEO}coordonnees/{LHEO}adresse")
        entry = f.findtext(LHEO + "code-niveau-entree") or "0"
        geo = place.find(LHEO + "geolocalisation") if place is not None else None
        url = f.findtext(LHEO + "resultats-attendus", "").strip()
        fid = re.search(r"FOR\.\d+", url)
        cat = catalogue.get(fid.group(), {}) if fid else {}
        cycle = action.findtext(LHEO + "duree-cycle", "").strip()
        out.append({
            "id": f.get("numero"),
            "title": f.findtext(LHEO + "intitule-formation", "").strip(),
            "url": url,
            "rome": romes,
            "entry_code": entry,
            "entry": ENTRY_LEVELS.get(entry, "non renseigné"),
            "no_bac": entry in NO_BAC_ENTRY,
            "level": extras.get("NIVEAU_LIBELLE", ""),
            # official duration from the national catalogue, else the regional cycle length
            "duration": cat.get("duration") or (f"{cycle} an{'s' if cycle != '1' else ''}"
                                                if cycle else ""),
            "diploma_type": cat.get("diploma_type") or extras.get("TYPE_FORMATION_LIBELLE", ""),
            "housing": action.findtext(LHEO + "hebergement", "").strip(),
            "rhythm": action.findtext(LHEO + "rythme-formation", "").strip(),
            "diploma_short": cat.get("diploma_short", ""),
            "rncp": cat.get("rncp", ""),
            "cert_level": cat.get("cert_level", ""),
            "ministry": cat.get("ministry", ""),
            "school": _text(place, "denomination"),
            "status": extras.get("STATUT", ""),
            "school_type": extras.get("TYPE_ETABLISSEMENT", ""),
            "city": _text(place, "ville"),
            "postcode": _text(place, "codepostal"),
            "lat": float(_text(geo, "latitude") or 0) or None,
            "lon": float(_text(geo, "longitude") or 0) or None,
        })
    return out


def build_jobs(matcher: JobMatcher, rome: dict[str, dict]) -> list[dict]:
    wb = openpyxl.load_workbook(JOB_TABLE, read_only=True)
    ws = wb.worksheets[0]
    jobs = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        real_zone, onet, job_en, job_fr, desc, zone, justif = row[:7]
        if not onet or not job_fr:
            continue
        jobs.append({
            "onet": onet,
            "label": job_fr,
            "label_en": job_en,
            "description": desc or "",
            "zone": zone,
            "zone_note": justif or "",
            "zone_real": (real_zone or "").strip(),
        })

    # Semantic similarity between each job description and each ROME sheet
    print("  embedding ROME sheets and job descriptions (CPU, ~2 min) ...")
    from fastembed import TextEmbedding

    model = TextEmbedding("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    codes = list(rome)
    rome_docs = [f"{rome[c]['label']}. {' '.join(rome[c]['definition'].splitlines()[:3])}"
                 for c in codes]
    job_docs = [f"{j['label']}. {j['description'][:400]}" for j in jobs]
    r_emb = _unit(np.array(list(model.embed(rome_docs, batch_size=32))))
    j_emb = _unit(np.array(list(model.embed(job_docs, batch_size=32))))
    sims = j_emb @ r_emb.T

    for job, row in zip(jobs, sims):
        top = np.argsort(-row)[:10]
        semantic = [(codes[i], float(row[i])) for i in top]
        cands = hybrid_candidates(matcher, job["label"],
                                  matcher.search(job["label"], limit=10), semantic)
        job["rome_candidates"] = cands
        job["rome"] = cands[0]["code"] if cands and cands[0]["confident"] else None
    return jobs


def _unit(m: np.ndarray) -> np.ndarray:
    return m / np.linalg.norm(m, axis=1, keepdims=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rome = build_rome()
    onisep = build_onisep()
    formations = build_formations()
    matcher = JobMatcher.from_sources(rome, onisep)
    jobs = build_jobs(matcher, rome)

    def dump(name: str, data) -> None:
        path = OUT / name
        path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")
        print(f"  {name:18} {len(data):6} records  {path.stat().st_size // 1024} KB")

    dump("rome.json", rome)
    dump("onisep.json", onisep)
    dump("formations.json", formations)
    enriched = sum(1 for f in formations if f["diploma_type"])
    print(f"  formations enriched by the national ONISEP catalogue: {enriched}/{len(formations)}")
    dump("jobs.json", jobs)
    linked = sum(1 for j in jobs if j["rome"])
    print(f"  O*NET jobs confidently linked to ROME: {linked}/{len(jobs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
