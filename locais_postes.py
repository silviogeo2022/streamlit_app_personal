import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio

# Configuração da página com layout amplo e redução de espaços
st.set_page_config(layout="wide")

# Título com menos espaço após ele
st.markdown("<h1 style='margin-bottom:0px;'>Painel de Localização de Postes</h1>", unsafe_allow_html=True)

# Carregando os dados
url = "https://raw.githubusercontent.com/silviogeo2022/streamlit_app_personal/main/Postes1.xlsx"
urlgeo = "https://raw.githubusercontent.com/silviogeo2022/streamlit_app_personal/main/BAIRROS.shp"
df = pd.read_excel(url)
#df = pd.read_excel("datasets\Postes1.xlsx")
gdf_bairros = gpd.read_file(urlgeo)  # Carregue seu shapefile de bairros

# Transformando sistemas de coordenadas se necessário
# Converta para o mesmo sistema de coordenadas (por exemplo, EPSG:4326)
gdf_bairros = gdf_bairros.to_crs(epsg=4326)

colunas_necessarias = {'Latitude', 'Longitude', 'Bairro', 'Potência_', 'Lâmpada_A'}
if colunas_necessarias.issubset(df.columns):
    
    cor = st.sidebar.color_picker("Escolha a cor dos pontos", value="#1f77b4")
    
    # Filtro de Bairro
    opcoes_bairros = ["Nenhum"] + sorted(df['Bairro'].unique().tolist())
    bairro_selecionado = st.sidebar.selectbox("Escolha o Bairro", options=opcoes_bairros)
    
    # Aplicação do filtro de bairro
    df_filtro_bairro = df if bairro_selecionado == "Nenhum" else df[df['Bairro'] == bairro_selecionado]
    
    # Filtro de Potência
    opcoes_potencia = ["Nenhum"] + sorted([str(x) for x in df_filtro_bairro['Potência_'].unique().tolist()])
    potencia_selecionada = st.sidebar.selectbox("Escolha a Potência", options=opcoes_potencia)
    
    # Aplicação do filtro de potência
    if potencia_selecionada != "Nenhum":
        try:
            potencia_valor = float(potencia_selecionada) if '.' in potencia_selecionada else int(potencia_selecionada)
            df_filtrado = df_filtro_bairro[df_filtro_bairro['Potência_'] == potencia_valor]
        except ValueError:
            df_filtrado = df_filtro_bairro[df_filtro_bairro['Potência_'] == potencia_selecionada]
    else:
        df_filtrado = df_filtro_bairro

    # Preparando os dados para o mapa com limites de bairros
    def create_map_with_boundaries(df_filtrado, gdf_bairros):
        # Criando o mapa base
        fig = go.Figure()

        # Adicionando os limites dos bairros
        for _, bairro in gdf_bairros.iterrows():
            if bairro.geometry is not None:
                # Tratamento para diferentes tipos de geometria
                def extract_polygon_coords(geometry):
                    if geometry.geom_type == 'Polygon':
                        return list(geometry.exterior.coords)
                    elif geometry.geom_type == 'MultiPolygon':
                        # Para multipolígonos, pegue o maior polígono
                        largest_poly = max(geometry.geoms, key=lambda p: p.area)
                        return list(largest_poly.exterior.coords)
                    return []

                # Obtendo as coordenadas
                coords = extract_polygon_coords(bairro.geometry)
                
                if coords:
                    # Separando latitudes e longitudes com segurança
                    lons = [coord[0] for coord in coords]
                    lats = [coord[1] for coord in coords]
                    
                    # Adicionando o polígono do bairro
                    fig.add_trace(go.Scattermapbox(
                        mode="lines",
                        lon=lons,
                        lat=lats,
                        line=dict(width=2, color='red'),
                        opacity=0.5,
                        showlegend=False  # Removendo legenda
                    ))

        # Adicionando os pontos de postes
        fig.add_trace(go.Scattermapbox(
            mode="markers",
            lon=df_filtrado['Longitude'],
            lat=df_filtrado['Latitude'],
            text=df_filtrado['Bairro'] + '<br>Potência: ' + df_filtrado['Potência_'].astype(str) + 
                 '<br>Lâmpada: ' + df_filtrado['Lâmpada_A'].astype(str),
            marker=dict(
                size=10,
                color=cor,
                opacity=0.7
            ),
            hoverinfo='text',
            showlegend=False  # Removendo legenda
        ))

        # Configurações de layout do mapa
        fig.update_layout(
            mapbox_style="open-street-map",
            mapbox=dict(
                center=dict(
                    lat=df_filtrado['Latitude'].mean(),
                    lon=df_filtrado['Longitude'].mean()
                ),
                zoom=13.3
            ),
            showlegend=False,  # Removendo legenda
            margin=dict(l=0, r=0, t=0, b=0),
            height=550
        )

        return fig

    # Criando o mapa
    fig_mapa = create_map_with_boundaries(df_filtrado, gdf_bairros)
    
    # Indicador de Quantidade de Postes
    total_pontos = len(df_filtrado)
    fig_indicador = go.Figure(go.Indicator(
        mode="number",
        value=total_pontos,
        title={"text": "Quantidade de Postes"},
    ))
    
    fig_indicador.update_layout(
        height=120,
        margin=dict(l=0, r=0, t=30, b=0),
    )
    
    # Renderizando os gráficos
    with st.container():
        st.markdown('<div style="padding: 0px;">', unsafe_allow_html=True)
        st.plotly_chart(fig_indicador, use_container_width=False)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div style="padding: 0px; margin-top: -20px;">', unsafe_allow_html=True)
        st.plotly_chart(fig_mapa, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Três gráficos abaixo do mapa - reduzindo espaço acima
    st.markdown('<div style="padding: 0px; margin-top: -20px;">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Gráfico de barras por bairro
        df_bairros = df_filtrado['Bairro'].value_counts().reset_index()
        df_bairros.columns = ['Bairro', 'Quantidade de Postes']

        fig_barras_bairros = px.bar(df_bairros,
                                    x='Bairro',
                                    y='Quantidade de Postes',
                                    title="Quantidade de Postes por Bairro",
                                    color='Bairro',
                                    color_discrete_sequence=px.colors.qualitative.Set2,
                                    text_auto=True,
                                    height=400)

        fig_barras_bairros.update_layout(
            margin=dict(l=0, r=0, t=40, b=0),
            xaxis={'categoryorder': 'total ascending'}
        )

        st.plotly_chart(fig_barras_bairros, use_container_width=True)
    
    with col2:
        # Gráfico de barras por potência
        df_potencia = df_filtrado.groupby(['Bairro', 'Potência_']).size().reset_index(name='Contagem')

        fig_barras_potencia = px.bar(df_potencia,
                                     x='Bairro',
                                     y='Contagem',
                                     color='Potência_',
                                     title="Frequência de Valores da Potência_ por Bairro",
                                     barmode="group",
                                     text_auto=True,
                                     height=400)

        fig_barras_potencia.update_layout(
            margin=dict(l=0, r=0, t=40, b=0),
            xaxis={'categoryorder': 'total ascending'}
        )

        st.plotly_chart(fig_barras_potencia, use_container_width=True)
    
    with col3:
        # Gráfico de barras por lâmpada
        df_lampada = df_filtrado.groupby(['Bairro', 'Lâmpada_A']).size().reset_index(name='Contagem')

        fig_barras_lampada = px.bar(df_lampada,
                                    x='Bairro',
                                    y='Contagem',
                                    color='Lâmpada_A',
                                    title="Frequência de Tipos de Lâmpada_A por Bairro",
                                    barmode="group",
                                    text_auto=True,
                                    height=400)

        fig_barras_lampada.update_layout(
            margin=dict(l=0, r=0, t=40, b=0),
            xaxis={'categoryorder': 'total ascending'}
        )

        st.plotly_chart(fig_barras_lampada, use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

else:
    st.error("O arquivo não contém as colunas necessárias: 'Latitude', 'Longitude', 'Bairro', 'Potência_' e 'Lâmpada_A'.")