"""
test_wgi_apis.py
================
Script de test autonome pour valider la connectivité et la réponse 
des 6 endpoints de l'API Worldwide Governance Indicators (WGI) de la Banque Mondiale.
"""

import sys
import json
import requests

# Sécurisation de l'affichage console sous Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

EN_TETES_HTTP = {
    "User-Agent": "INPPLC-Observatoire-Test/1.0 (Anas)"
}

# Configuration des 6 dimensions du WGI pour le Maroc (MAR)
CONFIG_APIS_WGI = {
    "WGI_VA": {"nom_complet": "Voice and Accountability", "url_base": "https://api.worldbank.org/v2/country/MAR/indicator/GOV_WGI_VA.EST"},
    "WGI_CC": {"nom_complet": "Control of Corruption", "url_base": "https://api.worldbank.org/v2/country/MAR/indicator/GOV_WGI_CC.EST"},
    "WGI_GE": {"nom_complet": "Government Effectiveness", "url_base": "https://api.worldbank.org/v2/country/MAR/indicator/GOV_WGI_GE.EST"},
    "WGI_PV": {"nom_complet": "Political Stability and Absence of Violence", "url_base": "https://api.worldbank.org/v2/country/MAR/indicator/GOV_WGI_PV.EST"},
    "WGI_RQ": {"nom_complet": "Regulatory Quality", "url_base": "https://api.worldbank.org/v2/country/MAR/indicator/GOV_WGI_RQ.EST"},
    "WGI_RL": {"nom_complet": "Rule of Law Index", "url_base": "https://api.worldbank.org/v2/country/MAR/indicator/GOV_WGI_RL.EST"}
}

def tester_les_apis_wgi():
    print("=" * 80)
    print("🧪 SCRIPT DE DIAGNOSTIC AUTONOME : TEST DES API WGI (BANQUE MONDIALE)")
    print("=" * 80)
    
    succes_total = 0
    
    for nom, config in CONFIG_APIS_WGI.items():
        print(f"\n🔍 Test de l'indicateur : {nom}")
        print(f"🔗 URL interrogée : {config['url_base']}")
        
        try:
            # Envoi de la requête avec un timeout de 10 secondes
            response = requests.get(config['url_base'], params={"format": "json", "per_page": 5}, headers=EN_TETES_HTTP, timeout=10)
            
            print(f"   ➔ Statut HTTP : {response.status_code}")
            
            if response.status_code == 200:
                donnees = response.json()
                
                # Vérification de la structure standard Banque Mondiale : un tableau [métadonnées, données]
                if isinstance(donnees, list) and len(donnees) > 1:
                    total_records = donnees[0].get("total", "Inconnu")
                    echantillon = donnees[1]
                    
                    print(f"    Connexion réussie ! Nombre total d'années disponibles : {total_records}")
                    
                    # Affichage d'un mini échantillon des 2 dernières années pour preuve visuelle
                    if echantillon:
                        print("   📊 Échantillon des dernières données reçues :")
                        for record in echantillon[:2]:
                            annee = record.get("date")
                            valeur = record.get("value")
                            print(f"      - Année {annee} : Score = {valeur}")
                    
                    succes_total += 1
                else:
                    print("    Réponse HTTP 200 reçue, mais le format JSON de la Banque Mondiale est inattendu ou vide.")
                    print(f"      Contenu reçu : {str(donnees)[:200]}")
            else:
                print(f"   ❌ Erreur serveur : Le serveur a répondu avec le code {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("   ❌ Erreur : Temps d'attente dépassé (Timeout de 10s). Le serveur met trop de temps à répondre.")
        except requests.exceptions.ConnectionError:
            print("   ❌ Erreur : Impossible de résoudre l'adresse ou de se connecter. Vérifie ta connexion Internet.")
        except json.JSONDecodeError:
            print("   ❌ Erreur : Le serveur n'a pas renvoyé un JSON valide (possible page d'erreur HTML ou proxy de blocage).")
        except Exception as e:
            print(f"   ❌ Erreur imprévue : {e}")
            
    # Rapport final
    print("\n" + "=" * 80)
    print(f" BILAN DU DIAGNOSTIC : {succes_total}/{len(CONFIG_APIS_WGI)} API(s) fonctionnelle(s).")
    print("=" * 80)

if __name__ == "__main__":
    tester_les_apis_wgi()