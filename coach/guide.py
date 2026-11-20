"""Texts from the « Guide pratique du Centre des Possibles » (docs/), used to explain a
young person's results the way the Centre does. Every text is cited as this guide."""

from __future__ import annotations

from coach.text import normalize

GUIDE = "Guide pratique du Centre des Possibles"
METIERS_360 = "https://www.metiers360.com"

INTERESTS = {
    "Réaliste": "préfère les activités concrètes, pratiques et souvent manuelles : objets, outils, "
                "machines, plantes ou animaux, souvent en extérieur. Plus à l'aise face à des "
                "problèmes concrets qu'abstraits ; préfère « faire » plutôt que réfléchir longuement.",
    "Investigateur": "aime observer, apprendre, analyser et comprendre le fonctionnement des "
                     "choses : recherche, sciences, mathématiques, problèmes complexes. Préfère "
                     "les idées et les données ; les cadres trop rigides peuvent freiner.",
    "Artistique": "attiré par la créativité, l'imagination et l'expression personnelle (art, "
                  "écriture, musique...). Préfère les environnements flexibles et originaux, "
                  "peut se sentir limité dans des cadres très réglementés.",
    "Social": "aime travailler avec les autres et pour les autres : aider, accompagner, "
              "enseigner, soigner, soutenir. Résout les problèmes par la discussion, l'écoute et "
              "la coopération ; moins attiré par les activités surtout techniques.",
    "Entreprenant": "aime influencer, convaincre, diriger ou motiver les autres, prendre des "
                    "initiatives et des responsabilités. Apprécie la décision et l'action, moins "
                    "les tâches très détaillées ou routinières.",
    "Conventionnel": "préfère les activités organisées, structurées et prévisibles : données, "
                     "chiffres, dossiers, procédures claires. Accorde de l'importance à l'ordre, "
                     "à la rigueur et à la fiabilité.",
}

APTITUDES = {
    "Originalité": ("trouver plusieurs solutions différentes à un même problème, avec créativité",
                    "un directeur artistique propose plusieurs concepts publicitaires ; une aide "
                    "médico-psychologique adapte une activité à différents handicaps"),
    "Raisonnement déductif": ("appliquer des règles générales pour résoudre des problèmes "
                              "spécifiques",
                              "tester la résistance des matériaux pour construire un pont ; un "
                              "pâtissier crée sa carte avec les produits de saison"),
    "Raisonnement inductif": ("trouver des liens entre des événements apparemment sans rapport "
                              "pour deviner une règle cachée",
                              "un médecin trouve le bon diagnostic grâce à plusieurs examens ; un "
                              "mécanicien trouve la panne d'un véhicule"),
    "Flexibilité des catégories": ("s'adapter rapidement à un changement de règle ou "
                                   "d'environnement",
                                   "passer en urgence à une césarienne ; un psychologue adapte "
                                   "son approche à un patient très inhibé"),
    "Facilité avec les nombres": ("calcul mental et estimation des quantités",
                                  "estimer les litres de peinture pour un mur ; rendre la "
                                  "monnaie sur un stand"),
    "Mémorisation": ("mémoriser, manipuler et restituer des informations",
                     "un acteur apprend son texte ; un gérant retient où sont rangés les "
                     "produits"),
    "Visualisation": ("se représenter mentalement des mouvements ou des rotations en 3D",
                      "concevoir un jardin en imaginant la croissance des plantes ; placer portes "
                      "et fenêtres dans un bâtiment"),
    "Attention sélective": ("repérer les informations utiles en ignorant les distractions",
                            "repérer une anomalie sur une IRM ; repérer les failles de sécurité "
                            "d'un chantier"),
    "Partage du temps": ("faire passer son attention d'une chose à une autre et faire plusieurs "
                         "choses à la fois sans se tromper",
                         "un serveur suit les clients, ses collègues et les commandes en même "
                         "temps"),
}

PERSONALITY = {
    "Emotivité": "grande sensibilité et empathie : on ressent fortement les émotions, les "
                 "siennes comme celles des autres, et on est attentif aux relations",
    "Caractère consciencieux": "organisé, discipliné, précis, réfléchit avant de décider",
    "Extraversion": "énergie, sociabilité, confiance en soi, goût pour les échanges et les groupes",
    "Humilité-honnêteté": "sincérité, équité, n'aime pas manipuler, peu motivé par le statut ou "
                          "l'argent",
    "Agréabilité": "bienveillance, coopération, indulgence, préfère éviter les conflits",
    "Ouvert à l'expérience": "curiosité, imagination, intérêt pour la nouveauté, l'art et les "
                             "idées originales",
}

ZONE_EXAMPLES = {
    1: "aide à domicile, barista, ouvrier agricole, hôtesse d'accueil",
    2: "charpentier, maçon, brancardier, aide-soignant, auxiliaire de puériculture "
       "(CAP/BEP, souvent en alternance)",
    3: "technicien de laboratoire, administrateur réseau, animateur socio-culturel, "
       "éducateur spécialisé (BTS, licence pro)",
    4: "infirmier-anesthésiste, professeur des écoles, ingénieur informaticien, psychologue, "
       "diététicien (master ou licence + concours)",
    5: "médecin généraliste, avocat, architecte-urbaniste, enseignant-chercheur "
       "(doctorat ou spécialisation après le master)",
}

HOW_TO_READ = (
    "Comment lire tes résultats (guide d'interprétation du Centre) :\n"
    "- Ce ne sont pas des résultats définitifs : c'est une image à un moment donné (fatigue, "
    "stress, contexte comptent), et les intérêts comme certaines aptitudes évoluent.\n"
    "- On compare tes résultats entre eux, pas avec les autres : ils montrent tes points forts "
    "relatifs, pas un classement par rapport à une norme.\n"
    "- Un profil hétérogène, c'est courant : ça veut dire que tu as plusieurs ressources et "
    "plusieurs directions possibles.\n"
    "- Les métiers proposés ne ferment aucune porte : le but est d'ouvrir des options, pas de prédire ta "
    "réussite.\n"
    "- C'est toi l'expert de ton vécu : ton avis sur ces résultats compte autant que les "
    "chiffres.\n"
    "- On peut refaire le parcours après quelques mois ou années.")

FAQ_ALGO = (
    "Comment le rapport choisit les métiers : un algorithme conçu avec l'Université Côte "
    "d'Azur compare ton profil (aptitudes cognitives et intérêts) à celui de professionnels "
    "de la base O*NET, et retient les métiers les plus proches. Certains métiers que tu "
    "envisages peuvent ne pas apparaître : ce n'est pas une interdiction.")


def topics_in(question: str) -> list[tuple[str, str]]:
    """Guide definitions for the aptitudes / traits / interests named in a question."""
    q = normalize(question)
    found = []
    for name, (definition, examples) in APTITUDES.items():
        if normalize(name) in q or (name == "Partage du temps" and "attention partagee" in q):
            found.append((name, f"{name} : capacité à {definition}. Exemples concrets : "
                                f"{examples}."))
    for name, text in PERSONALITY.items():
        key = normalize(name).split()[0]
        if key in q or (name == "Emotivité" and "emoti" in q):
            found.append((name, f"{name} (personnalité, modèle HEXACO) : {text}."))
    for name, text in INTERESTS.items():
        if normalize(name) in q:
            found.append((name, f"{name} (intérêts RIASEC) : une personne qui {text}"))
    return found
