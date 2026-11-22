"""Crée la base SQLite fictive et le jeu de données labellisé (train / test)."""
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nl2sql import jeu, schema  # noqa: E402
from nl2sql.evaluation import executer  # noqa: E402

RACINE = Path(__file__).resolve().parents[1]


def main() -> None:
    base = schema.creer_base(RACINE / "data" / "telecom_fictif.db")
    train, test = jeu.generer()
    import sqlite3
    con = sqlite3.connect(base)
    vides = []
    for ex in train + test:                      # chaque requête de référence doit s'exécuter et renvoyer quelque chose
        lignes, err = executer(con, ex["sql"])
        if err:
            raise SystemExit(f"Requête invalide {ex['id']} : {err}\n{ex['sql']}")
        if not lignes or all(v is None for l in lignes for v in l):
            vides.append(ex["id"])
    con.close()
    jeu.ecrire_jsonl(train, RACINE / "data" / "train.jsonl")
    jeu.ecrire_jsonl(test, RACINE / "data" / "test.jsonl")
    print(f"Base : {base}")
    print(f"Train : {len(train)} exemples · Test : {len(test)} exemples · {len(jeu.GABARITS)} gabarits")
    print(f"Résultats vides : {len(vides)}")
    print("Exemples par gabarit (train) :", dict(Counter(e['gabarit'] for e in train)))


if __name__ == "__main__":
    main()
