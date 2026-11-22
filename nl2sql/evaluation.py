"""Évaluation par exactitude d'exécution : on compare les RÉSULTATS des requêtes, pas leur texte.

Deux requêtes écrites différemment mais qui renvoient les mêmes lignes sont jugées justes.
La base est ouverte en lecture seule et chaque requête a un délai maximal.
"""
import sqlite3
import time
from collections import defaultdict
from pathlib import Path

INTERDITS = ("insert", "update", "delete", "drop", "alter", "create", "attach", "pragma", "replace")


def _normaliser(lignes: list[tuple], ordonne: bool) -> list[tuple]:
    def val(v):
        return round(v, 2) if isinstance(v, float) else v
    propres = [tuple(val(v) for v in l) for l in lignes]
    return propres if ordonne else sorted(propres, key=repr)


def executer(con: sqlite3.Connection, sql: str, delai_s: float = 5.0) -> tuple[list[tuple] | None, str | None]:
    s = (sql or "").strip().lower()
    if not s.startswith(("select", "with")) or any(f" {m} " in f" {s} " for m in INTERDITS):
        return None, "requête refusée (lecture seule)"
    fin = time.monotonic() + delai_s
    con.set_progress_handler(lambda: 1 if time.monotonic() > fin else 0, 10_000)
    try:
        return con.execute(sql).fetchall(), None
    except sqlite3.Error as e:
        return None, f"{type(e).__name__}: {e}"
    finally:
        con.set_progress_handler(None, 0)


def evaluer(base: Path, exemples: list[dict], predictions: dict[str, str]) -> dict:
    """`exemples` : jeu de test (id, gabarit, sql) ; `predictions` : id → SQL prédit."""
    con = sqlite3.connect(f"file:{Path(base)}?mode=ro", uri=True)
    justes, erreurs, details = 0, 0, []
    par_gabarit = defaultdict(lambda: [0, 0])
    for ex in exemples:
        attendu, err_ref = executer(con, ex["sql"])
        if err_ref:
            raise ValueError(f"Requête de référence invalide ({ex['id']}) : {err_ref}")
        pred = predictions.get(ex["id"], "")
        obtenu, err = executer(con, pred)
        ordonne = "order by" in ex["sql"].lower()
        ok = err is None and _normaliser(obtenu, ordonne) == _normaliser(attendu, ordonne)
        justes += ok
        erreurs += err is not None
        par_gabarit[ex["gabarit"]][0] += ok
        par_gabarit[ex["gabarit"]][1] += 1
        details.append({"id": ex["id"], "gabarit": ex["gabarit"], "juste": ok, "erreur": err, "sql_predit": pred})
    con.close()
    n = len(exemples)
    return {
        "n": n, "justes": justes, "exactitude": round(100 * justes / n, 1) if n else 0.0,
        "erreurs_sql": erreurs,
        "par_gabarit": {g: round(100 * j / t, 1) for g, (j, t) in sorted(par_gabarit.items())},
        "details": details,
    }
