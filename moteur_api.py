"""
moteur_api.py
==============

Moteur n°1 du pipeline INPPLC — Observatoire de la Gouvernance.

Rôle : interroger les API REST de la Banque Mondiale (WGI) et du portail Open Data 
       du Maroc (data.gov.ma pour l'indice TRACE) pour récupérer automatiquement l'historique.

Contrat de sortie :
    annee | index | indicateur_specifique | code_iso | pays | score | rang_worldwide
"""

from __future__ import annotations
import sys
import logging
from typing import Optional
import pandas as pd
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("moteur_api")

EN_TETES_HTTP = {
    "User-Agent": "INPPLC-Observatoire/1.0 (Projet de fin d'etudes - Anas)"
}

COLONNES_STANDARD = [
    "annee",
    "index",
    "indicateur_specifique",
    "code_iso",
    "pays",
    "score",
    "rang_worldwide",
]

# Configuration WGI (Banque Mondiale)
# /!\ La Banque Mondiale a publié en 2025 une révision de la méthodologie du WGI
# ("Worldwide Governance Indicators, 2025 Revision", www.govindicators.org).
# Les anciens codes (VA.EST, CC.EST, GE.EST, PV.EST, RQ.EST, RL.EST) ont été
# RETIRÉS du catalogue API et remplacés par des codes préfixés "GOV_WGI_"
# (vérifié directement sur https://api.worldbank.org/v2/sources/3/indicators,
# qui liste désormais uniquement les 36 nouveaux codes GOV_WGI_*). C'est
# exactement pourquoi l'API renvoyait "indicator not found... may have been
# deleted or archived" : elle avait raison, ils l'ont été.
# L'URL de WGI_CC pointait aussi vers "africa-api.com", qui n'est pas un
# domaine de la Banque Mondiale — corrigée également.
CONFIG_APIS_WGI = {
    "WGI_VA": {"nom_complet": "Voice and Accountability", "url_base": "https://api.worldbank.org/v2/country/MAR/indicator/GOV_WGI_VA.EST"},
    "WGI_CC": {"nom_complet": "Control of Corruption", "url_base": "https://api.worldbank.org/v2/country/MAR/indicator/GOV_WGI_CC.EST"},
    "WGI_GE": {"nom_complet": "Government Effectiveness", "url_base": "https://api.worldbank.org/v2/country/MAR/indicator/GOV_WGI_GE.EST"},
    "WGI_PV": {"nom_complet": "Political Stability and Absence of Violence", "url_base": "https://api.worldbank.org/v2/country/MAR/indicator/GOV_WGI_PV.EST"},
    "WGI_RQ": {"nom_complet": "Regulatory Quality", "url_base": "https://api.worldbank.org/v2/country/MAR/indicator/GOV_WGI_RQ.EST"},
    "WGI_RL": {"nom_complet": "Rule of Law Index", "url_base": "https://api.worldbank.org/v2/country/MAR/indicator/GOV_WGI_RL.EST"}
}

# --------------------------------------------------------------------------- #
# 1. COLLECTE API BANQUE MONDIALE (WGI)
# --------------------------------------------------------------------------- #
def _extraire_banque_mondiale() -> list[pd.DataFrame]:
    """Interroge la Banque Mondiale pour les 6 indicateurs WGI."""
    tableaux = []
    for identifiant, config in CONFIG_APIS_WGI.items():
        logger.info("Requête API Banque Mondiale pour : %s...", config["nom_complet"])
        try:
            response = requests.get(config["url_base"], params={"format": "json", "per_page": 100}, headers=EN_TETES_HTTP, timeout=15)
            if response.status_code == 200:
                donnees_brutes = response.json()
                if isinstance(donnees_brutes, list) and len(donnees_brutes) > 1 and donnees_brutes[1] is not None:
                    lignes = []
                    for record in donnees_brutes[1]:
                        annee = record.get("date")
                        score = record.get("value")
                        if annee is None or score is None: continue
                        lignes.append({
                            "annee": int(annee),
                            "index": "WGI",
                            "indicateur_specifique": config["nom_complet"],
                            "code_iso": record.get("countryiso3code", "MAR"),
                            "pays": record.get("country", {}).get("value", "Morocco"),
                            "score": float(score),
                            "rang_worldwide": None
                        })
                    if lignes:
                        tableaux.append(pd.DataFrame(lignes))
        except Exception as e:
            logger.error("Échec API Banque Mondiale %s : %s", identifiant, e)
    return tableaux

# --------------------------------------------------------------------------- #
# 2. COLLECTE API PORTAL DATA.GOV.MA (TRACE MATRIX)
# --------------------------------------------------------------------------- #
def _extraire_trace_gov_ma() -> Optional[pd.DataFrame]:
    """
    Interroge l'API CKAN de data.gov.ma pour récupérer de manière dynamique 
    le fichier de données TRACE publié par l'INPPLC.
    """
    url_api = "https://data.gov.ma/data/fr/dataset/api_dataset/trace-bribery-risk-matrix-tbr-2014-2024"
    logger.info("Requête API data.gov.ma (INPPLC) pour l'indice TRACE...")
    try:
        response = requests.get(url_api, headers=EN_TETES_HTTP, timeout=15)
        if response.status_code != 200:
            return None
        
        metadata = response.json()
        # Accès direct aux ressources de l'INPPLC définies dans l'objet 'result'
        resources = metadata.get("result", {}).get("resources", [])
        
        # Identification de la ressource Excel ou CSV (parmi les 2 présentes)
        ressource_data = next((r for r in resources if r.get("format", "").lower() in ["xlsx", "xls", "csv"]), None)
        if not ressource_data:
            logger.warning("Aucun fichier exploitable (CSV/XLSX) trouvé dans les ressources de data.gov.ma.")
            return None
            
        url_fichier = ressource_data["url"]
        logger.info("Téléchargement de la matrice TRACE depuis l'URL officielle : %s", url_fichier)
        
        if ressource_data["format"].lower() == "csv":
            df = pd.read_csv(url_fichier)
        else:
            df = pd.read_excel(url_fichier)
            
        df.columns = [str(c).strip() for c in df.columns]
        
        # Mappage automatique sur ton schéma standardisé
        col_annee = next((c for c in df.columns if c.lower() in ["year", "annee", "year_data", "année"]), None)
        col_score = next((c for c in df.columns if "score" in c.lower() or "risk" in c.lower() or "valeur" in c.lower()), None)
        col_rang = next((c for c in df.columns if "rank" in c.lower() or "rang" in c.lower() or "classement" in c.lower()), None)
        
        lignes = []
        for _, row in df.iterrows():
            lignes.append({
                "annee": int(row[col_annee]) if col_annee else 2024,
                "index": "TRACE",
                "indicateur_specifique": "Bribery Risk Score (API Gov)",
                "code_iso": "MAR",
                "pays": "Maroc",
                "score": float(row[col_score]) if col_score else None,
                "rang_worldwide": int(row[col_rang]) if col_rang and pd.notna(row[col_rang]) else None
            })
            
        return pd.DataFrame(lignes)
    except Exception as e:
        logger.error("Erreur lors de la récupération des données ouvertes TRACE : %s", e)
        return None
# --------------------------------------------------------------------------- #
# 3. FONCTION PRINCIPALE APPELÉE PAR MAIN.PY
# --------------------------------------------------------------------------- #
def extraire_les_apis() -> pd.DataFrame:
    """Combine l'ensemble des collectes API (Banque Mondiale + Data.gov.ma)."""
    logger.info("Début de la collecte globale via les moteurs API...")
    tableaux_globaux = []
    
    # 1. Banque Mondiale
    tableaux_globaux.extend(_extraire_banque_mondiale())
    
    # 2. Data.gov.ma
    df_trace = _extraire_trace_gov_ma()
    if df_trace is not None and not df_trace.empty:
        tableaux_globaux.append(df_trace)
        logger.info("✔ Données TRACE de data.gov.ma intégrées avec succès.")
        
    if tableaux_globaux:
        df_final_api = pd.concat(tableaux_globaux, ignore_index=True)
        df_final_api["annee"] = df_final_api["annee"].astype("Int64")
        df_final_api["score"] = pd.to_numeric(df_final_api["score"], errors="coerce")
        df_final_api["rang_worldwide"] = df_final_api["rang_worldwide"].astype("Int64")
        return df_final_api[COLONNES_STANDARD]
        
    return pd.DataFrame(columns=COLONNES_STANDARD)

if __name__ == "__main__":
    df_test = extraire_les_apis()
    print(df_test.head(10))