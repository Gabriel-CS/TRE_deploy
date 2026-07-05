from __future__ import annotations

import gc
import json
import os

import folium
import geopandas as gpd
import numpy as np
import pandas as pd
import requests
import streamlit as st
from branca.element import Element
from folium.plugins import MarkerCluster
from scipy.spatial import Voronoi
from shapely.geometry import Polygon
from streamlit_folium import st_folium

from src.ui_components import info_card

from src.analysis import (
    FILTER_COM_ATRASO,
    FILTER_SOMENTE_CRITICAS,
    STATUS_LABELS,
    STATUS_OPCOES,
)

# ── Paleta de status ─────────────────────────────────────────────────────────
_COR_STATUS: dict[int, str] = {
    0: "#0EA5E9",
    1: "#22C55E",
    2: "#EAB308",
    3: "#F97316",
    4: "#EF4444",
}
_COR_NAO_CRITICO: str = "#94A3B8"


def _fmt_min_sec_geo(total_seconds) -> str | None:
    """
    Formata segundos totais em horas/minutos para uso nos popups do mapa —
    o tempo total de votação de uma seção facilmente passa de 1 hora, então
    o formato inclui horas quando necessário (ex.: '10h32min').
    """
    if total_seconds is None or pd.isna(total_seconds) or total_seconds <= 0:
        return None
    total_seconds = int(total_seconds)
    h, resto = divmod(total_seconds, 3600)
    m, s = divmod(resto, 60)
    if h > 0:
        return f"{h}h{m:02d}min"
    if m > 0:
        return f"{m}min{s:02d}s"
    return f"{s}s"

SERGIPE_GEOJSON_URL: str = (
    "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-28-mun.json"
)
SERGIPE_GEOJSON_LOCAL: str = "data/geo/sergipe_municipios.geojson"

SERGIPE_CENTER: tuple[float, float] = (-10.57, -37.38)
SERGIPE_ZOOM: int = 8
SERGIPE_MIN_ZOOM: int = 8
SERGIPE_BOUNDS_SW: tuple[float, float] = (-11.55, -38.25)
SERGIPE_BOUNDS_NE: tuple[float, float] = (-9.60, -36.35)

# Altura do mapa.
MAPA_ALTURA_PX: int = 720


@st.cache_data(show_spinner=False, ttl=3600)
def _carregar_geojson_sergipe() -> dict | None:
    if os.path.exists(SERGIPE_GEOJSON_LOCAL):
        try:
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
def carregar_dados_geograficos(ano: str, status_filter: str | int) -> tuple[gpd.GeoDataFrame | None, str | None]:
    if status_filter == 0:
        return carregar_dados_nao_criticos(ano)

    df: pd.DataFrame | None = None

    if status_filter == FILTER_SOMENTE_CRITICAS:
        path_csv = f"data/data_map/df_locais_somente_criticos_{ano}.csv"
    elif status_filter == FILTER_COM_ATRASO:
        path_csv = f"data/data_map/df_locais_com_atraso_{ano}.csv"
    else:
        path_csv = f"data/data_map/locais_criticos_{ano}.csv"

    if isinstance(status_filter, int):
        path_zip = f"data/geo/{ano}_geo_n{status_filter}.csv.zip"
        if os.path.exists(path_zip):
            try:
                df = pd.read_csv(path_zip, compression="zip")
            except Exception:
                pass

    if df is None:
        if status_filter == FILTER_SOMENTE_CRITICAS and not os.path.exists(path_csv):
            path_csv = f"data/data_map/df_locais_votacao_consolidado_somente_criticos_{ano}.csv"
        elif status_filter == FILTER_COM_ATRASO and not os.path.exists(path_csv):
            path_csv = f"data/data_map/df_locais_votacao_consolidado_com_atraso_{ano}.csv"

        if not os.path.exists(path_csv):
            path_csv = f"data/data_map/locais_criticos_{ano}.csv"

        try:
            df = pd.read_csv(path_csv)
        except FileNotFoundError:
            return None, f"Arquivo não encontrado: `{path_csv}`"
        except Exception as e:
            return None, f"Erro na leitura: {str(e)}"

        if isinstance(status_filter, int):
            df = df[df["STATUS"] == status_filter].copy()
        elif isinstance(status_filter, str):
            if status_filter == FILTER_SOMENTE_CRITICAS:
                df = df[df["STATUS"] > 2].copy()
            elif status_filter == FILTER_COM_ATRASO:
                df = df[df["STATUS"] > 1].copy()

    cols_obrigatorias = ["NR_LATITUDE", "NR_LONGITUDE", "STATUS", "NM_LOCAL_VOTACAO", "NM_MUNICIPIO"]
    faltantes = [c for c in cols_obrigatorias if c not in df.columns]
    if faltantes:
        return None, f"Colunas ausentes: {', '.join(faltantes)}"

    df["NR_LATITUDE"]  = pd.to_numeric(df["NR_LATITUDE"],  errors="coerce")
    df["NR_LONGITUDE"] = pd.to_numeric(df["NR_LONGITUDE"], errors="coerce")
    df["STATUS"]       = pd.to_numeric(df["STATUS"],       errors="coerce")

    df_valid = df.dropna(subset=["NR_LATITUDE", "NR_LONGITUDE", "STATUS"])
    df_valid = df_valid[
        (df_valid["NR_LATITUDE"]  != -1) &
        (df_valid["NR_LONGITUDE"] != -1) &
        (df_valid["NR_LATITUDE"].between(-90, 90)) &
        (df_valid["NR_LONGITUDE"].between(-180, 180))
    ].copy()

    if df_valid.empty:
        return None, "Nenhum registro possui coordenadas geográficas válidas para esta seleção."

    gdf = gpd.GeoDataFrame(
        df_valid,
        geometry=gpd.points_from_xy(df_valid.NR_LONGITUDE, df_valid.NR_LATITUDE),
        crs="EPSG:4326",
    )
    return gdf, None


@st.cache_data(show_spinner=False, ttl=900)
def carregar_dados_nao_criticos(ano: str) -> tuple[gpd.GeoDataFrame | None, str | None]:
    candidates = [
        f"data/data_map/locais_votacao_consolidado_sc_{ano}.csv.zip",
        f"data/data_map/locais_votacao_consolidado_sc_{ano}.csv",
    ]
    df: pd.DataFrame | None = None
    for path in candidates:
        if os.path.exists(path):
            try:
                compression = "zip" if path.endswith(".zip") else "infer"
                df = pd.read_csv(path, compression=compression)
                break
            except Exception as e:
                return None, f"Erro ao ler {path}: {e}"

    if df is None:
        return None, (
            f"Arquivo de seções não críticas não encontrado. "
            f"Esperado em: {candidates[0]} ou {candidates[1]}"
        )

    cols_obrigatorias = ["NR_LATITUDE", "NR_LONGITUDE", "NM_LOCAL_VOTACAO", "NM_MUNICIPIO"]
    faltantes = [c for c in cols_obrigatorias if c not in df.columns]
    if faltantes:
        return None, f"Colunas ausentes no dataset não crítico: {', '.join(faltantes)}"

    if "STATUS" not in df.columns:
        df["STATUS"] = 0
    else:
        df = df[df["STATUS"] == 0].copy()

    df["NR_LATITUDE"]  = pd.to_numeric(df["NR_LATITUDE"],  errors="coerce")
    df["NR_LONGITUDE"] = pd.to_numeric(df["NR_LONGITUDE"], errors="coerce")

    df_valid = df.dropna(subset=["NR_LATITUDE", "NR_LONGITUDE"])
    df_valid = df_valid[
        (df_valid["NR_LATITUDE"]  != -1) &
        (df_valid["NR_LONGITUDE"] != -1) &
        (df_valid["NR_LATITUDE"].between(-90,  90)) &
        (df_valid["NR_LONGITUDE"].between(-180, 180))
    ].copy()

    if df_valid.empty:
        return None, "Nenhum registro não crítico possui coordenadas válidas."

    gdf = gpd.GeoDataFrame(
        df_valid,
        geometry=gpd.points_from_xy(df_valid.NR_LONGITUDE, df_valid.NR_LATITUDE),
        crs="EPSG:4326",
    )
    return gdf, None


def _kpi_card(cor: str, label: str, qtd: int) -> str:
    return (
        f'<div style="background:var(--color-surface);border:1px solid var(--color-border);'
        f'border-radius:var(--radius-card);padding:1.8rem 0.4rem;text-align:center;'
        f'box-shadow:var(--shadow-card);border-top:3px solid {cor};min-width:0;flex:1;'
        f'display:flex;flex-direction:column;justify-content:center;height:100%;">'
        f'<div style="font-size:0.6rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:{cor};margin-bottom:0.3rem;'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{label}</div>'
        f'<div style="font-size:1.25rem;font-weight:800;color:var(--color-ink);line-height:1.1;">{qtd:,}</div>'
        f'<div style="font-size:0.65rem;color:var(--color-ink-muted);margin-top:0.2rem;">Locais de Votação</div>'
        f'</div>'
    )


def _voronoi_finite_polygons_2d(vor: Voronoi, radius: float) -> tuple[list[list[int]], np.ndarray]:
    """
    Reconstrói as regiões infinitas de um diagrama de Voronoi 2D em polígonos
    finitos, estendendo as arestas abertas por uma distância `radius`.

    Sem essa reconstrução, os pontos localizados na borda do conjunto (o que
    inclui praticamente todo o contorno do estado) ficam com região infinita
    e são descartados — é isso que produzia os "buracos" na tesselação.
    Recorte (clip) contra o polígono do estado é aplicado depois, então o
    valor de `radius` só precisa ser grande o suficiente para ultrapassar
    os limites do estado.
    """
    if vor.points.shape[1] != 2:
        raise ValueError("Requer um diagrama de Voronoi 2D.")

    new_regions: list[list[int]] = []
    new_vertices = vor.vertices.tolist()

    center = vor.points.mean(axis=0)

    # Mapeia, para cada ponto, quais arestas (ridges) ele compartilha com vizinhos
    all_ridges: dict[int, list[tuple[int, int, int]]] = {}
    for (p1, p2), (v1, v2) in zip(vor.ridge_points, vor.ridge_vertices):
        all_ridges.setdefault(p1, []).append((p2, v1, v2))
        all_ridges.setdefault(p2, []).append((p1, v1, v2))

    for p1, region_idx in enumerate(vor.point_region):
        vertices = vor.regions[region_idx]

        if all(v >= 0 for v in vertices):
            # Região já é finita
            new_regions.append(vertices)
            continue

        # Região infinita: reconstrói mantendo os vértices finitos e
        # "fechando" as arestas abertas na direção correta
        ridges = all_ridges.get(p1, [])
        new_region = [v for v in vertices if v >= 0]

        for p2, v1, v2 in ridges:
            if v2 < 0:
                v1, v2 = v2, v1
            if v1 >= 0:
                continue  # aresta finita, já tratada

            # Direção perpendicular à reta que une os dois pontos geradores
            t = vor.points[p2] - vor.points[p1]
            t = t / np.linalg.norm(t)
            n = np.array([-t[1], t[0]])

            midpoint = vor.points[[p1, p2]].mean(axis=0)
            direction = np.sign(np.dot(midpoint - center, n)) * n
            far_point = vor.vertices[v2] + direction * radius

            new_region.append(len(new_vertices))
            new_vertices.append(far_point.tolist())

        # Ordena os vértices em sentido angular para formar um polígono válido
        vs = np.asarray([new_vertices[v] for v in new_region])
        c = vs.mean(axis=0)
        angulos = np.arctan2(vs[:, 1] - c[1], vs[:, 0] - c[0])
        new_region = list(np.array(new_region)[np.argsort(angulos)])

        new_regions.append(new_region)

    return new_regions, np.asarray(new_vertices)


def _gerar_voronoi_layer(
    gdf_points: gpd.GeoDataFrame,
    geojson_se: dict,
) -> folium.FeatureGroup | None:
    if len(gdf_points) < 4:
        return None

    # ── Reprojeta para uma CRS métrica (UTM) antes de calcular o diagrama ──
    # Calcular o Voronoi diretamente em graus (lat/lon) distorce as células:
    # 1° de longitude equivale a uma distância bem menor que 1° de latitude
    # nesta latitude, então as células ficam "esticadas" no eixo errado.
    # Trabalhar em metros corrige a proporção real das áreas.
    try:
        crs_metrica = gdf_points.estimate_utm_crs()
    except Exception:
        # Fallback: UTM 24S cobre a faixa de longitude de Sergipe (36°-42°W)
        crs_metrica = "EPSG:32724"
    gdf_points_m = gdf_points.to_crs(crs_metrica)
    gdf_se = gpd.GeoDataFrame.from_features(geojson_se["features"], crs="EPSG:4326")
    gdf_se_m = gdf_se.to_crs(crs_metrica)

    coords = np.column_stack([
        gdf_points_m.geometry.x.values,
        gdf_points_m.geometry.y.values,
    ])

    # Pequeno jitter (30 cm) para evitar pontos duplicados/colineares, que
    # fazem o algoritmo de Voronoi falhar ou gerar células degeneradas
    rng = np.random.default_rng(42)
    coords = coords + rng.uniform(-0.3, 0.3, coords.shape)

    vor = Voronoi(coords)

    # Raio de extensão bem maior que a extensão dos pontos, garantindo que
    # todas as células (inclusive as da borda) sejam fechadas antes do clip
    extensao = np.ptp(coords, axis=0).max()
    raio_extensao = max(extensao * 4, 5000.0)

    regioes, vertices = _voronoi_finite_polygons_2d(vor, radius=raio_extensao)

    polys: list[Polygon | None] = []
    for regiao in regioes:
        try:
            poly = Polygon(vertices[regiao])
            if not poly.is_valid:
                poly = poly.buffer(0)
            polys.append(poly if not poly.is_empty else None)
        except Exception:
            polys.append(None)

    gdf_vor = gpd.GeoDataFrame(
        gdf_points_m.reset_index(drop=True),
        geometry=polys,
        crs=crs_metrica,
    ).dropna(subset=["geometry"])

    if gdf_vor.empty:
        return None

    gdf_vor["geometry"] = gdf_vor["geometry"].apply(
        lambda g: g if g.is_valid else g.buffer(0)
    )
    gdf_se_m["geometry"] = gdf_se_m["geometry"].apply(
        lambda g: g if g.is_valid else g.buffer(0)
    )

    try:
        gdf_vor_clip = gpd.clip(gdf_vor, gdf_se_m)
    except Exception:
        gdf_vor_clip = gdf_vor

    if gdf_vor_clip.empty:
        return None

    # Volta para WGS84 (graus) para desenhar no folium
    gdf_vor_clip = gdf_vor_clip.to_crs("EPSG:4326")

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


def render_tab_geo(ano: str, status_filter: str | int, estado_means: dict | None = None) -> None:
    """Renderiza a aba 'Visão Geográfica'."""

    st.markdown(f"""
        <div class="section-header">
            <h2>Distribuição Geoespacial dos Locais Críticos
                <span style="color:var(--color-ink-muted); font-weight:400;"> · {ano}</span>
            </h2>
        </div>
    """, unsafe_allow_html=True)

    gdf_geo, erro_geo = carregar_dados_geograficos(ano, status_filter)
    if erro_geo:
        st.warning(f"Dados geográficos indisponíveis: {erro_geo}")
        return

    # Prefixo usado como key do componente folium (único por ano+status)
    ss_prefix = f"geo_{ano}_{status_filter}"

    # ── Controles superiores ─────────────────────────────────────────────────
    col_filtros, col_kpis, col_config = st.columns([1.3, 2.5, 1.2])

    with col_filtros:
        if "geo_last_global" not in st.session_state:
            st.session_state["geo_last_global"] = status_filter

        if st.session_state["geo_last_global"] != status_filter:
            st.session_state["geo_last_global"] = status_filter
            label_default = next(k for k, v in STATUS_OPCOES.items() if v == status_filter)
            st.session_state["_geo_status_local"] = label_default

        status_label_local = st.selectbox(
            "Status operacional",
            list(STATUS_OPCOES.keys()),
            key="_geo_status_local",
        )
        status_filter_local = STATUS_OPCOES[status_label_local]
        gdf_geo_status, erro_geo = carregar_dados_geograficos(ano, status_filter_local)

    if erro_geo:
        st.warning(f"Dados geográficos indisponíveis: {erro_geo}")
        return

    with col_filtros:
        municipios_disponiveis = sorted(gdf_geo_status["NM_MUNICIPIO"].dropna().unique())
        prev_sel = st.session_state.get("_geo_muni_main", [])
        valid_prev = [m for m in prev_sel if m in municipios_disponiveis]

        selected_munis = st.multiselect(
            "Municípios",
            municipios_disponiveis,
            default=valid_prev,
            placeholder="Selecione um ou mais...",
            key="_geo_muni_main",
            help="Filtra o mapa exibindo apenas os municípios selecionados.",
        )

    mask = pd.Series(True, index=gdf_geo_status.index)
    if selected_munis:
        mask &= gdf_geo_status["NM_MUNICIPIO"].isin(selected_munis)

    gdf_map = gdf_geo_status[mask].copy() if isinstance(mask, pd.Series) else gdf_geo_status

    if gdf_map.empty:
        st.info("Nenhum ponto corresponde aos filtros selecionados.")
        return

    with col_config:
        st.markdown("""
            <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;
                        letter-spacing:0.08em;color:var(--color-ink-soft);
                        margin-bottom:0.6rem;margin-top:0.2rem;">Ajustes Visuais</div>
        """, unsafe_allow_html=True)

        estilo_mapa = st.selectbox(
            "Tema Base",
            options=["Claro (Positron)", "Escuro (Dark Matter)", "Padrão (Voyager)", "OpenStreetMap"],
            index=0,
            label_visibility="collapsed",
            help="Altera o provedor de estilo do mapa de fundo.",
        )

        st.markdown("<div style='height:0.2rem;'></div>", unsafe_allow_html=True)
        agrupar_pontos = st.checkbox("Agrupar Locais", value=True, help="Agrupa marcadores próximos.")
        exibir_voronoi = st.checkbox("Voronoi", value=False, key="_geo_voronoi_toggle")

        exibir_nao_criticos = (status_filter_local == 0)

    gdf_nao_criticos: gpd.GeoDataFrame | None = None
    if exibir_nao_criticos:
        gdf_nc, erro_nc = carregar_dados_nao_criticos(ano)
        if erro_nc:
            st.warning(f"Pontos não críticos indisponíveis: {erro_nc}")
        else:
            if selected_munis:
                gdf_nao_criticos = gdf_nc[gdf_nc["NM_MUNICIPIO"].isin(selected_munis)].copy()
            else:
                gdf_nao_criticos = gdf_nc

    with col_kpis:
        st.markdown("<div style='margin-top:1.8rem;'></div>", unsafe_allow_html=True)
        info_card("Total de seções eleitorais filtradas, agrupadas por nível de criticidade.")
        if isinstance(status_filter_local, str):
            counts = gdf_map["STATUS"].value_counts().sort_index()
            cards_html = "".join(
                _kpi_card(
                    _COR_STATUS.get(int(s), "#6c757d"),
                    STATUS_LABELS.get(int(s), f"Nível {int(s)}"),
                    int(q),
                )
                for s, q in counts.items()
            )
        else:
            cor   = _COR_STATUS.get(int(status_filter_local), "#6c757d")
            label = STATUS_LABELS.get(int(status_filter_local), f"Nível {status_filter_local}")
            qtd   = len(gdf_map)
            cards_html = _kpi_card(cor, label, qtd)

        st.markdown(
            f'<div style="display:flex;gap:6px;align-items:stretch;">{cards_html}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:1.0rem;'></div>", unsafe_allow_html=True)

    # ── Renderização do mapa Folium ──────────────────────────────────────────
    info_card(
        "Cada ponto no mapa representa uma seção eleitoral. A cor indica o nível de "
        "criticidade (atraso no encerramento) e os agrupamentos/Voronoi ajudam a "
        "identificar regiões com maior concentração de seções críticas."
    )
    col_mapa = st.container()
    with col_mapa:
        dicionario_tiles = {
            "Claro (Positron)":    "CartoDB positron",
            "Escuro (Dark Matter)":"CartoDB dark_matter",
            "Padrão (Voyager)":    "CartoDB voyager",
            "OpenStreetMap":       "OpenStreetMap",
        }
        tema_selecionado = dicionario_tiles.get(estilo_mapa, "CartoDB positron")

        m = folium.Map(
            location=SERGIPE_CENTER,
            zoom_start=SERGIPE_ZOOM,
            min_zoom=SERGIPE_MIN_ZOOM,
            max_zoom=18,
            max_bounds=True,
            tiles=tema_selecionado,
            attr="CartoDB" if "CartoDB" in tema_selecionado else None,
            control_scale=True,
        )

        bounds = [
            [SERGIPE_BOUNDS_SW[0], SERGIPE_BOUNDS_SW[1]],
            [SERGIPE_BOUNDS_NE[0], SERGIPE_BOUNDS_NE[1]],
        ]
        m.fit_bounds(bounds)
        m.options["maxBounds"]           = bounds
        m.options["maxBoundsViscosity"]  = 1.0
        m.options["minZoom"]             = SERGIPE_MIN_ZOOM

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
                tooltip=folium.GeoJsonTooltip(
                    fields=["name"], aliases=["Município:"], localize=True, sticky=False,
                ),
            ).add_to(m)

        if exibir_voronoi and geojson_se:
            if len(gdf_map) < 4:
                st.warning("São necessários ao menos 4 pontos para a tesselação de Voronoi.")
            else:
                with st.spinner("Calculando tesselação de Voronoi…"):
                    grupo_vor = _gerar_voronoi_layer(gdf_map, geojson_se)
                if grupo_vor is not None:
                    grupo_vor.add_to(m)

        if agrupar_pontos:
            container_marcadores = MarkerCluster(name="Locais Votação", overlay=True, control=False).add_to(m)
        else:
            container_marcadores = folium.FeatureGroup(name="Locais Votação", overlay=True, control=False).add_to(m)

        gdf_sorted      = gdf_map.sort_values(by="STATUS", ascending=False)
        cols_agrupamento = ["NR_LATITUDE", "NR_LONGITUDE", "NM_LOCAL_VOTACAO", "NM_MUNICIPIO"]
        grupos_locais   = gdf_sorted.groupby(cols_agrupamento)

        cols_lista = [
            c for c in [
                "NR_ZONA", "NR_SECAO", "STATUS", "modelo", "ATRASO_FILA_MINUTOS",
                "HOUVE_TROCA_POR_CONTINGENCIA", "EH_URNA_CONTINGENCIA",
                "TEMPO_SECAO_PRIMEIRO_ULTIMO_VOTO_SEG",
            ] if c in gdf_sorted.columns
        ]

        for (lat, lon, local, municipio), df_local in grupos_locais:
            status_maximo  = int(df_local["STATUS"].max())
            cor_principal  = _COR_STATUS.get(status_maximo, "#6c757d")
            label_principal = STATUS_LABELS.get(status_maximo, f"Status {status_maximo}")
            qtd_secoes     = len(df_local)
            texto_secoes   = "seções com atraso" if status_maximo > 1 else "seções sem atraso"

            qtd_conting = 0
            if "HOUVE_TROCA_POR_CONTINGENCIA" in cols_lista or "EH_URNA_CONTINGENCIA" in cols_lista:
                mask_conting = pd.Series(False, index=df_local.index)
                if "HOUVE_TROCA_POR_CONTINGENCIA" in df_local.columns:
                    mask_conting |= df_local["HOUVE_TROCA_POR_CONTINGENCIA"].fillna(False).astype(bool)
                if "EH_URNA_CONTINGENCIA" in df_local.columns:
                    mask_conting |= df_local["EH_URNA_CONTINGENCIA"].fillna(False).astype(bool)
                qtd_conting = int(mask_conting.sum())
            selo_conting = (
                f' · ↻ <b>{qtd_conting}</b> com contingência' if qtd_conting > 0 else ""
            )

            # Lista individual das seções/urnas do local de votação
            itens_secoes_html = ""
            if {"NR_ZONA", "NR_SECAO"}.issubset(cols_lista):
                df_local_sorted = df_local.sort_values("STATUS", ascending=False)
                tem_modelo   = "modelo" in cols_lista
                tem_atraso   = "ATRASO_FILA_MINUTOS" in cols_lista
                tem_conting  = ("HOUVE_TROCA_POR_CONTINGENCIA" in cols_lista) or ("EH_URNA_CONTINGENCIA" in cols_lista)
                tem_t_voto   = "TEMPO_SECAO_PRIMEIRO_ULTIMO_VOTO_SEG" in cols_lista

                cards = []
                for _, row in df_local_sorted.iterrows():
                    st_row  = int(row["STATUS"])
                    cor_row = _COR_STATUS.get(st_row, "#6c757d")
                    lbl_row = STATUS_LABELS.get(st_row, f"Status {st_row}")

                    linha_modelo = ""
                    if tem_modelo and pd.notna(row.get("modelo")):
                        linha_modelo = (
                            f'<div style="font-size:0.72rem;color:#475569;margin-top:2px;">'
                            f'Modelo: <b>{row["modelo"]}</b></div>'
                        )

                    linha_atraso = ""
                    if tem_atraso and pd.notna(row.get("ATRASO_FILA_MINUTOS")):
                        linha_atraso = (
                            f'<div style="font-size:0.72rem;color:#475569;margin-top:2px;">'
                            f'Atraso: <b>{row["ATRASO_FILA_MINUTOS"]:.1f} min</b></div>'
                        )

                    # Indicação de urna de contingência (troca de urna na seção)
                    linha_conting = ""
                    if tem_conting:
                        houve_troca = bool(row.get("HOUVE_TROCA_POR_CONTINGENCIA", False))
                        eh_conting  = bool(row.get("EH_URNA_CONTINGENCIA", False))
                        if houve_troca or eh_conting:
                            linha_conting = (
                                '<div style="font-size:0.72rem;color:#92400e;margin-top:2px;">'
                                '↻ <b>Urna de contingência</b></div>'
                            )

                    # Tempo total de votação (1º voto -> último voto computado)
                    linha_t_voto = ""
                    if tem_t_voto:
                        t_voto_fmt = _fmt_min_sec_geo(row.get("TEMPO_SECAO_PRIMEIRO_ULTIMO_VOTO_SEG"))
                        if t_voto_fmt:
                            linha_t_voto = (
                                f'<div style="font-size:0.72rem;color:#475569;margin-top:2px;">'
                                f'Tempo de votação: <b>{t_voto_fmt}</b></div>'
                            )

                    cards.append(
                        f'<div style="padding:6px 8px;margin-top:6px;border-radius:6px;'
                        f'background:#f8fafc;border:1px solid #e2e8f0;">'
                        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                        f'<span style="font-size:0.78rem;font-weight:600;color:#0f172a;">'
                        f'Zona {row["NR_ZONA"]} | Seç. {row["NR_SECAO"]}</span>'
                        f'<span style="font-size:0.65rem;font-weight:700;color:#fff;background:{cor_row};'
                        f'padding:1px 6px;border-radius:10px;white-space:nowrap;">{lbl_row}</span>'
                        f'</div>'
                        f'{linha_modelo}'
                        f'{linha_atraso}'
                        f'{linha_conting}'
                        f'{linha_t_voto}'
                        f'</div>'
                    )

                itens_secoes_html = (
                    '<div style="max-height:220px;overflow-y:auto;margin-top:6px;'
                    'padding-top:4px;border-top:1px dashed #e2e8f0;">'
                    + "".join(cards) +
                    '</div>'
                )
                del df_local_sorted, cards

            popup_html = f"""
                <div style="font-family:'Inter',sans-serif;min-width:230px;max-width:300px;">
                    <div style="background:{cor_principal}12;border-left:3px solid {cor_principal};
                                padding:8px 10px;border-radius:0 6px 6px 0;">
                        <div style="font-size:0.9rem;font-weight:700;color:#0f172a;
                                    margin-bottom:2px;line-height:1.2;">{local}</div>
                        <div style="font-size:0.75rem;color:#64748b;">
                            {municipio} · <b>{qtd_secoes}</b> {texto_secoes}{selo_conting}</div>
                        {itens_secoes_html}
                    </div>
                </div>
            """

            folium.CircleMarker(
                location=[lat, lon],
                radius=5 + (status_maximo * 1.2),
                popup=folium.Popup(popup_html, max_width=320),
                tooltip=folium.Tooltip(
                    f"<b>{local}</b><br>"
                    f"<span style='color:{cor_principal};font-weight:500;'>{label_principal}</span><br>"
                    f"<span style='font-size:0.75rem;color:#64748b;'>{qtd_secoes} seções aglomeradas</span>",
                    sticky=False,
                ),
                color=cor_principal,
                fill=True,
                fillColor=cor_principal,
                fillOpacity=0.85,
                weight=1.5,
            ).add_to(container_marcadores)

        # Pontos não críticos
        if gdf_nao_criticos is not None and not gdf_nao_criticos.empty:
            if agrupar_pontos:
                container_nc = MarkerCluster(
                    name="Seções Não Críticas", overlay=True, control=True,
                ).add_to(m)
            else:
                container_nc = folium.FeatureGroup(
                    name="Seções Não Críticas", overlay=True, control=True,
                ).add_to(m)

            cols_nc    = ["NR_LATITUDE", "NR_LONGITUDE", "NM_LOCAL_VOTACAO", "NM_MUNICIPIO"]
            grupos_nc  = gdf_nao_criticos.groupby(cols_nc)

            for (lat, lon, local, municipio), df_nc_local in grupos_nc:
                qtd_nc = len(df_nc_local)

                popup_nc_html = (
                    f'<div style="font-family:\'Inter\',sans-serif;min-width:200px;max-width:260px;">'
                    f'<div style="background:{_COR_NAO_CRITICO}18;border-left:3px solid {_COR_NAO_CRITICO};'
                    f'padding:8px 10px;border-radius:0 6px 6px 0;">'
                    f'<div style="font-size:0.9rem;font-weight:700;color:#0f172a;line-height:1.2;">{local}</div>'
                    f'<div style="font-size:0.75rem;color:#64748b;">'
                    f'{municipio} · <b>{qtd_nc}</b> seção(ões) sem atraso</div>'
                    f'</div></div>'
                )

                folium.CircleMarker(
                    location=[lat, lon],
                    radius=4,
                    popup=folium.Popup(popup_nc_html, max_width=260),
                    tooltip=folium.Tooltip(
                        f"<b>{local}</b><br>"
                        f"<span style='color:{_COR_NAO_CRITICO};font-weight:500;'>Sem Atraso</span><br>"
                        f"<span style='font-size:0.75rem;color:#64748b;'>{qtd_nc} seção(ões)</span>",
                        sticky=False,
                    ),
                    color=_COR_NAO_CRITICO,
                    fill=True,
                    fillColor=_COR_NAO_CRITICO,
                    fillOpacity=0.55,
                    weight=1.0,
                ).add_to(container_nc)

        folium.LayerControl(collapsed=True).add_to(m)

        # Guard JS
        map_var = m.get_name()
        guard_js = f"""
        <script>
        (function() {{
            var MIN_ZOOM = {SERGIPE_MIN_ZOOM};
            var CENTER   = [{SERGIPE_CENTER[0]}, {SERGIPE_CENTER[1]}];
            var DEF_ZOOM = {SERGIPE_ZOOM};
            var BOUNDS   = L.latLngBounds(
                L.latLng({SERGIPE_BOUNDS_SW[0]}, {SERGIPE_BOUNDS_SW[1]}),
                L.latLng({SERGIPE_BOUNDS_NE[0]}, {SERGIPE_BOUNDS_NE[1]})
            );
            function enforceZoom(map) {{
                if (map.getZoom() < MIN_ZOOM) map.setZoom(MIN_ZOOM);
            }}
            function enforceBoundsAndZoom(map) {{
                if (!map) return;
                map.setMaxBounds(BOUNDS);
                map.options.maxBoundsViscosity = 1.0;
                map.setMinZoom(MIN_ZOOM);
                enforceZoom(map);
                if (!BOUNDS.contains(map.getCenter())) {{
                    map.setView(CENTER, DEF_ZOOM);
                }}
            }}
            function waitForMap() {{
                var map = window['{map_var}'];
                if (map && map._leaflet_id) {{
                    enforceBoundsAndZoom(map);
                    map.on('load',      function() {{ enforceBoundsAndZoom(map); }});
                    map.on('zoomend',   function() {{ enforceZoom(map); }});
                    map.on('dragend',   function() {{ enforceBoundsAndZoom(map); }});
                    map.on('viewreset', function() {{ enforceBoundsAndZoom(map); }});
                }} else {{
                    setTimeout(waitForMap, 200);
                }}
            }}
            waitForMap();
        }})();
        </script>
        """
        m.get_root().html.add_child(Element(guard_js))

        # Renderizar o mapa
        st_folium(
            m,
            use_container_width=True,
            height=MAPA_ALTURA_PX,
            returned_objects=[],
            key=f"{ss_prefix}_folium",
        )

    del gdf_map, m
    gc.collect()
