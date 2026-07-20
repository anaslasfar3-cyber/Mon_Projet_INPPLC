"""
main.py
=======
Chef d'orchestre principal (Pipeline INPPLC).

Rôle : 
    1. Lancer le téléchargeur autonome (telechargeur.py) pour obtenir le CPI et le BTI.
    2. Passer ces fichiers locaux téléchargés au moteur de fichiers (moteur_fichiers.py).
    3. Interroger en parallèle l'API de la Banque Mondiale pour le WGI (moteur_api.py).
    4. Fusionner l'ensemble, filtrer sur le Maroc (MAR) et exporter 'donnees_consolidees.csv'.
"""

from __future__ import annotations
import os
import pandas as pd
from pathlib import Path

# Importation directe de tes modules personnalisés
from telechargeur import telecharger_tous_les_indices
from moteur_api import extraire_les_apis
from moteur_fichiers import charger_tous_les_fichiers, COLONNES_STANDARD

def orchestrer_collecte_globale():
    print(" [ORCHESTRATEUR] Démarrage du pipeline d'automatisation INPPLC...")
    
    # =====================================================================
    # ÉTAPE 1 : TÉLÉCHARGEMENT AUTOMATIQUE DES FICHIERS (CPI et BTI)
    # =====================================================================
    print("\n--- ÉTAPE 1 : Lancement du téléchargeur autonome ---")
    fichiers_telecharges = {}
    try:
        # Appelle la fonction de ton fichier telechargeur.py
        fichiers_telecharges = telecharger_tous_les_indices()
    except Exception as e:
        print(f" Erreur critique lors de la phase de téléchargement : {e}")

    # Vérification de sécurité
    if not fichiers_telecharges:
        print(" Attention : Aucun fichier n'a été téléchargé par le module de scraping.")
        print("Le pipeline va tenter de continuer uniquement avec le moteur API.")

    # =====================================================================
    # ÉTAPE 2 : TRAITEMENT ET NORMALISATION DES FICHIERS (Moteur Fichiers)
    # =====================================================================
    print("\n--- ÉTAPE 2 : Extraction et normalisation des fichiers locaux ---")
    df_fichiers = pd.DataFrame(columns=COLONNES_STANDARD)
    
    if fichiers_telecharges:
        try:
            # Passe le dictionnaire contenant les chemins des fichiers téléchargés au moteur
            df_fichiers = charger_tous_les_fichiers(fichiers_telecharges)
            print(f" Moteur Fichiers : {len(df_fichiers)} lignes extraites au total.")
        except Exception as e:
            print(f" Échec du traitement dans 'moteur_fichiers.py' : {e}")
    else:
        print(" Étape ignorée : Aucun fichier local à traiter.")

    # =====================================================================
    # ÉTAPE 3 : COLLECTE DES DONNÉES EN LIGNE (Moteur API)
    # =====================================================================
    print("\n--- ÉTAPE 3 : Collecte des indicateurs WGI via l'API Banque Mondiale ---")
    df_api = pd.DataFrame(columns=COLONNES_STANDARD)
    try:
        df_api = extraire_les_apis()
        print(f" Moteur API : {len(df_api)} lignes récupérées.")
    except Exception as e:
        print(f" Échec de la collecte API dans 'moteur_api.py' : {e}")

    # =====================================================================
    # ÉTAPE 4 : CONSOLIDATION, FILTRAGE MAROC & EXPORT FINAL
    # =====================================================================
    print("\n--- ÉTAPE 4 : Consolidation des sources de données ---")

    try:
        combinaison = []
        if not df_api.empty:
            combinaison.append(df_api)
        if not df_fichiers.empty:
            combinaison.append(df_fichiers)

        if not combinaison:
            print(" Échec : Aucune donnée n'a pu être collectée (les deux moteurs ont échoué).")
            return

        # Fusion des DataFrames de l'API et des fichiers Excel/CSV
        df_global = pd.concat(combinaison, ignore_index=True)

        # Coercion défensive : garantit que .str.upper() ne plante jamais,
        # même si une source a produit une colonne code_iso mal typée
        # (ex: uniquement des None -> dtype float au lieu de string).
        df_global["code_iso"] = df_global["code_iso"].astype(str)

        # Filtrage strict sur le Maroc (ISO 3 : MAR) pour l'INPPLC
        print(" Application du filtre géographique : Maroc (MAR)...")
        df_maroc = df_global[df_global["code_iso"].str.upper() == "MAR"].copy()

        if df_maroc.empty:
            print(" Alerte : Le filtrage géographique a retourné 0 ligne pour le code ISO 'MAR'.")
            print("Vérifie que la colonne 'code_iso' de tes moteurs contient bien la valeur 'MAR'.")
            return

        # Tri pour une lecture chronologique propre par indice
        df_maroc = df_maroc.sort_values(by=["index", "annee"], ascending=[True, False])

        # Chemin ABSOLU (à côté de ce script), plutôt qu'un chemin relatif qui
        # dépend du dossier courant du terminal au moment du lancement — pour
        # ne plus jamais se demander "où est passé le fichier ?".
        chemin_csv_final = Path(__file__).resolve().parent / "donnees_consolidees.csv"
        df_maroc.to_csv(chemin_csv_final, index=False, encoding="utf-8-sig")

        print("\n====================================================================")
        print(" PIPELINE DE COLLECTE AUTOMATIQUE TERMINÉ AVEC SUCCÈS !")
        print(f" Fichier d'exportation créé : '{chemin_csv_final}'")
        print(f" Nombre total de lignes consolidées pour le Maroc : {len(df_maroc)}")
        print("====================================================================")

    except Exception as e:
        import traceback
        print(f"\n Échec à l'Étape 4 (consolidation/export) : {e}")
        print("--- Détail technique (à copier si besoin d'aide) ---")
        traceback.print_exc()

if __name__ == "__main__":
    orchestrer_collecte_globale()