import streamlit as st
import pandas as pd
import numpy as np
from scipy.interpolate import griddata, Rbf

# Mapas
import folium
from streamlit_folium import st_folium
import branca.colormap as bcm
import matplotlib.cm as cm
import matplotlib.colors as mcolors

# Shapefile (limite)
import geopandas as gpd
from shapely import vectorized

# ============================
# Config da página
# ============================
st.set_page_config(page_title="Distribuição espacial - Dados Agrícolas", page_icon="🌾", layout="wide")
st.title("🌾 Distribuição espacial - Dados Agrícolas")
st.markdown("---")

# ============================
# Ler shapefile fixo
# ============================
SHAPEFILE_PATH = "lotes.shp"   # ajuste se necessário
TALHAO_COL = "Talhão"          # ajuste se necessário

@st.cache_data
def load_talhoes(path: str, talhao_col: str):
    gdf = gpd.read_file(path)
    if gdf.crs is None:
        gdf.set_crs("EPSG:4326", inplace=True)
    else:
        gdf = gdf.to_crs("EPSG:4326")
    if talhao_col not in gdf.columns:
        raise ValueError(f"A coluna '{talhao_col}' não existe no shapefile. Colunas: {list(gdf.columns)}")
    gdf["nome"] = gdf[talhao_col].astype(str)
    return gdf

gdf_talhoes = None
try:
    gdf_talhoes = load_talhoes(SHAPEFILE_PATH, TALHAO_COL)
except Exception as e:
    st.error(f"Erro ao ler o shapefile de talhões ({SHAPEFILE_PATH}): {e}")
    gdf_talhoes = None

# ============================
# Dados (Excel)
# ============================
@st.cache_data
def load_data(path: str = "dados_agro.xlsx") -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [c.strip() for c in df.columns]
    return df

try:
    df = load_data("dados_agro.xlsx")
except Exception as e:
    st.error(f"❌ Não foi possível carregar 'dados_agro.xlsx': {e}")
    st.stop()

cols_necessarias = {'Fazenda', 'Talhão', 'Latitude', 'Longitude'}
if not cols_necessarias.issubset(df.columns):
    st.error(f"❌ Colunas obrigatórias ausentes. Esperado: {cols_necessarias}. Encontrado: {set(df.columns)}")
    st.stop()

# ============================
# Sidebar
# ============================
st.sidebar.header("🔍 Filtros")
talhoes_disponiveis = ['Todos'] + sorted(map(str, df['Talhão'].dropna().unique().tolist()))
talhao_selecionado = st.sidebar.selectbox("🏞️ Selecione o Talhão", talhoes_disponiveis)

elementos_disponiveis = [e for e in ['N', 'Mg', 'Ca_Mg', 'P', 'pH', 'CTC'] if e in df.columns]
if not elementos_disponiveis:
    st.error("❌ Nenhuma coluna de elemento disponível entre: N, Mg, Ca_Mg, P, pH, CTC")
    st.stop()

elemento_selecionado = st.sidebar.selectbox("🧪 Selecione o Elemento", elementos_disponiveis)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Configurações")

# Apenas dois métodos
metodo_interpolacao = st.sidebar.selectbox(
    "Método de Interpolação (uma única superfície)",
    ['rbf (suave e extrapolada)', 'idw (extrapolada)'],
    index=0
)

resolucao_grade = st.sidebar.slider("Resolução da Grade (nº de pixels por lado)", 50, 300, 140, 10)

# ============================
# Filtros e limpeza
# ============================
if talhao_selecionado == 'Todos':
    df_filtrado = df.copy()
else:
    df_filtrado = df[df['Talhão'].astype(str).str.contains(str(talhao_selecionado), case=False, na=False)]

if df_filtrado.empty:
    st.warning("⚠️ Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

col_lat, col_lon = 'Latitude', 'Longitude'
df_clean = df_filtrado.dropna(subset=[col_lat, col_lon, elemento_selecionado]).copy()
for c in [col_lat, col_lon, elemento_selecionado]:
    df_clean[c] = pd.to_numeric(df_clean[c], errors='coerce')
df_clean = df_clean.dropna(subset=[col_lat, col_lon, elemento_selecionado])
if df_clean.empty:
    st.warning("⚠️ Dados insuficientes após limpeza para interpolação.")
    st.stop()

df_agregado = df_clean.groupby([col_lat, col_lon], as_index=False)[elemento_selecionado].mean()

# ============================
# Métricas
# ============================
colA, colB, colC, colD, colE = st.columns(5)
valores = df_agregado[elemento_selecionado].values
with colA: st.metric("📊 Pontos válidos", len(df_agregado))
with colB: st.metric("📈 Máximo", f"{np.nanmax(valores):.3f}")
with colC: st.metric("📉 Mínimo", f"{np.nanmin(valores):.3f}")
with colD: st.metric("📊 Média", f"{np.nanmean(valores):.3f}")
with colE: st.metric("📏 Desvio Padrão", f"{np.nanstd(valores):.3f}")

# ============================
# Grade e máscara (limite)
# ============================
lats = df_agregado[col_lat].values
lons = df_agregado[col_lon].values

usar_mascara = (gdf_talhoes is not None) and (talhao_selecionado != 'Todos')

poly = None
if usar_mascara:
    gdf_poly = gdf_talhoes[gdf_talhoes["nome"].astype(str).str.contains(str(talhao_selecionado), case=False, na=False)].copy()
    if gdf_poly.empty:
        st.info("ℹ️ Talhão não encontrado no shapefile; usando o primeiro disponível.")
        gdf_poly = gdf_talhoes.iloc[[0]].copy()
    poly = gdf_poly.geometry.unary_union
    minx, miny, maxx, maxy = poly.bounds
else:
    lat_min, lat_max = float(np.nanmin(lats)), float(np.nanmax(lats))
    lon_min, lon_max = float(np.nanmin(lons)), float(np.nanmax(lons))
    lat_range = max(lat_max - lat_min, 1e-6)
    lon_range = max(lon_max - lon_min, 1e-6)
    miny = lat_min - 0.1 * lat_range
    maxy = lat_max + 0.1 * lat_range
    minx = lon_min - 0.1 * lon_range
    maxx = lon_max + 0.1 * lon_range

lat_grid = np.linspace(miny, maxy, resolucao_grade)
lon_grid = np.linspace(minx, maxx, resolucao_grade)
lon_mesh, lat_mesh = np.meshgrid(lon_grid, lat_grid)

if usar_mascara and poly is not None:
    mask = vectorized.contains(poly, lon_mesh, lat_mesh)
else:
    mask = np.ones_like(lon_mesh, dtype=bool)

# ============================
# Interpolação (apenas UM método, sem mistura)
# ============================
def idw_interpolation(x, y, z, xi, yi, power=2, eps=1e-12):
    # x,y,z: 1D; xi,yi: 2D grids
    x = x.reshape(-1, 1, 1)
    y = y.reshape(-1, 1, 1)
    z = z.reshape(-1, 1, 1)
    dist = np.sqrt((xi - x) ** 2 + (yi - y) ** 2) + eps
    w = 1.0 / (dist ** power)
    zi = np.sum(w * z, axis=0) / np.sum(w, axis=0)
    return zi

def compute_surface(method):
    if method == 'rbf (suave e extrapolada)':
        dx = float(maxx - minx)
        dy = float(maxy - miny)
        eps = max(dx, dy) / 25.0
        rbf = Rbf(lons, lats, valores, function='multiquadric', epsilon=eps, smooth=0.0)
        return rbf(lon_mesh, lat_mesh)
    elif method == 'idw (extrapolada)':
        return idw_interpolation(lons, lats, valores, lon_mesh, lat_mesh, power=2)
    else:
        # fallback (não deve ocorrer): RBF
        dx = float(maxx - minx)
        dy = float(maxy - miny)
        eps = max(dx, dy) / 25.0
        rbf = Rbf(lons, lats, valores, function='multiquadric', epsilon=eps, smooth=0.0)
        return rbf(lon_mesh, lat_mesh)

with st.spinner(f"🔄 Interpolando ({metodo_interpolacao}) {elemento_selecionado}..."):
    z = compute_surface(metodo_interpolacao)

# aplica máscara do limite
z_masked = np.where(mask, z, np.nan)

# ============================
# Mapa – somente UMA camada de interpolação
# ============================
finite_vals = z_masked[np.isfinite(z_masked)]
if finite_vals.size == 0:
    vmin, vmax = 0.0, 1.0
else:
    vmin, vmax = float(np.nanmin(finite_vals)), float(np.nanmax(finite_vals))
    if vmin == vmax:
        vmax = vmin + 1e-9

cmap = cm.get_cmap('viridis')
norm = mcolors.Normalize(vmin=vmin, vmax=vmax)

rgba = cmap(norm(z_masked))
rgba[..., 3] = np.where(np.isfinite(z_masked), 0.78, 0.0)
rgba = np.flipud(rgba)

# centro do mapa
if usar_mascara and poly is not None:
    c_lat, c_lon = poly.centroid.y, poly.centroid.x
else:
    c_lat, c_lon = float(np.nanmean(lats)), float(np.nanmean(lons))

m = folium.Map(location=[c_lat, c_lon], zoom_start=16, tiles=None, control_scale=True)

# Base Esri Satélite
folium.TileLayer(
    tiles="https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    name="Satélite (Esri.WorldImagery)",
    attr="Esri, Maxar, Earthstar Geographics",
    overlay=False,
    control=False
).add_to(m)

# Único overlay de interpolação
folium.raster_layers.ImageOverlay(
    image=rgba,
    bounds=[[float(miny), float(minx)], [float(maxy), float(maxx)]],
    name=f"{elemento_selecionado} (Interpolação)",
    opacity=1,
    interactive=False,
    zindex=1
).add_to(m)

# Contorno do limite
if usar_mascara and poly is not None:
    folium.GeoJson(
        gpd.GeoDataFrame(geometry=[poly], crs="EPSG:4326").__geo_interface__,
        name="Limite",
        style_function=lambda x: {"color": "black", "weight": 3, "fill": False}
    ).add_to(m)

# Pontos amostrais
for la, lo, v in zip(lats, lons, valores):
    folium.CircleMarker(
        location=[float(la), float(lo)],
        radius=5, weight=2, color="white",
        fill=True, fill_color=mcolors.to_hex(cmap(norm(float(v)))),
        fill_opacity=0.95,
        tooltip=f"Ponto - {elemento_selecionado}: {float(v):.3f}",
        popup=folium.Popup(
            f"{elemento_selecionado}: {float(v):.3f}<br>Lat: {float(la):.5f}<br>Lon: {float(lo):.5f}",
            max_width=240
        ),
    ).add_to(m)

# Barra de cores
cbar = bcm.LinearColormap(
    colors=[mcolors.to_hex(cmap(i)) for i in np.linspace(0, 1, 256)],
    vmin=vmin, vmax=vmax
)
cbar.caption = elemento_selecionado
cbar.add_to(m)

titulo_talhao = talhao_selecionado if talhao_selecionado != 'Todos' else 'Todos os Talhões'
st.markdown(f"#### Interpolação Espacial - {elemento_selecionado} | {titulo_talhao}")
st_folium(m, use_container_width=True, height=720)

# ============================
# Dados utilizados
# ============================
with st.expander("📋 Ver dados utilizados"):
    cols_show = ['Fazenda', 'Talhão', 'Latitude', 'Longitude', elemento_selecionado]
    st.dataframe(df_clean[cols_show].reset_index(drop=True), use_container_width=True)

st.markdown("---")
st.markdown("🌾 Análise Espacial de Elementos Agrícolas")