"""Le Forum - web UI.   uv run streamlit run app.py"""

from __future__ import annotations

import html
import math
import re
from pathlib import Path

import altair as alt
import pydeck as pdk
import streamlit as st

from coach.assistant import CENTRE, ORIENTATION_SUD, RIASEC, Assistant, Profile
from coach.guide import METIERS_360
from coach.kb import CONTEXT_LABELS
from coach.llm import LLMError
from coach.pdf import Sheet, roadmap_pdf
from coach.report import ReportResults, read_report
from coach.roadmap import PREFS, SITUATIONS, STAGES, Route, next_rentree, rank, relevance
from coach.theme import CSS, EMPTY, HERO, LUMIERE_BLEUE, ROSE_NEON

ORS_FORMATIONS = ORIENTATION_SUD + "formations"

st.set_page_config(page_title="Équipe 11 — Hackathon Azuréen #3", page_icon="🧭", layout="wide")
st.html(CSS)
# Bandeau commun du hackathon (le numéro d'équipe est déjà renseigné)
st.html('<script src="https://orientation.code4sud.fr/bandeau.js" data-equipe="11"></script>',
        unsafe_allow_javascript=True)


@st.cache_resource
def get_bot() -> Assistant:
    return Assistant()


@st.cache_resource
def job_options() -> list[str]:
    """Every job a jeune can look up: the Centre's table + every ROME job."""
    names = {j["label"] for j in kb.jobs} | {r["label"] for r in kb.rome.values()}
    return sorted(names, key=str.lower)


bot = get_bot()
kb = bot.kb
ss = st.session_state
ss.setdefault("messages", [])      # [{"role", "content", "sources"}]
ss.setdefault("report_jobs", [])   # [(name, zone)] read from the PDF
ss.setdefault("extra_jobs", [])    # jobs the jeune added himself
ss.setdefault("focus", None)
ss.setdefault("report_name", None)
ss.setdefault("results", None)     # ReportResults of the uploaded PDF

# demo mode for the pitch: http://localhost:8501/?demo=1&job=Infirmier&city=Toulon&sit=0
# (uses the sample report in docs/, which is never published)
DEMO_PDF = Path(__file__).parent / "docs" / "rapport-des-possibles-2190.pdf"
if "demo" in st.query_params and DEMO_PDF.exists() and ss.report_name is None:
    demo = read_report(DEMO_PDF.read_bytes(), kb)
    ss.results, ss.report_jobs, ss.report_name = demo, demo.jobs, "demo"
    ss["city"] = st.query_params.get("city", "Nice")
    sit = st.query_params.get("sit")
    if sit in ("0", "1", "2", "3"):
        ss["situation"] = list(SITUATIONS)[int(sit)]
    ss.focus = st.query_params.get("job")
    if st.query_params.get("cmp"):  # e.g. &cmp=Infirmier|Coach sportif
        ss["cmp"] = st.query_params.get("cmp").split("|")


def esc(x: object) -> str:
    return html.escape(str(x or ""))


# --------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Ton profil")
    pdf = st.file_uploader("Ton Rapport des Possibles (PDF)", type="pdf",
                           help="Lu uniquement en mémoire, jamais enregistré ni envoyé.")
    if pdf is not None and pdf.file_id != ss.report_name:
        with st.spinner("Je lis ton rapport..."):
            res: ReportResults = read_report(pdf.getvalue(), kb)
        ss.results, ss.report_jobs, ss.report_name = res, res.jobs, pdf.file_id
        ss.focus, ss.messages = None, []
    if pdf is None and ss.report_name not in (None, "demo"):  # PDF removed: forget it
        ss.results, ss.report_jobs, ss.report_name = None, [], None
    res = ss.results
    if res is not None:
        if res.jobs:
            st.success(f"✅ Rapport lu : {len(res.jobs)} métiers"
                       + (", tes intérêts" if res.interests else "")
                       + (", tes aptitudes" if res.aptitudes else "")
                       + (" et ta personnalité" if res.personality else "") + ".")
        else:
            st.error("Je n'ai trouvé aucun métier dans ce PDF. Est-ce bien un "
                     "Rapport des Possibles ?")

    city = st.text_input("Ta ville (Région Sud)", placeholder="ex. Nice, Toulon, Marseille",
                         key="city")
    loc = kb.locate(city) if city else None
    if city and not loc:
        st.warning("Ville non trouvée dans l'offre de formation de la Région Sud.")
    ss.setdefault("situation", list(SITUATIONS)[-1])
    sit_label = st.selectbox("Où en es-tu ?", list(SITUATIONS), key="situation")
    situation = SITUATIONS[sit_label]
    if res is not None and res.riasec:
        letters = list(res.riasec)
        st.caption("Tes intérêts dominants (lus dans ton rapport) : "
                   + ", ".join(RIASEC[c][0] for c in letters))
    else:
        letters = st.multiselect("Tes intérêts dominants (facultatif)", list(RIASEC),
                                 format_func=lambda c: RIASEC[c][0], max_selections=3,
                                 placeholder="Choisis 1 à 3 intérêts")
    near = loc[:2] if loc else None

    st.divider()
    if st.button("🔄 Recommencer", width="stretch"):
        ss.messages, ss.focus, ss.extra_jobs = [], None, []
        st.rerun()
    st.caption(f"Modèle : `{bot.llm.model}` (open weight, en local)")

# the jeune's jobs: from the report + the ones he added (the report's zones are not shown)
my_jobs = list(dict.fromkeys([n for n, _ in ss.report_jobs] + ss.extra_jobs))
if ss.focus and ss.focus not in my_jobs:
    ss.extra_jobs.append(ss.focus)
    my_jobs.append(ss.focus)
added = [(n, None) for n in ss.extra_jobs if n not in dict(ss.report_jobs)]
profile = Profile(report_jobs=list(ss.report_jobs) + added,
                  city=loc[2] if loc else "",
                  has_bac=None if situation is None else situation >= 2,
                  situation=situation, riasec="".join(letters), results=res)

# --------------------------------------------------------------------- header
st.html(HERO)


def hbar(values: dict[str, float], color: str, maximum: float, unit: str) -> alt.Chart:
    """Horizontal bars with full labels (st.bar_chart cuts long names)."""
    data = [{"nom": k, "score": v} for k, v in values.items()]
    order = [d["nom"] for d in sorted(data, key=lambda d: -d["score"])]
    return alt.Chart(alt.Data(values=data)).mark_bar(
        color=color, cornerRadiusEnd=6, height=14).encode(
        x=alt.X("score:Q", scale=alt.Scale(domain=[0, maximum]), title=None,
                axis=alt.Axis(format="%" if unit == "%" else "d", grid=False)),
        y=alt.Y("nom:N", sort=order, title=None, axis=alt.Axis(labelLimit=260)),
        tooltip=[alt.Tooltip("nom:N", title=""), alt.Tooltip("score:Q", title=unit)],
    ).properties(height=34 * len(data) + 20).configure_view(strokeWidth=0)


if res is not None and (res.interests or res.aptitudes):
    with st.expander("📊 Ce que j'ai lu dans ton rapport", expanded=False):
        c1, c2 = st.columns(2)
        if res.interests:
            c1.markdown("**Tes intérêts professionnels**")
            c1.altair_chart(hbar(res.interests, ROSE_NEON, 1, "%"), width="stretch")
        if res.aptitudes:
            c2.markdown("**Tes aptitudes cognitives** (sur 8)")
            c2.altair_chart(hbar(res.aptitudes, LUMIERE_BLEUE, 8, "/ 8"), width="stretch")
            c2.caption("Une image à un instant T, pas une évaluation définitive.")
        if res.personality:
            st.markdown("**Tes traits de personnalité les plus marqués** : "
                        + ", ".join(list(res.personality)[:3]))


# --------------------------------------------------------------------- job picker
def _pick() -> None:
    ss.focus = ss.job_pill


def _add() -> None:
    name = ss.add_job
    if name:
        if name not in ss.extra_jobs and name not in dict(ss.report_jobs):
            ss.extra_jobs.append(name)
        ss.focus = name
    ss.add_job = None


st.html('<div class="cdp-section">Tes métiers</div>')
if my_jobs:
    ss.job_pill = ss.focus if ss.focus in my_jobs else None
    st.pills("Tes métiers", my_jobs, key="job_pill", on_change=_pick,
             label_visibility="collapsed")
c_add, _ = st.columns([2, 3])
c_add.selectbox("Un autre métier en tête ?", job_options(), index=None, key="add_job",
                on_change=_add, label_visibility="collapsed",
                placeholder="➕ Ajouter un autre métier : tape son nom…" if my_jobs
                else "🔎 Quel métier t'intrigue ? Tape son nom…")
if not my_jobs:
    st.html(EMPTY)


# --------------------------------------------------------------------- job page
def first_sentence(text: str, limit: int = 150) -> str:
    t = (text or "").split("\n")[0].strip()
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0] + "…"
    return t


def answer_card(col, question: str, answer: str, detail: str, mood: str = "") -> None:
    col.html(f'<div class="cdp-answer"><div class="q">{question}</div>'
             f'<div class="a {mood}">{answer}</div><div class="d">{detail}</div></div>')


def main_route(rts: list[Route]) -> Route | None:
    """The direct route (never the « passerelle »)."""
    return next((r for r in rts if not r.plus_experience), None)


def cap(t: str) -> str:
    return t[:1].upper() + t[1:]


def diploma_answer(f: dict, dips: list, rts: list[Route]) -> tuple[str, str, str]:
    r = main_route(rts)
    main = next((s for s in r.steps if s.kind == "course"), None) if r else None
    dip = next((d for d in dips if main and d.title == main.title), None)
    if dip:
        others = len(dips) - 1
        return (esc(cap(dip.title)),
                "<b>" + esc(" · ".join(x for x in (dip.level, dip.duration) if x)) + "</b>"
                + (" · obligatoire pour exercer" if f["regulated"] else "")
                + (f"<br>+ {others} autre(s) diplôme(s) dans « Ton chemin »" if others > 0
                   else ""), "")
    if f["diplomas"]:
        return (esc(f["diplomas"][0]), "cité par France Travail · aucune formation trouvée "
                "en Région Sud", "")
    return ("Je ne sais pas", "aucune formation reliée à ce métier en Région Sud", "maybe")


def bac_answer(f: dict, dips: list, rts: list[Route]) -> tuple[str, str, str]:
    no_bac = sorted((d for d in dips if d.no_bac),
                    key=lambda d: relevance(f["name"], d.title) < 80)
    detour = next((r for r in rts if r.plus_experience), None)
    if no_bac:
        d = no_bac[0]
        return ("Oui", "par exemple <b>" + esc(d.title) + f"</b> ({esc(d.duration)}), entrée "
                + esc(d.nearest["entry"]), "yes")
    if dips and detour:
        bridge = next(s for s in detour.steps if s.kind == "job")
        return ("Pas directement", "il faut le bac pour se former, mais il existe une "
                f"passerelle : devenir <b>{esc(bridge.title.lower())}</b> puis évoluer",
                "maybe")
    if dips:
        return ("Non", f"les <b>{sum(len(d.schools) for d in dips)}</b> formations de la "
                "Région Sud demandent le bac", "no")
    return ("Je ne sais pas", "aucune formation trouvée en Région Sud pour ce métier", "maybe")


def rome_choice(c: dict) -> str:
    """The name to use for a ROME « piste »: the job name found (« Plongeur en
    restauration ») when it surely points to that code, else the official label."""
    return c["matched"] if kb.rome_for_name(c["matched"])[0] == c["code"] else c["label"]


def use_rome(old: str, new: str) -> None:
    if new not in ss.extra_jobs:
        ss.extra_jobs.append(new)
    ss.focus = new
    if old in ss.get("cmp", []):
        ss.cmp = list(dict.fromkeys(new if n == old else n for n in ss.cmp))


def rome_pistes(f: dict, key: str) -> None:
    """Uncertain job: let the jeune pick the right official job instead of guessing."""
    st.warning(f"Je n'ai pas trouvé de correspondance sûre pour « {f['name']} » dans le "
               "répertoire officiel des métiers (France Travail), donc je préfère ne rien "
               "inventer. **Tu pensais à l'un de ces métiers ?**")
    cols = st.columns(len(f["candidates"]) or 1)
    for col, c in zip(cols, f["candidates"]):
        alt_name = rome_choice(c)
        col.button(f"👉 {alt_name}", key=f"{key}-{c['code']}", width="stretch",
                   on_click=use_rome, args=(f["name"], alt_name),
                   help=f"Fiche ROME {c['code']} : {c['label']}")


def job_page(f: dict, dips: list, rts: list[Route]) -> None:
    """The 4 questions of the jeune, answered from the data, before any chat."""
    badges = []
    if f["regulated"]:
        badges.append('<span class="cdp-badge">⚖️ métier réglementé</span>')
    if f["name"] in dict(ss.report_jobs):
        badges.append('<span class="cdp-badge">📄 dans ton rapport</span>')
    st.html(f'<div class="cdp-job"><h2>{esc(f["name"])}</h2>{"".join(badges)}</div>')
    if not f["rome_code"]:
        rome_pistes(f, "alt")
        return
    c1, c2, c3, c4 = st.columns(4)
    answer_card(c1, "🔎 C'est quoi ?", esc(f["rome_label"]),
                esc(first_sentence(f["definition"])))
    answer_card(c2, "🎓 Quel diplôme ?", *diploma_answer(f, dips, rts))
    answer_card(c3, "🔓 Sans le bac ?", *bac_answer(f, dips, rts))
    sal = (f"<a href='{esc(f['onisep_url'])}' target='_blank'>fiche ONISEP</a> (rubrique "
           "salaire)" if f["onisep_url"] else "un conseiller du Centre des Possibles")
    answer_card(c4, "💶 Combien on gagne ?", "Je ne sais pas encore",
                f"pas de source officielle fiable intégrée : je préfère ne rien inventer. "
                f"Regarde la {sal}.", "maybe")

    links = [("Fiche métier France Travail", f["rome_url"])]
    if f["onisep_url"]:
        links.append(("Fiche ONISEP", f["onisep_url"]))
    links += [("Formations sur Orientation Région Sud", ORS_FORMATIONS),
              ("🎥 Vidéos Métiers 360", METIERS_360)]
    st.html('<div class="cdp-links">' + "".join(
        f'<a href="{esc(u)}" target="_blank">{esc(t)} ↗</a>' for t, u in links) + "</div>")
    daily_life(f)


def daily_life(f: dict) -> None:
    """« C'est quoi concrètement ? » straight from ROME 4.0 (skills + work context)."""
    if not f["tasks"]:
        return
    with st.expander("🔎 Le quotidien, les horaires, les conditions de travail "
                     "(France Travail)", expanded=False):
        c1, c2 = st.columns([3, 2])
        c1.markdown("**Au quotidien**\n" + "\n".join(f"- {t}" for t in f["tasks"][:6]))
        if f["qualities"]:
            c1.markdown("**Qualités attendues** : " + " · ".join(f["qualities"]))
        ctx = f["context"]
        for key, icon in (("Horaires et durée du travail", "🕒"),
                          ("Conditions de travail et risques professionnels", "🦺"),
                          ("Lieux et déplacements", "🚗"),
                          ("Types de structures", "🏢")):
            if ctx.get(key):
                c2.markdown(f"{icon} **{CONTEXT_LABELS[key]}**  \n"
                            + " · ".join(ctx[key][:5]))
        if f["diplomas"]:
            c2.markdown("🎓 **Diplômes cités**  \n" + " · ".join(f["diplomas"][:4]))


def route_html(r: Route) -> str:
    parts = []
    long_ = len(r.steps) >= 5  # narrow boxes: keep only the key chips
    keep = ("entrée", "✓", "sans le bac", "🏠")
    for st_ in r.steps:
        when = f'<div class="when">{esc(st_.when)}</div>' if st_.when else ""
        detail = esc(st_.detail.split("  \n")[0] if st_.kind == "course" else st_.detail)
        chips = "".join(
            f'<span class="chip{" ok" if c.startswith("✓") or c == "sans le bac" else ""}">'
            f'{esc(c)}</span>' for c in st_.facts
            if not long_ or c.startswith(keep) or st_.kind == "job")
        lines = "".join(f'<div class="line">{esc(x)}</div>' for x in st_.lines)
        link = (f'<a href="{esc(st_.url)}" target="_blank">fiche ONISEP ↗</a>' if st_.url else "")
        parts.append(f'<div class="cdp-step {st_.kind}">{when}<b>{esc(st_.title)}</b>'
                     f'<span>{detail}</span>'
                     + (f'<div class="chips">{chips}</div>' if chips else "")
                     + f'{lines}{link}</div>')
    steps = '<div class="cdp-arrow">→</div>'.join(parts)
    note = f'<div class="cdp-note">ℹ️ {esc(r.note)}</div>' if r.note else ""
    ends = ""
    if r.ends and situation is not None:
        what = "premier diplôme" if r.plus_experience else "diplômé·e"
        ends = (f'<span class="ends"> · {what} vers {esc(r.ends)} si tu commences à la '
                f'rentrée {next_rentree()}</span>')
    return (f'<div class="cdp-route"><h4>{esc(r.name)}</h4>'
            f'<span class="len">{esc(r.duration_text)}</span>{ends}'
            f'<div class="cdp-steps{" long" if long_ else ""}">{steps}</div>{note}</div>')


def staircase(dips: list, situation: int | None, job: str) -> None:
    """Every diploma leading to the job, by the moment you can start it."""
    used = [i for i in range(len(STAGES)) if any(d.stage == i for d in dips)]
    cols = st.columns(len(used))
    for col, i in zip(cols, used):
        here = situation == i
        col.html(f'<div class="cdp-stage{" here" if here else ""}">'
                 f'{"📍 Toi · " if here else ""}{STAGES[i][0]}</div>')
        here_dips = sorted((d for d in dips if d.stage == i),
                           key=lambda d: relevance(job, d.title) < 80)
        for d in here_dips[:6]:
            n = d.nearest
            tags = [f'<span class="cdp-tag">{esc(x)}</span>'
                    for x in (d.kind, d.duration, d.level) if x]
            if d.no_bac:
                tags.append('<span class="cdp-tag green">sans le bac</span>')
            tags.append(f'<span class="cdp-tag pink">{len(d.schools)} établ. '
                        f'({d.n_public} public{"s" if d.n_public > 1 else ""})</span>')
            if d.boarding:
                tags.append('<span class="cdp-tag">🏠 internat</span>')
            near_txt = (f"<br>📍 le plus proche : <b>{esc(n['city'])}</b> "
                        f"({n['distance_km']:.0f} km)" if n.get("distance_km") is not None else "")
            var = f" · {len(d.variants)} spécialités" if len(d.variants) > 1 else ""
            col.html(f'<div class="cdp-dip"><b>{esc(d.title)}</b>{var}<br>{"".join(tags)}'
                     f'{near_txt}<br><a href="{esc(n["url"])}" target="_blank">fiche ONISEP ↗'
                     f'</a></div>')


def feuille_pdf(f: dict, dips: list, rts: list[Route], picks: list) -> bytes:
    """« Ma feuille de route » (PDF): the same facts as the page, to keep or print."""
    ctx = f["context"]
    sheet = Sheet(
        job=f["name"], definition=first_sentence(f["definition"], 420),
        answers=[("Quel diplôme ?", *diploma_answer(f, dips, rts)),
                 ("Sans le bac ?", *bac_answer(f, dips, rts)),
                 ("Combien on gagne ?", "Je ne sais pas encore",
                  "pas de source officielle intégrée : regarde la fiche ONISEP du métier "
                  "(rubrique salaire)", "maybe")],
        routes=rts, picks=picks, tasks=f["tasks"],
        context=[(CONTEXT_LABELS[k], " · ".join(ctx[k][:4])) for k in (
            "Horaires et durée du travail", "Conditions de travail et risques professionnels",
            "Types de structures") if ctx.get(k)],
        situation=sit_label if situation is not None else "",
        city=profile.city,
        links=[(t, u) for t, u in (
            ("Fiche métier France Travail", f["rome_url"]), ("Fiche ONISEP", f["onisep_url"]),
            ("Formations sur Orientation Région Sud", ORS_FORMATIONS),
            ("Vidéos de métiers (Métiers 360)", METIERS_360),
            ("Centre des Possibles", CENTRE)) if u],
        qr_url=f["onisep_url"] or f["rome_url"] or "",
        qr_label="fiche métier ONISEP" if f["onisep_url"] else "fiche métier France Travail")
    return roadmap_pdf(sheet)


def frame(pts: list[list[float]]) -> pdk.ViewState:
    """Centre and zoom so that every point fits in a ~550 x 470 px map."""
    lons, lats = [p[0] for p in pts], [p[1] for p in pts]
    span_lon = max(max(lons) - min(lons), 0.05) * 1.35
    span_lat = max(max(lats) - min(lats), 0.05) * 1.35 / math.cos(math.radians(43.5))
    # deck.gl zoom z shows 360 / 2^z degrees per 512 px
    zoom = min(math.log2(550 / 512 * 360 / span_lon), math.log2(470 / 512 * 360 / span_lat))
    return pdk.ViewState(latitude=(max(lats) + min(lats)) / 2,
                         longitude=(max(lons) + min(lons)) / 2, zoom=max(6.0, min(zoom, 11.5)))


PINK, LILAC, WHITE = [224, 52, 155, 240], [93, 98, 234, 220], [255, 255, 255, 255]
TOOLTIP = {"text": "{tip}", "style": {  # plain text: Streamlit escapes HTML in tooltips
    "backgroundColor": "#1b1b62", "color": "#f3f3fe", "fontSize": "14px", "whiteSpace": "pre-line",
    "borderRadius": "12px", "border": "1px solid #5d62ea", "padding": "8px 10px"}}


def plain_tip(tip: str) -> str:
    """The hover text without tags: line breaks kept, entities decoded."""
    return html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"<br\s*/?>", "\n", tip or "")))


def dots(layer_id: str, rows: list, r_m: int, r_min: int, r_max: int,
         outline: list) -> pdk.Layer:
    """Dots sized in metres, clamped in pixels (Streamlit's deck.gl ignores pixel units)."""
    rows = [{**r, "tip": plain_tip(r.get("tip", ""))} for r in rows]
    return pdk.Layer("ScatterplotLayer", rows, id=layer_id, get_position=["lon", "lat"],
                     get_fill_color="color", get_radius=r_m, radius_min_pixels=r_min,
                     radius_max_pixels=r_max, stroked=True, get_line_color=outline,
                     line_width_min_pixels=1.5, pickable=True)


def labels(layer_id: str, rows: list, size: int = 14, offset: list | None = None,
           color: list | None = None) -> pdk.Layer:
    return pdk.Layer("TextLayer", rows, id=layer_id, get_position=["lon", "lat"],
                     get_text="label", get_size=size, get_color=color or [255, 255, 255],
                     get_pixel_offset=offset or [0, 0])


def home_layers(near: tuple[float, float]) -> list[pdk.Layer]:
    home = [{"lat": near[0], "lon": near[1], "tip": "<b>Toi</b>", "label": "Toi",
             "color": WHITE}]
    return [dots("home", home, 900, 8, 11, PINK), labels("home-label", home, 15, [0, -22], [27, 27, 98])]


def spots_of(rows: list) -> list[dict]:
    """One spot per school address, with all its courses."""
    spots: dict[tuple, dict] = {}
    for r in rows:
        if not r["lat"]:
            continue
        p = spots.setdefault((round(r["lat"], 4), round(r["lon"], 4)), {
            "lat": r["lat"], "lon": r["lon"], "school": r["school"], "city": r["city"],
            "km": r["distance_km"], "courses": []})
        if all(c["title"] != r["title"] for c in p["courses"]):
            p["courses"].append({"title": r["title"], "url": r["url"], "duration": r["duration"],
                                 "entry": r["entry"], "no_bac": r["no_bac"],
                                 "status": r["status"],
                                 "housing": "internat" in (r.get("housing") or "")})
    for p in spots.values():
        km = f" · {p['km']:.0f} km" if p["km"] is not None else ""
        more = f"<br>+ {len(p['courses']) - 3} autre(s)" if len(p["courses"]) > 3 else ""
        p["tip"] = (f"<b>{esc(p['school'])}</b><br>{esc(p['city'])}{km}<br>"
                    + "<br>".join("• " + esc(c["title"]) for c in p["courses"][:3]) + more
                    + "<br><i>Clique pour le détail</i>")
    return list(spots.values())


def spot_card(p: dict) -> None:
    """What a click on the map shows: the school and every course it offers for this job."""
    km = f" · <strong>{p['km']:.0f} km</strong>" if p.get("km") is not None else ""
    items = []
    for c in p.get("courses", []):
        tags = [esc(x) for x in (c["duration"], c["entry"], c["status"]) if x]
        extra = ('<span class="cdp-tag green">sans le bac</span>' if c["no_bac"] else "") + (
            '<span class="cdp-tag">🏠 internat</span>' if c["housing"] else "")
        items.append(f'<li><a href="{esc(c["url"])}" target="_blank">{esc(c["title"])} ↗</a>'
                     f'<br><small>{" · ".join(tags)}</small> {extra}</li>')
    st.html(f'<div class="cdp-spot"><b>📍 {esc(p.get("school"))}</b>'
            f'<div class="where">{esc(p.get("city"))}{km}</div><ul>{"".join(items)}</ul></div>')


def course_map(ranked: list, near: tuple[float, float] | None, key: str, n_top: int = 3) -> None:
    """One dot per school; the « Pour toi » picks numbered in pink; « Toi » in white.
    Hover = quick look, click = every course of the school below the map."""
    data = spots_of([r for _, _, r in ranked])
    pick_rank = {}
    for i, (_, _, r) in enumerate(ranked[:n_top]):
        pick_rank.setdefault((round(r["lat"] or 0, 4), round(r["lon"] or 0, 4)), i + 1)
    for p in data:
        rank_ = pick_rank.get((round(p["lat"], 4), round(p["lon"], 4)))
        p["label"] = str(rank_) if rank_ else ""
        p["color"] = PINK if rank_ else LILAC
        if rank_:
            p["tip"] = f"<b>⭐ Choix n°{rank_}</b><br>" + p["tip"]
    tops = [p for p in data if p["label"]]
    view_all = True
    if near:
        view = st.segmented_control("Vue", ["Autour de moi", "Toute la région"],
                                    default="Autour de moi", key=f"view-{key}",
                                    label_visibility="collapsed")
        view_all = view == "Toute la région"
    layers = (home_layers(near) if near else []) + [
        dots("others", [p for p in data if not p["label"]], 700, 5, 9, [255, 255, 255, 150]),
        dots("picks", tops, 1500, 11, 16, WHITE), labels("pick-labels", tops)]
    pts = [[p["lon"], p["lat"]] for p in data]
    if near:
        pts = pts + [[near[1], near[0]]] if view_all else \
            [[near[1], near[0]]] + ([[p["lon"], p["lat"]] for p in tops] or pts)
    event = st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=frame(pts),
                                     map_style=None, tooltip=TOOLTIP),
                            height=470, on_select="rerun", selection_mode="single-object",
                            key=f"map-{key}-{view_all}")
    st.html('<div class="cdp-legend"><span><i style="background:#e0349b"></i>Pour toi '
            '(numérotées)</span><span><i style="background:#5d62ea"></i>Autres '
            'établissements</span>' + ('<span><i style="background:#fff;border:3px solid '
                                       '#e0349b"></i>Toi</span>' if near else "")
            + "</div>")
    chosen = next((o for objs in (event.selection.get("objects") or {}).values() for o in objs
                   if o.get("courses")), None) if event else None
    if chosen:
        spot_card(chosen)
    else:
        st.caption("👆 Clique sur un point pour voir toutes ses formations.")


focus_facts = kb.facts(ss.focus, near, dict(ss.report_jobs).get(ss.focus)) if ss.focus else None
dips, rts = ([], [])
if focus_facts and focus_facts["rome_code"]:
    dips, rts = kb.plan(focus_facts["name"], focus_facts["rome_code"], near, situation)
if focus_facts:
    job_page(focus_facts, dips, rts)
elif my_jobs:
    st.info("👆 Clique sur un de tes métiers pour voir ce que c'est, quel diplôme il faut et "
            "le chemin pour y arriver. Ou pose une question dans l'onglet 💬.")

tab_road, tab_map, tab_chat, tab_cmp = st.tabs(
    ["🧭 Ton chemin", "📍 Où te former ?", "💬 Pose ta question", "⚖️ Comparer"])

# --------------------------------------------------------------------- where to train
# computed first: the « Pour toi » picks also go into the downloadable roadmap
ranked, rows, picks = [], [], []
if focus_facts and focus_facts["rome_code"]:
    f = focus_facts
    with tab_map:
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        prefs = c1.pills("Ce qui compte pour toi", list(PREFS), format_func=PREFS.get,
                         selection_mode="multi", key="prefs") or []
        has_no_bac = any(r["no_bac"] for r in f["trainings"])
        detour = next((r for r in rts if r.plus_experience), None)
        only_no_bac = c2.toggle("Seulement sans le bac",
                                value=situation in (0, 1) and (has_no_bac or detour is not None))
    rows = [r for r in f["trainings"] if r["no_bac"] or not only_no_bac]
    bridge_info = None
    if only_no_bac and not rows and detour:
        bridge = next(s for s in detour.steps if s.kind == "job")
        bridge_info = bridge.title
        code_b = next(c for c in kb.rome[f["rome_code"]]["mobility_from"]
                      if kb.rome_name(c) == bridge.title)
        rows = kb.trainings(code_b, near=near, no_bac=True, limit=500)
    ranked = rank(rows, situation, set(prefs), near is not None, f["name"])
    picks = ranked[:3]

with tab_map:
    if not focus_facts:
        st.info("Choisis un métier ci-dessus pour voir les formations qui y mènent.")
    elif not focus_facts["rome_code"]:
        st.warning("Pas de correspondance sûre avec le ROME pour ce métier : "
                   "je préfère ne rien inventer.")
    elif not rows:
        st.warning("Aucune formation trouvée dans l'offre ONISEP de la Région Sud pour ce "
                   f"filtre. Regarde aussi [Orientation Région Sud]({ORS_FORMATIONS}).")
    else:
        if bridge_info:
            st.info(f"Toutes les formations de « {focus_facts['name']} » demandent le bac. "
                    f"Voici celles de la passerelle sans le bac : devenir **{bridge_info}** "
                    "d'abord (voir « Ton chemin »).")
        left, right = st.columns([2, 3])
        with left:
            st.markdown("##### ⭐ Pour toi")
            if near is None:
                st.caption("Indique ta ville à gauche pour que je tienne compte de la distance.")
            for i, (_, why, r) in enumerate(picks):
                km = (f" · <strong>{r['distance_km']:.0f} km</strong>"
                      if r["distance_km"] is not None else "")
                st.html(
                    f'<div class="cdp-pick"><span class="rank">N°{i + 1}</span>'
                    f'<b>{esc(r["title"])}</b><div class="where">{esc(r["school"])}<br>'
                    f'<strong>{esc(r["city"])}</strong>{km} · {esc(r["duration"])}</div>'
                    + "".join(f'<span class="cdp-tag green">{esc(w)}</span>' for w in why)
                    + f'<br><a href="{esc(r["url"])}" target="_blank">fiche ONISEP ↗</a></div>')
            st.caption("Classées par des règles simples, pas par une IA : accessible depuis ta "
                       "situation, distance, public, diplôme reconnu, durée.")
        with right:
            course_map(ranked, near, re.sub(r"\W+", "-", focus_facts["name"]))
        with st.expander(f"📋 Comparer toutes les formations ({len(ranked)})"):
            st.dataframe(
                [{"Pour toi": score, "Formation": r["title"], "Pourquoi": ", ".join(why),
                  "Durée": r["duration"], "Entrée": r["entry"], "Niveau": r["level"],
                  "Établissement": r["school"], "Ville": r["city"],
                  "Distance (km)": r["distance_km"], "Statut": r["status"],
                  "Internat": "oui" if "internat" in r["housing"] else "",
                  "Reconnu (RNCP)": "oui" if r["rncp"] else "non", "Fiche ONISEP": r["url"]}
                 for score, why, r in ranked],
                column_config={
                    "Fiche ONISEP": st.column_config.LinkColumn(display_text="voir"),
                    "Pour toi": st.column_config.ProgressColumn(
                        format="%d", min_value=0, max_value=max(s for s, _, _ in ranked) or 1)},
                hide_index=True, width="stretch")
        st.caption("Sources : ONISEP, Idéo-Actions de formation Provence-Alpes-Côte d'Azur "
                   "et Idéo-Formations initiales en France (open data). Dates, places et "
                   f"apprentissage : [Orientation Région Sud]({ORS_FORMATIONS}).")

# --------------------------------------------------------------------- roadmap
with tab_road:
    if not focus_facts:
        st.info("Choisis un métier ci-dessus : je te montre le chemin pour y arriver.")
    elif not focus_facts["rome_code"]:
        st.warning("Sans correspondance sûre dans le ROME, je ne peux pas tracer de chemin "
                   "fiable pour ce métier. Les pistes sont indiquées plus haut.")
    elif not rts:
        st.warning("Je n'ai trouvé aucune formation reliée à ce métier dans l'offre ONISEP de "
                   f"la Région Sud. Regarde la fiche métier ou [Orientation Région Sud]"
                   f"({ORS_FORMATIONS}).")
    else:
        if situation is None:
            st.info("💡 Dis-moi **où tu en es** (à gauche) pour que je calcule le chemin à "
                    "partir de ta situation.")
        st.html("".join(route_html(r) for r in rts))
        slug = re.sub(r"[^a-z0-9]+", "-", focus_facts["name"].lower()).strip("-")
        st.download_button("📄 Télécharger ma feuille de route (PDF)",
                           feuille_pdf(focus_facts, dips, rts, picks),
                           file_name=f"feuille-de-route-{slug}.pdf", mime="application/pdf",
                           type="primary",
                           help="Un PDF à garder, imprimer ou montrer à un conseiller.")
        st.markdown("##### Tous les diplômes qui mènent à ce métier en Région Sud")
        staircase(dips, situation, focus_facts["name"])
        st.caption("Calculé à partir de l'offre ONISEP de la Région Sud et des mobilités du "
                   "ROME 4.0 (France Travail). Les durées sont indicatives.")

# --------------------------------------------------------------------- chat
with tab_chat:
    for m in ss.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("sources"):
                with st.expander(f"📚 Sources ({len(m['sources'])})"):
                    for i, (title, url) in enumerate(m["sources"], 1):
                        st.markdown(f"[{i}] [{title}]({url})" if url else f"[{i}] {title}")

    suggestions = []
    if ss.focus:
        suggestions = [f"Comment je deviens {ss.focus.lower()} ?",
                       "C'est quoi une journée type ?",
                       "Quelle différence entre ces formations ?",
                       "Je peux le faire sans le bac ?"]
    elif ss.report_jobs:
        suggestions = ["Explique-moi mes résultats",
                       "Pourquoi on me propose ces métiers ?",
                       "Quels métiers de mon rapport sont accessibles sans le bac ?",
                       "Lesquels correspondent le plus à mes intérêts ?"]
    clicked = None
    if suggestions:
        cols = st.columns(len(suggestions))
        for i, s in enumerate(suggestions):
            if cols[i].button(s, key=f"sugg-{i}", width="stretch"):
                clicked = s

    question = st.chat_input("Pose ta question (ex. : c'est quoi un musicothérapeute ?)") or clicked
    if question:
        ss.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)
        history = [{"role": m["role"], "content": m["content"]} for m in ss.messages[:-1]]
        turn, stream = bot.answer(question, profile, history, ss.focus)
        with st.chat_message("assistant"):
            try:
                answer = st.write_stream(stream)
            except LLMError as exc:
                answer = ("⚠️ Le modèle ne répond pas pour le moment. Vérifie qu'Ollama tourne "
                          f"(`ollama serve`).\n\n`{exc}`")
                st.markdown(answer)
            sources = [(s.title, s.url) for s in turn.sources]
            if sources:
                with st.expander(f"📚 Sources ({len(sources)})"):
                    for i, (title, url) in enumerate(sources, 1):
                        st.markdown(f"[{i}] [{title}]({url})" if url else f"[{i}] {title}")
        ss.messages.append({"role": "assistant", "content": answer, "sources": sources})
        if turn.jobs and turn.jobs[0] != ss.focus:
            ss.focus = turn.jobs[0]
            st.rerun()

# --------------------------------------------------------------------- compare
JOB_COLORS = [([224, 52, 155, 235], "#e0349b"), ([93, 98, 234, 235], "#7d82ff"),
              ([56, 166, 120, 235], "#38a678")]


def job_summary(name: str) -> tuple[dict, list, list[Route]]:
    f = kb.facts(name, near, dict(ss.report_jobs).get(name))
    dips, rts = kb.plan(f["name"], f["rome_code"], near, situation) if f["rome_code"] else ([], [])
    return f, dips, rts


def cell(value: str, detail: str = "", mood: str = "", best: str = "") -> str:
    star = f'<span class="best">⭐ {best}</span>' if best else ""
    return (f'<td><div class="v {mood}">{value}</div>{star}'
            + (f'<div class="d">{detail}</div>' if detail else "") + "</td>")


def compare_table(items: list[tuple[dict, list, list[Route]]]) -> str:
    """Rows = the jeune's questions, columns = the jobs; the best value of a row is starred."""
    routes_ = [main_route(r) for _, _, r in items]
    years = [r.total_years if r and r.total_years else None for r in routes_]
    kms = [round(f["nearest"]["distance_km"]) if f["nearest"] else None for f, _, _ in items]
    best_y = min((y for y in years if y), default=None)
    best_km = min((k for k in kms if k is not None), default=None)
    several = len(items) > 1
    mine = set(profile.riasec)
    head = "".join(f'<th><i style="background:{JOB_COLORS[i][1]}"></i>{esc(f["name"])}</th>'
                   for i, (f, _, _) in enumerate(items))
    rows = {k: [] for k in ("🎓 Diplôme le plus direct", "⏱️ Durée depuis ta situation",
                            "🔓 Sans le bac ?", "📍 Formation la plus proche",
                            "🏫 Formations en Région Sud", "🕒 Horaires",
                            "💡 Intérêts en commun avec toi", "⚖️ Métier réglementé")}
    for i, (f, dips, rts) in enumerate(items):
        if not f["rome_code"]:
            for k in rows:
                rows[k].append(cell("—", "métier à préciser (voir les pistes en dessous)")
                               if k.startswith("🎓") else cell("—"))
            continue
        ans, det, mood = diploma_answer(f, dips, rts)
        rows["🎓 Diplôme le plus direct"].append(cell(ans, det.split("<br>")[0], mood))
        r = routes_[i]
        rows["⏱️ Durée depuis ta situation"].append(
            cell(esc(r.duration_text), "" if situation is not None else "dis-moi où tu en es",
                 best="le plus court" if several and years[i] == best_y else "") if r
            else cell("Je ne sais pas", "aucune formation trouvée en Région Sud", "maybe"))
        rows["🔓 Sans le bac ?"].append(cell(*bac_answer(f, dips, rts)))
        if f["nearest"]:
            n = f["nearest"]
            rows["📍 Formation la plus proche"].append(cell(
                f"{esc(n['city'])} · {n['distance_km']:.0f} km", esc(n["title"]),
                best="le plus proche" if several and kms[i] == best_km else ""))
        elif f["n_trainings"]:
            rows["📍 Formation la plus proche"].append(cell("—", "indique ta ville à gauche"))
        else:
            rows["📍 Formation la plus proche"].append(cell("Aucune en Région Sud", "", "maybe"))
        pub = sum(1 for t in f["trainings"] if t["status"] == "public")
        rows["🏫 Formations en Région Sud"].append(cell(
            str(f["n_trainings"]), f"dont {pub} dans le public" if f["n_trainings"] else "",
            "" if f["n_trainings"] else "maybe"))
        hours = f["context"].get("Horaires et durée du travail", [])
        rows["🕒 Horaires"].append(cell(esc(" · ".join(hours[:3])) or "—"))
        common = [RIASEC[c][0] for c in f["riasec"] if c in mine]
        rows["💡 Intérêts en commun avec toi"].append(
            cell(", ".join(common) or "aucun", "") if mine else
            cell("—", "renseigne tes intérêts à gauche"))
        rows["⚖️ Métier réglementé"].append(cell("Oui" if f["regulated"] else "Non",
                                                 "diplôme obligatoire" if f["regulated"] else ""))
    body = "".join(f'<tr><th class="k">{k}</th>{"".join(v)}</tr>' for k, v in rows.items())
    return (f'<div class="cdp-cmp-wrap"><table class="cdp-cmp"><thead><tr><th></th>{head}'
            f'</tr></thead><tbody>{body}</tbody></table></div>')


def compare_map(items: list[tuple[dict, list, list[Route]]]) -> None:
    """The 5 closest (or best) schools of each compared job, one colour per job."""
    layers, pts, legend = [], [], []
    for i, (f, _, _) in enumerate(items):
        if not f["trainings"]:
            continue
        ranked_f = rank(f["trainings"], situation, set(), near is not None, f["name"])[:5]
        data = spots_of([r for _, _, r in ranked_f])
        for p in data:
            p["color"] = JOB_COLORS[i][0]
            p["tip"] = f"<b style='color:{JOB_COLORS[i][1]}'>{esc(f['name'])}</b><br>" + p["tip"]
        layers.append(dots(f"job{i}", data, 1100, 7, 13, WHITE))
        pts += [[p["lon"], p["lat"]] for p in data]
        legend.append(f'<span><i style="background:{JOB_COLORS[i][1]}"></i>'
                      f'{esc(f["name"])}</span>')
    if not layers:
        return
    if near:
        layers = home_layers(near) + layers
        pts.append([near[1], near[0]])
    st.markdown("##### 🗺️ Où te former pour chacun")
    event = st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=frame(pts),
                                     map_style=None, tooltip=TOOLTIP),
                            height=420, on_select="rerun", selection_mode="single-object",
                            key="map-cmp-" + "-".join(re.sub(r"\W+", "", f["name"])
                                                      for f, _, _ in items))
    st.html('<div class="cdp-legend">' + "".join(legend)
            + ('<span><i style="background:#fff;border:3px solid #e0349b"></i>Toi</span>'
               if near else "") + "</div>")
    chosen = next((o for objs in (event.selection.get("objects") or {}).values() for o in objs
                   if o.get("courses")), None) if event else None
    if chosen:
        spot_card(chosen)
    else:
        st.caption("Les 5 formations les mieux placées pour toi, par métier. 👆 Clique sur un "
                   "point pour le détail.")


with tab_cmp:
    ss.setdefault("cmp", [n for n in [ss.focus] if n in my_jobs])
    ss.cmp = [n for n in ss.cmp if n in my_jobs]
    st.multiselect("Choisis 2 ou 3 de tes métiers à comparer", my_jobs, key="cmp",
                   max_selections=3, placeholder="Choisis des métiers")
    chosen_jobs = ss.cmp
    if len(chosen_jobs) < 2:
        st.info("Choisis au moins 2 métiers pour les comparer côte à côte : diplôme, durée, "
                "sans le bac, distance, horaires.")
    else:
        items = [job_summary(n) for n in chosen_jobs]
        st.html(compare_table(items))
        for f, _, _ in items:
            if not f["rome_code"]:
                rome_pistes(f, f"cmp-{f['name']}")
        if any(f["via_diplomas"] for f, _, _ in items):
            st.caption("Pour certains métiers, les formations ont été trouvées à partir des "
                       "diplômes que France Travail cite dans la fiche métier.")
        compare_map(items)
        st.caption("Le salaire n'est pas encore dans mes sources : regarde la fiche ONISEP du "
                   "métier ou demande au Centre des Possibles.")

st.divider()
st.caption("Les résultats du Rapport des Possibles sont des pistes de réflexion, pas un verdict. "
           f"Pour en parler avec quelqu'un : [Centre des Possibles]({CENTRE}).")
