# cd C:\Users\USER_DELL\OneDrive\Bureau\Mon_Projet_INPPLC
# python -m streamlit run dashboard.py

"""
app.py
======
Rôle : Orchestrateur principal du pipeline d'automatisation de l'INPPLC.
Gère le téléchargement automatisé des 4 indices (CPI, BTI, WJP, IIAG),
l'extraction locale, l'appel API, et la consolidation pour le Maroc.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
import pandas as pd
import requests

# Importation de tes moteurs personnalisés
import moteur_fichiers
import moteur_api

# Sécurisation de l'affichage sur console Windows (accents, émojis)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

# Configuration de la journalisation générale
logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("ORCHESTRATEUR")

# En-tête HTTP d'identification pour les téléchargements de fichiers
EN_TETES_HTTP = {
    "User-Agent": "INPPLC-Observatoire/1.0 (Projet de stage  - Anas)"
}

# --------------------------------------------------------------------------- #
# CONFIGURATION DES CHEMINS ET URLS (LES 4 INDICES)
# --------------------------------------------------------------------------- #
DOSSIER_DATA = Path("./data")
FICHIER_CONSOLIDE = Path("./donnees_consolidees.csv")

# URLs publiques et stables pour les téléchargements directs
SOURCES_A_TELECHARGER = {
    "CPI": {
        "url": "https://data.humdata.org/dataset/global-corruption-perceptions-index/resource/2019bc34-2771-40ce-870f-7a92cc1176a0/download/global_cpi_all.csv",
        "chemin_local": DOSSIER_DATA / "CPI_GlobalResults.csv"
    },
    "BTI": {
        "url": "https://bti-project.org/fileadmin/api/content/en/downloads/data/BTI_2026_Scores.xlsx",
        "chemin_local": DOSSIER_DATA / "BTI_Database.xlsx"
    },
    "WJP": {
        # Lien d'archive stable du World Justice Project (Rule of Law Historical Data)
        "url": "https://worldjusticeproject.org/sites/default/files/documents/WJP_Rule_of_Law_Index_2023_Historical_Data.xlsx",
        "chemin_local": DOSSIER_DATA / "WJP_Historical_Data.xlsx"
    },
    "IIAG": {
        # Lien de l'index Ibrahim de la gouvernance africaine (IIAG)
        "url": "https://mo.ibrahim.foundation/sites/default/files/2024-10/2024-iiag-dataset-maroc.xlsx",
        "chemin_local": DOSSIER_DATA / "IIAG_Dataset.xlsx"
    },
    "OBI": {
        # Lien de l'Open Budget Survey (OBS)
        "url": "https://internationalbudget.org/sites/default/files/2026-06/OBS_Full_Timeseries_2006_2025.xlsx",
        "chemin_local": DOSSIER_DATA / "OBI_Dataset.xlsx"
    }  
    ""
}


# --------------------------------------------------------------------------- #
# ÉTAPE 1 : TÉLÉCHARGEUR AUTOMATIQUE RÉSISTANT
# --------------------------------------------------------------------------- #
def executer_telechargements() -> dict[str, Path]:
    """
    Télécharge automatiquement les fichiers sources configurés.
    Retourne uniquement les chemins des fichiers qui sont bien présents localement.
    """
    logger.info("[TÉLÉCHARGEUR] Lancement de la collecte automatisée des sources...")
    DOSSIER_DATA.mkdir(parents=True, exist_ok=True)
    
    fichiers_prets = {}
    
    for nom_source, infos in SOURCES_A_TELECHARGER.items():
        url = infos["url"]
        chemin_destination = infos["chemin_local"]
        
        logger.info(" Téléchargement de %s : %s", nom_source, url)
        
        try:
            response = requests.get(url, headers=EN_TETES_HTTP, timeout=30, stream=True)
            if response.status_code == 200:
                with open(chemin_destination, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                logger.info("✔ %s téléchargé avec succès.", nom_source)
                fichiers_prets[nom_source] = chemin_destination
            else:
                logger.warning("⚠ Impossible de télécharger %s en ligne (Code HTTP: %d).", nom_source, response.status_code)
                # Fallback : si le fichier existe déjà d'une session précédente, on l'utilise
                if chemin_destination.exists():
                    logger.info(" Utilisation de la version locale existante pour %s.", nom_source)
                    fichiers_prets[nom_source] = chemin_destination
        except Exception as e:
            logger.warning(" Erreur réseau pour %s : %s", nom_source, e)
            if chemin_destination.exists():
                logger.info(" Utilisation du fichier local de secours pour %s.", nom_source)
                fichiers_prets[nom_source] = chemin_destination
            
    return fichiers_prets


# --------------------------------------------------------------------------- #
# ORCHESTRATION DU PIPELINE
# --------------------------------------------------------------------------- #
def main():
    print("\n [ORCHESTRATEUR] Démarrage du pipeline d'automatisation INPPLC...")
    print("-" * 80)

    # --- ÉTAPE 1 : Téléchargement autonome ---
    fichiers_disponibles = executer_telechargements()
    print("-" * 80)

    # --- ÉTAPE 2 : Extraction et normalisation des fichiers locaux ---
    logger.info("--- ÉTAPE 2 : Extraction et normalisation des fichiers locaux ---")
    if fichiers_disponibles:
        df_fichiers = moteur_fichiers.charger_tous_les_fichiers(fichiers_disponibles)
        logger.info("✔ Moteur Fichiers : %d lignes extraites au total.", len(df_fichiers))
    else:
        logger.warning("⚠ Aucun fichier n'a pu être collecté ou trouvé en local.")
        df_fichiers = pd.DataFrame()
    print("-" * 80)

    # --- ÉTAPE 3 : Collecte via le Moteur API (Banque Mondiale) ---
    logger.info("--- ÉTAPE 3 : Collecte via l'API Banque Mondiale (Population MAR) ---")
    df_api = moteur_api.extraire_les_apis()
    logger.info("✔ Moteur API : %d lignes récupérées.", len(df_api))
    print("-" * 80)

    # --- ÉTAPE 4 : Consolidation, filtrage final (Maroc) et tri ---
    logger.info("--- ÉTAPE 4 : Consolidation des sources de données ---")
    
    dfs_a_fusionner = []
    if not df_fichiers.empty:
        dfs_a_fusionner.append(df_fichiers)
    if not df_api.empty:
        dfs_a_fusionner.append(df_api)
        
    if not dfs_a_fusionner:
        logger.error(" Échec critique : Aucune donnée n'a été collectée par les deux moteurs.")
        sys.exit(1)
        
    # Fusion finale
    df_consolide = pd.concat(dfs_a_fusionner, ignore_index=True)
    
    # Filtrage sur le Maroc
    df_maroc = moteur_fichiers.filtrer_maroc(df_consolide)
    
    if df_maroc.empty:
        logger.warning("⚠ La consolidation finale est vide : aucun enregistrement 'MAR' trouvé.")
    else:
        # Tri chronologique propre pour chaque indice
        df_maroc = df_maroc.sort_values(
            by=["index", "indicateur_specifique", "annee"], 
            ascending=[True, True, False]
        )
        
        # Sauvegarde
        df_maroc.to_csv(FICHIER_CONSOLIDE, index=False, encoding="utf-8-sig")
        logger.info(" Succès complet ! Le pipeline s'est exécuté sans erreur.")
        logger.info(" Fichier d'observation disponible : %s (%d lignes)", FICHIER_CONSOLIDE, len(df_maroc))
        
        # Aperçu élargi (les 30 premières lignes) pour voir les nouveaux indices
        print("\n APERÇU DE LA BASE CONSOLIDÉE POUR LE MAROC :")
        print("#" * 115)
        print(df_maroc.head(30).to_string(index=False))
        print("#" * 115)


if __name__ == "__main__":
    main()