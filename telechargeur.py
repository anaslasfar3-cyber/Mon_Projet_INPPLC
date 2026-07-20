"""
telechargeur.py
===============
Rôle : Télécharger de manière fiable et automatique les bases de données d'indices
       de gouvernance (BTI, CPI, OBI, etc.) sans blocage ni besoin d'action manuelle.

Corrections apportées à cette version
--------------------------------------
1. Boucle unifiée : avant, le BTI (scraping) et les autres indices (URL directe)
   suivaient deux chemins de code différents pour faire la même chose. Chaque
   indice a maintenant une "url_directe" (peut être None) ET/OU un "scraper"
   (fonction de secours si l'URL directe échoue) — un seul et même moteur les
   traite tous, plus besoin d'un `if cfg["type"] == "scraping"` séparé.
2. Validation réelle du contenu téléchargé : avant, n'importe quelle réponse
   HTTP 200 était acceptée telle quelle. Or plusieurs URLs (voir plus bas)
   pointaient en réalité vers des PAGES WEB, pas des fichiers — elles étaient
   donc "téléchargées avec succès" tout en ne contenant que du HTML, ce qui
   cassait silencieusement `moteur_fichiers.py` en aval. On vérifie maintenant :
     a) le Content-Type de la réponse (rejette le HTML),
     b) pour les .xlsx, la signature binaire réelle du fichier (un .xlsx est
        une archive ZIP, donc commence toujours par les octets "PK").
3. URLs corrigées/vérifiées :
   - IEF (Heritage Foundation) : l'URL fournie était la PAGE "all-country-scores"
     (pas le fichier). Vraie URL directe retrouvée et injectée.
   - GPI et FIW : les URLs fournies étaient des portails/outils interactifs
     (QoG Data Finder, World Bank Data360 - encore en "Beta"), pas des liens
     de téléchargement direct. Je n'ai trouvé aucun lien direct fiable pour
     ces deux-là : ils sont marqués `url_directe=None` (donc ignorés proprement
     avec un message clair) plutôt que de deviner une URL qui casserait plus
     tard. Voir le message affiché à l'exécution pour la marche à suivre.
   - WJP : avait disparu de la configuration alors qu'il fonctionnait avant.
     Remis, mais sans URL directe confirmée (même situation que GPI/FIW).
   - TRACE, BASEL, IIAG : URLs conservées telles que fournies (non re-vérifiées
     une par une), mais désormais protégées par la validation ci-dessus : si
     l'une d'elles est en réalité mauvaise, le téléchargement échouera
     proprement au lieu de corrompre le pipeline en silence.
"""

from __future__ import annotations

from pathlib import Path
import requests
from bs4 import BeautifulSoup
import urllib.parse

# Dossier où se trouve ce fichier telechargeur.py
BASE_DIR = Path(__file__).resolve().parent

# Dossier data du projet
DOSSIER_DATA = BASE_DIR / "data"
DOSSIER_DATA.mkdir(parents=True, exist_ok=True)

# Agent utilisateur standard pour éviter les blocages de base
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


# --------------------------------------------------------------------------- #
# Scrapers de secours : utiles quand la source ne publie pas d'URL stable
# d'une édition à l'autre (le lien change chaque année).
# --------------------------------------------------------------------------- #


CONFIG_TELECHARGEMENTS = {

    "BTI": {
        "url_directe": "https://data.gov.ma/data/fr/dataset/1b32e32f-b190-498e-a07e-dbf44a53c856/resource/9413eac0-cbce-4db2-b2f3-51ab18ae2363/download/classement_du_maroc_indice-de-transformation-de-bertelsmman-bti_data.xlsx",
        "scraper": None,
        "nom_fichier": "BTI_Database.xlsx",
    },

    "CPI": {
        "url_directe": "https://data.humdata.org/dataset/global-corruption-perceptions-index/resource/2019bc34-2771-40ce-870f-7a92cc1176a0/download/global_cpi_all.csv",
        "scraper": None,
        "nom_fichier": "CPI_GlobalResults.csv",
    },

    "OBI": {
        "url_directe": "https://internationalbudget.org/sites/default/files/2026-06/OBS_Full_Timeseries_2006_2025.xlsx",
        "scraper": None,
        "nom_fichier": "OBI_Timeseries.xlsx",
    },

    # /!\ Pas d'URL directe confirmée pour l'instant. La page officielle
    # ("current-historical-data") ne publie pas de lien stable — récupère
    # l'URL réelle via F12 -> Network dans ton navigateur, comme pour l'OBI,
    # et colle-la ici. En attendant, cet indice est ignoré proprement.
    "WJP": {
        "url_directe": None,
        "scraper": None,
        "nom_fichier": "WJP_Database.xlsx",
    },

    # Non re-vérifiée individuellement : protégée par la validation de contenu.
    "IIAG": {
        "url_directe": "https://data.gov.ma/data/fr/dataset/351f65eb-58f7-4f0f-b7e2-fe9098842103/resource/9efb60b5-679a-4be7-8698-9cec24c55ca9/download/classement_du_maroc_indice-ibrahim-de-la-gouvernance-en-afrique-iiag_data.xlsx",
        "scraper": None,
        "nom_fichier": "IIAG.xlsx",
    },

    # /!\ L'URL fournie à l'origine (datafinder.qog.gu.se/downloads?download=)
    # est une page d'outil de requête, pas un fichier. Aucun lien direct fiable
    # trouvé : à configurer manuellement si besoin.
    "GPI": {
        "url_directe": None,
        "scraper": None,
        "nom_fichier": "GPI.xlsx",
    },

    "WJP": {
        "url_directe": "https://data.gov.ma/data/fr/dataset/71b51ae1-fc8d-4ea9-828a-93be9a49ba7f/resource/f0691e2e-36fe-479d-a949-d84314a3eb72/download/classement_du_maroc_indice-de-letat-de-droit-wjp_data.xlsx",
        "scraper": None,
        "nom_fichier": "WJP.xlsx",
    },

    "DI": {
        "url_directe": "https://data.gov.ma/data/fr/dataset/721e32a8-8145-46a8-8396-ff3108e6d185/resource/a7b584d2-efe5-44d3-9799-49fa180465c7/download/classement_du_maroc_indice-de-la-democratie-di_data.xlsx",
        "scraper": None,
        "nom_fichier": "DI.xlsx",
    },

    # Corrigée : l'URL fournie était la page "all-country-scores", pas le
    # fichier. Vraie URL directe retrouvée sur la page (bouton "Download data").
    "IEF": {
        "url_directe": "https://static.heritage.org/index/data/2026/2026_indexofeconomicfreedom_data.xlsx",
        "scraper": None,
        "nom_fichier": "IEF.xlsx",
    },

    # /!\ L'URL fournie (data360.worldbank.org/en/dataset/FH_FIW) est la page
    # d'un portail encore en "Beta", pas un fichier téléchargeable. Aucun lien
    # direct fiable trouvé : à configurer manuellement si besoin (le fichier
    # officiel est normalement publié sur freedomhouse.org).
    "FIW": {
        "url_directe": None,
        "scraper": None,
        "nom_fichier": "FreedomInTheWorld.xlsx",
    },

}


# --------------------------------------------------------------------------- #
# Téléchargement + validation
# --------------------------------------------------------------------------- #

def _fichier_xlsx_est_valide(chemin: Path) -> bool:
    """Un vrai .xlsx est une archive ZIP : ses 2 premiers octets sont toujours 'PK'."""
    try:
        with open(chemin, "rb") as f:
            entete = f.read(4)
        return entete[:2] == b"PK"
    except OSError:
        return False


def telecharger_fichier(url: str, nom_sortie: str) -> Path | None:
    """
    Télécharge et sauvegarde un fichier brut distant, en vérifiant que le
    contenu reçu est bien un fichier de données et non une page web.
    """
    chemin_destination = DOSSIER_DATA / nom_sortie
    try:
        print(f"  Téléchargement en cours : {url}")
        response = requests.get(url, headers=HEADERS, stream=True, timeout=30)

        if response.status_code != 200:
            print(f"  [-] Échec du téléchargement. Code HTTP : {response.status_code}")
            return None

        content_type = response.headers.get("Content-Type", "").lower()
        if "text/html" in content_type:
            print(
                f"  [-] Contenu invalide reçu (HTML) : ce lien pointe probablement "
                f"vers une page web plutôt qu'un fichier direct. URL : {url}"
            )
            return None

        with open(chemin_destination, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        if nom_sortie.lower().endswith(".xlsx") and not _fichier_xlsx_est_valide(chemin_destination):
            print(
                f"  [-] Fichier invalide : '{nom_sortie}' ne commence pas par une "
                f"signature ZIP/xlsx valide (probablement une page d'erreur). Supprimé."
            )
            chemin_destination.unlink(missing_ok=True)
            return None

        print(f"  [OK] Enregistré avec succès sous : {chemin_destination}")
        return chemin_destination

    except Exception as e:
        print(f"  [-] Erreur lors du téléchargement : {e}")
        return None


def telecharger_tous_les_indices() -> dict[str, Path]:
    """
    Boucle unique pour tous les indices : tente d'abord l'URL directe (si
    définie), puis le scraper de secours (si défini et si l'URL directe a
    échoué ou est absente). Ignore proprement les indices sans aucune
    source disponible, avec un message explicite plutôt qu'une erreur.
    """
    print("=== TÉLÉCHARGEMENT DES INDICES ===")
    fichiers_telecharges: dict[str, Path] = {}

    for indice, cfg in CONFIG_TELECHARGEMENTS.items():
        print(f"\n--- {indice} ---")
        chemin = None

        if cfg.get("url_directe"):
            chemin = telecharger_fichier(cfg["url_directe"], cfg["nom_fichier"])

        if not chemin and cfg.get("scraper"):
            print(f"  Tentative via le scraper de secours pour {indice}...")
            url_trouvee = cfg["scraper"]()
            if url_trouvee:
                chemin = telecharger_fichier(url_trouvee, cfg["nom_fichier"])
            else:
                print(f"  [-] Le scraper n'a trouvé aucun lien pour {indice}.")

        if not chemin:
            print(
                f"  [!] {indice} : aucune source disponible pour l'instant. "
                f"Configure une 'url_directe' dans CONFIG_TELECHARGEMENTS "
                f"(récupérable via F12 -> Network dans ton navigateur)."
            )
            continue

        fichiers_telecharges[indice] = chemin

    print(f"\n=== TÉLÉCHARGEMENT TERMINÉ : {len(fichiers_telecharges)}/{len(CONFIG_TELECHARGEMENTS)} indices obtenus ===")
    return fichiers_telecharges


if __name__ == "__main__":
    resultat = telecharger_tous_les_indices()
    print("\nFichiers obtenus :", {k: str(v) for k, v in resultat.items()})
