"""
dashboard.py
============
Rôle : Interface de visualisation interactive (Streamlit).
Lit le fichier de données consolidé et l'affiche sous forme de KPIs et graphiques.

Corrections apportées à cette version
--------------------------------------
1. Le fichier n'existe pas encore -> le message pointait vers "python app.py",
   qui n'est pas le nom réel de ton orchestrateur (c'est Main.py). Corrigé.
2. Lecture du CSV : `Main.py` l'écrit en `encoding="utf-8-sig"` (avec BOM).
   On relit donc explicitement dans le même encodage, pour ne jamais dépendre
   du comportement par défaut de pandas selon les environnements/versions.
3. Le logo distant (`st.image(url...)`) plantait tout le dashboard si l'URL
   était injoignable (site en maintenance, réseau bloqué, etc.) -> protégé
   par un try/except, avec repli silencieux si l'image ne charge pas.
4. Ajout d'une vérification de schéma : si le CSV existe mais n'a pas les
   colonnes attendues (pipeline mal exécuté), un message clair l'indique au
   lieu d'un KeyError brut illisible pour ton jury.
5. Le calcul de la variation (delta) plantait si le score de l'année
   précédente était manquant (NaN) -> protégé.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

# --------------------------------------------------------------------------- #
# Configuration de la page
# --------------------------------------------------------------------------- #
st.set_page_config(
    page_title="INPPLC - Observatoire Dashboard",
    page_icon="®©",
    layout="wide",
)

FICHIER_CONSOLIDE = Path("./donnees_consolidees.csv")
COLONNES_ATTENDUES = [
    "annee", "index", "indicateur_specifique",
    "code_iso", "pays", "score", "rang_worldwide",
]

# --------------------------------------------------------------------------- #
# Menu latéral (Sidebar)
# --------------------------------------------------------------------------- #
with st.sidebar:
    try:
        st.image("https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcS43Htfi3yHFPO_5nuCXTRJD3z4R_jO4N5IUOYBI9AwYQ&s=10", width=170)
    except Exception:
        # Le dashboard ne doit jamais planter pour un simple logo indisponible
        # (site en maintenance, pas de connexion internet lors de la démo...).
        st.write("**INPPLC**")

    st.title(" Menu")
    st.markdown("---")
    st.info(
        " **Dashboard de l'Observatoire**\n"
        "Ce module lit les données consolidées par le pipeline backend "
        "(`Main.py`)."
    )

# --------------------------------------------------------------------------- #
# Titre principal
# --------------------------------------------------------------------------- #
st.title(" Tableau de Bord de l'Observatoire — Maroc")
st.write("Visualisation interactive des indicateurs de gouvernance et de lutte contre la corruption.")
st.markdown("---")

# --------------------------------------------------------------------------- #
# Chargement sécurisé du fichier CSV
# --------------------------------------------------------------------------- #
if not FICHIER_CONSOLIDE.exists():
    st.error(
        " Fichier de données consolidées manquant ! "
        "Exécutez d'abord `python Main.py` dans un terminal pour générer la base "
        "(`donnees_consolidees.csv`)."
    )
    st.stop()

try:
    # utf-8-sig car Main.py écrit le CSV avec ce même encodage (gère le BOM proprement)
    df_global = pd.read_csv(FICHIER_CONSOLIDE, encoding="utf-8-sig")
except Exception as e:
    st.error(f" Impossible de lire '{FICHIER_CONSOLIDE.name}' : {e}")
    st.stop()

if df_global.empty:
    st.warning("La base de données est vide. Relancez `Main.py` : aucune ligne n'a été consolidée.")
    st.stop()

colonnes_manquantes = [c for c in COLONNES_ATTENDUES if c not in df_global.columns]
if colonnes_manquantes:
    st.error(
        " Le fichier CSV ne respecte pas le schéma attendu. "
        f"Colonnes manquantes : {colonnes_manquantes}. "
        f"Colonnes trouvées : {list(df_global.columns)}. "
        "Vérifiez que Main.py, moteur_api.py et moteur_fichiers.py utilisent "
        "bien tous le même schéma standardisé."
    )
    st.stop()

# --------------------------------------------------------------------------- #
# 1. Filtres dynamiques (double niveau : indice parent -> sous-indicateur)
# --------------------------------------------------------------------------- #
indices_disponibles = sorted(df_global["index"].dropna().unique())

col_f1, col_f2 = st.columns(2)                            
with col_f1:
    index_choisi = st.selectbox(" Sélectionner l'Indice :", indices_disponibles)

df_index = df_global[df_global["index"] == index_choisi]
indicateurs_disponibles = sorted(df_index["indicateur_specifique"].dropna().unique())

with col_f2:
    indicateur_choisi = st.selectbox(" Sélectionner la Dimension :", indicateurs_disponibles)

# Filtrage final
df_visu = df_index[df_index["indicateur_specifique"] == indicateur_choisi].copy()
df_visu = df_visu.dropna(subset=["annee", "score"]).sort_values(by="annee")

if df_visu.empty:
    st.warning("Aucune donnée pour cette sélection.")
    st.stop()

# --------------------------------------------------------------------------- #
# 2. Cartes KPI
# --------------------------------------------------------------------------- #
dernier = df_visu.iloc[-1]
score_actuel = dernier["score"]
annee_actuelle = dernier["annee"]
rang_actuel = dernier["rang_worldwide"]

variation = None
if len(df_visu) > 1:
    score_precedent = df_visu.iloc[-2]["score"]
    if pd.notna(score_precedent) and pd.notna(score_actuel):
        variation = score_actuel - score_precedent

st.markdown(" Indicateurs Clés")
col_m1, col_m2, col_m3 = st.columns(3)

with col_m1:
    delta_str = f"{variation:+.2f}" if variation is not None else None
    st.metric(label=f"Dernier Score ({int(annee_actuelle)})", value=f"{score_actuel:.2f}", delta=delta_str)

with col_m2:
    if pd.notna(rang_actuel):
        st.metric(label="Rang Mondial", value=f"#{int(rang_actuel)}")
    else:
        st.metric(label="Rang Mondial", value="Non disponible")

with col_m3:
    st.metric(
        label="Plage d'années",
        value=f"{int(df_visu['annee'].min())} - {int(df_visu['annee'].max())}",
    )

# --------------------------------------------------------------------------- #
# 3. Graphique interactif Plotly
# --------------------------------------------------------------------------- #
st.markdown("###  Courbe d'Évolution")
fig = px.line(
    df_visu,
    x="annee",
    y="score",
    markers=True,
    title=f"Évolution de {indicateur_choisi} ({index_choisi}) pour le Maroc",
    labels={"annee": "Année", "score": "Score d'évaluation"},
    template="plotly_white",
)
fig.update_traces(line_color="#1E3D59", marker=dict(size=8, color="#F5F0BB"))
st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------------------------------- #
# 4. Table des données
# --------------------------------------------------------------------------- #
with st.expander(" Afficher la table des données"):
    st.dataframe(df_visu.sort_values(by="annee", ascending=False), use_container_width=True)
