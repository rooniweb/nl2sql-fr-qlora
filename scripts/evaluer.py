"""Évalue un fichier de prédictions JSONL ({"id": ..., "sql": ...}) sur le jeu de test."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nl2sql import jeu  # noqa: E402
from nl2sql.evaluation import evaluer  # noqa: E402

RACINE = Path(__file__).resolve().parents[1]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("predictions")
    p.add_argument("--sortie", default=None, help="fichier JSON du rapport")
    a = p.parse_args()
    preds = {l["id"]: l["sql"] for l in jeu.lire_jsonl(a.predictions)}
    r = evaluer(RACINE / "data" / "telecom_fictif.db", jeu.lire_jsonl(RACINE / "data" / "test.jsonl"), preds)
    print(f"Exactitude d'exécution : {r['exactitude']} % ({r['justes']}/{r['n']}) · erreurs SQL : {r['erreurs_sql']}")
    if a.sortie:
        Path(a.sortie).write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
