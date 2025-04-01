import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from io import BytesIO
from datetime import datetime

# Configuração da página com estilo moderno
st.set_page_config(page_title="Painel de Postes", layout="wide", page_icon="⚡")

# Estilos personalizados 
st.markdown("""
<style>
.stAlert { padding: 20px; }
.st-b7 { color: #1f77b4; }
.css-1aumxhk { background-color: #f0f8ff; }
.dashboard-title {
    font-size: 2.5rem;
    font-weight: bold;
    color: #1f77b4;
    margin-bottom: 0.5rem;
}
.dashboard-subtitle {
    font-size: 1.2rem;
    color: #777;
    margin-bottom: 2rem;
}
</style>
""", unsafe_allow_html=True)

# Título com estilo aprimorado
st.markdown("<h1 class='dashboard-title'>⚡ Painel de Localização de Postes</h1>", unsafe_allow_html=True)
st.markdown("<p class='dashboard-subtitle'>Visualização interativa de distribuição de postes por bairro, potência e tipo de lâmpada</p>", unsafe_allow_html=True)

# Função para carregar os dados com cache
@st.cache_data(ttl=3600)  # Cache de 1 hora
def load_poste_data():
    try:
        url = "https://raw.githubusercontent.com/silviogeo2022/streamlit_app_personal/main/Postes1.xlsx"
        urlgeo = "https://raw.githubusercontent.com/silviogeo2022/streamlit_app_personal/main/BAIRROS.shp"
        df = pd.read_excel(url)
        gdf_bairros = gpd.read_file(urlgeo)
        
        # Transformando sistemas de coordenadas
        gdf_bairros = gdf_bairros.to_crs(epsg=4326)
        
        return df, gdf_bairros
    except Exception as e:
        st.error(f"Erro ao carregar dados: {str(e)}")
        return None, None

def main():
    # Carregar dados
    with st.spinner("Carregando dados dos postes..."):
        df, gdf_bairros = load_poste_data()
    
    if df is not None and gdf_bairros is not None:
        colunas_necessarias = {'Latitude', 'Longitude', 'Bairro', 'Potência_', 'Lâmpada_A'}
        if colunas_necessarias.issubset(df.columns):
            # Sidebar com filtros
            st.sidebar.header("🔍 Filtros")
            
            # Escolha de cor
            cor = st.sidebar.color_picker("Escolha a cor dos pontos", value="#1f77b4")
            
            # Filtro de Bairro
            opcoes_bairros = ["Nenhum"] + sorted(df['Bairro'].unique().tolist())
            bairro_selecionado = st.sidebar.selectbox("Escolha o Bairro", options=opcoes_bairros)
            
            # Aplicação do filtro de bairro
            df_filtro_bairro = df if bairro_selecionado == "Nenhum" else df[df['Bairro'] == bairro_selecionado]
            
            # Filtro de Potência
            opcoes_potencia = ["Nenhum"] + sorted([str(x) for x in df_filtro_bairro['Potência_'].unique().tolist()])
            potencia_selecionada = st.sidebar.selectbox("Escolha a Potência", options=opcoes_potencia)
            
            # Filtro de Lâmpada (adicional)
            opcoes_lampada = ["Nenhum"] + sorted([str(x) for x in df_filtro_bairro['Lâmpada_A'].unique().tolist()])
            lampada_selecionada = st.sidebar.selectbox("Lâmpada acessa 24h?", options=opcoes_lampada)
            
            # Aplicação do filtro de potência
            if potencia_selecionada != "Nenhum":
                try:
                    potencia_valor = float(potencia_selecionada) if '.' in potencia_selecionada else int(potencia_selecionada)
                    df_filtrado = df_filtro_bairro[df_filtro_bairro['Potência_'] == potencia_valor]
                except ValueError:
                    df_filtrado = df_filtro_bairro[df_filtro_bairro['Potência_'] == potencia_selecionada]
            else:
                df_filtrado = df_filtro_bairro
            
            # Aplicação do filtro de lâmpada
            if lampada_selecionada != "Nenhum":
                df_filtrado = df_filtrado[df_filtrado['Lâmpada_A'].astype(str) == lampada_selecionada]
            
            # Configurações adicionais
            show_boundaries = st.sidebar.checkbox("🗺️ Mostrar limites dos bairros", True)
            point_size = st.sidebar.slider("Tamanho dos pontos no mapa", 5, 15, 10)
            
            # Criar abas
            tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Mapa", "📊 Dados", "📈 Análise", "ℹ️ Sobre"])
            
            with tab1:
                st.subheader("Mapa Interativo de Postes")
                st.markdown(f"""
                > **Total de postes visualizados:** {len(df_filtrado)} postes
                """)
                
                # Função para criar mapa com limites
                def create_map_with_boundaries(df_filtrado, gdf_bairros):
                    # Criando o mapa base
                    fig = go.Figure()

                    # Adicionando os limites dos bairros
                    if show_boundaries:
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
                                        showlegend=False
                                    ))

                    # Adicionando os pontos de postes
                    fig.add_trace(go.Scattermapbox(
                        mode="markers",
                        lon=df_filtrado['Longitude'],
                        lat=df_filtrado['Latitude'],
                        text=df_filtrado['Bairro'] + '<br>Potência: ' + df_filtrado['Potência_'].astype(str) + 
                             '<br>Lâmpada: ' + df_filtrado['Lâmpada_A'].astype(str),
                        marker=dict(
                            size=point_size,
                            color=cor,
                            opacity=0.7
                        ),
                        hoverinfo='text',
                        showlegend=False
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
                        showlegend=False,
                        margin=dict(l=0, r=0, t=0, b=0),
                        height=550
                    )
                    return fig

                # Criando o mapa
                fig_mapa = create_map_with_boundaries(df_filtrado, gdf_bairros)
                st.plotly_chart(fig_mapa, use_container_width=True)
                
                # Legenda
                st.markdown("""
                **Legenda:**
                - 🔵 Pontos azuis: Postes
                - 🔴 Linhas vermelhas: Limites dos bairros
                """)
            
            with tab2:
                st.subheader("Dados dos Postes")
                
                # Opções de visualização
                cols_to_show = st.multiselect(
                    "Selecione colunas para exibir",
                    options=df_filtrado.columns,
                    default=['Bairro', 'Potência_', 'Lâmpada_A', 'Latitude', 'Longitude']
                )
                
                # Ordenação
                sort_by = st.selectbox("Ordenar por", options=cols_to_show if cols_to_show else df_filtrado.columns, index=0)
                sort_order = st.radio("Ordem", options=['Ascendente', 'Descendente'], horizontal=True)
                
                display_df = df_filtrado.sort_values(
                    by=sort_by,
                    ascending=(sort_order == 'Ascendente')
                )[cols_to_show]
                
                st.dataframe(display_df, use_container_width=True, height=400)
                
                # Opções de download
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    st.download_button(
                        "⬇️ Baixar como CSV",
                        data=display_df.to_csv(index=False, sep=';'),
                        file_name="postes.csv",
                        mime="text/csv"
                    )
                with col2:
                    excel_buffer = BytesIO()
                    display_df.to_excel(excel_buffer, index=False)
                    st.download_button(
                        "⬇️ Baixar como Excel",
                        data=excel_buffer.getvalue(),
                        file_name="postes.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            with tab3:
                st.subheader("Análise Estatística")
                
                if not df_filtrado.empty:
                    col1, col2 = st.columns(2)
                    
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
                        
                        # Gráfico de distribuição de potência
                        fig_potencia_pie = px.pie(
                            df_filtrado, 
                            names='Potência_',
                            title="Distribuição por Potência",
                            hole=0.4,
                            color_discrete_sequence=px.colors.sequential.Blues_r
                        )
                        st.plotly_chart(fig_potencia_pie, use_container_width=True)
                    
                    with col2:
                        # Gráfico de barras por potência
                        df_potencia = df_filtrado.groupby(['Bairro', 'Potência_']).size().reset_index(name='Contagem')

                        fig_barras_potencia = px.bar(df_potencia,
                                                    x='Bairro',
                                                    y='Contagem',
                                                    color='Potência_',
                                                    title="Frequência de Valores da Potência por Bairro",
                                                    barmode="group",
                                                    text_auto=True,
                                                    height=400)

                        fig_barras_potencia.update_layout(
                            margin=dict(l=0, r=0, t=40, b=0),
                            xaxis={'categoryorder': 'total ascending'}
                        )

                        st.plotly_chart(fig_barras_potencia, use_container_width=True)
                        
                        # Gráfico de barras por lâmpada
                        df_lampada = df_filtrado.groupby(['Bairro', 'Lâmpada_A']).size().reset_index(name='Contagem')

                        fig_barras_lampada = px.bar(df_lampada,
                                                   x='Bairro',
                                                   y='Contagem',
                                                   color='Lâmpada_A',
                                                   title="Frequência de Lâmpada acesa por Bairro",
                                                   barmode="group",
                                                   text_auto=True,
                                                   height=400)

                        fig_barras_lampada.update_layout(
                            margin=dict(l=0, r=0, t=40, b=0),
                            xaxis={'categoryorder': 'total ascending'}
                        )

                        st.plotly_chart(fig_barras_lampada, use_container_width=True)
                else:
                    st.warning("Nenhum dado disponível para os filtros selecionados.")
            
            with tab4:
                st.subheader("Sobre o Painel de Postes")
                
                with st.expander("ℹ️ Como usar este painel?"):
                    st.markdown("""
                    ### 🔍 Como usar
                    Este painel permite visualizar a localização de postes com diferentes filtros:
                    
                    - **Bairro**: Selecione um bairro específico ou visualize todos
                    - **Potência**: Filtre por valor de potência das lâmpadas
                    - **Lâmpada acesa 24h?**: Filtre por lâmpada acessa 24h
                    
                    Você pode interagir com o mapa, fazer zoom e exportar os dados para CSV ou Excel.
                    """)
                
                with st.expander("🔌 Sobre os dados"):
                    st.markdown("""
                    ### 📡 Fonte dos dados
                    Os dados utilizados neste painel incluem:
                    
                    - **Localização**: Coordenadas geográficas (latitude/longitude)
                    - **Bairros**: Divisão administrativa da cidade
                    - **Potência**: Valor em Watts das lâmpadas
                    - **Lâmpada acesa 24h?**: Filtre por lâmpada acessa 24h
                    
                    Os dados são atualizados periodicamente para refletir novas instalações e manutenções.
                    """)
                
                st.markdown("---")
                st.markdown(f"""
                **Desenvolvido por:** Silvio Lemos, Engenheiro de Dados Geoespaciais. Linkedin: https://www.linkedin.com/in/silvio-lemos-75219096/  
                **Fonte dos dados:** Base Municipal de Iluminação  
                **Última atualização:** {datetime.now().strftime("%d/%m/%Y %H:%M")}
                """)
        else:
            st.error("O arquivo não contém as colunas necessárias: 'Latitude', 'Longitude', 'Bairro', 'Potência_' e 'Lâmpada_A'.")
    else:
        st.error("Não foi possível carregar os dados dos postes.")

if __name__ == "__main__":
    main()
