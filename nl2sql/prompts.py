"""Format des échanges envoyés au modèle (identique à l'entraînement et à l'évaluation)."""
import re

from nl2sql.schema import DDL

SYSTEME = (
    "Tu traduis des questions métier posées en français en une seule requête SQL SQLite, en lecture seule.\n"
    "Règles : une seule instruction SELECT ou WITH ; utilise uniquement les tables et colonnes du schéma ; "
    "une facture appartient à un compte (factures.compte_id), pas directement à un client ; "
    "les mois s'écrivent AAAA-MM. Réponds uniquement par la requête SQL, sans explication.\n\n"
    f"Schéma :\n{DDL}"
)


def messages_prompt(question: str) -> list[dict]:
    return [{"role": "system", "content": SYSTEME}, {"role": "user", "content": question}]


def exemple_sft(exemple: dict) -> dict:
    """Format « prompt / completion » conversationnel de TRL : la perte ne porte que sur la réponse."""
    return {"prompt": messages_prompt(exemple["question"]),
            "completion": [{"role": "assistant", "content": exemple["sql"]}]}


def extraire_sql(texte: str) -> str:
    """Récupère la requête dans la réponse du modèle (blocs ```sql, texte autour, plusieurs lignes)."""
    texte = (texte or "").strip()
    bloc = re.search(r"```(?:sql)?\s*(.*?)```", texte, re.S | re.I)
    if bloc:
        texte = bloc.group(1).strip()
    debut = re.search(r"\b(WITH|SELECT)\b", texte, re.I)
    if not debut:
        return ""
    texte = texte[debut.start():]
    texte = texte.split(";")[0].strip()
    return texte + ";" if texte else ""
