"""
moteur_fichiers.py
===================
Version regroupée, optimisée et enrichie avec l'intégralité des indices de l'Observatoire :
CPI, BTI, WJP, OBI, IIAG, TRACE, BASEL, GPI, et FreedomInTheWorld.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

try:
    import pycountry
except ImportError:
    pycountry = None

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(name)s | %(message)s")
logger = logging.getLogger("moteur_fichiers")

# --------------------------------------------------------------------------- #
# 1. CONSTANTES & RÉFÉRENTIELS
# --------------------------------------------------------------------------- #

COLONNES_STANDARD = ["annee", "index", "indicateur_specifique", "code_iso", "pays", "score", "rang_worldwide"]
CODE_ISO_MAROC = "MAR"

CORRECTIONS_PAYS = {
    "Ivory Coast": "CIV", "Cote d'Ivoire": "CIV", "Côte d'Ivoire": "CIV",
    "DR Congo": "COD", "Democratic Republic of the Congo": "COD", "Congo, Dem. Rep.": "COD",
    "Congo, Rep.": "COG", "Republic of Congo": "COG", "Russia": "RUS",
    "South Korea": "KOR", "North Korea": "PRK", "Iran": "IRN", "Syria": "SYR",
    "Laos": "LAO", "Vietnam": "VNM", "Venezuela": "VEN", "Bolivia": "BOL",
    "Tanzania": "TZA", "Moldova": "MDA", "Brunei": "BRN", "Cape Verde": "CPV",
    "Swaziland": "SWZ", "Eswatini": "SWZ", "Micronesia": "FSM", "The Gambia": "GMB",
    "Gambia": "GMB", "Turkiye": "TUR", "Türkiye": "TUR", "Morocco": "MAR", "Maroc": "MAR"
}

# --------------------------------------------------------------------------- #
# 2. FONCTIONS DE REGROUPEMENT & UTILITAIRES (ÉCONOMIE DE CODE)
# --------------------------------------------------------------------------- #

def normaliser_iso3(nom_pays: str) -> Optional[str]:
    """Convertit de manière robuste un nom de pays en code ISO3 (Alpha-3)."""
    if not isinstance(nom_pays, str) or not nom_pays.strip():
        return None
    nom_pays = nom_pays.strip()
    if nom_pays in CORRECTIONS_PAYS:
        return CORRECTIONS_PAYS[nom_pays]
    if pycountry is not None:
        try:
            return pycountry.countries.lookup(nom_pays).alpha_3
        except LookupError:
            try:
                return pycountry.countries.search_fuzzy(nom_pays)[0].alpha_3
            except LookupError:
                return None
    return None

def _construire_dataframe_standard(lignes: list[dict]) -> pd.DataFrame:
    """Force le schéma strict et nettoie les types de données."""
    df = pd.DataFrame(lignes)
    if df.empty:
        return pd.DataFrame(columns=COLONNES_STANDARD)
    for col in COLONNES_STANDARD:
        if col not in df.columns:
            df[col] = None
    df["annee"] = pd.to_numeric(df["annee"], errors="coerce").astype("Int64")
    df["score"] = pd.to_numeric(df["score"], errors="coerce")
    df["rang_worldwide"] = pd.to_numeric(df["rang_worldwide"], errors="coerce").astype("Int64")
    return df[COLONNES_STANDARD].dropna(subset=["annee", "code_iso"])

def _charger_indice_generique(
    chemin_fichier: str | Path,
    nom_index: str,
    ind_specifique: str,
    termes_pays: list[str],
    termes_score: list[str],
    termes_annee: list[str] = [],
    termes_rang: list[str] = [],
    annee_defaut: Optional[int] = None,
    feuille: Optional[str] = None
) -> pd.DataFrame:
    """
    Fonction générique de regroupement : Parse automatiquement n'importe quel fichier 
    d'indice en gérant à la fois les formats verticaux et les séries horizontales par année.
    """
    chemin_fichier = Path(chemin_fichier)
    try:
        if chemin_fichier.suffix.lower() == '.csv':
            df = pd.read_csv(chemin_fichier, encoding='utf-8')
        else:
            if feuille:
                df = pd.read_excel(chemin_fichier, sheet_name=feuille)
            else:
                xls = pd.ExcelFile(chemin_fichier)
                df = pd.read_excel(chemin_fichier, sheet_name=xls.sheet_names[0])
    except Exception as e:
        logger.error("Erreur lecture %s : %s", nom_index, e)
        return pd.DataFrame(columns=COLONNES_STANDARD)

    df.columns = [str(c).strip() for c in df.columns]
    
    col_pays = next((c for c in df.columns if c.lower() in termes_pays), None)
    col_iso = next((c for c in df.columns if c.lower() in ("iso", "iso3", "code_iso", "country code")), None)
    
    if col_pays is None:
        return pd.DataFrame(columns=COLONNES_STANDARD)

    # --- CAS 1 : Format Horizontal (Une colonne brute par Année, ex: '2023') ---
    colonnes_annees = [c for c in df.columns if re.fullmatch(r"(19|20)\d{2}", c)]
    if colonnes_annees:
        lignes = []
        for _, row in df.iterrows():
            pays = row[col_pays]
            code_iso = (col_iso and row.get(col_iso)) or normaliser_iso3(pays)
            if not code_iso: continue
            for col_annee in colonnes_annees:
                score = pd.to_numeric(row[col_annee], errors="coerce")
                if pd.isna(score) or score == 0.0: continue
                lignes.append({
                    "annee": int(col_annee), "index": nom_index, "indicateur_specifique": ind_specifique,
                    "code_iso": code_iso, "pays": pays, "score": score, "rang_worldwide": None
                })
        return _construire_dataframe_standard(lignes)

    # --- CAS 2 : Format Vertical Standard (Colonnes d'identification explicites) ---
    col_annee = next((c for c in df.columns if c.lower() in termes_annee), None)
    col_score = next((c for c in df.columns if any(t in c.lower() for t in termes_score) and "rank" not in c.lower()), None)
    col_rang = next((c for c in df.columns if c.lower() in termes_rang), None)

    if col_score is None:
        return pd.DataFrame(columns=COLONNES_STANDARD)

    lignes = []
    for _, row in df.iterrows():
        pays = row[col_pays]
        code_iso = (col_iso and row.get(col_iso)) or normaliser_iso3(pays)
        if not code_iso: continue
        
        lignes.append({
            "annee": row[col_annee] if col_annee else (annee_defaut or 2026),
            "index": nom_index,
            "indicateur_specifique": ind_specifique,
            "code_iso": code_iso,
            "pays": pays,
            "score": row[col_score],
            "rang_worldwide": row[col_rang] if col_rang else None
        })
    return _construire_dataframe_standard(lignes)


# --------------------------------------------------------------------------- #
# 3. INTERFACES INDIVIDUELLES DES INDICES (APPELS DU REGROUPEMENT)
# --------------------------------------------------------------------------- #

def charger_cpi(chemin_fichier: str | Path) -> pd.DataFrame:
    """Parse le Corruption Perceptions Index de Transparency International."""
    return _charger_indice_generique(chemin_fichier, "CPI", "Score Global", 
                                     ["country", "pays", "country_name", "jurisdiction"], ["score", "cpi_score"], ["year", "annee"])

def charger_bti(chemin_fichier: str | Path) -> pd.DataFrame:
    """Parse le Bertelsmann Transformation Index."""
    return _charger_indice_generique(chemin_fichier, "BTI", "Transformation Index", 
                                     ["country", "pays"], ["score", "status"], ["year", "annee"])

def charger_wjp(chemin_fichier: str | Path) -> pd.DataFrame:
    """Parse le World Justice Project Rule of Law Index."""
    return _charger_indice_generique(chemin_fichier, "WJP", "Rule of Law Index", 
                                     ["country", "pays"], ["score", "index"], ["year", "annee"], ["rank", "rang"])

def charger_obi(chemin_fichier: str | Path) -> pd.DataFrame:
    """Parse l'Open Budget Index."""
    return _charger_indice_generique(chemin_fichier, "OBI", "Transparence Budgétaire", 
                                     ["country", "country name", "pays"], ["score"], ["year", "annee"])

def charger_iiag(chemin_fichier: str | Path) -> pd.DataFrame:
    """Parse l'Ibrahim Index of African Governance."""
    return _charger_indice_generique(chemin_fichier, "IIAG", "Overall Governance Score", 
                                     ["country", "pays"], ["score", "overall"], ["year", "annee"])

def charger_trace(chemin_fichier: str | Path) -> pd.DataFrame:
    """Parse la TRACE Bribery Risk Matrix."""
    return _charger_indice_generique(chemin_fichier, "TRACE", "Bribery Risk Score", 
                                     ["country", "pays"], ["score", "risk"], ["year", "annee"])

def charger_basel(chemin_fichier: str | Path) -> pd.DataFrame:
    """Parse le Basel AML Index (Anti-Money Laundering)."""
    return _charger_indice_generique(chemin_fichier, "BASEL", "Overall AML Score", 
                                     ["country", "pays", "year"], ["score", "overall score"], ["year"], ["ranking", "rank"])

def charger_gpi(chemin_fichier: str | Path) -> pd.DataFrame:
    """Parse le Global Peace Index."""
    return _charger_indice_generique(chemin_fichier, "GPI", "Peace Index Score", 
                                     ["country", "pays"], ["score"], ["year", "annee"])

def charger_freedom(chemin_fichier: str | Path) -> pd.DataFrame:
    """Parse le Freedom in the World Index."""
    return _charger_indice_generique(chemin_fichier, "Freedom", "Global Freedom Score", 
                                     ["country", "pays"], ["score", "total"], ["year", "annee"])


# --------------------------------------------------------------------------- #
# 4. REGISTRE CENTRALISÉ DES LOADERS & FILTRES
# --------------------------------------------------------------------------- #

LOADERS: dict[str, Callable[[str | Path], pd.DataFrame]] = {
    "CPI": charger_cpi,
    "BTI": charger_bti,
    "WJP": charger_wjp,
    "OBI": charger_obi,
    "IIAG": charger_iiag,
    "TRACE": charger_trace,
    "BASEL": charger_basel,
    "GPI": charger_gpi,
    "Freedom": charger_freedom
}

def charger_tous_les_fichiers(fichiers: dict[str, str | Path]) -> pd.DataFrame:
    """Parcourt dynamiquement le registre pour extraire l'ensemble des sources."""
    resultats: list[pd.DataFrame] = []
    for nom_indice, chemin in fichiers.items():
        loader = LOADERS.get(nom_indice)
        if loader is None:
            logger.warning("Aucun loader enregistré pour '%s' — fichier ignoré.", nom_indice)
            continue
        try:
            df = loader(chemin)
            logger.info("✔ %s : %d lignes normalisées extraites.", nom_indice, len(df))
            if not df.empty:
                resultats.append(df)
        except Exception as exc:
            logger.error("Échec du traitement de '%s' : %s", nom_indice, exc)

    if not resultats:
        return pd.DataFrame(columns=COLONNES_STANDARD)
    return pd.concat(resultats, ignore_index=True)

def filtrer_maroc(df: pd.DataFrame) -> pd.DataFrame:
    """Filtre les données consolidées exclusivement sur le Royaume du Maroc."""
    return df[df["code_iso"] == CODE_ISO_MAROC].reset_index(drop=True)