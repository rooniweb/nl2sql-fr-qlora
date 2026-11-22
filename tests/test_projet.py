from pathlib import Path

import pytest

from nl2sql import jeu, schema
from nl2sql.evaluation import evaluer
from nl2sql.prompts import exemple_sft, extraire_sql


@pytest.fixture(scope="module")
def base(tmp_path_factory) -> Path:
    return schema.creer_base(tmp_path_factory.mktemp("db") / "t.db")


@pytest.fixture(scope="module")
def jeux():
    return jeu.generer()


def test_jeu_deterministe(jeux):
    assert jeu.generer() == jeux


def test_formulations_de_test_jamais_vues(jeux):
    """Aucune question d'entraînement n'est une variante (même préfixée) de la formulation réservée au test."""
    from itertools import product
    train, test = jeux
    questions_train = {e["question"].lower() for e in train}
    for g in jeu.GABARITS:
        noms = list(g["params"])
        combos = [dict(zip(noms, v)) for v in product(*(g["params"][n] for n in noms))] or [{}]
        rendus_test = {jeu._rendre(g["q"][-1], c).lower() for c in combos}
        for q in questions_train:
            assert not any(q == r or q.endswith(r[1:]) for r in rendus_test), (g["id"], q)
    assert not {e["question"].lower() for e in test} & questions_train


def test_tous_les_gabarits_au_test(jeux):
    _, test = jeux
    assert {e["gabarit"] for e in test} == {g["id"] for g in jeu.GABARITS}


def test_evaluation_reference_parfaite(base, jeux):
    _, test = jeux
    r = evaluer(base, test, {e["id"]: e["sql"] for e in test})
    assert r["exactitude"] == 100.0 and r["erreurs_sql"] == 0


def test_evaluation_par_resultat_pas_par_texte(base, jeux):
    _, test = jeux
    ex = next(e for e in test if e["gabarit"] == "clients_region")
    region = ex["sql"].split("'")[1]
    reformulee = f"select count(id) from clients c where c.region = '{region}'"
    r = evaluer(base, [ex], {ex["id"]: reformulee})
    assert r["justes"] == 1


def test_evaluation_detecte_les_erreurs(base, jeux):
    _, test = jeux
    preds = {e["id"]: e["sql"] for e in test}
    premier = test[0]["id"]
    preds[premier] = "SELECT 1;"
    preds[test[1]["id"]] = "DELETE FROM clients;"
    r = evaluer(base, test, preds)
    assert r["justes"] == len(test) - 2 and r["erreurs_sql"] == 1


def test_extraire_sql():
    assert extraire_sql("```sql\nSELECT 1;\n```") == "SELECT 1;"
    assert extraire_sql("Voici la requête : SELECT a FROM t; Bonne journée") == "SELECT a FROM t;"
    assert extraire_sql("WITH x AS (SELECT 1) SELECT * FROM x") == "WITH x AS (SELECT 1) SELECT * FROM x;"
    assert extraire_sql("Je ne sais pas.") == ""


def test_format_sft(jeux):
    train, _ = jeux
    ex = exemple_sft(train[0])
    assert [m["role"] for m in ex["prompt"]] == ["system", "user"]
    assert ex["completion"] == [{"role": "assistant", "content": train[0]["sql"]}]
    assert "compte_id" in ex["prompt"][0]["content"]
