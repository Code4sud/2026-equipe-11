# Équipe 11 — Hackathon Azuréen #3

Projet réalisé à Nice les 18, 19 et 20 novembre 2026, sur le thème **« L'orientation et l'employabilité grâce à l'IA »**, organisé par [Code4Sud](https://code4sud.fr).

## Le projet

Nos jeunes cherchent une formation et ne savent pas quelle est la marche à suivre.
Quelle école/formation intégrer ? Ai-je besoin du bac ? Quel est le salaire d'entrée ?  

C'est la qu'intervient Le Forum, notre assistant IA qui assimile le "Rapport des Possibilités" généré par le "Centre des Possibles" et guide l'utilisateur étape par étape pour réaliser son projet, en prenant en compte ses capacités, ses centres d'intérêt et les contraintes auxquelles il peut être confronté.
Il répondra à ses questions à partir des données qui lui ont été fournies, et l'aiguillera dans sa recherche afin d'arriver à son objectif, le plus rapidement possible.

## Lancer le projet

1. **Installer les dépendances** (il faut [uv](https://docs.astral.sh/uv/)) :

```bash
    uv sync
```

2. **Lancer le modèle IA en local** (il faut [Ollama](https://ollama.com) :

```bash
    ollama serve &
    ollama pull qwen2.5:3b    # qwen2.5:7b = réponses plus riches mais 2x plus lent
    cp .env.example .env
```

3. **Démarrer l'appli** :

```bash
    uv run streamlit run app.py
```

Puis ouvrir http://localhost:8501.

## Licence

MIT — voir `LICENSE`.

## Auteurs
***Ali ABOU DAHER***  
***Alan BALLOTEAU***  
***Tim BOISSEAU***  
***Noé BERNARD***  
***Ibrahim ABDELKABIR***  
***Andrés BALLESTEROS***
