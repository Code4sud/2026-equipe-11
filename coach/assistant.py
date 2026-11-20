"""Grounded conversational assistant: retrieve -> cite -> answer (or say "je ne sais pas")."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from coach.kb import KnowledgeBase, Source
from coach.roadmap import relevance
from coach.guide import (APTITUDES, FAQ_ALGO, HOW_TO_READ, INTERESTS, PERSONALITY,
                         topics_in)
from coach.llm import LLM
from coach.report import ReportResults

ORIENTATION_SUD = "https://www.orientation-regionsud.fr/"
CENTRE = "https://centredespossibles.org"
GUIDE = "Guide pratique du Centre des Possibles"

RIASEC = {
    "R": ("Réaliste", "aime les activités concrètes, pratiques, manuelles : outils, machines, "
          "plantes, animaux, souvent en extérieur."),
    "I": ("Investigateur", "aime observer, analyser, comprendre, résoudre des problèmes, "
          "les sciences et la recherche."),
    "A": ("Artistique", "aime créer, imaginer, s'exprimer : art, écriture, musique, graphisme."),
    "S": ("Social", "aime être en contact avec les autres pour aider, informer, enseigner, soigner."),
    "E": ("Entreprenant", "aime influencer, convaincre, diriger, prendre des initiatives."),
    "C": ("Conventionnel", "aime les activités précises et organisées, les règles et "
          "consignes claires, trier, classer."),
}

SYSTEM = f"""Tu es « Le Forum », un assistant d'orientation pour des jeunes \
(15-25 ans) du Centre des Possibles (Région Sud). Tu tutoies, tu parles simplement, \
avec des phrases courtes, sans jargon.

RÈGLES ABSOLUES :
1. Tu réponds UNIQUEMENT avec les informations des SOURCES fournies. Tu n'inventes jamais \
un diplôme, une école, une durée, un salaire ou une condition d'accès.
2. Après chaque information, cite sa source entre crochets : [1], [2]...
3. Si l'information n'est pas dans les sources, dis-le franchement : « Je ne sais pas, \
ce n'est pas dans mes sources. » Puis propose de regarder {ORIENTATION_SUD} ou d'en parler \
avec un psychologue du Centre des Possibles.
4. Les salaires ne sont pas dans tes sources : ne donne jamais de chiffre de salaire.
5. Si une source dit que la correspondance avec le ROME est incertaine, préviens le jeune.
6. Pour savoir si on peut se former sans le bac, fie-toi à la synthèse des formations \
ONISEP quand elle existe et ne la contredis jamais.
7. Réponse courte : 100 mots maximum, avec des puces. Ne recopie pas les sources mot à mot : \
résume-les avec tes mots. Finis par une seule petite question pour aider le jeune à avancer \
(sans écrire « question : »).
8. Les résultats (intérêts, aptitudes, personnalité) sont des tendances : présente-les \
avec bienveillance, en valorisant les points forts, sans jamais poser de diagnostic. \
Compare les résultats du jeune entre eux, jamais avec les autres ; utilise les exemples \
concrets du guide pour expliquer une aptitude.
9. Tu ne juges jamais le jeune et tu ne lui dis pas qu'un métier est « fait pour lui » : \
les résultats du rapport sont des pistes de réflexion, pas un verdict.

FORMAT : une phrase qui répond directement, puis 2 à 4 puces, chaque information suivie \
d'UNE source [n] (pas de liste de sources à la fin), puis une petite question. Si les \
sources ne disent rien sur un point, ne l'écris pas."""


# one worked example (its own sources -> its answer): shows the format and the citing
# without giving the model any real content it could copy into another answer
EXAMPLE = [
    {"role": "user", "content": (
        "PROFIL DU JEUNE : non renseigné\n\nSOURCES :\n"
        "[1] Fiche métier : Métier X\nLe métier X consiste à réparer des objets Y en atelier.\n\n"
        "[2] Au quotidien : diagnostiquer la panne ; commander les pièces ; réparer.\n"
        "Horaires : travail en journée.\n\n"
        "QUESTION DU JEUNE : C'est quoi le métier X ?")},
    {"role": "assistant", "content": (
        "Le métier X consiste à réparer des objets Y, en atelier [1].\n"
        "- Au quotidien : trouver la panne, commander les pièces, puis réparer [2].\n"
        "- Horaires : plutôt en journée [2].\n"
        "Qu'est-ce qui t'attire le plus : chercher la panne, ou réparer de tes mains ?")},
]


@dataclass
class Profile:
    report_jobs: list[tuple[str, int]] = field(default_factory=list)
    city: str = ""
    has_bac: bool | None = None
    situation: int | None = None  # index in coach.roadmap.SITUATIONS
    riasec: str = ""  # e.g. "SA"
    results: ReportResults | None = None


@dataclass
class Turn:
    question: str
    sources: list[Source]
    jobs: list[str]
    infos: list[dict]
    messages: list[dict]


class Assistant:
    def __init__(self, kb: KnowledgeBase | None = None, llm: LLM | None = None):
        self.kb = kb or KnowledgeBase()
        self.llm = llm or LLM()

    # ---- retrieval --------------------------------------------------------
    def detect_jobs(self, question: str, profile: Profile, focus: str | None) -> list[str]:
        report = [name for name, _ in profile.report_jobs]
        jobs = self.kb.find_in_text(question, among=report) if report else []
        if not jobs:
            jobs = self.kb.find_in_text(question)
        if not jobs and focus and not REPORT_LEVEL.search(question):
            jobs = [focus]
        return jobs[:3]

    def retrieve(self, question: str, profile: Profile, focus: str | None = None) -> Turn:
        near = None
        if profile.city:
            loc = self.kb.locate(profile.city)
            near = loc[:2] if loc else None
        jobs = self.detect_jobs(question, profile, focus)
        sources: list[Source] = []
        infos: list[dict] = []
        zones = dict(profile.report_jobs)
        for name in jobs:
            src, info = self.kb.sources_for_job(name, near=near, has_bac=profile.has_bac,
                                                report_zone=zones.get(name),
                                                situation=profile.situation)
            if not info["rome"]:
                pistes = ", ".join(
                    f"{self.kb.rome[c['code']]['label']} ({c['code']})"
                    for c in info["candidates"][:2])
                src.append(Source("Correspondance ROME incertaine", None,
                                  f"Le métier « {info['name']} » n'a pas de correspondance "
                                  f"sûre dans le ROME. Pistes possibles à vérifier : {pistes}. "
                                  "Aucune formation n'a donc pu être reliée avec certitude."))
            elif not any("formation" in s.title for s in src):
                src.append(Source("Offre de formation Région Sud (ONISEP)", ORIENTATION_SUD,
                                  f"Aucune formation reliée au métier « {info['name']} » "
                                  "n'a été trouvée dans l'offre ONISEP de la Région Sud. "
                                  "Donc : on ne sait pas s'il est accessible sans le bac, ni "
                                  "où se former près de chez soi (ne rien affirmer là-dessus)."))
            if not (FORMATION_Q.search(question) or NO_BAC_Q.search(question)
                    or HOW_Q.search(question) or NEAR_Q.search(question)):
                # « c'est quoi ? » : talk about the job only, the course facts are on the cards
                src = [x for x in src if not x.title.startswith(COURSE_SOURCES)]
            if len(jobs) == 1:
                sources += src[:8]
            else:  # several jobs: keep the essentials of each (sheet, ROME, bac, daily life)
                keep = ("Fiche métier", "fiche ROME", "synthèse", "au quotidien", "Chemin vers",
                        "Correspondance ROME incertaine")
                sources += [x for x in src if any(k in x.title for k in keep)][:5]
            infos.append(info)
        if jobs:
            if profile.results:  # "est-ce que ce métier me correspond ?"
                sources.append(self._results_source(profile.results, short=True))
        else:
            sources += self._profile_sources(profile, near)
        topics = topics_in(question)  # "c'est quoi le raisonnement inductif ?"
        if topics:
            sources.append(Source(f"{GUIDE} : définitions", None,
                                  "\n".join(text for _, text in topics)))
        return Turn(question, sources, jobs, infos, [])

    def _results_source(self, res: ReportResults, short: bool = False) -> Source:
        """The young person's results, explained with the Centre's own guide."""
        lines = []
        if res.interests:
            ranked = [f"{k} ({v:.0%})" for k, v in res.interests.items()]
            lines.append("Intérêts professionnels, du plus fort au plus faible : "
                         + ", ".join(ranked) + ".")
            if not short:
                for k in [k for k, v in res.interests.items() if v > 0][:2]:
                    lines.append(f"  {k} : une personne qui {INTERESTS[k]}")
        if res.aptitudes:
            ranked = sorted(res.aptitudes.items(), key=lambda kv: kv[1], reverse=True)
            lines.append("Aptitudes cognitives (score sur 8) - points forts : "
                         + ", ".join(f"{k} {v:g}/8" for k, v in ranked[:3]) + ".")
            if not short:
                for k, _ in ranked[:3]:
                    definition, example = APTITUDES[k]
                    lines.append(f"  {k} : {definition} (exemple : {example}).")
                lines.append("Les autres aptitudes : "
                             + ", ".join(f"{k} {v:g}/8" for k, v in ranked[3:]) + ".")
        if res.personality and not short:
            top = list(res.personality)[:3]
            lines.append("Personnalité (HEXACO), traits les plus marqués : " + ", ".join(top) + ".")
            for k in top:
                lines.append(f"  {k} : {PERSONALITY[k]}.")
        return Source("Tes résultats (Rapport des Possibles, expliqués avec le guide du Centre)",
                      None, "\n".join(lines))

    def _profile_sources(self, profile: Profile, near) -> list[Source]:
        out = []
        if profile.results:
            out.append(self._results_source(profile.results))
        if profile.report_jobs:
            out.append(self._report_jobs_source(profile, near))
        if profile.results:
            out.append(Source(f"{GUIDE} : comment lire tes résultats", None,
                              HOW_TO_READ + "\n" + FAQ_ALGO))
        if not profile.results:
            letters = profile.riasec or "RIASEC"
            out.append(Source(f"{GUIDE} : intérêts professionnels (RIASEC)", None, "\n".join(
                f"{RIASEC[c][0]} : {RIASEC[c][1]}" for c in letters if c in RIASEC)))
        return out

    def _report_jobs_source(self, profile: Profile, near) -> Source:
        """One factual line per job of the report, so the LLM can answer
        "lesquels sans le bac ?", "lequel est le plus proche ?", "lequel me correspond ?"."""
        g = self.report_groups(profile, near)
        no_bac, bac, unknown, match, lines = g["no_bac"], g["bac"], g["unknown"], g["match"], \
            g["lines"]
        mine = set(profile.riasec)
        head = [
            "RÉSUMÉ (déjà calculé, à recopier tel quel) :",
            f"- Formation accessible SANS le bac : {', '.join(no_bac) or 'aucun'}.",
            f"- Formation qui DEMANDE le bac ou plus : {', '.join(bac) or 'aucun'}.",
            f"- Je ne sais pas (pas de formation reliée avec certitude) : "
            f"{', '.join(unknown) or 'aucun'}.",
        ]
        if mine:
            head.append(f"- Métiers qui partagent tes intérêts dominants "
                        f"({', '.join(RIASEC[c][0] for c in profile.riasec)}) : "
                        f"{', '.join(match) or 'aucun'}.")
        return Source("Ton Rapport des Possibles : les métiers proposés (faits)", None,
                      "\n".join(head + ["", "DÉTAIL PAR MÉTIER :"] + lines))

    def report_groups(self, profile: Profile, near) -> dict:
        """Deterministic grouping of the report's jobs (bac / no bac / unknown / interests)."""
        mine = set(profile.riasec)
        lines = []
        no_bac, bac, unknown, match = [], [], [], []
        for name, zone in profile.report_jobs:
            f = self.kb.facts(name, near, zone)
            if not f["rome_code"] or not f["n_trainings"]:
                unknown.append(name)
                acces = "accès sans le bac : je ne sais pas"
            else:
                (no_bac if f["n_no_bac"] else bac).append(name)
                acces = (f"sans le bac : {'oui' if f['n_no_bac'] else 'non'}, "
                         f"{f['n_trainings']} formation(s) en Région Sud")
                if f["nearest"]:
                    acces += (f", la plus proche à {f['nearest']['city']} "
                              f"({f['nearest']['distance_km']:.0f} km)")
            interets = [RIASEC[c][0] for c in f["riasec"] if c in RIASEC]
            commun = [RIASEC[c][0] for c in f["riasec"] if c in mine]
            if commun:
                match.append(f"{name} ({', '.join(commun)})")
            line = f"- {name} : {acces}"
            if interets:
                line += f" ; intérêts du métier : {', '.join(interets)}"
            lines.append(line)
        return {"no_bac": no_bac, "bac": bac, "unknown": unknown, "match": match,
                "lines": lines}

    def results_answer(self, turn: Turn, profile: Profile) -> str:
        """« Explique-moi mes résultats », written from the report + the Centre's guide."""
        res = profile.results
        idx = {s.title.split(" (")[0].split(" :")[0]: i for i, s in enumerate(turn.sources, 1)}
        cite_res = f" [{idx.get('Tes résultats', 1)}]"
        cite_guide = f" [{idx.get(GUIDE, len(turn.sources))}]"
        out = ["Voici ce que dit ton rapport, expliqué avec le guide du Centre des Possibles :", ""]
        if res.interests:
            ranked = [(k, v) for k, v in res.interests.items() if v > 0]
            top, top_v = ranked[0]
            dominant = [k for k, v in ranked if v >= 0.5 * top_v]
            out.append(f"🎯 **Tes intérêts** : surtout **{' et '.join(dominant)}**{cite_res}.")
            for k in dominant:
                out.append(f"   *{k}* : une personne qui {INTERESTS[k]}")
            rest = [f"{k} ({v:.0%})" for k, v in ranked if k not in dominant]
            if rest:
                out.append(f"   Viennent ensuite, plus loin : {', '.join(rest)}.")
        if res.aptitudes:
            ranked = sorted(res.aptitudes.items(), key=lambda kv: kv[1], reverse=True)
            out += ["", f"🧠 **Tes points forts** (aptitudes, sur 8){cite_res} :"]
            for k, v in ranked[:3]:
                definition, example = APTITUDES[k]
                out.append(f"- **{k}** ({v:g}/8) : {definition}. Par exemple : {example}.")
        if res.personality:
            top = list(res.personality)[:3]
            out += ["", f"🌱 **Ta personnalité**, traits les plus marqués{cite_res} :"]
            out += [f"- **{k}** : {PERSONALITY[k]}." for k in top]
        out += ["", f"ℹ️ À garder en tête{cite_guide} : ces résultats sont une image à un moment "
                "donné, pas un verdict. On les compare entre eux, pas avec les autres, et c'est "
                "toi l'expert de ton vécu.", "",
                "Qu'est-ce qui te ressemble le plus là-dedans, et qu'est-ce qui te surprend ?"]
        return "\n".join(out)

    def job_answer(self, question: str, turn: Turn, profile: Profile) -> str | None:
        """« Je peux le faire sans le bac ? » and « quelles formations ? » for an unsure
        job are the brief's core questions: answered from the data, never improvised."""
        if len(turn.jobs) != 1 or not turn.infos:
            return None
        info = turn.infos[0]
        name, code = info["name"], info["rome"]

        def cite(prefix: str) -> str:
            i = next((i for i, s in enumerate(turn.sources, 1) if s.title.startswith(prefix)),
                     None)
            return f" [{i}]" if i else ""

        if not code:
            if not FORMATION_Q.search(question):
                return None
            pistes = ", ".join(f"{self.kb.rome[c['code']]['label']} ({c['code']})"
                               for c in info["candidates"][:2])
            return (f"⚠️ Pour « {name} », je n'ai pas trouvé de correspondance sûre dans le "
                    "répertoire officiel des métiers (ROME), donc **je ne sais pas** quelles "
                    "formations y mènent : je préfère ne rien inventer"
                    f"{cite('Correspondance ROME')}.\n\n"
                    f"- Pistes à vérifier : {pistes}{cite('Correspondance ROME')}.\n"
                    f"- Cherche « {name.lower()} » sur {ORIENTATION_SUD}formations, ou demande "
                    "à un conseiller du Centre des Possibles.\n\n"
                    "Tu veux que je t'explique ce que fait ce métier au quotidien ?")
        if not (NO_BAC_Q.search(question) or HOW_Q.search(question)
                or FORMATION_Q.search(question)):
            return None
        loc = self.kb.locate(profile.city) if profile.city else None
        near = loc[:2] if loc else None
        dips, rts = self.kb.plan(name, code, near, profile.situation)
        syn, road = cite("ONISEP - offre de formation"), cite("Chemin vers")
        if not dips:
            rome = self.kb.rome[code]
            out = [f"**Je ne sais pas** : je n'ai trouvé aucune formation reliée au métier de "
                   f"{name.lower()} dans l'offre ONISEP de la Région Sud"
                   f"{cite('Offre de formation Région Sud')}, donc je ne peux pas te dire si "
                   "c'est possible sans le bac ni où te former."]
            if rome.get("diplomas"):
                out += ["", "France Travail cite ces diplômes pour ce métier"
                        f"{cite('France Travail - ROME')} :"]
                out += [f"- {d}" for d in rome["diplomas"][:5]]
            out += ["", f"Pour aller plus loin : {ORIENTATION_SUD}formations, ou un conseiller "
                    "du Centre des Possibles. Tu veux que je t'explique le métier au quotidien ?"]
            return "\n".join(out)
        if not (NO_BAC_Q.search(question) or HOW_Q.search(question)):
            return None  # « quel diplôme ? » with courses found: the LLM has all the sources
        if not NO_BAC_Q.search(question):  # « comment je deviens X ? » : the computed routes
            out = [f"Voici le chemin pour devenir {name.lower()}"
                   + (" depuis ta situation" if profile.situation is not None else "")
                   + f", d'après les formations de la Région Sud{road} :"]
            for r in rts:
                out += ["", f"**{r.name}** ({r.duration_text}) :"]
                for i, s in enumerate(r.steps[1:-1], 1):
                    extra = f" — {s.detail.split('  ')[0]}" if s.kind == "course" else ""
                    out.append(f"{i}. {s.title}{extra}")
                if r.note:
                    out.append(f"ℹ️ {r.note}{road}")
            if profile.situation is None:
                out += ["", "Dis-moi où tu en es (à gauche) pour que je l'adapte à ta situation."]
            out += ["", "Tout est détaillé dans l'onglet « Ton chemin ». Quelle étape te pose "
                    "le plus de questions ?"]
            return "\n".join(out)
        no_bac = [d for d in dips if d.no_bac]
        if no_bac:
            d = min(no_bac, key=lambda d: (relevance(name, d.title) < 80, d.stage))
            n = d.nearest
            where = (f", le plus proche à {n['city']} ({n['distance_km']:.0f} km)"
                     if n.get("distance_km") is not None else "")
            return (f"**Oui** 🎉 : on peut se former au métier de {name.lower()} sans le bac"
                    f"{syn}.\n\n"
                    f"- Par exemple : **{d.title}** ({d.duration}), entrée "
                    f"{d.nearest['entry']}{syn}.\n"
                    f"- {len(d.schools)} établissement(s) en Région Sud{where}{syn}.\n\n"
                    "Le détail est dans l'onglet « Ton chemin ». Tu veux que je te compare les "
                    "formations ?")
        main = next((s for r in rts[:1] for s in r.steps if s.kind == "course"), None)
        detour = next((r for r in rts if r.plus_experience), None)
        out = [f"**Pas directement** : en Région Sud, toutes les formations qui mènent au "
               f"métier de {name.lower()} demandent le bac{syn}."]
        if detour:
            course = next(s for s in detour.steps if s.kind == "course")
            bridge = next(s for s in detour.steps if s.kind == "job")
            out += ["", f"Mais il existe une passerelle{road} :",
                    f"1. Te former sans le bac : **{course.title}**{road}.",
                    f"2. Travailler comme {bridge.title.lower()}.",
                    f"3. Évoluer vers {name.lower()}, avec de l'expérience et souvent une "
                    f"sélection : les conditions sont à vérifier avec un conseiller{road}."]
        if main:
            out += ["", f"L'autre chemin : passer le bac (général, technologique ou "
                    f"professionnel), puis **{main.title}**{road}."]
        out += ["", "Lequel de ces chemins t'intéresse ?"]
        return "\n".join(out)

    def list_answer(self, question: str, turn: Turn, profile: Profile) -> str | None:
        """Report-wide list questions are answered from the data, not by the LLM:
        a small model mixes up lists, a lookup does not."""
        if turn.jobs:
            return None
        if profile.results and RESULTS_Q.search(question):
            return self.results_answer(turn, profile)
        if not profile.report_jobs:
            return None
        idx = next((i for i, s in enumerate(turn.sources, 1) if "(faits)" in s.title), None)
        if idx is None:
            return None
        loc = self.kb.locate(profile.city) if profile.city else None
        g = self.report_groups(profile, loc[:2] if loc else None)
        cite = f" [{idx}]"
        if NO_BAC_Q.search(question):
            out = ["Voici ce que disent les formations de la Région Sud (ONISEP) pour les "
                   "métiers de ton rapport :", ""]
            out.append("✅ **Formation accessible sans le bac** : "
                       + (", ".join(g["no_bac"]) or "aucun") + cite)
            out.append("🎓 **Formation qui demande le bac ou plus** : "
                       + (", ".join(g["bac"]) or "aucun") + cite)
            if g["unknown"]:
                out.append("❓ **Je ne sais pas** (pas de formation reliée avec certitude) : "
                           + ", ".join(g["unknown"]) + cite)
            out += ["", "Tu veux que je t'en dise plus sur l'un d'eux ? Clique sur un métier "
                    "ou pose-moi la question."]
            return "\n".join(out)
        if MATCH_Q.search(question):
            if not profile.riasec:
                return ("Je ne connais pas encore tes intérêts dominants : dépose ton rapport "
                        "ou choisis-les à gauche, et je te dirai quels métiers les partagent.")
            names = ", ".join(RIASEC[c][0] for c in profile.riasec)
            out = [f"Tes intérêts dominants : **{names}**.", "",
                   "Métiers de ton rapport qui partagent ces intérêts (selon le ROME) : "
                   + (", ".join(g["match"]) or "aucun") + cite, "",
                   "C'est une piste, pas un verdict : ce qui compte aussi, c'est ce que tu "
                   "ressens en découvrant le métier. Lequel veux-tu explorer ?"]
            return "\n".join(out)
        return None

    # ---- generation -------------------------------------------------------
    def build_messages(self, turn: Turn, profile: Profile, history: list[dict]) -> list[dict]:
        ctx = []
        for i, s in enumerate(turn.sources, 1):
            limit = 3000 if s.title.startswith(("Ton ", "Tes ", GUIDE)) else 900
            ctx.append(f"[{i}] {s.title}\n{s.text[:limit]}")
        who = []
        if profile.city:
            who.append(f"habite près de {profile.city}")
        if profile.has_bac is not None:
            who.append("a le bac" if profile.has_bac else "n'a pas le bac")
        if profile.riasec:
            who.append("intérêts dominants : " + ", ".join(
                RIASEC[c][0] for c in profile.riasec if c in RIASEC))
        user = (f"PROFIL DU JEUNE : {'; '.join(who) or 'non renseigné'}\n\n"
                f"SOURCES :\n" + ("\n\n".join(ctx) if ctx else "(aucune source trouvée)")
                + f"\n\nQUESTION DU JEUNE : {turn.question}")
        msgs = [{"role": "system", "content": SYSTEM}, *EXAMPLE]
        msgs += history[-6:]
        msgs.append({"role": "user", "content": user})
        turn.messages = msgs
        return msgs

    def answer(self, question: str, profile: Profile, history: list[dict],
               focus: str | None = None) -> tuple[Turn, Iterator[str]]:
        turn = self.retrieve(question, profile, focus)
        # --- deterministic guardrails: honesty must not depend on the model ---
        if not turn.sources:
            return turn, iter([DONT_KNOW])
        if not turn.jobs and not ON_TOPIC.search(question) and not topics_in(question):
            return turn, iter([OFF_TOPIC])
        listed = (self.list_answer(question, turn, profile)
                  or self.job_answer(question, turn, profile))
        if listed:
            return turn, iter([listed])
        if SALARY.search(question):
            return turn, iter([SALARY_ANSWER])
        prefix = ""
        uncertain = [i["name"] for i in turn.infos if not i["rome"]]
        if uncertain:
            prefix = ("⚠️ Pour « " + " », « ".join(uncertain) + " », je n'ai pas trouvé de "
                      "correspondance sûre dans le répertoire officiel des métiers (ROME) : "
                      "je ne peux pas te lister de formations avec certitude.\n\n")
        stream = self.llm.stream(self.build_messages(turn, profile, history))
        return turn, _prepend(prefix, stream)


def _prepend(prefix: str, stream: Iterator[str]) -> Iterator[str]:
    if prefix:
        yield prefix
    yield from stream


DONT_KNOW = ("Je ne sais pas, je n'ai trouvé aucune source fiable pour répondre. "
             f"Tu peux regarder {ORIENTATION_SUD} ou en parler avec un psychologue "
             "du Centre des Possibles.")
RESULTS_Q = re.compile(r"(mes r[ée]sultats|mon profil|explique.{0,20}(mon )?rapport|"
                       r"que dit mon rapport|mes points forts|je suis comment)", re.I)
NO_BAC_Q = re.compile(r"sans (le |mon |avoir le )?bac", re.I)
NEAR_Q = re.compile(r"(pr[eè]s de|proche|o[uù] |loin|ville|distance|lyc[ée]e|compar|diff[ée]ren)",
                    re.I)
COURSE_SOURCES = ("ONISEP - formation", "ONISEP - offre", "Chemin vers", "Offre de formation")
HOW_Q = re.compile(r"(comment (je )?(deviens|devenir|faire pour (devenir|[êe]tre))|"
                   r"quel(s|le)? (chemin|parcours)|par o[uù] (je )?commence|[ée]tapes? pour)",
                   re.I)
FORMATION_Q = re.compile(r"(formation|dipl[ôo]m|[ée]cole|se former|[ée]tudes|bac\b|cap\b|"
                         r"comment (je )?(deviens|devenir)|o[uù] (me|se) former)", re.I)
MATCH_Q = re.compile(r"(correspond|ressembl|mes int[ée]r[êe]ts|fait pour moi|me convien)", re.I)
REPORT_LEVEL = re.compile(
    r"(mon rapport|mes r[ée]sultats|mes m[ée]tiers|mes int[ée]r[êe]ts|mes aptitudes|"
    r"ma personnalit|mon profil|lequel|lesquels|laquelle|quels m[ée]tiers|"
    r"les m[ée]tiers|zones?\b|compar|d[ée]partager|choisir entre)", re.I)
ON_TOPIC = re.compile(
    r"(m[ée]tier|travail|job|emploi|formation|[ée]tud|dipl[ôo]m|bac|cap\b|bts|licence|"
    r"master|[ée]cole|zone|rapport|int[ée]r[êe]t|riasec|orientation|apprentissage|"
    r"alternance|lyc[ée]e|fac|universit|comp[ée]tence|avenir|choisir|h[ée]site|"
    r"d[ée]partager|aime|passion|profil|r[ée]sultat)", re.I)
OFF_TOPIC = ("Je ne sais pas répondre à ça : je suis là pour t'aider à explorer les métiers "
             "de ton rapport et les formations qui y mènent. 🙂 Tu veux que je t'explique un "
             "de tes métiers, ou le chemin pour y arriver ?")
SALARY = re.compile(r"(salaire|gagn|pay[ée]|rémunér|€|euros?\b|smic|combien .*touch)", re.I)
SALARY_ANSWER = (
    "Je ne sais pas : les salaires ne sont pas dans mes sources (France Travail ROME, ONISEP, "
    "Centre des Possibles), et je préfère ne pas inventer de chiffre. 💶\n\n"
    "- Les fiches métiers ONISEP donnent souvent un salaire débutant (lien dans les sources).\n"
    f"- Tu peux aussi regarder {ORIENTATION_SUD}.\n"
    "- Et c'est une très bonne question à poser au psychologue du Centre des Possibles !")
