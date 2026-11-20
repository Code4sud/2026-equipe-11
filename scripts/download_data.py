"""Download the open datasets used by the assistant into data/raw/.

Sources (all open data, Licence Ouverte / Etalab):
- ONISEP Idéo-Métiers            https://www.data.gouv.fr/datasets/ideo-metiers-onisep
- ONISEP Idéo-Formations init.   https://www.data.gouv.fr/datasets/ideo-formations-initiales-en-france
- ONISEP Idéo-Actions de formation PACA (LHEO, géolocalisées)
- France Travail ROME 4.0 (toutes les données, CSV)
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import httpx

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

SOURCES = {
    "onisep_metiers.csv":
        "https://data.onisep.fr/api/v1/downloads/5fa5949243f97/5fa5949243f97.csv",
    "onisep_formations.csv":
        "https://data.onisep.fr/api/v1/downloads/5fa591127f501/5fa591127f501.csv",
    "onisep_actions_paca.zip":
        "https://data.onisep.fr/api/v1/downloads/5fa4389e34b6a/5fa4389e34b6a.zip",
    "rome.zip":
        "https://api.francetravail.fr/api-nomenclatureemploi/v1/open-data/csv",
}


def download(name: str, url: str) -> Path:
    dest = RAW / name
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  ok (cached) {name}")
        return dest
    print(f"  downloading {name} ...")
    with httpx.stream("GET", url, follow_redirects=True, timeout=300) as r:
        r.raise_for_status()
        with dest.open("wb") as fh:
            for chunk in r.iter_bytes():
                fh.write(chunk)
    return dest


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        download(name, url)
    with zipfile.ZipFile(RAW / "rome.zip") as z:
        z.extractall(RAW / "rome")
    with zipfile.ZipFile(RAW / "onisep_actions_paca.zip") as z:
        z.extractall(RAW / "actions")
    print(f"Done -> {RAW}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
