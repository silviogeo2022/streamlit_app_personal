# app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.interpolate import griddata

# ============================
# Configuração da página
# ============================
st.set_page_config(
    page_title="Distribuição espacial - Dados Agrícolas",
    page_icon="🌾",
    layout="wide"
)

st.title("🌾 Distribuição espacial - Dados Agrícolas")
st.markdown("---")

# ============================
# Carregamento de dados
# ============================
@st.cache_data
def load_data(path: str = "dados_agro.xlsx") -> pd.DataFrame:
    df = pd.read_excel(path)
    # Padronizar nomes de colunas removendo espaços extras
    df.columns = [c.strip() for c in df.columns]
    return df

try:
    df = load_data("dados_agro.xlsx")
except Exception as e:
    st.error(f"❌ Não foi possível carregar 'dados_agro.xlsx': {e}")
    st.stop()

# Verificações mínimas de colunas
cols_necessarias = {'Fazenda', 'Talhão', 'Latitude', 'Longitude'}
if not cols_necessarias.issubset(set(df.columns)):
    st.error(f"❌ Colunas obrigatórias ausentes. Esperado: {cols_necessarias}. Encontrado: {set(df.columns)}")
    st.stop()

# ============================
# Sidebar - Filtros e Config
# ============================
st.sidebar.header("🔍 Filtros")

talhoes_disponiveis = ['Todos'] + sorted(map(str, df['Talhão'].dropna().unique().tolist()))
talhao_selecionado = st.sidebar.selectbox(
    "🏞️ Selecione o Talhão",
    talhoes_disponiveis,
    help="Escolha um talhão específico ou 'Todos'"
)

# Elementos fixos conforme pedido
elementos_disponiveis = ['N', 'Mg', 'Ca_Mg', 'P', 'pH', 'CTC']
# Mostrar somente os que existem no arquivo (evita erro se faltar algum)
elementos_disponiveis = [e for e in elementos_disponiveis if e in df.columns]
if not elementos_disponiveis:
    st.error("❌ Nenhuma coluna de elemento disponível entre: N, Mg, Ca_Mg, P, pH, CTC")
    st.stop()

elemento_selecionado = st.sidebar.selectbox(
    "🧪 Selecione o Elemento",
    elementos_disponiveis,
    help="Elemento químico para interpolação"
)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Configurações")

metodo_interpolacao = st.sidebar.selectbox(
    "Método de Interpolação",
    ['linear', 'cubic', 'nearest'],
    index=0,
    help="Linear: suave | Cubic: detalhada (pode exigir mais pontos) | Nearest: rápida"
)

resolucao_grade = st.sidebar.slider(
    "Resolução da Grade",
    min_value=50, max_value=200, value=100, step=10,
    help="Maior = mais detalhes (pode ficar mais lento)"
)

# ============================
# Aplicar filtros
# ============================
if talhao_selecionado == 'Todos':
    df_filtrado = df.copy()
else:
    # Comparação leniente (caso haja variação de espaços/pontos)
    df_filtrado = df[df['Talhão'].astype(str).str.contains(str(talhao_selecionado), case=False, na=False)]

if df_filtrado.empty:
    st.warning("⚠️ Nenhum dado encontrado para os filtros selecionados.")
    st.stop()

# ============================
# Limpeza e agregação
# ============================
col_lat, col_lon = 'Latitude', 'Longitude'
df_clean = (
    df_filtrado
      .dropna(subset=[col_lat, col_lon, elemento_selecionado])
      .copy()
)

# Converter para numéricos se vier algo como string
for c in [col_lat, col_lon, elemento_selecionado]:
    df_clean[c] = pd.to_numeric(df_clean[c], errors='coerce')
df_clean = df_clean.dropna(subset=[col_lat, col_lon, elemento_selecionado])

if df_clean.empty:
    st.warning("⚠️ Dados insuficientes após limpeza para interpolação.")
    st.stop()

# Agregar por média em coordenadas repetidas (melhora estabilidade do griddata)
df_agregado = (
    df_clean
    .groupby([col_lat, col_lon], as_index=False)[elemento_selecionado]
    .mean()
)

# ============================
# Painel de métricas
# ============================
colA, colB, colC, colD, colE = st.columns(5)
valores = df_agregado[elemento_selecionado].values
with colA: st.metric("📊 Pontos válidos", len(df_agregado))
with colB: st.metric("📈 Máximo", f"{np.nanmax(valores):.3f}")
with colC: st.metric("📉 Mínimo", f"{np.nanmin(valores):.3f}")
with colD: st.metric("📊 Média", f"{np.nanmean(valores):.3f}")
with colE: st.metric("📏 Desvio Padrão", f"{np.nanstd(valores):.3f}")

# ============================
# Preparar grade
# ============================
lats = df_agregado[col_lat].values
lons = df_agregado[col_lon].values

lat_min, lat_max = np.nanmin(lats), np.nanmax(lats)
lon_min, lon_max = np.nanmin(lons), np.nanmax(lons)
lat_range = max(lat_max - lat_min, 1e-6)
lon_range = max(lon_max - lon_min, 1e-6)

# Expandir limites 10% para bordas
lat_min -= 0.1 * lat_range
lat_max += 0.1 * lat_range
lon_min -= 0.1 * lon_range
lon_max += 0.1 * lon_range

lat_grid = np.linspace(lat_min, lat_max, resolucao_grade)
lon_grid = np.linspace(lon_min, lon_max, resolucao_grade)
lon_mesh, lat_mesh = np.meshgrid(lon_grid, lat_grid)

# ============================
# Interpolação com fallback
# ============================
def interp_with_fallback(method: str):
    try:
        zi = griddata(
            (lons, lats),
            valores,
            (lon_mesh, lat_mesh),
            method=method,
            fill_value=np.nan
        )
        return zi, method, None
    except Exception as e:
        return None, method, str(e)

with st.spinner(f"🔄 Interpolando ({metodo_interpolacao}) {elemento_selecionado}..."):
    z, used_method, err = interp_with_fallback(metodo_interpolacao)
    if z is None:
        # fallback 1: linear
        if metodo_interpolacao != 'linear':
            z, used_method, err = interp_with_fallback('linear')
        # fallback 2: nearest
        if z is None:
            z, used_method, err = interp_with_fallback('nearest')

    if z is None:
        st.error(f"❌ Erro na interpolação: {err}")
        st.info("💡 Tente reduzir a resolução da grade ou use 'nearest'.")
        st.stop()

# ============================
# Mapa (Heatmap + Pontos)
# ============================
fig = go.Figure()

# Camada interpolada
fig.add_trace(go.Heatmap(
    x=lon_grid,
    y=lat_grid,
    z=z,
    colorscale='Viridis',
    name=f'{elemento_selecionado} Interpolado',
    hovertemplate=f'<b>{elemento_selecionado}</b><br>' +
                  'Longitude: %{x:.5f}<br>' +
                  'Latitude: %{y:.5f}<br>' +
                  'Valor: %{z:.3f}<extra></extra>',
    colorbar=dict(
        title=dict(text=f"{elemento_selecionado}", side="right")
    )
))

# Pontos originais (agregados)
fig.add_trace(go.Scatter(
    x=lons,
    y=lats,
    mode='markers',
    marker=dict(
        size=9,
        color=valores,
        colorscale='Viridis',
        line=dict(width=1.5, color='white'),
        showscale=False
    ),
    text=[f'{elemento_selecionado}: {v:.3f}' for v in valores],
    hovertemplate='<b>Ponto</b><br>' +
                  'Longitude: %{x:.5f}<br>' +
                  'Latitude: %{y:.5f}<br>' +
                  '%{text}<extra></extra>',
    name='Pontos'
))

titulo_talhao = talhao_selecionado if talhao_selecionado != 'Todos' else 'Todos os Talhões'
fig.update_layout(
    title=f'Interpolação Espacial - {elemento_selecionado} | {titulo_talhao} (método: {used_method})',
    xaxis_title='Longitude',
    yaxis_title='Latitude',
    height=720,
    showlegend=True
)

st.plotly_chart(fig, use_container_width=True)

# ============================
# Dados filtrados
# ============================
with st.expander("📋 Ver dados utilizados"):
    cols_show = ['Fazenda', 'Talhão', 'Latitude', 'Longitude']
    if elemento_selecionado not in cols_show:
        cols_show.append(elemento_selecionado)
    st.dataframe(df_clean[cols_show].reset_index(drop=True), use_container_width=True)

# ============================
# Rodapé
# ============================
st.markdown("---")
st.markdown("🌾 Análise Espacial de Elementos Agrícolas")