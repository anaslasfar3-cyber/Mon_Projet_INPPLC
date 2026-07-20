import os
import requests
import pandas as pd

# Configuration spécifique au WJP
# Note : C'est l'URL des données historiques globales du WJP
WJP_URL = "https://worldjusticeproject.org/rule-of-law-index/.xlsx" 
FICHIER_TEMPORAIRE = "wjp_brut.xlsx"

def get_data():
    print("[WJP] Début de l'extraction...")
    
    # 1. Téléchargement du fichier Excel
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        print(f" Téléchargement du fichier depuis le site du WJP...")
        response = requests.get(WJP_URL, headers=headers, timeout=15)
        
        if response.status_code == 200:
            with open(FICHIER_TEMPORAIRE, "wb") as f:
                f.write(response.content)
            print(" Fichier téléchargé localement.")
        else:
            print(f" Échec du téléchargement. Code HTTP : {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Erreur lors de la connexion au site du WJP : {e}")
        return None

    # 2. Lecture et Traitement des données avec Pandas
    try:
        print("  Traitement des données avec Pandas...")
        
        # Le WJP stocke souvent ses scores historiques dans un onglet spécifique, 
        # Si besoin, on peut ajuster le paramètre sheet_name (ex: sheet_name="Historical Data")
        df = pd.read_excel(FICHIER_TEMPORAIRE)
        
        # --- PHASE DE NETTOYAGE / NORMALISATION ---
        # Remarque : Les noms exacts des colonnes dépendent du fichier Excel mis en ligne par le WJP.
        # En général, on y trouve : 'Year', 'Country', 'Three_Letter_Country_Code' (ou ISO3), 'WJP Rule of Law Index Rank', 'WJP Rule of Law Index Score'
        
        # Pour ce test, on renomme et on standardise dynamiquement pour l'INPPLC :
        # (Ces lignes s'adaptent aux colonnes types du WJP)
        df_standardise = pd.DataFrame()
        
        # On essaie de mapper intelligemment les colonnes du WJP vers notre format cible
        df_standardise['annee'] = df['Year'] if 'Year' in df.columns else df['year']
        df_standardise['index'] = 'WJP'
        df_standardise['pays'] = df['Country'] if 'Country' in df.columns else df['country']
        
        # Code ISO (Tranche indispensable pour la base de l'INPPLC)
        if 'Three_Letter_Country_Code' in df.columns:
            df_standardise['code_iso'] = df['Three_Letter_Country_Code']
        elif 'ISO3' in df.columns:
            df_standardise['code_iso'] = df['ISO3']
        else:
            df_standardise['code_iso'] = 'ND' # Non Défini (à corriger si manquant)
            
        df_standardise['score'] = df['WJP Rule of Law Index Score'] if 'WJP Rule of Law Index Score' in df.columns else None
        df_standardise['rang_worldwide'] = df['WJP Rule of Law Index Rank'] if 'WJP Rule of Law Index Rank' in df.columns else None
        
        # Nettoyage final : supprimer les lignes vides
        df_standardise = df_standardise.dropna(subset=['annee', 'pays'])
        
        # Convertir les types pour éviter les bugs
        df_standardise['annee'] = df_standardise['annee'].astype(int)
        
        print(f"✔ Traitement réussi : {len(df_standardise)} lignes normalisées.")
        return df_standardise

    except Exception as e:
        print(f"❌ Erreur lors du traitement du fichier Excel WJP : {e}")
        return None
        
    finally:
        # Nettoyage : suppression du fichier temporaire pour laisser le projet propre
        if os.path.exists(FICHIER_TEMPORAIRE):
            os.remove(FICHIER_TEMPORAIRE)
            print(" _________Fichier temporaire supprimé.")

if __name__ == "__main__":
    # Test autonome du script
    resultat = get_data()
    if resultat is not None:
        print("\n📊 APERÇU DU TABLEAU OBTENU POUR WJP :")
        print(resultat.head(10).to_string(index=False))
        
        # Focus rapide sur le Maroc pour ton stage
        maroc_data = resultat[resultat['code_iso'] == 'MAR']
        if not maroc_data.empty:
            print("\n🇲🇦 Données extraites pour le Maroc :")
            print(maroc_data.to_string(index=False))