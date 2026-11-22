"""Schéma d'un SI commercial télécom FICTIF et génération d'une base SQLite de test.

Toutes les données sont simulées. Le piège métier volontaire : une facture appartient à un COMPTE,
pas directement à un client ; il faut passer par `comptes` pour relier factures et clients.
"""
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DDL = """
CREATE TABLE boutiques (
  id INTEGER PRIMARY KEY,
  nom TEXT NOT NULL,              -- nom de la boutique
  region TEXT NOT NULL            -- région administrative
);
CREATE TABLE clients (
  id INTEGER PRIMARY KEY,
  nom TEXT NOT NULL,
  segment TEXT NOT NULL,          -- 'Particulier' ou 'Entreprise'
  region TEXT NOT NULL,
  date_creation TEXT NOT NULL     -- AAAA-MM-JJ
);
CREATE TABLE comptes (
  id INTEGER PRIMARY KEY,
  client_id INTEGER NOT NULL REFERENCES clients(id),
  offre TEXT NOT NULL,            -- 'Fixe', 'Mobile', 'Prepaye' ou 'Internet'
  statut TEXT NOT NULL,           -- 'Actif', 'Suspendu' ou 'Resilie'
  date_activation TEXT NOT NULL,  -- AAAA-MM-JJ, date d'effet de l'activation
  boutique_id INTEGER REFERENCES boutiques(id)
);
CREATE TABLE factures (
  id INTEGER PRIMARY KEY,
  compte_id INTEGER NOT NULL REFERENCES comptes(id),  -- une facture appartient à un compte
  mois TEXT NOT NULL,             -- mois facturé, AAAA-MM
  date_emission TEXT NOT NULL,    -- AAAA-MM-JJ
  montant REAL NOT NULL,          -- en FCFA
  statut TEXT NOT NULL            -- 'Payee' ou 'Impayee'
);
CREATE TABLE paiements (
  id INTEGER PRIMARY KEY,
  facture_id INTEGER NOT NULL REFERENCES factures(id),
  date_paiement TEXT NOT NULL,    -- AAAA-MM-JJ
  montant REAL NOT NULL,          -- en FCFA
  canal TEXT NOT NULL,            -- 'Boutique', 'Orange Money' ou 'Virement'
  boutique_id INTEGER REFERENCES boutiques(id)  -- renseigné seulement pour le canal 'Boutique'
);
""".strip()

REGIONS = ["Dakar", "Thiès", "Saint-Louis", "Ziguinchor", "Kaolack", "Touba"]
OFFRES = ["Fixe", "Mobile", "Prepaye", "Internet"]
STATUTS_COMPTE = ["Actif", "Suspendu", "Resilie"]
CANAUX = ["Boutique", "Orange Money", "Virement"]
SEGMENTS = ["Particulier", "Entreprise"]
MOIS = [f"2026-{m:02d}" for m in range(1, 11)]
PRENOMS = ["Awa", "Moussa", "Fatou", "Ibrahima", "Aminata", "Cheikh", "Mariama", "Ousmane", "Khady", "Mamadou"]
NOMS = ["Diop", "Ndiaye", "Fall", "Sow", "Gueye", "Ba", "Sarr", "Faye", "Diallo", "Cissé"]


def creer_base(chemin: Path, graine: int = 42, n_clients: int = 1500) -> Path:
    """Crée une base SQLite déterministe (même graine = mêmes données)."""
    rnd = random.Random(graine)
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    if chemin.exists():
        chemin.unlink()
    con = sqlite3.connect(chemin)
    con.executescript(DDL)
    boutiques = []
    for i, region in enumerate(REGIONS):
        for j in range(1, 4):
            boutiques.append((len(boutiques) + 1, f"Boutique {region} {j}", region))
    con.executemany("INSERT INTO boutiques VALUES (?,?,?)", boutiques)
    clients, comptes, factures, paiements = [], [], [], []
    for cid in range(1, n_clients + 1):
        region = rnd.choices(REGIONS, weights=[40, 15, 10, 8, 12, 15])[0]
        segment = rnd.choices(SEGMENTS, weights=[85, 15])[0]
        cree = date(2023, 1, 1) + timedelta(days=rnd.randint(0, 1000))
        nom = f"{rnd.choice(PRENOMS)} {rnd.choice(NOMS)}" if segment == "Particulier" else f"Société {rnd.choice(NOMS)} {cid}"
        clients.append((cid, nom, segment, region, cree.isoformat()))
        for _ in range(rnd.choices([1, 2, 3], weights=[60, 30, 10])[0]):
            kid = len(comptes) + 1
            offre = rnd.choices(OFFRES, weights=[15, 35, 35, 15])[0]
            statut = rnd.choices(STATUTS_COMPTE, weights=[75, 15, 10])[0]
            active = date(2025, 6, 1) + timedelta(days=rnd.randint(0, 500))
            b_region = [b for b in boutiques if b[2] == region]
            comptes.append((kid, cid, offre, statut, active.isoformat(), rnd.choice(b_region)[0]))
            if offre == "Prepaye":
                continue                              # le prépayé n'est pas facturé
            base = {"Fixe": 15000, "Mobile": 9000, "Internet": 25000}[offre] * (3 if segment == "Entreprise" else 1)
            for mois in MOIS:
                if mois < active.isoformat()[:7]:
                    continue
                fid = len(factures) + 1
                montant = round(base * rnd.uniform(0.7, 1.4), 0)
                p_payee = {"Actif": 0.9, "Suspendu": 0.4, "Resilie": 0.5}[statut]
                payee = rnd.random() < p_payee
                emission = f"{mois}-05"
                factures.append((fid, kid, mois, emission, montant, "Payee" if payee else "Impayee"))
                if payee or (statut == "Suspendu" and rnd.random() < 0.15):   # quelques paiements « orphelins » à détecter
                    canal = rnd.choices(CANAUX, weights=[35, 50, 15])[0]
                    jour = min(28, 5 + rnd.randint(1, 23))
                    y, m = int(mois[:4]), int(mois[5:])
                    if rnd.random() < 0.3:                # paiement le mois suivant
                        m = m + 1 if m < 12 else 1
                    dp = date(y, m, jour).isoformat()
                    bid = rnd.choice(b_region)[0] if canal == "Boutique" else None
                    paiements.append((len(paiements) + 1, fid, dp, montant if payee else round(montant / 2, 0), canal, bid))
    con.executemany("INSERT INTO clients VALUES (?,?,?,?,?)", clients)
    con.executemany("INSERT INTO comptes VALUES (?,?,?,?,?,?)", comptes)
    con.executemany("INSERT INTO factures VALUES (?,?,?,?,?,?)", factures)
    con.executemany("INSERT INTO paiements VALUES (?,?,?,?,?,?)", paiements)
    con.commit()
    con.close()
    return chemin
