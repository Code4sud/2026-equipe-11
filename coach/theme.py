"""Visual touches inspired by centredespossibles.org that the Streamlit theme
(.streamlit/config.toml) cannot express. Light page with white cards and bleu nuit accents
(hero band, sidebar, table headers); one colour per meaning (pink = key info, green = yes,
orange = careful, red = no)."""

BLEU_NUIT = "#1b1b62"
ROSE_NEON = "#e0349b"
LUMIERE_BLEUE = "#5d62ea"
VIOLET = "#9940c4"
LAVANDE = "#e7e8fb"

CSS = f"""
<style>
:root {{
  --blue-nuit: {BLEU_NUIT}; --rose-neon: {ROSE_NEON}; --lumiere-bleue: {LUMIERE_BLEUE};
  --violet-cosmique: {VIOLET}; --lavande-stardust: {LAVANDE};
  --card: #ffffff; --card-border: #dcdef5; --text: #1b1b62; --muted: #4b4d86;
  --label: #4a4fd6; --yes: #1f8a5c; --no: #c8463a; --maybe: #c9631f;
  --shadow: 0 2px 10px #1b1b6212;
}}
/* white / lavande page, a touch of pink and blue light in the corners */
[data-testid="stAppViewContainer"] {{
  background:
    radial-gradient(circle at 96% -10%, #e0349b1a 0, transparent 30%),
    radial-gradient(circle at -5% 5%, #5d62ea1f 0, transparent 35%),
    #f6f6fd;
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2.2rem; max-width: 1250px; }}
h1, h2, h3 {{ letter-spacing: .01em; }}
a {{ color: #4a4fd6; }}

/* hero: a bleu nuit band, the site's signature */
.cdp-hero {{ background:
    radial-gradient(circle at 95% 0%, #e0349b40 0, transparent 45%),
    radial-gradient(circle at 0% 100%, #5d62ea55 0, transparent 50%), var(--blue-nuit);
  border-radius: 1.4rem; padding: 1.4rem 1.6rem 1.3rem; margin-bottom: .6rem; }}
.cdp-eyebrow {{ text-transform: uppercase; letter-spacing: .16em; font-size: .8rem;
  font-weight: 800; color: #c9cbff; }}
.cdp-title {{ font-size: clamp(1.9rem, 4vw, 2.6rem); font-weight: 800; line-height: 1.05;
  text-transform: uppercase; color: #fff; margin: .1rem 0 0;
  text-shadow: 0 3px 6px var(--rose-neon); }}
.cdp-title span {{ color: var(--rose-neon); }}
.cdp-sub {{ color: #e6e7fc; max-width: 48rem; margin-top: .5rem; font-size: 1.05rem;
  line-height: 1.45; }}
.cdp-sub b {{ color: #fff; }}
.cdp-line {{ height: 5px; border-radius: 41px; margin: .8rem 0 .2rem; max-width: 12rem;
  background: linear-gradient(90deg, var(--rose-neon) 0%, var(--lumiere-bleue) 100%); }}

/* section titles */
.cdp-section {{ text-transform: uppercase; letter-spacing: .1em; font-weight: 800;
  font-size: .9rem; color: var(--label); margin: 1.2rem 0 .3rem; }}

/* buttons and pills */
[data-testid="stMain"] [data-testid="stBaseButton-secondary"] {{ border: 1.5px solid #c3c5f0;
  background: #fff; color: var(--text); }}
[data-testid="stBaseButton-secondary"]:hover {{ border-color: var(--rose-neon);
  box-shadow: 0 0 10px #e0349b33; }}
[data-testid^="stBaseButton"] p, [data-testid^="stBaseButton"] div,
[data-testid^="stBaseButton"] .stMarkdownEllipsis {{
  white-space: normal !important; overflow: visible !important;
  text-overflow: clip !important; line-height: 1.25; }}
[data-testid^="stBaseButton"] {{ min-height: 2.5rem; height: auto; }}
[data-testid="stBaseButton-primary"] {{ border: none; font-weight: 700; color: #fff;
  background: linear-gradient(90deg, var(--rose-neon) 0%, var(--lumiere-bleue) 100%); }}
[data-testid="stBaseButton-pillsActive"] {{ border: none; font-weight: 700;
  background: linear-gradient(90deg, var(--rose-neon) 0%, var(--lumiere-bleue) 100%);
  color: #fff; }}
[data-testid="stBaseButton-pillsActive"] p {{ color: #fff; }}
/* pills: wrap on several lines instead of a horizontal scroll strip */
[data-testid="stButtonGroup"] [role="radiogroup"], [data-testid="stButtonGroup"] [role="group"] {{
  flex-wrap: wrap !important; overflow: visible !important; row-gap: .45rem; }}
[data-testid="stBaseButton-pills"] {{ border: 1.5px solid #c3c5f0; background: #fff;
  font-weight: 600; color: var(--text); }}

/* tabs: big and clear */
[data-testid="stTabs"] button[role="tab"] p {{ font-size: 1.05rem; font-weight: 700; }}
[data-testid="stTabs"] [aria-selected="true"] p {{ color: var(--rose-neon); }}

/* job header */
.cdp-job {{ display: flex; flex-wrap: wrap; align-items: baseline; gap: .4rem .8rem;
  margin: .6rem 0 .8rem; }}
.cdp-job h2 {{ margin: 0; padding: 0; font-size: clamp(1.6rem, 3.2vw, 2.2rem);
  font-weight: 800; text-transform: uppercase; color: var(--text); }}
.cdp-badge {{ display: inline-block; border-radius: 41px; padding: .15rem .65rem;
  font-size: .85rem; font-weight: 700; background: #e3e4fc; color: var(--text); }}

/* the 4 instant answers */
.cdp-answer {{ background: var(--card); border: 1px solid var(--card-border);
  border-radius: 1.1rem; padding: 1rem 1.1rem; height: 100%; box-shadow: var(--shadow); }}
.cdp-answer .q {{ font-size: .85rem; font-weight: 800; color: var(--label);
  text-transform: uppercase; letter-spacing: .06em; }}
.cdp-answer .a {{ font-size: 1.35rem; font-weight: 800; color: var(--text);
  line-height: 1.2; margin-top: .35rem; }}
.cdp-answer .a.yes {{ color: var(--yes); }} .cdp-answer .a.no {{ color: var(--no); }}
.cdp-answer .a.maybe {{ color: var(--maybe); }}
.cdp-answer .d {{ color: var(--muted); font-size: .98rem; margin-top: .45rem;
  line-height: 1.45; }}
.cdp-answer .d b {{ color: var(--text); }}

/* external links as pills */
.cdp-links {{ display: flex; flex-wrap: wrap; gap: .45rem; margin: .9rem 0 .2rem; }}
.cdp-links a {{ text-decoration: none; border: 1.5px solid #c3c5f0; border-radius: 41px;
  padding: .3rem .8rem; font-size: .9rem; font-weight: 600; color: var(--text);
  background: #fff; }}
.cdp-links a:hover {{ border-color: var(--rose-neon); }}

/* « Ton chemin » */
.cdp-route {{ background: #fff; border: 1px solid var(--card-border); border-radius: 1.2rem;
  padding: 1rem 1.1rem 1.1rem; margin: .4rem 0 1rem; box-shadow: var(--shadow); }}
.cdp-route h4 {{ font-size: 1.1rem; font-weight: 800; margin: 0; color: var(--text);
  padding: 0; }}
.cdp-route .len {{ color: var(--rose-neon); font-weight: 800; font-size: 1rem; }}
.cdp-steps {{ display: flex; flex-wrap: wrap; align-items: stretch; gap: .5rem;
  margin-top: .7rem; }}
.cdp-step {{ flex: 1 1 0; min-width: 8.5rem; border-radius: 1rem; padding: .8rem .9rem;
  background: #fff; border: 1.5px solid #b9bcf2; }}
.cdp-step b {{ display: block; color: var(--text); font-size: 1.02rem; line-height: 1.25; }}
.cdp-step span {{ display: block; color: var(--muted); font-size: .9rem; margin-top: .35rem;
  line-height: 1.4; }}
.cdp-step a {{ display: inline-block; margin-top: .35rem; font-size: .88rem; font-weight: 600; }}
.cdp-step.start {{ border-color: #b9bcf2; background: #eeeffd; }}
.cdp-step.bridge {{ border-style: dashed; border-color: var(--maybe); background: #fff8f2; }}
.cdp-step.job {{ border: none; background: linear-gradient(120deg, #e0349b 0%, #5d62ea 100%); }}
.cdp-step.job b, .cdp-step.job span {{ color: #fff; }}
.cdp-step .when {{ font-size: .74rem; font-weight: 800; letter-spacing: .05em;
  text-transform: uppercase; color: var(--rose-neon); margin-bottom: .3rem; }}
.cdp-step.job .when {{ color: #fff; }}
.cdp-step .chips {{ margin-top: .45rem; }}
.cdp-step .chip {{ display: inline-block; border-radius: 41px; padding: .05rem .5rem;
  margin: .2rem .2rem 0 0; font-size: .76rem; font-weight: 700; background: #e3e4fc;
  color: #2b2d8a; }}
.cdp-step .chip.ok {{ background: #d8f2e6; color: #17704a; }}
.cdp-step.job .chip {{ background: #ffffff33; color: #fff; }}
.cdp-step .line {{ color: var(--text); font-size: .86rem; margin-top: .45rem; line-height: 1.4; }}
.cdp-step.job .line {{ color: #fff; }}
.cdp-route .ends {{ color: var(--muted); font-size: .95rem; }}
.cdp-step.course, .cdp-step.job {{ flex-grow: 1.5; }}
.cdp-step.start {{ flex-grow: .45; min-width: 6.5rem; }}
.cdp-steps.long .cdp-step.bridge {{ flex-grow: .8; }}
.cdp-arrow {{ align-self: center; color: var(--rose-neon); font-size: 1.5rem; font-weight: 800; }}
.cdp-note {{ color: var(--muted); font-size: .92rem; margin-top: .7rem; }}

/* all the diplomas, by when you can start */
.cdp-stage {{ text-transform: uppercase; letter-spacing: .08em; font-weight: 800;
  font-size: .85rem; color: var(--label); margin-bottom: .45rem; }}
.cdp-stage.here {{ color: var(--rose-neon); }}
.cdp-dip {{ background: var(--card); border: 1px solid var(--card-border); border-radius: 1rem;
  padding: .75rem .85rem; margin-bottom: .55rem; font-size: .92rem; color: var(--muted);
  line-height: 1.45; box-shadow: var(--shadow); }}
.cdp-dip b {{ color: var(--text); font-size: 1rem; }}
.cdp-tag {{ display: inline-block; border-radius: 41px; padding: .08rem .55rem;
  margin: .3rem .25rem 0 0; font-size: .8rem; font-weight: 700; background: #e3e4fc;
  color: #2b2d8a; }}
.cdp-tag.pink {{ background: #fbe1ef; color: #a51c6e; }}
.cdp-tag.green {{ background: #d8f2e6; color: #17704a; }}

/* « Pour toi » picks */
.cdp-pick {{ border-radius: 1.1rem; padding: .85rem 1rem; margin-bottom: .6rem;
  background: var(--card); border: 1.5px solid #f0a6cf; box-shadow: var(--shadow); }}
.cdp-pick .rank {{ display: inline-block; background: var(--rose-neon); color: #fff;
  border-radius: 41px; font-weight: 800; font-size: .8rem; padding: .05rem .55rem; }}
.cdp-pick b {{ display: block; color: var(--text); font-size: 1.05rem; margin: .35rem 0 .15rem;
  line-height: 1.25; }}
.cdp-pick .where {{ color: var(--muted); font-size: .95rem; }}
.cdp-pick .where strong {{ color: var(--text); }}
.cdp-pick a {{ font-size: .9rem; font-weight: 600; }}
.cdp-legend {{ display: flex; flex-wrap: wrap; gap: 1rem; font-size: .88rem; color: var(--muted);
  margin-top: .4rem; }}
.cdp-legend i {{ display: inline-block; width: .8rem; height: .8rem; border-radius: 50%;
  margin-right: .35rem; vertical-align: -1px; }}

/* job comparator: rows = questions, columns = jobs */
.cdp-cmp-wrap {{ overflow-x: auto; margin: .6rem 0 1rem; }}
.cdp-cmp {{ width: 100%; border-collapse: separate; border-spacing: 0; min-width: 40rem;
  background: var(--card); border: 1px solid var(--card-border); border-radius: 1.1rem;
  overflow: hidden; box-shadow: var(--shadow); }}
.cdp-cmp th, .cdp-cmp td {{ padding: .75rem .9rem; vertical-align: top; text-align: left;
  border-bottom: 1px solid #e6e7f8; }}
.cdp-cmp tr:last-child th, .cdp-cmp tr:last-child td {{ border-bottom: none; }}
.cdp-cmp thead th {{ font-size: 1.08rem; font-weight: 800; color: #fff;
  background: var(--blue-nuit); }}
.cdp-cmp thead th i {{ display: inline-block; width: .75rem; height: .75rem; border-radius: 50%;
  margin-right: .45rem; }}
.cdp-cmp th.k {{ width: 13rem; font-size: .9rem; font-weight: 700; color: var(--label);
  background: #f3f3fd; }}
.cdp-cmp td .v {{ font-weight: 800; color: var(--text); line-height: 1.3; }}
.cdp-cmp td .v.yes {{ color: var(--yes); }} .cdp-cmp td .v.no {{ color: var(--no); }}
.cdp-cmp td .v.maybe {{ color: var(--maybe); }}
.cdp-cmp td .d {{ color: var(--muted); font-size: .88rem; margin-top: .2rem; line-height: 1.4; }}
.cdp-cmp td .d b {{ color: var(--text); }}
.cdp-cmp .best {{ display: inline-block; margin-top: .3rem; border-radius: 41px;
  padding: .05rem .5rem; font-size: .78rem; font-weight: 800; background: #d8f2e6;
  color: #17704a; }}

/* what a click on the map shows */
.cdp-spot {{ background: var(--card); border: 1.5px solid #b9bcf2; border-radius: 1.1rem;
  padding: .85rem 1rem; margin-top: .6rem; box-shadow: var(--shadow); }}
.cdp-spot > b {{ font-size: 1.05rem; color: var(--text); }}
.cdp-spot .where {{ color: var(--muted); }}
.cdp-spot ul {{ margin: .5rem 0 0; padding-left: 1.1rem; }}
.cdp-spot li {{ margin-bottom: .45rem; color: var(--text); }}
.cdp-spot small {{ color: var(--muted); font-size: .85rem; }}

/* empty state */
.cdp-steps3 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(14rem, 1fr));
  gap: .8rem; margin-top: .6rem; }}
.cdp-steps3 div {{ background: var(--card); border: 1px solid var(--card-border);
  border-radius: 1.1rem; padding: 1rem 1.1rem; color: var(--muted); line-height: 1.45;
  box-shadow: var(--shadow); }}
.cdp-steps3 b {{ display: block; color: var(--text); font-size: 1.05rem; margin-bottom: .3rem; }}
.cdp-steps3 em {{ font-style: normal; color: var(--rose-neon); font-weight: 800;
  font-size: 1.3rem; }}

/* chat */
[data-testid="stChatMessage"] {{ background: #fff; border: 1px solid var(--card-border);
  border-radius: 1.25rem; box-shadow: var(--shadow); }}
[data-testid="stSidebar"] h2 {{ font-size: 1.15rem; }}
[data-testid="stExpander"] {{ background: #fff; border-radius: 1rem; }}
[data-testid="stExpander"] summary p {{ font-weight: 700; }}
[data-testid="stMain"] [data-testid="stCaptionContainer"],
[data-testid="stMain"] [data-testid="stCaptionContainer"] p {{ color: var(--muted) !important;
  opacity: 1; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ color: #e6e7fc !important;
  opacity: 1; }}
</style>
"""

HERO = """
<div class="cdp-hero">
  <div class="cdp-eyebrow">Explore ton champ des possibles</div>
  <h1 class="cdp-title">Le <span>Forum</span></h1>
  <div class="cdp-line"></div>
  <div class="cdp-sub">Choisis un métier : je te dis <b>ce que c'est</b>, <b>quel diplôme</b> il
  faut, si c'est <b>possible sans le bac</b>, et <b>le chemin</b> pour y arriver depuis chez toi.
  Tout vient de sources officielles, et quand je ne sais pas, je te le dis.</div>
</div>
"""

EMPTY = """
<div class="cdp-steps3">
  <div><em>1</em><b>Choisis un métier</b>Dépose ton Rapport des Possibles à gauche, ou tape
  un métier qui t'intrigue juste au-dessus.</div>
  <div><em>2</em><b>Dis-moi où tu en es</b>Collège, lycée, bac… et ta ville : je calcule le
  chemin depuis ta situation.</div>
  <div><em>3</em><b>Découvre ton chemin</b>Les étapes, les formations près de chez toi, et
  celles qui te correspondent le mieux.</div>
</div>
"""
