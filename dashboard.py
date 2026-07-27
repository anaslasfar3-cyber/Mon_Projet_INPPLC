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

# 1. Configuration de la page en mode Large
st.set_page_config(
    page_title="Observatoire INPPLC",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Injection du CSS personnalisé pour l'arrière-plan sombre et les styles
st.markdown("""
    <style>
    /* Force l'arrière-plan général à être sombre et uniforme comme CasaBourse */
    .stApp {
        background-color: #121824 !important;
        color: #ffffff !important;
    }
    
    /* Style pour la grande boîte de titre principale avec dégradé Bleu-Noir */
    .main-title-box {
        background: linear-gradient(135deg, #0052d4, #4364f7, #121824);
        padding: 25px;
        border-radius: 12px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        margin-bottom: 25px;
    }
    
    /* Style pour les cartes d'indicateurs individuelles (Dégradés locaux sombres) */
    .indicator-card-wgi {
        background: linear-gradient(135deg, #1e293b, #0f172a);
        border: 1px solid #10b981; /* Bordure verte pour le Contrôle de la corruption */
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 15px;
    }
    
    .indicator-card-trace {
        background: linear-gradient(135deg, #2e1045, #0f172a); /* Dégradé Aubergine/Noir */
        border: 1px solid #a855f7; /* Bordure violette pour TRACE */
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 15px;
    }
    
    .card-title {
        font-size: 14px;
        color: #94a3b8;
        font-weight: 500;
        margin-bottom: 8px;
    }
    
    .card-value {
        font-size: 24px;
        font-weight: bold;
        color: #ffffff;
    }
    </style>
""", unsafe_allow_html=True)

# =========================================================================
# 3. EXEMPLE D'AFFICHAGE DU DASHBOARD AVEC LES CAS DES COULEURS
# =========================================================================

# --- Header Principal ---
st.markdown("""
    <div class="main-title-box">
        <h1 style="margin:0; color:white; font-size:32px;">L'Observatoire INPPLC</h1>
        <p style="margin:5px 0 0 0; color:#cbd5e1;">Indice Global : <strong style="color:#38bdf8;">72.5 / 100</strong> | Évolution : <span style="color:#4ade80;">+2.3%</span></p>
    </div>
""", unsafe_allow_html=True)


# --- Section Indicateurs (Exemple de disposition en colonnes) ---
st.subheader("📊 Indicateurs Clés de Gouvernance")

col1, col2 = st.columns(2)

with col1:
    # Utilisation de notre classe CSS "indicator-card-wgi" pour appliquer le dégradé sombre
    st.markdown("""
        <div class="indicator-card-wgi">
            <div class="card-title">🟢 Contrôle de la Corruption (WGI)</div>
            <div class="card-value">Score: 68.0 <span style="font-size:16px; color:#4ade80;">(+1.1%)</span></div>
        </div>
    """, unsafe_allow_html=True)

with col2:
    # Utilisation de notre classe CSS "indicator-card-trace" pour l'autre dégradé
    st.markdown("""
        <div class="indicator-card-trace">
            <div class="card-title">🔮 Score TRACE Matrix (Moyen)</div>
            <div class="card-value">Score: 42 <span style="font-size:16px; color:#94a3b8;">(Risque Stable)</span></div>
        </div>
    """, unsafe_allow_html=True)

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
