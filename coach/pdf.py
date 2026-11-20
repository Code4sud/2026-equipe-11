"""« Ma feuille de route » as a printable A4 PDF, in the Centre des Possibles colours.
Light background (made to be printed or shown to a counsellor), dark header band.
Only data already computed by the app goes in it: nothing is generated here."""

from __future__ import annotations

import html
import io
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import segno
from fpdf import FPDF

from coach.roadmap import Route

FONTS = Path(__file__).resolve().parent.parent / "assets" / "fonts"
NUIT, ROSE, BLEU = (27, 27, 98), (224, 52, 155), (93, 98, 234)
LAVANDE, LILAS, MUTED = (240, 241, 253), (180, 183, 255), (85, 87, 143)
MOODS = {"yes": (46, 140, 100), "no": (200, 70, 58), "maybe": (194, 94, 31), "": NUIT}
M = 14  # page margin (mm)


def clean(text: object) -> str:
    """Characters the font has, no HTML, no emoji."""
    t = html.unescape(re.sub(r"<br\s*/?>", " ", str(text or "")))
    t = re.sub(r"<[^>]+>", "", t).replace("≈", "environ")
    t = re.sub(r"[\U0001F000-\U0001FFFF☀-➿⭐️]", "", t)
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class Sheet:
    """Everything the PDF shows, already decided by the app."""
    job: str
    definition: str
    answers: list[tuple[str, str, str, str]]       # (question, answer, detail, mood)
    routes: list[Route]
    picks: list[tuple[int, list[str], dict]]       # rank() output
    tasks: list[str] = field(default_factory=list)
    context: list[tuple[str, str]] = field(default_factory=list)  # (label, values)
    situation: str = ""
    city: str = ""
    links: list[tuple[str, str]] = field(default_factory=list)
    qr_url: str = ""          # the job sheet, scannable once printed
    qr_label: str = ""


class _PDF(FPDF):
    def multi_cell(self, *args, **kwargs):  # left-aligned: justified text leaves holes
        kwargs.setdefault("align", "L")
        return super().multi_cell(*args, **kwargs)

    def footer(self) -> None:
        self.set_y(-13)
        self.set_font("Outfit", "", 7.5)
        self.set_text_color(*MUTED)
        self.cell(165, 4, "Le Forum · Sources : ONISEP (formations Région Sud), "
                  "France Travail (ROME 4.0), Centre des Possibles · Des pistes, pas un verdict.")
        self.cell(0, 4, f"{self.page_no()} / {{nb}}", align="R")


def _qr(pdf: FPDF, url: str, x: float, y: float, size: float) -> None:
    """A QR code (clickable too), so the links still work on a printed page."""
    buf = io.BytesIO()
    segno.make(url, error="m").save(buf, kind="png", scale=10, border=0, dark="#1b1b62")
    buf.seek(0)
    pdf.image(buf, x=x, y=y, w=size, h=size, link=url)


def _gradient_line(pdf: FPDF, x: float, y: float, w: float, h: float = 1.4) -> None:
    n = 40
    for i in range(n):
        t = i / (n - 1)
        pdf.set_fill_color(*(round(a + (b - a) * t) for a, b in zip(ROSE, BLEU)))
        pdf.rect(x + w * i / n, y, w / n + 0.2, h, style="F")


def _title(pdf: FPDF, text: str, need: float = 30) -> None:
    """Section title, never left alone at the bottom of a page."""
    if pdf.get_y() + need > 280:
        pdf.add_page()
    pdf.ln(4)
    pdf.set_font("Outfit", "B", 12.5)
    pdf.set_text_color(*NUIT)
    pdf.cell(0, 7, text.upper(), new_x="LMARGIN", new_y="NEXT")
    _gradient_line(pdf, M, pdf.get_y(), 22, 1)
    pdf.ln(3)


def _lines(pdf: FPDF, text: str, w: float, size: float, style: str = "") -> int:
    pdf.set_font("Outfit", style, size)
    return len(pdf.multi_cell(w, size * 0.45, text, dry_run=True, output="LINES"))


def _box(pdf: FPDF, x: float, y: float, w: float, h: float, fill=LAVANDE, border=LILAS,
         dashed: bool = False) -> None:
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(*border)
    pdf.set_line_width(0.35)
    if dashed:
        pdf.set_dash_pattern(dash=1.2, gap=1)
    pdf.rect(x, y, w, h, style="DF", round_corners=True, corner_radius=2.5)
    pdf.set_dash_pattern()


def _header(pdf: FPDF, s: Sheet) -> None:
    band, qr = 48, 28
    pdf.set_fill_color(*NUIT)
    pdf.rect(0, 0, 210, band, style="F")
    text_w = 210 - 2 * M - (qr + 10 if s.qr_url else 0)
    if s.qr_url:  # white tile with the QR code, top right
        x, y = 210 - M - qr - 4, 5
        pdf.set_fill_color(255, 255, 255)
        pdf.rect(x, y, qr + 4, qr + 4, style="F", round_corners=True, corner_radius=2.5)
        _qr(pdf, s.qr_url, x + 2, y + 2, qr)
        pdf.set_xy(x - 6, y + qr + 5)
        pdf.set_font("Outfit", "B", 7.5)
        pdf.set_text_color(*LILAS)
        pdf.cell(qr + 16, 4, clean(f"Scanne-moi : {s.qr_label}"), align="C")
    pdf.set_xy(M, 10)
    pdf.set_font("Outfit", "B", 8.5)
    pdf.set_text_color(*LILAS)
    pdf.cell(text_w, 5, "MA FEUILLE DE ROUTE  ·  LE FORUM", new_x="LMARGIN",
             new_y="NEXT")
    pdf.set_font("Outfit", "B", 24 if len(s.job) < 26 else 18)
    pdf.set_text_color(255, 255, 255)
    pdf.multi_cell(text_w, 10, clean(s.job).upper(), new_x="LMARGIN", new_y="NEXT")
    _gradient_line(pdf, M, pdf.get_y() + 1, 40)
    who = " · ".join(x for x in (f"Préparée le {date.today():%d/%m/%Y}", clean(s.situation),
                                 clean(s.city)) if x)
    pdf.set_xy(M, band - 9)
    pdf.set_font("Outfit", "", 9)
    pdf.set_text_color(220, 221, 250)
    pdf.cell(text_w, 5, who)
    pdf.set_y(band + 6)


def _answers(pdf: FPDF, s: Sheet) -> None:
    if s.definition:
        pdf.set_font("Outfit", "", 10.5)
        pdf.set_text_color(*NUIT)
        pdf.multi_cell(0, 5.2, clean(s.definition), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)
    n = len(s.answers)
    if not n:
        return
    gap, w = 4, (210 - 2 * M - 4 * (n - 1)) / n
    pad = 3.5
    heights = [10 + _lines(pdf, clean(a), w - 2 * pad, 13, "B") * 6
               + _lines(pdf, clean(d), w - 2 * pad, 8.5) * 4 for _, a, d, _ in s.answers]
    h, y = max(heights) + 4, pdf.get_y()
    for i, (q, a, d, mood) in enumerate(s.answers):
        x = M + i * (w + gap)
        _box(pdf, x, y, w, h)
        pdf.set_xy(x + pad, y + pad)
        pdf.set_font("Outfit", "B", 7.5)
        pdf.set_text_color(*BLEU)
        pdf.cell(w - 2 * pad, 4, clean(q).upper(), new_x="LEFT", new_y="NEXT")
        pdf.set_font("Outfit", "B", 13)
        pdf.set_text_color(*MOODS.get(mood, NUIT))
        pdf.multi_cell(w - 2 * pad, 6, clean(a), new_x="LEFT", new_y="NEXT")
        pdf.set_font("Outfit", "", 8.5)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(w - 2 * pad, 4, clean(d), new_x="LEFT", new_y="NEXT")
    pdf.set_y(y + h + 2)


def _route(pdf: FPDF, r: Route) -> None:
    steps = r.steps
    arrow, pad = (6, 2.5) if len(steps) < 5 else (5, 2)
    w = (210 - 2 * M - arrow * (len(steps) - 1)) / len(steps)
    ts = 9.5 if len(steps) < 5 else 8.5  # title size: long words must fit narrow boxes

    def brief(st) -> str:  # the essentials only: the web page has the details
        parts = [st.when] if st.when else []
        parts.append(st.detail.split("  ")[0])
        parts += [f for f in st.facts if f.startswith("entrée")]
        parts += [x.replace("Le plus proche : ", "") for x in st.lines if x.startswith("📍")]
        return clean(" · ".join(x for x in parts if x))
    texts = [(clean(st.title), brief(st)) for st in steps]
    h = max(6 + _lines(pdf, t, w - 2 * pad, ts, "B") * 4.4 + _lines(pdf, d, w - 2 * pad, 7.5) * 3.5
            for t, d in texts) + 3
    if pdf.get_y() + h + 14 > 280:
        pdf.add_page()
    pdf.set_font("Outfit", "B", 10.5)
    pdf.set_text_color(*NUIT)
    pdf.cell(pdf.get_string_width(clean(r.name)) + 3, 6, clean(r.name))
    pdf.set_font("Outfit", "B", 9.5)
    pdf.set_text_color(*ROSE)
    pdf.cell(0, 6, clean(r.duration_text), new_x="LMARGIN", new_y="NEXT")
    y = pdf.get_y() + 1
    for i, (st, (t, d)) in enumerate(zip(steps, texts)):
        x = M + i * (w + arrow)
        if st.kind == "job":
            _box(pdf, x, y, w, h, fill=ROSE, border=ROSE)
            tc, dc = (255, 255, 255), (255, 235, 246)
        elif st.kind == "bridge":
            _box(pdf, x, y, w, h, fill=(255, 247, 240), border=(227, 118, 54), dashed=True)
            tc, dc = NUIT, MUTED
        elif st.kind == "start":
            _box(pdf, x, y, w, h, fill=(226, 228, 255), border=BLEU)
            tc, dc = NUIT, MUTED
        else:
            _box(pdf, x, y, w, h, fill=(255, 255, 255), border=BLEU)
            tc, dc = NUIT, MUTED
        pdf.set_xy(x + pad, y + pad)
        pdf.set_font("Outfit", "B", ts)
        pdf.set_text_color(*tc)
        pdf.multi_cell(w - 2 * pad, 4.4, t, new_x="LEFT", new_y="NEXT")
        pdf.set_font("Outfit", "", 7.5)
        pdf.set_text_color(*dc)
        pdf.multi_cell(w - 2 * pad, 3.5, d, new_x="LEFT", new_y="NEXT")
        if st.url:
            pdf.set_font("Outfit", "B", 7.5)
            pdf.set_text_color(*BLEU)
            pdf.cell(w - 2 * pad, 4, "Fiche ONISEP >", link=st.url)
        if i < len(steps) - 1:
            pdf.set_xy(x + w, y + h / 2 - 3)
            pdf.set_font("Outfit", "B", 13)
            pdf.set_text_color(*ROSE)
            pdf.cell(arrow, 6, "→", align="C")
    pdf.set_y(y + h + 2)
    if r.note:
        pdf.set_font("Outfit", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.multi_cell(0, 4, "i  " + clean(r.note), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)


def _picks(pdf: FPDF, s: Sheet) -> None:
    qr, tw = 17, 138  # QR size, text width
    for i, (_, why, r) in enumerate(s.picks, 1):
        km = f" · {r['distance_km']:.0f} km" if r.get("distance_km") is not None else ""
        where = clean(f"{r['school']} - {r['city']}{km} · {r['duration']} · {r['status']}")
        reasons = clean(" · ".join(why))
        h = 6 + _lines(pdf, clean(r["title"]), tw, 10.5, "B") * 5 + 4.5 + \
            (_lines(pdf, reasons, tw, 8) * 4 if reasons else 0) + 2
        h = max(h, qr + 6)
        if pdf.get_y() + h > 280:
            pdf.add_page()
        y = pdf.get_y()
        _box(pdf, M, y, 210 - 2 * M, h, fill=(255, 255, 255), border=ROSE)
        pdf.set_fill_color(*ROSE)
        pdf.rect(M + 3, y + 3, 11, 6, style="F", round_corners=True, corner_radius=3)
        pdf.set_xy(M + 3, y + 3)
        pdf.set_font("Outfit", "B", 8.5)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(11, 6, f"N°{i}", align="C")
        pdf.set_xy(M + 17, y + 3)
        pdf.set_font("Outfit", "B", 10.5)
        pdf.set_text_color(*NUIT)
        pdf.multi_cell(tw, 5, clean(r["title"]), new_x="LEFT", new_y="NEXT")
        pdf.set_font("Outfit", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.cell(tw, 4.5, where, new_x="LEFT", new_y="NEXT")
        if reasons:
            pdf.set_font("Outfit", "B", 8)
            pdf.set_text_color(*MOODS["yes"])
            pdf.multi_cell(tw, 4, "Pourquoi pour toi : " + reasons, new_x="LEFT", new_y="NEXT")
        if r.get("url"):
            _qr(pdf, r["url"], 210 - M - qr - 3, y + (h - qr) / 2, qr)
            pdf.set_xy(210 - M - qr - 26, y + h - 7)
            pdf.set_font("Outfit", "B", 7.5)
            pdf.set_text_color(*BLEU)
            pdf.cell(22, 4, "Fiche ONISEP >", align="R", link=r["url"])
        pdf.set_y(y + h + 2.5)


def _daily(pdf: FPDF, s: Sheet) -> None:
    col = (210 - 2 * M - 6) / 2
    y0 = pdf.get_y()
    pdf.set_text_color(*NUIT)
    pdf.set_font("Outfit", "B", 9.5)
    pdf.cell(col, 5, "Au quotidien", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Outfit", "", 9)
    for t in s.tasks[:5]:
        pdf.multi_cell(col, 4.4, "•  " + clean(t), new_x="LMARGIN", new_y="NEXT")
    y_left = pdf.get_y()
    pdf.set_y(y0)
    for label, values in s.context:
        pdf.set_x(M + col + 6)
        pdf.set_font("Outfit", "B", 9.5)
        pdf.cell(col, 5, clean(label), new_x="LEFT", new_y="NEXT")
        pdf.set_font("Outfit", "", 9)
        pdf.multi_cell(col, 4.4, clean(values), new_x="LEFT", new_y="NEXT")
        pdf.ln(1)
    pdf.set_y(max(y_left, pdf.get_y()) + 1)


def _questions(pdf: FPDF) -> None:
    _title(pdf, "Mes questions pour un conseiller", need=45)
    pdf.set_draw_color(*LILAS)
    pdf.set_line_width(0.3)
    pdf.set_dash_pattern(dash=0.8, gap=1)
    for _ in range(4):
        y = pdf.get_y() + 8
        pdf.line(M, y, 210 - M, y)
        pdf.set_y(y)
    pdf.set_dash_pattern()
    pdf.ln(5)


def roadmap_pdf(s: Sheet) -> bytes:
    pdf = _PDF(format="A4")
    for style, file in (("", "Outfit-Regular.ttf"), ("B", "Outfit-ExtraBold.ttf"),
                        ("I", "Outfit-SemiBold.ttf")):
        pdf.add_font("Outfit", style, str(FONTS / file))
    pdf.set_margins(M, M, M)
    pdf.set_auto_page_break(True, margin=16)
    pdf.set_title(f"Ma feuille de route - {clean(s.job)}")
    pdf.set_author("Le Forum")
    pdf.add_page()
    _header(pdf, s)
    _title(pdf, "Le métier en bref")
    _answers(pdf, s)
    if s.routes:
        _title(pdf, "Ton chemin")
        for r in s.routes:
            _route(pdf, r)
    if s.picks:
        _title(pdf, "Les formations qui te correspondent le mieux", need=45)
        _picks(pdf, s)
    if s.tasks or s.context:
        _title(pdf, "C'est quoi, concrètement ?", need=45)
        _daily(pdf, s)
    _questions(pdf)
    if s.links:
        pdf.set_font("Outfit", "B", 9)
        pdf.set_text_color(*NUIT)
        pdf.cell(0, 5, "Pour aller plus loin", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Outfit", "", 9)
        for label, url in s.links:
            pdf.set_text_color(*BLEU)
            pdf.cell(0, 4.8, f"{clean(label)} : {url}", link=url, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
