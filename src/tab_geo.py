from __future__ import annotations

import gc
import os

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import streamlit as st
from folium.plugins import MarkerCluster
from scipy.spatial import Voronoi
from shapely.geometry import Polygon
from streamlit_folium import st_folium

from src.analysis import STATUS_LABELS as _STATUS_LABELS

# Constantes de cor por status (inclui nível 0)
_COR_STATUS: dict[int, str] = {
    0: "#0EA5E9",  # azul-céu  — sem atraso
    1: "#22C55E",  # verde     — normal
    2: "#EAB308",  # âmbar     — atenção
    3: "#F97316",  # laranja   — crítico
    4: "#EF4444",  # vermelho  — super crítica
}

_STATUS_OPCOES: dict[str, int | None] = {
    "Todas as críticas": None,
    "0 — Sem Atraso":    0,
    "1 — Normal":        1,
    "2 — Atenção":       2,
    "3 — Crítico":       3,
    "4 — Super Crítica": 4,
}


# GeoJSON das fronteiras de Sergipe (municípios) — fonte: tbrugz/geodata-br (CC0)
SERGIPE_GEOJSON_URL: str = (
    "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-28-mun.json"
)
SERGIPE_GEOJSON_LOCAL: str = "data/geo/sergipe_municipios.geojson"

# Centro geográfico de Sergipe e zoom calibrado para caber o estado inteiro
SERGIPE_CENTER: tuple[float, float] = (-10.57, -37.38)
SERGIPE_ZOOM: int = 8
SERGIPE_MIN_ZOOM: int = 8

# Bounding box apertado em torno de Sergipe
SERGIPE_BOUNDS_SW: tuple[float, float] = (-11.55, -38.25)
SERGIPE_BOUNDS_NE: tuple[float, float] = (-9.60, -36.35)


@st.cache_data(show_spinner=False, ttl=3600)
def _carregar_geojson_sergipe() -> dict | None:
    """Carrega o GeoJSON das fronteiras de Sergipe (local ou remoto)."""
    if os.path.exists(SERGIPE_GEOJSON_LOCAL):
        try:
            import json
            with open(SERGIPE_GEOJSON_LOCAL, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    try:
        resp = requests.get(SERGIPE_GEOJSON_URL, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None

@st.cache_data(show_spinner=False, ttl=900)
def carregar_dados_geograficos(ano: str, status_filter: int | None) -> tuple[gpd.GeoDataFrame | None, str | None]:
    """Carrega dados geográficos particionados por ano e status."""
    if status_filter is None or status_filter == "Todas":
        suffix = "all"
    else:
        suffix = f"n{status_filter}"

    particionado_path = f"data/geo/{ano}_geo_{suffix}.csv.zip"

    if os.path.exists(particionado_path):
        try:
            df = pd.read_csv(particionado_path, compression="zip")
        except Exception as e:
            return None, f"Erro ao ler arquivo particionado: {str(e)}"
    else:
        geo_raw_path = f"data/data_map/locais_criticos_{ano}.csv"
        try:
            df = pd.read_csv(geo_raw_path)
        except FileNotFoundError:
            return None, f"Arquivo não encontrado: `{geo_raw_path}`"
        except Exception as e:
            return None, f"Erro na leitura: {str(e)}"

        if status_filter is None:
            mask = df["STATUS"] > 0
        else:
            mask = df["STATUS"] == status_filter
        df = df[mask].copy()

    cols_obrigatorias = ["NR_LATITUDE", "NR_LONGITUDE", "STATUS", "NM_LOCAL_VOTACAO", "NM_MUNICIPIO"]
    faltantes = [c for c in cols_obrigatorias if c not in df.columns]
    if faltantes:
        return None, f"Colunas ausentes: {', '.join(faltantes)}"

    df["NR_LATITUDE"] = pd.to_numeric(df["NR_LATITUDE"], errors="coerce")
    df["NR_LONGITUDE"] = pd.to_numeric(df["NR_LONGITUDE"], errors="coerce")
    df["STATUS"] = pd.to_numeric(df["STATUS"], errors="coerce")

    df_valid = df.dropna(subset=["NR_LATITUDE", "NR_LONGITUDE", "STATUS"])
    df_valid = df_valid[
        (df_valid["NR_LATITUDE"] != -1) &
        (df_valid["NR_LONGITUDE"] != -1) &
        (df_valid["NR_LATITUDE"].between(-90, 90)) &
        (df_valid["NR_LONGITUDE"].between(-180, 180))
    ].copy()

    if df_valid.empty:
        return None, "Nenhum registro possui coordenadas geográficas válidas."

    gdf = gpd.GeoDataFrame(
        df_valid,
        geometry=gpd.points_from_xy(df_valid.NR_LONGITUDE, df_valid.NR_LATITUDE),
        crs="EPSG:4326",
    )
    return gdf, None


def _kpi_card(cor: str, label: str, qtd: int) -> str:
    """Retorna HTML de um card KPI compacto e proporcional (inline, sem quebras)."""
    return (
        f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:10px;'
        # ALTERAÇÃO: Padding vertical aumentado e flexbox para centralização Y
        f'padding:1.8rem 0.4rem;text-align:center;box-shadow:0 1px 3px rgba(15,23,42,0.04);'
        f'border-top:3px solid {cor};min-width:0;flex:1;'
        f'display:flex;flex-direction:column;justify-content:center;height:100%;">'
        f'<div style="font-size:0.6rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:{cor};margin-bottom:0.3rem;'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{label}</div>'
        f'<div style="font-size:1.25rem;font-weight:800;color:#0f172a;line-height:1.1;">{qtd:,}</div>'
        f'<div style="font-size:0.65rem;color:#94a3b8;margin-top:0.2rem;">pontos no mapa</div>'
        f'</div>'
    )


# ──────────────────────────────────────────────────────────────────────────────
# Tesselação de Voronoi
# ──────────────────────────────────────────────────────────────────────────────

def _gerar_voronoi_layer(
    gdf_points: gpd.GeoDataFrame,
    geojson_se: dict,
) -> folium.FeatureGroup | None:
    """
    Constrói uma camada Folium com a tesselação de Voronoi dos pontos em gdf_points,
    recortada pelo contorno do estado de Sergipe.

    Cada célula é colorida pelo STATUS do local de votação associado.
    Requer ao menos 4 pontos com coordenadas distintas.

    Adaptado de testevoronou.py (Camada B — Vitral de Voronoi).
    """
    if len(gdf_points) < 4:
        return None

    # Ruído estocástico sutil para evitar pontos colineares/coincidentes
    # (mesma estratégia do testevoronou.py, linha 113-116)
    np.random.seed(42)
    coords = np.column_stack([gdf_points.geometry.x.values,
                               gdf_points.geometry.y.values])
    coords += np.random.uniform(-1e-5, 1e-5, coords.shape)

    vor = Voronoi(coords)

    # Mapear cada ponto à sua região de Voronoi (ignora regiões infinitas com -1)
    polys: list[Polygon | None] = []
    for region_idx in vor.point_region:
        region = vor.regions[region_idx]
        if -1 not in region and len(region) > 0:
            polys.append(Polygon(vor.vertices[region]))
        else:
            polys.append(None)

    gdf_vor = gpd.GeoDataFrame(
        gdf_points.reset_index(drop=True),
        geometry=polys,
        crs="EPSG:4326",
    ).dropna(subset=["geometry"])

    if gdf_vor.empty:
        return None

    # Recorte pela malha do estado (mesmo approach do testevoronou.py, linha 199)
    gdf_se = gpd.GeoDataFrame.from_features(geojson_se["features"], crs="EPSG:4326")
    try:
        gdf_vor_clip = gpd.clip(gdf_vor, gdf_se)
    except Exception:
        gdf_vor_clip = gdf_vor  # fallback sem clip em caso de erro topológico

    if gdf_vor_clip.empty:
        return None

    # Serializar apenas as colunas necessárias para evitar erros de tipo no GeoJson
    cols_export = ["STATUS", "NM_LOCAL_VOTACAO", "NM_MUNICIPIO", "geometry"]
    cols_export = [c for c in cols_export if c in gdf_vor_clip.columns]
    geojson_str = gdf_vor_clip[cols_export].to_json()

    grupo = folium.FeatureGroup(name="Tesselação de Voronoi", overlay=True, control=True)

    folium.GeoJson(
        geojson_str,
        style_function=lambda feat: {
            "fillColor": _COR_STATUS.get(int(feat["properties"].get("STATUS", 0)), "#6c757d"),
            "color": "#ffffff",
            "weight": 0.8,
            "fillOpacity": 0.45,
        },
        highlight_function=lambda feat: {
            "fillColor": _COR_STATUS.get(int(feat["properties"].get("STATUS", 0)), "#6c757d"),
            "fillOpacity": 0.75,
            "weight": 2.0,
            "color": "#ffffff",
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["NM_LOCAL_VOTACAO", "NM_MUNICIPIO", "STATUS"],
            aliases=["Local:", "Município:", "Status:"],
            localize=True,
            sticky=False,
            style=(
                "font-family: 'Inter', sans-serif; font-size: 0.75rem;"
                "background: #ffffffcc; border-radius: 6px; border: none;"
                "padding: 4px 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05);"
            ),
        ),
    ).add_to(grupo)

    return grupo


def render_tab_geo(ano: str, status_filter: int | None) -> None:
    """Renderiza o conteúdo completo da aba 'Visão Geográfica'."""
    st.markdown(f"""
        <div class="section-header"><h2>Distribuição Geoespacial dos Locais Críticos <span style="color: #adb5bd; font-weight: 400;">· {ano}</span></h2></div>
    """, unsafe_allow_html=True)

    gdf_geo, erro_geo = carregar_dados_geograficos(ano, status_filter)

    if erro_geo:
        st.warning(f"Dados geográficos indisponíveis: {erro_geo}")
        st.info(
            "Para habilitar o mapa, certifique-se de que os arquivos particionados existam "
            "em `data/geo/` ou os arquivos `data/data_map/locais_criticos_2018.csv` e "
            "`data/data_map/locais_criticos_2022.csv` estejam presentes com as colunas "
            "NR_LATITUDE, NR_LONGITUDE, STATUS, NM_LOCAL_VOTACAO e NM_MUNICIPIO."
        )
        return

    # ── CSS customizado para os selects combinarem com o tema ──────────────
    st.markdown("""
        <style>
            .stSelectbox label, .stMultiSelect label {
                font-family: 'Inter', sans-serif !important;
                font-size: 0.7rem !important;
                font-weight: 700 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.08em !important;
                color: #64748b !important;
                margin-bottom: 0.25rem !important;
            }
            .stSelectbox > div[data-baseweb="select"],
            .stMultiSelect > div[data-baseweb="select"] {
                border-radius: 10px !important;
                border: 1px solid #e2e8f0 !important;
                box-shadow: 0 1px 3px rgba(15,23,42,0.04) !important;
                font-family: 'Inter', sans-serif !important;
                font-size: 0.82rem !important;
                color: #0f172a !important;
                min-height: 38px !important;
            }
            .stSelectbox > div[data-baseweb="select"]:hover,
            .stMultiSelect > div[data-baseweb="select"]:hover {
                border-color: #0072B2 !important;
                box-shadow: 0 2px 8px rgba(0,114,178,0.08) !important;
            }
            div[data-baseweb="popover"] {
                border-radius: 10px !important;
                border: 1px solid #e2e8f0 !important;
                box-shadow: 0 8px 24px rgba(15,23,42,0.10) !important;
                font-family: 'Inter', sans-serif !important;
            }
            div[data-baseweb="popover"] li {
                font-family: 'Inter', sans-serif !important;
                font-size: 0.82rem !important;
                color: #0f172a !important;
                padding: 8px 14px !important;
            }
            div[data-baseweb="popover"] li:hover {
                background: #f0f9ff !important;
            }
            div[data-baseweb="popover"] li[aria-selected="true"] {
                background: #f0f9ff !important;
                color: #0072B2 !important;
                font-weight: 600 !important;
            }
            div[data-baseweb="tag"] {
                background: #f0f9ff !important;
                border: 1px solid #bae6fd !important;
                border-radius: 6px !important;
                font-family: 'Inter', sans-serif !important;
                font-size: 0.78rem !important;
                color: #0072B2 !important;
                font-weight: 600 !important;
            }
            div[data-baseweb="tag"] svg {
                color: #0072B2 !important;
            }
            .stMultiSelect [data-baseweb="select"] input::placeholder {
                color: #94a3b8 !important;
                font-family: 'Inter', sans-serif !important;
                font-size: 0.82rem !important;
            }
        </style>
    """, unsafe_allow_html=True)

    # ── Layout: Filtros | KPIs | Configurações ─────────────────────────────────
    col_filtros, col_kpis, col_config = st.columns([1.3, 2.5, 1.2])

    # ═══════════════════════════════════════════════════════════════════════
    # COLUNA 1 — Filtros (Empilhados)
    # ═══════════════════════════════════════════════════════════════════════
    with col_filtros:
        # Renderizar STATUS primeiro (ele filtra os municípios)
        status_presentes = sorted(gdf_geo["STATUS"].dropna().unique())
        opcoes_filtradas = {
            k: v for k, v in _STATUS_OPCOES.items()
            if v is None or v in status_presentes
        }
        
        if status_filter is not None and status_filter in status_presentes:
            label_default = next(
                (k for k, v in _STATUS_OPCOES.items() if v == status_filter),
                list(opcoes_filtradas.keys())[0]
            )
        else:
            label_default = list(opcoes_filtradas.keys())[0]

        status_label_local = st.selectbox(
            "Status operacional",
            list(opcoes_filtradas.keys()),
            index=list(opcoes_filtradas.keys()).index(label_default),
            key="_geo_status_local",
        )
        status_filter_local = opcoes_filtradas[status_label_local]

        # Filtrar dados pelo status para obter municípios válidos
        if status_filter_local is not None:
            gdf_geo_status = gdf_geo[gdf_geo["STATUS"] == status_filter_local].copy()
        else:
            gdf_geo_status = gdf_geo.copy()

        municipios_disponiveis = sorted(gdf_geo_status["NM_MUNICIPIO"].dropna().unique())

        # Renderizar MUNICÍPIOS logo abaixo
        prev_sel = st.session_state.get("_geo_muni_main", [])
        valid_prev = [m for m in prev_sel if m in municipios_disponiveis]

        selected_munis = st.multiselect(
            "Municípios",
            municipios_disponiveis,
            default=valid_prev,
            placeholder="Selecione um ou mais...",
            key="_geo_muni_main",
            help="Filtra o mapa exibindo apenas os municípios selecionados."
        )

    # ═══════════════════════════════════════════════════════════════════════
    # APLICAÇÃO DO FILTRO FINAL
    # ═══════════════════════════════════════════════════════════════════════
    mask = pd.Series(True, index=gdf_geo_status.index)
    if selected_munis:
        mask &= gdf_geo_status["NM_MUNICIPIO"].isin(selected_munis)

    gdf_map = gdf_geo_status[mask]

    if gdf_map.empty:
        st.info("Nenhum ponto corresponde aos filtros selecionados.")
        return

    # ═══════════════════════════════════════════════════════════════════════
    # COLUNA 2 — KPIs (Alinhados no centro horizontal)
    # ═══════════════════════════════════════════════════════════════════════
    with col_kpis:
        # Margin-top para empurrar as boxes e alinhar com o centro dos filtros
        st.markdown("<div style='margin-top: 1.8rem;'></div>", unsafe_allow_html=True)
        
        if status_filter_local is None:
            counts = gdf_map["STATUS"].value_counts().sort_index()
            cards_html = "".join(
                _kpi_card(
                    _COR_STATUS.get(int(s), "#6c757d"),
                    _STATUS_LABELS.get(int(s), f"Nível {int(s)}"),
                    int(q)
                )
                for s, q in counts.items()
            )
            st.markdown(
                f'<div style="display:flex;gap:6px;align-items:stretch;">{cards_html}</div>',
                unsafe_allow_html=True
            )
        else:
            cor = _COR_STATUS.get(int(status_filter_local), "#6c757d")
            label = _STATUS_LABELS.get(int(status_filter_local), f"Nível {status_filter_local}")
            qtd = len(gdf_map)
            st.markdown(_kpi_card(cor, label, qtd), unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════════════
    # COLUNA 3 — Configurações do Mapa
    # ═══════════════════════════════════════════════════════════════════════
    with col_config:
        st.markdown("""
            <div style="font-family: 'Inter', sans-serif; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: #64748b; margin-bottom: 0.6rem; margin-top: 0.2rem;">
                ⚙️ Ajustes Visuais
            </div>
        """, unsafe_allow_html=True)
        
        # 1. Seletor de Tema do Mapa Base
        estilo_mapa = st.selectbox(
            "Tema Base",
            options=["Claro (Positron)", "Escuro (Dark Matter)", "Padrão (Voyager)", "OpenStreetMap"],
            index=0,
            label_visibility="collapsed",
            help="Altera o provedor de estilo do mapa de fundo."
        )

        st.markdown("<div style='height: 0.2rem;'></div>", unsafe_allow_html=True)
        
        # 2. Chaves de renderização (Toggles)
        agrupar_pontos = st.checkbox("📍 Agrupar Pontos", value=True, help="Agrupa marcadores próximos para limpar a visualização.")
        exibir_voronoi = st.checkbox(
            "🔷 Voronoi",
            value=False,
            key="_geo_voronoi_toggle",
            help="Divide o mapa em células de influência ao redor de cada local de votação.",
        )

    st.markdown("<div style='height: 1.0rem;'></div>", unsafe_allow_html=True)
    # ========== MAPEAMENTO DE TEMAS ==========
    dicionario_tiles = {
        "Claro (Positron)": "CartoDB positron",
        "Escuro (Dark Matter)": "CartoDB dark_matter",
        "Padrão (Voyager)": "CartoDB voyager",
        "OpenStreetMap": "OpenStreetMap"
    }
    tema_selecionado = dicionario_tiles.get(estilo_mapa, "CartoDB positron")

    # ========== MAPA MINIMALISTA ==========
    m = folium.Map(
        location=SERGIPE_CENTER,
        zoom_start=SERGIPE_ZOOM,
        min_zoom=SERGIPE_MIN_ZOOM,
        max_zoom=18,
        max_bounds=True,
        tiles=tema_selecionado, # Usa o tema escolhido pelo usuário
        attr="CartoDB" if "CartoDB" in tema_selecionado else None,
        control_scale=True,
    )

    bounds = [[SERGIPE_BOUNDS_SW[0], SERGIPE_BOUNDS_SW[1]],
              [SERGIPE_BOUNDS_NE[0], SERGIPE_BOUNDS_NE[1]]]
    m.fit_bounds(bounds)
    m.options['maxBounds'] = bounds
    m.options['maxBoundsViscosity'] = 1.0
    m.options['minZoom'] = SERGIPE_MIN_ZOOM

    # Adiciona o GeoJSON dos municípios (Oculto código do geojson_se para encurtar, mantenha o seu original!)
    geojson_se = _carregar_geojson_sergipe()
    if geojson_se:
        folium.GeoJson(
            geojson_se,
            name="Municípios de Sergipe",
            style_function=lambda feature: {
                "fillColor": "#d1d5db", "color": "#4b5563",
                "weight": 1.2, "fillOpacity": 0.15, "opacity": 0.7,
            },
            highlight_function=lambda feature: {
                "fillColor": "#9ca3af", "fillOpacity": 0.3,
                "weight": 1.8, "color": "#1f2937",
            },
            tooltip=folium.GeoJsonTooltip(fields=["name"], aliases=["Município:"], localize=True, sticky=False)
        ).add_to(m)

    # ── Camada 1: Voronoi (opcional) ─────────────────────────────────────────
    if exibir_voronoi and geojson_se:
        if len(gdf_map) < 4:
            st.warning("São necessários ao menos 4 pontos para gerar a tesselação de Voronoi.")
        else:
            with st.spinner("Calculando tesselação de Voronoi…"):
                grupo_vor = _gerar_voronoi_layer(gdf_map, geojson_se)
            if grupo_vor is not None:
                grupo_vor.add_to(m)

    # ── Camada 3: Marcadores (Clusterizado ou Individual) ────────────────────
    if agrupar_pontos:
        container_marcadores = MarkerCluster(name="Locais Críticos", overlay=True, control=False).add_to(m)
    else:
        container_marcadores = folium.FeatureGroup(name="Locais Críticos", overlay=True, control=False).add_to(m)

    # 1. Ordenar por STATUS descendente para garantir que a cor principal seja o pior cenário
    gdf_sorted = gdf_map.sort_values(by="STATUS", ascending=False)
    
    # 2. Agrupar por Coordenadas e Local de Votação
    cols_agrupamento = ["NR_LATITUDE", "NR_LONGITUDE", "NM_LOCAL_VOTACAO", "NM_MUNICIPIO"]
    grupos_locais = gdf_sorted.groupby(cols_agrupamento)

    for (lat, lon, local, municipio), df_local in grupos_locais:
        # Pega a métrica mais alta do grupo para estilizar o marcador principal
        status_maximo = int(df_local["STATUS"].max())
        cor_principal = _COR_STATUS.get(status_maximo, "#6c757d")
        label_principal = _STATUS_LABELS.get(status_maximo, f"Status {status_maximo}")
        qtd_secoes = len(df_local)

        # 3. Construir HTML do Cabeçalho Fixo (Sticky)
        # max-height e overflow-y criam uma barra de rolagem nativa se houver muitas seções no mesmo local
        popup_html = f"""
            <div style="font-family:'Inter',sans-serif; min-width:240px; max-width:280px; max-height:300px; overflow-y:auto; overflow-x:hidden; padding-right:4px;">
                <div style="background-color:rgba(255,255,255,0.95); position:sticky; top:0; z-index:999; padding-bottom:4px; margin-bottom:8px;">
                    <div style="background:{cor_principal}12; border-left:3px solid {cor_principal}; padding:6px 8px; border-radius:0 4px 4px 0;">
                        <div style="font-size:0.9rem; font-weight:700; color:#0f172a; margin-bottom:2px; line-height:1.2;">{local}</div>
                        <div style="font-size:0.75rem; color:#64748b;">{municipio} • <b>{qtd_secoes}</b> seções críticas</div>
                    </div>
                </div>
        """

        # 4. Iterar sobre as seções do grupo para construir a lista interna do Pop-up
        for _, row in df_local.iterrows():
            status_sec = int(row["STATUS"])
            cor_sec = _COR_STATUS.get(status_sec, "#6c757d")
            
            zona_val = int(row["NR_ZONA"]) if "NR_ZONA" in row.index and pd.notna(row["NR_ZONA"]) else "—"
            secao_val = int(row["NR_SECAO"]) if "NR_SECAO" in row.index and pd.notna(row["NR_SECAO"]) else "—"
            modelo_val = str(row["modelo"]) if "modelo" in row.index and pd.notna(row["modelo"]) else "—"

            atraso_html = ""
            if "ATRASO_FILA_MINUTOS" in row.index and pd.notna(row["ATRASO_FILA_MINUTOS"]):
                atraso_min = float(row["ATRASO_FILA_MINUTOS"])
                atraso_html = f'<div style="font-size:0.75rem; color:#475569; margin-top:4px;"><b>⏱ Atraso:</b> {atraso_min:.1f} min</div>'

            # Sub-card da seção
            popup_html += f"""
                <div style="border:1px solid #e2e8f0; border-radius:6px; padding:6px; margin-bottom:6px; background:#fafafa;">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span style="font-size:0.75rem; font-weight:700; color:#334155;">Zona: {zona_val} | Seç: {secao_val}</span>
                        <span style="background:{cor_sec}20; color:{cor_sec}; padding:2px 6px; border-radius:10px; font-size:0.6rem; font-weight:800; text-transform:uppercase;">Nível {status_sec}</span>
                    </div>
                    <div style="font-size:0.7rem; color:#64748b;"><b>Modelo:</b> {modelo_val}</div>
                    {atraso_html}
                </div>
            """

        popup_html += "</div>"

        # 5. Instanciar o marcador único
        folium.CircleMarker(
            location=[lat, lon],
            radius=5 + (status_maximo * 1.2),
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=folium.Tooltip(
                f"<b>{local}</b><br><span style='color:{cor_principal};font-weight:500;'>{label_principal}</span><br><span style='font-size:0.75rem;color:#64748b;'>{qtd_secoes} seções aglomeradas</span>", 
                sticky=False
            ),
            color=cor_principal,
            fill=True,
            fillColor=cor_principal,
            fillOpacity=0.85,
            weight=1.5,
        ).add_to(container_marcadores)

    folium.LayerControl(collapsed=True).add_to(m)

    # ========== JAVASCRIPT DE FALLBACK (TRAVA ZOOM + MOVIMENTO) ==========
    map_var = m.get_name()
    guard_js = f"""
    <script>
    (function() {{
        var MIN_ZOOM = {SERGIPE_MIN_ZOOM};
        var CENTER = [{SERGIPE_CENTER[0]}, {SERGIPE_CENTER[1]}];
        var DEFAULT_ZOOM = {SERGIPE_ZOOM};
        var BOUNDS = L.latLngBounds(
            L.latLng({SERGIPE_BOUNDS_SW[0]}, {SERGIPE_BOUNDS_SW[1]}),
            L.latLng({SERGIPE_BOUNDS_NE[0]}, {SERGIPE_BOUNDS_NE[1]})
        );

        function enforceZoom(map) {{
            var currentZoom = map.getZoom();
            if (currentZoom < MIN_ZOOM) {{
                map.setZoom(MIN_ZOOM);
            }}
        }}

        function enforceBoundsAndZoom(map) {{
            if (!map) return;
            map.setMaxBounds(BOUNDS);
            map.options.maxBoundsViscosity = 1.0;
            map.setMinZoom(MIN_ZOOM);
            enforceZoom(map);
            if (!BOUNDS.contains(map.getCenter())) {{
                map.setView(CENTER, DEFAULT_ZOOM);
            }}
        }}

        function waitForMap() {{
            var map = window['{map_var}'];
            if (map && map._leaflet_id) {{
                enforceBoundsAndZoom(map);
                map.on('load', function() {{ enforceBoundsAndZoom(map); }});
                map.on('zoomend', function() {{ enforceZoom(map); }});
                map.on('dragend', function() {{ enforceBoundsAndZoom(map); }});
                map.on('viewreset', function() {{ enforceBoundsAndZoom(map); }});
                if (map._container) {{
                    map._container.addEventListener('wheel', function(e) {{
                        setTimeout(function() {{ enforceZoom(map); }}, 10);
                    }}, false);
                    map._container.addEventListener('touchstart', function(e) {{
                        setTimeout(function() {{ enforceZoom(map); }}, 10);
                    }}, false);
                }}
            }} else {{
                setTimeout(waitForMap, 200);
            }}
        }}
        waitForMap();
    }})();
    </script>
    """
    from branca.element import Element
    m.get_root().html.add_child(Element(guard_js))

    spacer_left, map_col, spacer_right = st.columns([1, 7, 1])
    with map_col:
        st_folium(m, width=1450, height=720, returned_objects=[])

    del gdf_map, container_marcadores, m
    gc.collect()