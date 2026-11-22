# NL2SQL-FR — Fine-tuning QLoRA d'un LLM open source pour le NL-to-SQL en français

Un petit modèle open source (**Qwen2.5-Coder-1.5B-Instruct**) affiné en **QLoRA** pour traduire des questions métier posées en français en requêtes SQL, sur le SI commercial d'un opérateur télécom **fictif**. L'objectif : mesurer ce que le fine-tuning apporte, par rapport au même modèle sans affinage, sur des formulations qu'il n'a jamais vues.

> Toutes les données sont **100 % fictives** et générées par le code du dépôt.

## Pourquoi ce projet

En entreprise, une assistante NL-to-SQL doit connaître le modèle de données et ses pièges métier : ici, *une facture appartient à un compte, pas directement à un client*. Le prompting d'un grand modèle généraliste coûte cher à chaque requête et envoie le schéma à un fournisseur externe. Un petit modèle affiné sur les questions du métier peut tourner en local, à coût fixe.

## Démarche

| Étape | Ce qui est fait | Fichier |
| --- | --- | --- |
| Données | Base SQLite fictive (clients, comptes, factures, paiements, boutiques), générée de façon déterministe | `nl2sql/schema.py` |
| Labellisation | 28 gabarits de questions métier, 4 formulations chacun, requête SQL de référence ; 1 272 exemples d'entraînement, 138 de test | `nl2sql/jeu.py` |
| Généralisation | La 4ᵉ formulation de chaque gabarit est **réservée au test** : le modèle est évalué sur des tournures jamais vues | `tests/test_projet.py` |
| Fine-tuning | QLoRA : modèle chargé en 4 bits (nf4), adaptateurs LoRA r = 16 sur toutes les projections, 2 époques, perte calculée sur la seule requête SQL (PEFT + TRL) | `notebooks/finetune_qlora.ipynb` |
| Évaluation | **Exactitude d'exécution** : on compare les résultats des requêtes sur la base, pas leur texte ; base ouverte en lecture seule, requêtes d'écriture refusées, délai maximal | `nl2sql/evaluation.py` |

## Résultats

Le tableau est rempli par le notebook (`resultats/resultats.json`) : modèle de base contre modèle affiné, exactitude d'exécution, erreurs SQL, temps par question, détail par gabarit.

## Lancer le projet

```bash
pip install -r requirements.txt
python scripts/preparer_donnees.py      # base fictive + jeu train/test
pytest -q                               # vérifie le jeu de données et l'évaluation
```

Entraînement et évaluation : ouvrir `notebooks/finetune_qlora.ipynb` dans Google Colab (GPU T4 gratuit) ou Kaggle, puis tout exécuter. Compter 30 à 45 minutes.

Évaluer un fichier de prédictions (`{"id": ..., "sql": ...}` par ligne) :

```bash
python scripts/evaluer.py resultats/predictions_qlora.jsonl --sortie resultats/rapport.json
```

## Stack

Python · PyTorch · Hugging Face Transformers · PEFT (LoRA / QLoRA) · TRL (SFT) · bitsandbytes · SQLite · pytest · GitHub Actions
