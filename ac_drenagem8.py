import os
import json
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import folium
from streamlit_folium import st_folium


# -----------------------
# CONFIGURAÇÃO STREAMLIT
# -----------------------
st.set_page_config(page_title="PMSB - Drenagem", layout="wide")
st.title("💧 PMSB de Augusto Corrêa - PA: Drenagem")

# Caminho do GeoJSON (na mesma pasta do script)
DATA_PATH = Path(__file__).parent / "BD_BAIRROS_E_ZONA_RURAL_CONSUMO_ALL_DRENAGEM.geojson"


# -----------------------
# UTILITÁRIOS PARA GEOJSON
# -----------------------
def _is_git_lfs_pointer(txt_head: str) -> bool:
    return "git-lfs.github.com/spec" in txt_head


def _iter_coords(geom):
    """Percorre coordenadas de vários tipos de geometria do GeoJSON."""
    if not geom:
        return
    t = geom.get("type")
    coords = geom.get("coordinates")
    if t == "Point":
        yield coords
    elif t in ("MultiPoint", "LineString"):
        for c in coords:
            yield c
    elif t in ("MultiLineString", "Polygon"):
        for part in coords:
            for c in part:
                yield c
    elif t == "MultiPolygon":
        for poly in coords:
            for ring in poly:
                for c in ring:
                    yield c
    elif t == "GeometryCollection":
        for g in geom.get("geometries", []):
            yield from _iter_coords(g)


def _bounds_from_geojson(gj: dict):
    """Retorna (minx, miny, maxx, maxy) do FeatureCollection."""
    xs, ys = [], []
    for feat in gj.get("features", []):
        for x, y in _iter_coords(feat.get("geometry")):
            xs.append(x)
            ys.append(y)
    if not xs or not ys:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _filter_geojson(gj: dict, area: str, bairros_sel: list):
    """Filtra o FeatureCollection considerando campos ausentes como 'Não informado'."""
    def norm(v, default="Não informado"):
        if v is None:
            return default
        if isinstance(v, str) and v.strip() in ("", "nan", "None"):
            return default
        return v

    def cond(props):
        area_val = norm(props.get("AREA_y"))
        bairro_val = norm(props.get("BAIRRO_COM"))
        if area != "Todas" and area_val != area:
            return False
        if bairros_sel and bairro_val not in bairros_sel:
            return False
        return True

    feats = [f for f in gj.get("features", []) if cond(f.get("properties", {}))]
    return {"type": "FeatureCollection", "features": feats}


# -----------------------
# CARREGAMENTO DE DADOS
# -----------------------
@st.cache_data(show_spinner="Carregando dados...")
def load_data(geojson_path: Path):
    if not geojson_path.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {geojson_path.name}. "
            "Coloque o BD_BAIRROS_E_ZONA_RURAL_CONSUMO_ALL_DRENAGEM.geojson na raiz do app."
        )

    head = geojson_path.read_text(encoding="utf-8", errors="ignore")[:200]
    if _is_git_lfs_pointer(head):
        raise RuntimeError(
            "O GeoJSON parece ser um 'pointer' do Git LFS. "
            "Remova do LFS e faça commit do arquivo real no Git."
        )

    with geojson_path.open("r", encoding="utf-8") as f:
        gj = json.load(f)

    # DataFrame com as propriedades dos features
    props_list = [feat.get("properties", {}) for feat in gj.get("features", [])]
    df = pd.DataFrame(props_list)

    # Garante colunas usadas
    text_cols = ["AREA_y", "BAIRRO_COM", "LABEL_21", "LABEL_Q22", "LABEL_Q23", "LABEL_Q24", "LABEL_Q25", "LABEL_Q26"]
    for c in text_cols:
        if c not in df.columns:
            df[c] = "Não informado"
        df[c] = df[c].fillna("Não informado").astype(str)

    num_cols = ["N_domi", "pop_estim1"]
    for c in num_cols:
        if c not in df.columns:
            df[c] = 0
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    return df, gj


try:
    df_all, geojson_all = load_data(DATA_PATH)
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()


# -----------------------
# FILTROS
# -----------------------
st.markdown("### 🔎 Filtros")
col1, col2 = st.columns(2)

with col1:
    areas = ["Todas"] + sorted(df_all["AREA_y"].dropna().unique().tolist())
    area = st.selectbox("Área", areas)

if area != "Todas":
    bairros_disponiveis = sorted(
        df_all.loc[df_all["AREA_y"] == area, "BAIRRO_COM"].dropna().unique().tolist()
    )
else:
    bairros_disponiveis = sorted(df_all["BAIRRO_COM"].dropna().unique().tolist())

with col2:
    bairros_sel = st.multiselect("Bairro/Comunidade", bairros_disponiveis)


# Aplica filtros no DataFrame
df = df_all.copy()
if area != "Todas":
    df = df[df["AREA_y"] == area]
if bairros_sel:
    df = df[df["BAIRRO_COM"].isin(bairros_sel)]


# -----------------------
# INDICADORES
# -----------------------
st.markdown("### 📊 Indicadores Gerais")
col1, col2 = st.columns(2)
with col1:
    st.metric("Nº Domicílios", f"{df['N_domi'].sum():,.0f}")
with col2:
    st.metric("População Estimada", f"{df['pop_estim1'].sum():,.0f}")


# -----------------------
# GRÁFICOS
# -----------------------
st.markdown("### 📈 Indicadores de Consumo de Água")
col1, col2 = st.columns(2)

def pie(dataframe, col, title):
    if col not in dataframe.columns:
        st.warning(f"Coluna ausente: {col}")
        return
    tmp = dataframe.copy()
    tmp[col] = tmp[col].fillna("Não informado").astype(str)
    fig = px.pie(tmp, names=col, title=title)
    st.plotly_chart(fig, use_container_width=True)

with col1:
    pie(df, "LABEL_21", "Há pavimentação asfáltica")
    pie(df, "LABEL_Q22", "Há água saindo por esgoto")
    pie(df, "LABEL_Q23", "Sistema de drenagem")

with col2:
    pie(df, "LABEL_Q24", "Problemas em período de chuva")
    pie(df, "LABEL_Q25", "Problemas de drenagem")
    pie(df, "LABEL_Q26", "Moradia próximo a rio")


# -----------------------
# MAPA
# -----------------------
st.markdown("### 🗺️ Mapa das Comunidades")

geojson_filtered = _filter_geojson(geojson_all, area, bairros_sel)

if geojson_filtered.get("features"):
    bounds = _bounds_from_geojson(geojson_filtered)
    if bounds:
        minx, miny, maxx, maxy = bounds
        center = [(miny + maxy) / 2, (minx + maxx) / 2]
    else:
        center = [-5.0, -50.0]  # fallback

    m = folium.Map(location=center, zoom_start=11, tiles="cartodbpositron")

    folium.GeoJson(
        data=geojson_filtered,
        name="Polígonos",
        style_function=lambda x: {
            "fillColor": "#1f78b4",
            "color": "black",
            "weight": 1,
            "fillOpacity": 0.4,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["AREA_y", "BAIRRO_COM"],
            aliases=["Área:", "Bairro:"],
        ),
    ).add_to(m)

    if bounds:
        m.fit_bounds([[miny, minx], [maxy, maxx]])

    folium.LayerControl().add_to(m)
    st_folium(m, width=900, height=600)
else:
    st.warning("⚠️ Nenhum polígono encontrado para os filtros selecionados.")


# -----------------------
# SUGESTÕES DE MELHORIAS
# -----------------------
st.markdown("### 🔧 Sugestões de Melhorias")
st.write("""
- Ações educativas  
- Rede de drenagem por tubulação profunda 
- Rede de drenagem por tubulação superficial 
- Implantação de meio-fio
- Abertura de canaletas
- Limpeza e manutenção dos sistemas implantados
- Fiscalização de esgotamento irregular
""")