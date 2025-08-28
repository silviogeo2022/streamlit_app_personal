import streamlit as st
import geopandas as gpd
import plotly.express as px
import folium
from streamlit_folium import st_folium

import geopandas as gpd

# Caminho do shapefile (sem extensão, se preferir pode colocar direto "arquivo.shp")
# shapefile_path = "BD_CONSUMO_AGUA_AC._REV1.shp"

# # Ler shapefile
# gdf = gpd.read_file(shapefile_path)

# # Garantir que está em WGS84 (lat/lon)
# gdf = gdf.to_crs(epsg=4326)

# # Exportar para GeoJSON
# gdf.to_file("BD_CONSUMO_AGUA_AC.geojson", driver="GeoJSON")

#print("✅ Conversão concluída: BD_CONSUMO_AGUA_AC.geojson gerado com sucesso!")

# CONFIGURAÇÃO STREAMLIT
# -----------------------
st.set_page_config(page_title="PMSB - Consumo de Água", layout="wide")
st.title("💧 PMSB de Augusto Corrêa - PA: Consumo de Água")

# -----------------------
# FUNÇÃO PARA CARREGAR POLÍGONOS DO GEOJSON
# -----------------------
@st.cache_data
def load_poligonos():
    # agora lê direto o geojson
    gdf = gpd.read_file("BD_CONSUMO_AGUA_AC.geojson")
    gdf = gdf.to_crs(epsg=4326)
    gdf["AREA_y"] = gdf["AREA_y"].fillna("Não informado")
    gdf["BAIRRO_COM"] = gdf["BAIRRO_COM"].fillna("Não informado")
    return gdf

gdf = load_poligonos()

# -----------------------
# FILTROS DEPENDENTES COM MULTI-SELEÇÃO
# -----------------------
col1, col2 = st.columns(2)

with col1:
    area = st.selectbox("Área", ["Todas"] + sorted(gdf["AREA_y"].unique().tolist()))

# bairros dependem da área escolhida
if area != "Todas":
    bairros_disponiveis = gdf[gdf["AREA_y"] == area]["BAIRRO_COM"].unique().tolist()
else:
    bairros_disponiveis = gdf["BAIRRO_COM"].unique().tolist()

with col2:
    bairros_sel = st.multiselect("Bairro/Comunidade", sorted(bairros_disponiveis))

# aplicar filtros nos polígonos
df = gdf.copy()
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
    st.metric("População Estimada", f"{df['Pop_estim1'].sum():,.0f}")

# -----------------------
# GRÁFICOS
# -----------------------
st.markdown("### 📈 Indicadores de Consumo de Água")
col1, col2 = st.columns(2)

with col1:
    fig1 = px.pie(df, names="LABEL_Q5", title="Fonte de água de abastecimento")
    st.plotly_chart(fig1, use_container_width=True)

    fig2 = px.pie(df, names="LABEL_Q8", title="Entrega regular de água")
    st.plotly_chart(fig2, use_container_width=True)

    fig3 = px.pie(df, names="LABEL_Q7", title="Problemas relacionados à água")
    st.plotly_chart(fig3, use_container_width=True)

with col2:
    fig4 = px.pie(df, names="LABEL_Q6", title="Qualidade da água")
    st.plotly_chart(fig4, use_container_width=True)

    fig5 = px.pie(df, names="LABEL_Q9", title="Falta de água")
    st.plotly_chart(fig5, use_container_width=True)

    fig6 = px.pie(df, names="LABEL_Q10", title="Poço próximo de fossa séptica")
    st.plotly_chart(fig6, use_container_width=True)

# -----------------------
# MAPA
# -----------------------
st.markdown("### 🗺️ Mapa das Comunidades")

if not df.empty:
    center = [df.geometry.centroid.y.mean(), df.geometry.centroid.x.mean()]
    m = folium.Map(location=center, zoom_start=11, tiles="cartodbpositron")

    folium.GeoJson(
        data=df.to_json(),
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
        )
    ).add_to(m)

    # zoom para o filtro aplicado
    bounds = df.total_bounds  # [minx, miny, maxx, maxy]
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

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
- Cisternas ou caixas d’água coletivas  
- Distribuição de hipoclorito de sódio  
- Sistemas de tratamento doméstico  
- Melhoria no acesso à rede pública  
""")