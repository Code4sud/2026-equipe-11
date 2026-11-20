# 🧭 Coach des Possibles

**Hackathon Code4Sud, sujet 2 : l'assistant IA d'exploration des métiers.**

Un jeune reçoit son *Rapport des Possibles* : 25 métiers dont il n'a souvent jamais entendu parler.
Ses questions sont simples. *C'est quoi, concrètement ? Il faut quel diplôme ? Je peux le faire sans
le bac ? Où me former près de chez moi ?* Il est 23 h et personne n'est là pour répondre.

Coach des Possibles est un assistant conversationnel qui :

- **lit le rapport PDF** (en mémoire uniquement) : les métiers proposés zone par zone **et les
  résultats du jeune**. Les scores (intérêts RIASEC, 9 aptitudes cognitives, personnalité HEXACO)
  ne sont pas du texte dans le PDF : ils sont relus depuis la géométrie des graphiques vectoriels
  (polygone des radars, hauteur des barres) ;
- **relie chaque métier du rapport aux référentiels publics** : ROME 4.0 (France Travail), puis
  ONISEP (fiches métiers), puis l'offre de formation géolocalisée de la Région Sud ;
- **répond en citant ses sources** [1], [2]… avec des liens cliquables ;
- **sait dire « je ne sais pas »** : salaires, correspondance incertaine, hors sujet ;
- **tourne sur un modèle open weight en local** (Qwen 2.5 via Ollama), sur un simple PC portable
  sans GPU.

Il couvre aussi l'angle 3 : un jeune **sans rapport** peut choisir des métiers vus au lycée ou dans
un forum.

## Stack

**Langages**
- **Python 3.11** : tout le projet (données, logique, interface)
- **HTML / CSS** : le style de l'interface, injecté dans Streamlit (`coach/theme.py`)
- **TOML** : la configuration (thème Streamlit, dépendances)
- **JavaScript** : uniquement le bandeau du hackathon, chargé depuis le site des organisateurs

**Outils et bibliothèques**

| Rôle | Outil |
|---|---|
| Gestion du projet et des dépendances | **uv** (`pyproject.toml`) |
| Interface web | **Streamlit**, avec **pydeck** (cartes) et **Altair** (graphiques) |
| IA (LLM open-weight, en local) | **Ollama** + **qwen2.5:3b**, appelé par une API compatible OpenAI via **httpx** |
| Rapprochement des métiers avec le ROME | **rapidfuzz** (noms proches) + **fastembed** (modèle multilingue MiniLM, par le sens) |
| Lecture du Rapport des Possibles | **pdfplumber** (texte, radars et barres du PDF) |
| PDF « feuille de route » | **fpdf2** + **segno** (QR codes), police Outfit |
| Données ouvertes | ROME 4.0 (France Travail), ONISEP (métiers, formations Région Sud, catalogue national) |

## Lancer le projet

1. **Installer les dépendances** (il faut [uv](https://docs.astral.sh/uv/)) :
   bash
   uv sync
   
2. **Lancer le modèle IA en local** (il faut [Ollama](https://ollama.com) ; pas besoin de GPU) :
   bash
   ollama serve &
   ollama pull qwen2.5:3b    # qwen2.5:7b = réponses plus riches mais 2x plus lent
   cp .env.example .env
   
3. **Démarrer l'appli** :
   bash
   uv run streamlit run app.py
   
   Puis ouvrir http://localhost:8501.
4. **Pour la démo**, avec le rapport d'exemple, un métier, une ville et une situation déjà
   remplis : http://localhost:8501/?demo=1&job=Infirmier&city=Toulon&sit=0
   (le rapport d'exemple doit être dans `docs/`, qui n'est pas publié sur git).

**Bon à savoir**
- Les données sont déjà prêtes dans `data/processed/`. Pour les retélécharger et les
  reconstruire (environ 2 min) :
  bash
  uv run python scripts/download_data.py
  uv run python scripts/build_data.py
  
- Sans Ollama, l'appli marche quand même : les cartes, le chemin, la carte des formations, le
  comparateur, le PDF et les réponses calculées n'utilisent pas l'IA. Seules les questions libres
  du chat affichent alors un message d'erreur.
- Le chat existe aussi en terminal :
  bash
  uv run python main.py --city Nice --no-bac -q "infirmier, je peux le faire sans le bac ?"
  
- Pour vérifier la qualité du chat, il y a un test automatique de 13 vérifications :
  bash
  uv run python scripts/eval.py
  

## Ce que voit le jeune

Le problème du sujet : le jeune reçoit d'un coup des métiers dont il n'a jamais entendu
parler, et ses questions sont simples. **Un clic sur un métier y répond tout de suite, sans
avoir à taper quoi que ce soit, et sans LLM (donc sans risque d'invention).**

| Écran | À quoi ça sert |
|---|---|
| **Tes métiers** | Les métiers lus dans le rapport (sans les « zones » : le jeune choisit directement ce qui l'intéresse), plus une recherche parmi **tous les métiers** (table du Centre + 1 923 fiches ROME) pour en ajouter un. Sans rapport, la recherche suffit pour commencer. |
| **4 réponses immédiates** | 🔎 *C'est quoi ?* (définition ROME) · 🎓 *Quel diplôme ?* (le diplôme du chemin le plus direct, son niveau et sa durée) · 🔓 *Sans le bac ?* (**Oui** / **Pas directement, mais une passerelle existe** / **Non**) · 💶 *Combien ?* (« je ne sais pas encore », avec un lien vers la fiche ONISEP, plutôt qu'un chiffre inventé). Le détail « au quotidien » (tâches, horaires, conditions, lieux) est juste en dessous. |
| **🧭 Ton chemin** | La **feuille de route** depuis la situation du jeune (collège, lycée/CAP, bac, études sup.) : étapes, durée totale, établissement le plus proche. Si toutes les formations demandent le bac, une **passerelle sans le bac** issue des mobilités officielles du ROME (ex. *aide-soignant → infirmier*). En dessous : **tous les diplômes** qui mènent au métier, rangés par moment d'entrée (après la 3e, après une 2de ou un CAP, après le bac, après bac + 2), avec durée, niveau, nombre d'établissements publics, internat, le plus proche. Bouton **📄 Télécharger ma feuille de route (PDF)** : un A4 aux couleurs du Centre, à garder, imprimer ou montrer à un conseiller le lendemain. Il contient le métier en bref, les réponses-clés, le chemin dessiné étape par étape, les 3 formations conseillées (liens cliquables **et QR codes**, pour que la feuille imprimée reste utile), le quotidien, des lignes « Mes questions pour un conseiller » et les sources. En haut, un **QR code vers la fiche métier** (ONISEP, sinon France Travail). Il est généré avec `fpdf2`, `segno` (QR codes) et la police libre Outfit (`assets/fonts/`). |
| **📍 Où te former ?** | **⭐ Pour toi** : les 3 formations qui conviennent le mieux, chacune avec le **pourquoi** (« tu peux y entrer maintenant », « à 6 km », « public », « diplôme reconnu (RNCP) », « internat possible »…). Le jeune choisit ce qui compte pour lui (études courtes, rester près de chez soi, public, internat). Le classement suit des règles simples et transparentes, **pas une IA**. **Carte** : un point par établissement, les 3 choix « Pour toi » numérotés en rose, ton domicile (« Toi »), et la liste des formations au survol. Le cadrage montre ton domicile et tes meilleurs choix (bouton « Toute la région » pour dézoomer). **Un clic sur un point** affiche toutes les formations de l'établissement (durée, niveau d'entrée, public/privé, sans le bac, internat, lien ONISEP). Tableau comparatif complet dans un volet. |
| **💬 Pose ta question** | Le chat, pour les questions de 23 h. Les questions clés (*sans le bac ?*, *comment je deviens… ?*, *quel diplôme ?* quand rien n'est trouvé) ont des **réponses calculées** ; le reste est rédigé par le LLM à partir des sources citées. |
| **⚖️ Comparer** | 2 ou 3 métiers dans un tableau aligné (une ligne par question : diplôme le plus direct, durée depuis ta situation, sans le bac, formation la plus proche, nombre de formations, horaires, intérêts en commun, réglementé), avec **⭐ le plus court / le plus proche**. En dessous, une carte des 5 formations les mieux placées de chaque métier, une couleur par métier. |

## Architecture

```
Rapport PDF ──► report.py ──► métiers + zones du rapport
                                   │
table métiers Centre (O*NET) ──────┤  matching.py : nom (fuzzy) + sens (embeddings)
                                   ▼
                              code ROME 4.0 ──► fiche ROME (définition, accès, RIASEC)
                                   │        ──► fiches ONISEP
                                   │        ──► formations Région Sud (ONISEP/LHEO, GPS)
                                   ▼
               kb.py : sources numérotées + faits calculés (sans le bac ? la plus proche ?)
                                   ▼
               assistant.py : garde-fous déterministes ──► LLM local (Ollama) ──► réponse citée
```

| Fichier | Rôle |
|---|---|
| `scripts/download_data.py` | télécharge les jeux open data |
| `scripts/build_data.py` | construit `data/processed/*.json` et relie les 721 métiers O*NET au ROME |
| `coach/matching.py` | correspondance métier → ROME : similarité des noms (toutes appellations ROME + ONISEP, masculin/féminin) **et** similarité sémantique des descriptions (`paraphrase-multilingual-MiniLM`, CPU) |
| `coach/kb.py` | base de connaissances : sources citables, formations triées par distance, faits déterministes |
| `coach/assistant.py` | détection du métier dans la question, prompt, garde-fous |
| `coach/llm.py` | client pour tout endpoint compatible OpenAI (Ollama, LM Studio, Mistral, HF) |
| `app.py` / `main.py` | interface web Streamlit / terminal |
| `scripts/eval.py` | évaluation comportementale |

## Fiabilité : comment on évite d'inventer

1. **Le LLM ne répond qu'à partir des sources fournies**, qui sont numérotées, et il doit les citer.
2. **Les faits sensibles sont calculés, pas générés.** « Accessible sans le bac : oui/non » vient
   du niveau d'entrée des formations ONISEP. La fiche express ne passe jamais par le LLM.
3. **Plus de métiers reliés à des formations, sans deviner.** Quand l'ONISEP ne relie aucune
   formation à un métier ROME, on cherche dans l'offre Région Sud **les diplômes que France
   Travail cite pour ce métier** (ex. *Coach sportif* → BPJEPS « activités de la forme »,
   licences STAPS). La correspondance est stricte : même diplôme, ou tous ses mots dans le
   titre. Elle relie 786 métiers ROME de plus, et la source le signale.
4. **La correspondance métier → ROME a un niveau de confiance.** Elle est « sûre » seulement si le
   nom et le sens concordent (485 / 721 métiers). Sinon l'assistant **le dit** et propose des
   pistes à vérifier au lieu d'inventer des formations. Dans l'interface, ces pistes sont des
   **boutons** (« 👉 Plongeur en restauration ») : c'est le jeune qui précise, pas le modèle
   qui devine.
5. **« Explique-moi mes résultats »** est rédigé à partir du rapport et des textes du guide du
   Centre (définitions, exemples concrets, règles d'interprétation), pas improvisé par le modèle.
   Seuls les intérêts vraiment dominants sont présentés comme tels.
6. **Les questions au cœur du sujet sont calculées.** *« Je peux le faire sans le bac ? »*,
   *« Comment je deviens… ? »* et *« Quel diplôme ? »* (pour un métier sans formation trouvée)
   sont répondues à partir de la feuille de route et des données, avec les numéros de source. Le
   modèle 3B, lui, se contredisait (« tu peux le faire sans le bac, mais aucune formation n'est
   accessible sans le bac »).
7. **Pas d'exemple « réel » dans le prompt.** Le modèle recopiait l'exemple du prompt
   (« CAP boulanger au lycée Escoffier » dans une réponse sur le musicothérapeute !). Il est
   remplacé par un échange fictif (« métier X », « source [1] »). Pour une question qui ne porte
   pas sur les formations, on ne lui donne pas non plus les sources de formation : ces
   informations sont déjà sur les cartes.
8. **Questions de liste sur tout le rapport** (« lesquels sont accessibles sans le bac ? »,
   « lesquels correspondent à mes intérêts ? ») : la réponse est **calculée**, pas générée. Un
   petit modèle mélange les listes, une requête sur les données non.
9. **Garde-fous codés en dur**, indépendants du modèle :
   - question de salaire : « je ne sais pas » + où chercher (aucune donnée salaire ouverte
     n'est intégrée pour l'instant) ;
   - question hors sujet : recentrage poli ;
   - aucune source : « je ne sais pas » + Orientation Région Sud / psychologue du Centre.
10. **Pas de « zones »** : le jeune part des métiers qui l'intéressent (son rapport, ou un métier
   qu'il ajoute lui-même). Les zones O*NET du rapport ne sont plus affichées : la table du Centre
   signale d'ailleurs qu'elles ne correspondent pas toujours à la réalité française.

### Évaluation (`scripts/eval.py`)

9 questions types, 13 vérifications automatiques :
- citations ;
- « non » pour *infirmier sans le bac*, « oui » pour *auxiliaire de puériculture sans le bac* ;
- pas de salaire inventé ;
- incertitude signalée pour *plongeur* ;
- hors sujet ;
- **chemin avec la passerelle aide-soignant** pour *comment je deviens infirmier* ;
- **aucune formation ou école inventée** pour *musicothérapeute*, qui n'a pas de formation en
  Région Sud.

| Modèle (CPU, sans GPU) | Score | Temps total |
|---|---|---|
| qwen2.5:3b | 13 / 13 | ~25 s |

Sans nos sources, le même modèle affirmait qu'on peut devenir musicothérapeute sans le bac. Avec
elles, il dit qu'il ne sait pas et cite les diplômes indiqués par France Travail.

## Données (toutes ouvertes)

| Source | Utilisation |
|---|---|
| Centre des Possibles : table des métiers (O*NET → FR, zones) | métiers du rapport, descriptions, zones |
| [ROME 4.0, France Travail](https://www.data.gouv.fr/datasets/repertoire-operationnel-des-metiers-et-des-emplois-rome) (v62, oct. 2026) | définition, accès au métier, RIASEC, appellations, **mobilités** (de quel métier on peut évoluer vers celui-ci : les passerelles de « Ton chemin »), **compétences** (savoir-faire « cœur de métier », savoir-être, savoirs, diplômes cités) et **contextes de travail** (horaires, conditions, lieux, structures, statut) |
| Guide pratique du Centre des Possibles | explication des résultats : définitions et exemples concrets des 9 aptitudes, 6 traits HEXACO, 6 profils RIASEC, exemples de métiers par zone, règles d'interprétation (résultats non définitifs, comparaison intra-individuelle, le jeune expert de son vécu), FAQ, lien Métiers 360 |
| [ONISEP Idéo-Métiers](https://www.data.gouv.fr/datasets/ideo-metiers-onisep) | fiches métiers et lien ROME |
| [ONISEP Idéo-Actions de formation PACA](https://www.data.gouv.fr) | 5 845 formations géolocalisées, niveau d'entrée, statut public/privé, internat |
| [ONISEP Idéo-Formations initiales en France](https://www.data.gouv.fr/datasets/ideo-formations-initiales-en-france) | complète chaque formation régionale (jointure par identifiant ONISEP `FOR.xxxx`, 100 % des lignes) : type de diplôme, durée officielle, niveau RNCP, ministère de tutelle |
| [orientation-regionsud.fr](https://www.orientation-regionsud.fr/) | cité par lien uniquement, jamais extrait (règle du hackathon) : lien vers sa recherche de formations (dates, places, apprentissage) |

## Vie privée

- Le rapport PDF est lu **en mémoire**, n'est ni stocké ni envoyé : tout tourne en local.
- Aucune clé d'API dans le code : configuration par `.env` (ignoré par git).
- Les rapports PDF sont exclus du dépôt (`.gitignore`).

## Limites et suite

- **Salaires** : pas encore de source ouverte intégrée. Piste : API « Marché du travail » de France
  Travail (salaires par ROME et par région).
- 236 métiers sur 721 n'ont pas de correspondance ROME sûre. Une relecture humaine ou un rerank
  par LLM améliorerait la couverture.
- Offre de formation limitée à la formation initiale ONISEP. Les données Carif-Oref (formation
  continue) seraient le complément naturel pour les jeunes déscolarisés.
- Version vocale (angle 1) : Whisper en local et synthèse vocale.
