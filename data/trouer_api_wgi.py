"""
trouver_codes_wgi.py
====================
Script autonome pour chercher et afficher les codes exacts des 6 indicateurs WGI
directement depuis le catalogue de l'API de la Banque Mondiale.
"""

import sys
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

def chercher_vrais_codes():
    print("🔍 Recherche des identifiants officiels WGI dans l'API...")
    
    # Étape 1 : On interroge le catalogue des indicateurs en filtrant sur le mot-clé "Governance"
    url = "https://api.worldbank.org/v2/indicator"
    params = {
        "format": "json",
        "q": "Governance",
        "per_page": 100
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            donnees = response.json()
            if isinstance(donnees, list) and len(donnees) > 1:
                indicators = donnees[1]
                print(f"✅ {len(indicators)} indicateurs trouvés. Voici les correspondances WGI :\n")
                print(f"{'Code exact à copier':<25} | {'Nom de la dimension'}")
                print("-" * 80)
                
                # On affiche les codes qui contiennent les dimensions clés
                mots_cles = ["Corruption", "Rule of Law", "Accountability", "Effectiveness", "Regulatory", "Stability"]
                for ind in indicators:
                    id_code = ind.get("id", "")
                    name = ind.get("name", "")
                    if any(mot in name for mot in mots_cles):
                        print(f"{id_code:<25} | {name}")
            else:
                print("Format de catalogue inattendu.")
        else:
            print(f"Erreur HTTP {response.status_code}")
            
    except Exception as e:
        print(f"Erreur : {e}")

if __name__ == "__main__":
    chercher_vrais_codes()