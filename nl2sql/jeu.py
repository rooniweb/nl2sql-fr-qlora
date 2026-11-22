"""Génération du jeu de données labellisé question (français) → SQL.

Chaque gabarit a plusieurs formulations. La DERNIÈRE formulation de chaque gabarit est réservée au jeu de
test : le modèle est évalué sur des tournures de phrase qu'il n'a jamais vues pendant l'entraînement.
"""
import json
import random
from itertools import product
from pathlib import Path

from nl2sql.schema import CANAUX, MOIS, OFFRES, REGIONS, SEGMENTS

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre"]
OFFRE_FR = {"Fixe": "fixe", "Mobile": "mobile", "Prepaye": "prépayé", "Internet": "Internet"}
STATUT_FR = {"Actif": "actifs", "Suspendu": "suspendus", "Resilie": "résiliés"}


def _mois_txt(m: str) -> str:
    return f"{MOIS_FR[int(m[5:]) - 1]} {m[:4]}"


# Chaque gabarit : formulations (avec {variables}), SQL de référence, domaines des variables.
# Les variables suffixées _txt sont dérivées automatiquement (voir _rendre).
GABARITS = [
    {"id": "clients_par_region", "params": {},
     "q": ["Combien de clients avons-nous par région ?", "Donne le nombre de clients dans chaque région.",
           "Répartition des clients par région, s'il te plaît.", "Quel est l'effectif client de chaque région ?"],
     "sql": "SELECT region, COUNT(*) AS nb_clients FROM clients GROUP BY region ORDER BY nb_clients DESC;"},
    {"id": "clients_region", "params": {"region": REGIONS},
     "q": ["Combien de clients sont basés à {region} ?", "Nombre de clients dans la région de {region}.",
           "Combien de clients compte la région {region} ?", "Quel est le nombre total de clients situés à {region} ?"],
     "sql": "SELECT COUNT(*) AS nb_clients FROM clients WHERE region = '{region}';"},
    {"id": "comptes_offre_actifs", "params": {"offre": OFFRES},
     "q": ["Combien de comptes {offre_txt} sont actifs ?", "Nombre de comptes actifs sur l'offre {offre_txt}.",
           "Donne-moi le nombre de comptes {offre_txt} au statut actif.", "Combien a-t-on de lignes {offre_txt} encore actives ?"],
     "sql": "SELECT COUNT(*) AS nb_comptes FROM comptes WHERE offre = '{offre}' AND statut = 'Actif';"},
    {"id": "comptes_statut_region", "params": {"statut": ["Suspendu", "Resilie"], "region": REGIONS},
     "q": ["Combien de comptes {statut_txt} à {region} ?", "Nombre de comptes {statut_txt} pour les clients de {region}.",
           "Dans la région {region}, combien de comptes sont {statut_txt} ?", "Quel est le nombre de comptes {statut_txt} chez les clients basés à {region} ?"],
     "sql": "SELECT COUNT(*) AS nb_comptes FROM comptes co JOIN clients c ON c.id = co.client_id WHERE co.statut = '{statut}' AND c.region = '{region}';"},
    {"id": "comptes_par_statut", "params": {},
     "q": ["Combien de comptes par statut ?", "Répartition des comptes selon leur statut.",
           "Donne le nombre de comptes actifs, suspendus et résiliés.", "Quelle est la ventilation des comptes par statut ?"],
     "sql": "SELECT statut, COUNT(*) AS nb_comptes FROM comptes GROUP BY statut ORDER BY nb_comptes DESC;"},
    {"id": "facture_total_mois", "params": {"mois": MOIS},
     "q": ["Quel est le montant total facturé en {mois_txt} ?", "Montant total des factures du mois {mois}.",
           "Combien avons-nous facturé en {mois_txt} ?", "Total facturé pour le mois de {mois_txt}, en FCFA."],
     "sql": "SELECT SUM(montant) AS total_facture FROM factures WHERE mois = '{mois}';"},
    {"id": "encaisse_total_mois", "params": {"mois": MOIS},
     "q": ["Quel est le montant total encaissé en {mois_txt} ?", "Total des encaissements du mois {mois}.",
           "Combien avons-nous encaissé en {mois_txt} ?", "Montant des paiements reçus pendant le mois de {mois_txt}."],
     "sql": "SELECT SUM(montant) AS total_encaisse FROM paiements WHERE strftime('%Y-%m', date_paiement) = '{mois}';"},
    {"id": "encaisse_boutique_mois", "params": {"mois": MOIS},
     "q": ["Encaissements de {mois_txt} par boutique.", "Donne le montant encaissé par chaque boutique en {mois_txt}.",
           "Classement des boutiques selon leurs encaissements du mois {mois}.", "Combien chaque boutique a-t-elle encaissé en {mois_txt} ?"],
     "sql": "SELECT b.nom, SUM(p.montant) AS total_encaisse FROM paiements p JOIN boutiques b ON b.id = p.boutique_id WHERE strftime('%Y-%m', p.date_paiement) = '{mois}' GROUP BY b.nom ORDER BY total_encaisse DESC;"},
    {"id": "meilleure_boutique_mois", "params": {"mois": MOIS},
     "q": ["Quelle boutique a le plus encaissé en {mois_txt} ?", "Boutique avec le plus gros montant encaissé au mois {mois}.",
           "Quelle est la meilleure boutique en encaissements pour {mois_txt} ?", "Donne la boutique numéro un des encaissements de {mois_txt}."],
     "sql": "SELECT b.nom, SUM(p.montant) AS total_encaisse FROM paiements p JOIN boutiques b ON b.id = p.boutique_id WHERE strftime('%Y-%m', p.date_paiement) = '{mois}' GROUP BY b.nom ORDER BY total_encaisse DESC LIMIT 1;"},
    {"id": "encaisse_canal_mois", "params": {"mois": MOIS},
     "q": ["Encaissements de {mois_txt} par canal de paiement.", "Répartition des montants encaissés par canal en {mois_txt}.",
           "Combien a été encaissé via chaque canal au mois {mois} ?", "Montant payé par canal pour {mois_txt}."],
     "sql": "SELECT canal, SUM(montant) AS total_encaisse FROM paiements WHERE strftime('%Y-%m', date_paiement) = '{mois}' GROUP BY canal ORDER BY total_encaisse DESC;"},
    {"id": "nb_paiements_canal_mois", "params": {"canal": CANAUX, "mois": MOIS},
     "q": ["Combien de paiements via {canal} en {mois_txt} ?", "Nombre de paiements par {canal} au mois {mois}.",
           "Combien de clients ont payé par {canal} en {mois_txt} ?", "Quel est le nombre de transactions {canal} enregistrées en {mois_txt} ?"],
     "sql": "SELECT COUNT(*) AS nb_paiements FROM paiements WHERE canal = '{canal}' AND strftime('%Y-%m', date_paiement) = '{mois}';"},
    {"id": "paiement_moyen_canal", "params": {"canal": CANAUX},
     "q": ["Quel est le montant moyen d'un paiement via {canal} ?", "Paiement moyen par {canal}.",
           "Montant moyen des paiements effectués par {canal}.", "En moyenne, combien paie-t-on par {canal} ?"],
     "sql": "SELECT ROUND(AVG(montant), 2) AS paiement_moyen FROM paiements WHERE canal = '{canal}';"},
    {"id": "part_canal", "params": {},
     "q": ["Quelle part des encaissements passe par chaque canal ?", "Pourcentage du montant encaissé par canal.",
           "Donne la part de chaque canal dans le total encaissé.", "Répartition en pourcentage des encaissements selon le canal."],
     "sql": "SELECT canal, ROUND(100.0 * SUM(montant) / (SELECT SUM(montant) FROM paiements), 2) AS part_pct FROM paiements GROUP BY canal ORDER BY part_pct DESC;"},
    {"id": "impayees_par_offre", "params": {},
     "q": ["Combien de factures impayées par offre ?", "Nombre de factures non payées pour chaque offre.",
           "Répartition des factures impayées selon l'offre.", "Pour chaque offre, combien de factures restent impayées ?"],
     "sql": "SELECT co.offre, COUNT(*) AS nb_impayees FROM factures f JOIN comptes co ON co.id = f.compte_id WHERE f.statut = 'Impayee' GROUP BY co.offre ORDER BY nb_impayees DESC;"},
    {"id": "impaye_par_region", "params": {},
     "q": ["Montant total impayé par région.", "Quel est le montant des impayés dans chaque région ?",
           "Classement des régions par montant impayé.", "Combien reste-t-il à recouvrer par région ?"],
     "sql": "SELECT c.region, SUM(f.montant) AS total_impaye FROM factures f JOIN comptes co ON co.id = f.compte_id JOIN clients c ON c.id = co.client_id WHERE f.statut = 'Impayee' GROUP BY c.region ORDER BY total_impaye DESC;"},
    {"id": "top_clients_impayes", "params": {"n": [3, 5, 10]},
     "q": ["Quels sont les {n} clients avec le plus gros montant impayé ?", "Top {n} des clients par montant d'impayés.",
           "Donne les {n} clients qui doivent le plus.", "Liste des {n} plus gros débiteurs."],
     "sql": "SELECT c.nom, SUM(f.montant) AS total_impaye FROM factures f JOIN comptes co ON co.id = f.compte_id JOIN clients c ON c.id = co.client_id WHERE f.statut = 'Impayee' GROUP BY c.id, c.nom ORDER BY total_impaye DESC LIMIT {n};"},
    {"id": "comptes_n_impayees", "params": {"n": [2, 3, 4, 5]},
     "q": ["Combien de comptes ont plus de {n} factures impayées ?", "Nombre de comptes avec strictement plus de {n} factures non payées.",
           "Combien de comptes cumulent plus de {n} impayés ?", "Quels comptes dépassent {n} factures impayées ? Donne leur nombre."],
     "sql": "SELECT COUNT(*) AS nb_comptes FROM (SELECT compte_id FROM factures WHERE statut = 'Impayee' GROUP BY compte_id HAVING COUNT(*) > {n});"},
    {"id": "taux_paiement_mois", "params": {"mois": MOIS},
     "q": ["Quel est le taux de factures payées en {mois_txt} ?", "Pourcentage des factures du mois {mois} qui sont payées.",
           "Quelle part des factures de {mois_txt} a été réglée ?", "Taux de recouvrement en nombre de factures pour {mois_txt}."],
     "sql": "SELECT ROUND(100.0 * SUM(CASE WHEN statut = 'Payee' THEN 1 ELSE 0 END) / COUNT(*), 2) AS taux_paiement_pct FROM factures WHERE mois = '{mois}';"},
    {"id": "facture_moyenne_offre", "params": {"offre": ["Fixe", "Mobile", "Internet"]},
     "q": ["Quel est le montant moyen d'une facture {offre_txt} ?", "Facture moyenne pour l'offre {offre_txt}.",
           "Montant moyen facturé sur les comptes {offre_txt}.", "En moyenne, combien facture-t-on un compte {offre_txt} ?"],
     "sql": "SELECT ROUND(AVG(f.montant), 2) AS facture_moyenne FROM factures f JOIN comptes co ON co.id = f.compte_id WHERE co.offre = '{offre}';"},
    {"id": "ca_mensuel_offre", "params": {"offre": ["Fixe", "Mobile", "Internet"]},
     "q": ["Montant facturé par mois pour l'offre {offre_txt}.", "Évolution mensuelle du chiffre d'affaires {offre_txt}.",
           "Donne le total facturé chaque mois sur les comptes {offre_txt}.", "Chiffre d'affaires facturé mois par mois pour le {offre_txt}."],
     "sql": "SELECT f.mois, SUM(f.montant) AS total_facture FROM factures f JOIN comptes co ON co.id = f.compte_id WHERE co.offre = '{offre}' GROUP BY f.mois ORDER BY f.mois;"},
    {"id": "region_max_facture_mois", "params": {"mois": MOIS},
     "q": ["Quelle région a été la plus facturée en {mois_txt} ?", "Région avec le plus gros montant facturé au mois {mois}.",
           "Dans quelle région a-t-on le plus facturé en {mois_txt} ?", "Quelle est la région numéro un du chiffre d'affaires facturé en {mois_txt} ?"],
     "sql": "SELECT c.region, SUM(f.montant) AS total_facture FROM factures f JOIN comptes co ON co.id = f.compte_id JOIN clients c ON c.id = co.client_id WHERE f.mois = '{mois}' GROUP BY c.region ORDER BY total_facture DESC LIMIT 1;"},
    {"id": "clients_segment_region", "params": {"segment": SEGMENTS, "region": REGIONS},
     "q": ["Combien de clients {segment} à {region} ?", "Nombre de clients du segment {segment} dans la région {region}.",
           "À {region}, combien de clients sont de type {segment} ?", "Quel est le nombre de clients {segment} installés à {region} ?"],
     "sql": "SELECT COUNT(*) AS nb_clients FROM clients WHERE segment = '{segment}' AND region = '{region}';"},
    {"id": "activations_mois_offre", "params": {"mois": MOIS},
     "q": ["Nouvelles activations de {mois_txt} par offre.", "Combien de comptes ont été activés en {mois_txt}, par offre ?",
           "Nombre d'activations par offre au mois {mois}.", "Répartition par offre des comptes activés pendant le mois de {mois_txt}."],
     "sql": "SELECT offre, COUNT(*) AS nb_activations FROM comptes WHERE strftime('%Y-%m', date_activation) = '{mois}' GROUP BY offre ORDER BY nb_activations DESC;"},
    {"id": "impaye_resilies", "params": {},
     "q": ["Quel est le montant impayé des comptes résiliés ?", "Total des impayés sur les comptes résiliés.",
           "Combien doivent encore les comptes résiliés ?", "Montant restant dû par les comptes au statut résilié."],
     "sql": "SELECT SUM(f.montant) AS total_impaye FROM factures f JOIN comptes co ON co.id = f.compte_id WHERE co.statut = 'Resilie' AND f.statut = 'Impayee';"},
    {"id": "suspendus_ayant_paye_mois", "params": {"mois": MOIS},
     "q": ["Combien de comptes suspendus ont quand même payé en {mois_txt} ?", "Nombre de comptes suspendus avec un paiement au mois {mois}.",
           "Quels comptes ont payé en {mois_txt} mais sont toujours suspendus ? Donne leur nombre.", "Détecte les comptes suspendus malgré un paiement reçu en {mois_txt} : combien sont-ils ?"],
     "sql": "SELECT COUNT(DISTINCT co.id) AS nb_comptes FROM paiements p JOIN factures f ON f.id = p.facture_id JOIN comptes co ON co.id = f.compte_id WHERE co.statut = 'Suspendu' AND strftime('%Y-%m', p.date_paiement) = '{mois}';"},
    {"id": "impayees_par_mois", "params": {},
     "q": ["Évolution du nombre de factures impayées par mois.", "Combien de factures impayées pour chaque mois ?",
           "Nombre de factures non payées mois par mois.", "Donne, mois après mois, le nombre de factures restées impayées."],
     "sql": "SELECT mois, COUNT(*) AS nb_impayees FROM factures WHERE statut = 'Impayee' GROUP BY mois ORDER BY mois;"},
    {"id": "clients_sans_compte_actif", "params": {},
     "q": ["Combien de clients n'ont aucun compte actif ?", "Nombre de clients sans le moindre compte actif.",
           "Combien de clients ont uniquement des comptes suspendus ou résiliés ?", "Quel est le nombre de clients qui n'ont plus aucune ligne active ?"],
     "sql": "SELECT COUNT(*) AS nb_clients FROM clients c WHERE NOT EXISTS (SELECT 1 FROM comptes co WHERE co.client_id = c.id AND co.statut = 'Actif');"},
    {"id": "impaye_region_offre", "params": {"region": REGIONS, "offre": ["Fixe", "Mobile", "Internet"]},
     "q": ["Montant impayé des comptes {offre_txt} à {region}.", "Total des impayés {offre_txt} pour les clients de {region}.",
           "Combien reste-t-il à recouvrer sur le {offre_txt} dans la région {region} ?", "Quel est le montant des factures {offre_txt} impayées des clients basés à {region} ?"],
     "sql": "SELECT SUM(f.montant) AS total_impaye FROM factures f JOIN comptes co ON co.id = f.compte_id JOIN clients c ON c.id = co.client_id WHERE f.statut = 'Impayee' AND co.offre = '{offre}' AND c.region = '{region}';"},
]


# Variantes de surface ajoutées aux formulations d'entraînement (jamais au test).
PREFIXES = ["", "Peux-tu me dire : ", "J'aimerais savoir : ", "Stp, ", "Question rapide : ", "Pour le reporting, ",
            "Dis-moi ", "Besoin du chiffre : "]


def _varier(question: str, prefixe: str) -> str:
    if not prefixe:
        return question
    return prefixe + question[0].lower() + question[1:]


def _rendre(texte: str, valeurs: dict) -> str:
    v = dict(valeurs)
    if "mois" in v:
        v["mois_txt"] = _mois_txt(v["mois"])
    if "offre" in v:
        v["offre_txt"] = OFFRE_FR[v["offre"]]
    if "statut" in v:
        v["statut_txt"] = STATUT_FR[v["statut"]]
    return texte.format(**v)


def generer(graine: int = 7, cible_par_gabarit: int = 54, max_test_par_gabarit: int = 8) -> tuple[list[dict], list[dict]]:
    """Renvoie (train, test). Test = dernière formulation de chaque gabarit, jamais vue à l'entraînement.

    Chaque gabarit reçoit environ `cible_par_gabarit` exemples d'entraînement (formulations × valeurs × préfixes),
    pour que les gabarits sans variable ne soient pas sous-représentés.
    """
    rnd = random.Random(graine)
    train, test = [], []
    for g in GABARITS:
        noms = list(g["params"])
        combinaisons = [dict(zip(noms, vals)) for vals in product(*(g["params"][n] for n in noms))] or [{}]
        *formulations_train, formulation_test = g["q"]
        candidats = [(f, v, pre) for f in formulations_train for v in combinaisons for pre in PREFIXES]
        vus = set()
        for f, valeurs, pre in rnd.sample(candidats, min(cible_par_gabarit, len(candidats))):
            q = _varier(_rendre(f, valeurs), pre)
            if q in vus:
                continue
            vus.add(q)
            train.append({"id": f"{g['id']}-{len(train)}", "gabarit": g["id"], "question": q, "sql": _rendre(g["sql"], valeurs)})
        for valeurs in rnd.sample(combinaisons, min(max_test_par_gabarit, len(combinaisons))):
            test.append({"id": f"{g['id']}-test-{len(test)}", "gabarit": g["id"],
                         "question": _rendre(formulation_test, valeurs), "sql": _rendre(g["sql"], valeurs)})
    rnd.shuffle(train)
    return train, test


def ecrire_jsonl(lignes: list[dict], chemin: Path) -> None:
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("w", encoding="utf-8") as f:
        for l in lignes:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")


def lire_jsonl(chemin: Path) -> list[dict]:
    with Path(chemin).open(encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]
