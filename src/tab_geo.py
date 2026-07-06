from __future__ import annotations

import gc
import html
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

from src.ui_components import info_card, section_header

from src.analysis import (
    FILTER_COM_ATRASO,
    FILTER_CONTINGENCIA,
    FILTER_SOMENTE_CRITICAS,
    STATUS_DETALHES,
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
SERGIPE_ZOOM: int = 7
SERGIPE_MIN_ZOOM: int = 7
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
    elif status_filter == FILTER_CONTINGENCIA:
        path_csv = f"data/data_map/df_locais_contingencia_{ano}.csv"
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
        veio_do_shard_dedicado = status_filter in (FILTER_SOMENTE_CRITICAS, FILTER_COM_ATRASO, FILTER_CONTINGENCIA)

        if status_filter == FILTER_SOMENTE_CRITICAS and not os.path.exists(path_csv):
            path_csv = f"data/data_map/df_locais_votacao_consolidado_somente_criticos_{ano}.csv"
        elif status_filter == FILTER_COM_ATRASO and not os.path.exists(path_csv):
            path_csv = f"data/data_map/df_locais_votacao_consolidado_com_atraso_{ano}.csv"

        if not os.path.exists(path_csv):
            path_csv = f"data/data_map/locais_criticos_{ano}.csv"
            veio_do_shard_dedicado = False

        try:
            df = pd.read_csv(path_csv)
        except FileNotFoundError:
            return None, f"Arquivo não encontrado: `{path_csv}`"
        except Exception as e:
            return None, f"Erro na leitura: {str(e)}"

        if isinstance(status_filter, int):
            df = df[df["STATUS"] == status_filter].copy()
        elif isinstance(status_filter, str) and not veio_do_shard_dedicado:
            # Só filtramos manualmente aqui quando o CSV carregado é o
            # consolidado (locais_criticos_{ano}.csv) — os shards dedicados
            # já vêm pré-filtrados pelo preprocess_geo.py.
            if status_filter == FILTER_SOMENTE_CRITICAS:
                df = df[df["STATUS"] > 2].copy()
            elif status_filter == FILTER_COM_ATRASO:
                df = df[df["STATUS"] > 1].copy()
            elif status_filter == FILTER_CONTINGENCIA:
                mask_conting = pd.Series(False, index=df.index)
                if "HOUVE_TROCA_POR_CONTINGENCIA" in df.columns:
                    mask_conting |= df["HOUVE_TROCA_POR_CONTINGENCIA"].fillna(False).astype(bool)
                if "EH_URNA_CONTINGENCIA" in df.columns:
                    mask_conting |= df["EH_URNA_CONTINGENCIA"].fillna(False).astype(bool)
                df = df[mask_conting].copy()

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


# ══════════════════════════════════════════════════════════════════════════════
# VORONOI — tesselação para visualizar áreas de influência dos locais
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS DE UI — cards, legendas e painéis
# ══════════════════════════════════════════════════════════════════════════════

def _kpi_card(cor: str, label: str, qtd: int, sublabel: str = "Locais de Votação") -> str:
    """Card de KPI compacto com borda superior colorida pelo status."""
    return (
        f'<div style="background:var(--color-surface);border:1px solid var(--color-border);'
        f'border-radius:var(--radius-card);padding:1.4rem 0.8rem;text-align:center;'
        f'box-shadow:var(--shadow-card);border-top:3px solid {cor};min-width:0;flex:1;'
        f'display:flex;flex-direction:column;justify-content:center;height:100%;">'
        f'<div style="font-size:0.62rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:{cor};margin-bottom:0.35rem;'
        f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{label}</div>'
        f'<div style="font-size:1.4rem;font-weight:800;color:var(--color-ink);line-height:1.1;">{qtd:,}</div>'
        f'<div style="font-size:0.62rem;color:var(--color-ink-muted);margin-top:0.25rem;">{sublabel}</div>'
        f'</div>'
    )


_LEGEND_CSS = """
<style>
.geo-legend-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 0.4rem 0 1.2rem 0;
    padding: 0.7rem 0.85rem;
    background: var(--color-surface-2, #f8fafc);
    border: 1px solid var(--color-border, #e2e8f0);
    border-radius: var(--radius-card, 12px);
}
.geo-legend-item {
    display: flex;
    align-items: center;
    gap: 7px;
    padding: 4px 10px;
    background: var(--color-surface, #ffffff);
    border-radius: 999px;
    border: 1px solid var(--color-border, #e2e8f0);
    font-size: 0.72rem;
    color: var(--color-ink-mid, #334155);
    line-height: 1.2;
    transition: transform 0.12s ease, box-shadow 0.12s ease;
}
.geo-legend-item:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 6px rgba(15,23,42,0.08);
}
.geo-legend-dot {
    width: 11px;
    height: 11px;
    border-radius: 50%;
    flex-shrink: 0;
    box-shadow: 0 0 0 2px rgba(255,255,255,0.9);
}
.geo-legend-label { font-weight: 700; color: var(--color-ink, #0f172a); }
.geo-legend-interval { color: var(--color-ink-muted, #94a3b8); font-size: 0.66rem; }
.geo-legend-nc { color: var(--color-ink-muted, #94a3b8); }
</style>
"""


def _render_status_legend() -> None:
    """
    Faixa horizontal sempre visível com os 5 níveis de criticidade + o estado
    'Sem Atraso' (não-críticos). Funciona como referência visual rápida para
    interpretar as cores dos pontos no mapa, sem precisar hover nem adivinhar
    pelo card de KPI.
    """
    items_html = ""
    for status in [0, 1, 2, 3, 4]:
        info = STATUS_DETALHES.get(status, {})
        cor = info.get("cor", _COR_STATUS.get(status, "#6c757d"))
        label = info.get("label", STATUS_LABELS.get(status, f"Nível {status}"))
        intervalo = info.get("intervalo", "")
        items_html += (
            f'<div class="geo-legend-item">'
            f'<span class="geo-legend-dot" style="background:{cor};"></span>'
            f'<span class="geo-legend-label">{html.escape(label)}</span>'
            f'<span class="geo-legend-interval">{html.escape(intervalo)}</span>'
            f'</div>'
        )

    # Item extra para pontos não-críticos quando exibidos
    items_html += (
        f'<div class="geo-legend-item geo-legend-nc">'
        f'<span class="geo-legend-dot" style="background:{_COR_NAO_CRITICO};"></span>'
        f'<span class="geo-legend-label">Não Crítico</span>'
        f'<span class="geo-legend-interval">pontos de referência</span>'
        f'</div>'
    )

    st.markdown(
        _LEGEND_CSS + f'<div class="geo-legend-wrap">{items_html}</div>',
        unsafe_allow_html=True,
    )


_PANEL_CSS = """
<style>
.geo-panel {
    background: var(--color-surface, #ffffff);
    border: 1px solid var(--color-border, #e2e8f0);
    border-radius: var(--radius-card, 12px);
    box-shadow: var(--shadow-card, 0 1px 4px rgba(15,23,42,0.05));
    padding: 0.9rem 1rem 0.6rem;
    height: 100%;
}
.geo-panel-title {
    font-size: 0.66rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    color: var(--color-brand, #0072B2);
    margin: 0 0 0.55rem 0;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid var(--color-border, #e2e8f0);
    display: flex;
    align-items: center;
    gap: 6px;
}
.geo-panel-title-icon { font-size: 0.85rem; }
</style>
"""


def _render_control_panel(
    ano: str,
    status_filter: str | int,
    gdf_geo: gpd.GeoDataFrame,
) -> dict | None:
    """
    Painel de controles dividido em duas colunas lógicas:
      1. Filtros de dados (status, municípios)
      2. Ajustes visuais do mapa (tema, agrupamento, voronoi)

    O filtro por nível de criticidade (antes restrito à visão de contingência
    via multiselect dedicado) agora é feito clicando diretamente nos cards de
    KPI abaixo — funciona para qualquer visão agregada, não só contingência.

    Retorna um dict com todos os valores selecionados, ou None se houve erro
    ao recarregar os dados para o novo status local.
    """
    st.markdown(_PANEL_CSS, unsafe_allow_html=True)

    col_filtros, col_ajustes = st.columns([1.5, 1.0])

    # ── Coluna 1: Filtros de dados ──────────────────────────────────────
    with col_filtros:
        st.markdown(
            '<div class="geo-panel">',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="geo-panel-title"><span class="geo-panel-title-icon">⚑</span>Filtros de dados</div>',
            unsafe_allow_html=True,
        )

        # Sync do status global → local
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
            st.markdown("</div>", unsafe_allow_html=True)
            return None

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

        # Dica contextual sobre o filtro por nível (agora feito via cards de KPI)
        if isinstance(status_filter_local, str):
            st.markdown(
                '<div style="font-size:0.7rem;color:var(--color-ink-muted);'
                'margin-top:0.4rem;padding:0.4rem 0.55rem;background:var(--color-surface-2,#f8fafc);'
                'border-radius:6px;border-left:2px solid var(--color-brand,#0072B2);">'
                '💡 Para filtrar por <b>nível de criticidade</b>, clique nos cards coloridos '
                'logo abaixo do mapa de controles.'
                '</div>',
                unsafe_allow_html=True,
            )

        st.markdown("</div>", unsafe_allow_html=True)

    # ── Coluna 2: Ajustes visuais do mapa ───────────────────────────────
    with col_ajustes:
        st.markdown(
            '<div class="geo-panel">',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="geo-panel-title"><span class="geo-panel-title-icon">⚙</span>Ajustes do mapa</div>',
            unsafe_allow_html=True,
        )

        estilo_mapa = st.selectbox(
            "Tema base",
            options=["Claro (Positron)", "Escuro (Dark Matter)", "Padrão (Voyager)", "OpenStreetMap"],
            index=0,
            help="Altera o provedor de estilo do mapa de fundo.",
        )

        agrupar_pontos = st.checkbox(
            "Agrupar locais próximos",
            value=True,
            help="Agrupa marcadores próximos em clusters. Facilita a visualização quando há muitos pontos.",
        )

        exibir_voronoi = st.checkbox(
            "Mostrar tesselação de Voronoi",
            value=False,
            key="_geo_voronoi_toggle",
            help="Desenha células de Voronoi ao redor de cada ponto, mostrando a área de influência "
                 "teórica de cada local de votação. Útil para identificar regiões com cobertura rarefeita.",
        )

        st.markdown("</div>", unsafe_allow_html=True)

    return {
        "status_filter_local": status_filter_local,
        "gdf_geo_status": gdf_geo_status,
        "selected_munis": selected_munis,
        "estilo_mapa": estilo_mapa,
        "agrupar_pontos": agrupar_pontos,
        "exibir_voronoi": exibir_voronoi,
    }


def _apply_muni_filter(
    gdf_geo_status: gpd.GeoDataFrame,
    selected_munis: list[str],
) -> gpd.GeoDataFrame:
    """
    Aplica apenas o filtro de municípios sobre o GeoDataFrame.

    O filtro por nível de criticidade NÃO é aplicado aqui — ele é controlado
    pelos cards de KPI clicáveis (função `_render_kpi_summary`) e aplicado
    depois, sobre o resultado desta função. Isso permite que os cards sempre
    mostrem o total por nível dentro da seleção de municípios, mesmo quando
    o usuário clica para filtrar apenas um nível específico no mapa.
    """
    mask = pd.Series(True, index=gdf_geo_status.index)
    if selected_munis:
        mask &= gdf_geo_status["NM_MUNICIPIO"].isin(selected_munis)
    return gdf_geo_status[mask].copy() if isinstance(mask, pd.Series) else gdf_geo_status


def _load_nao_criticos_if_needed(
    ano: str,
    status_filter_local: str | int,
    selected_munis: list[str],
) -> gpd.GeoDataFrame | None:
    """Carrega pontos não-críticos apenas quando o filtro local é nível 0."""
    if status_filter_local != 0:
        return None

    gdf_nc, erro_nc = carregar_dados_nao_criticos(ano)
    if erro_nc:
        st.warning(f"Pontos não críticos indisponíveis: {erro_nc}")
        return None

    if selected_munis:
        return gdf_nc[gdf_nc["NM_MUNICIPIO"].isin(selected_munis)].copy()
    return gdf_nc


_KPI_CARD_BTN_CSS = """
<style>
div.st-key-geo_kpi_cards button {
    font-size: 0.7rem !important;
    padding: 0.3rem 0.5rem !important;
    min-height: 30px !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    width: 100% !important;
    margin-top: -0.3rem !important;
    transition: all 0.15s ease !important;
}
div.st-key-geo_kpi_cards button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 3px 8px rgba(15,23,42,0.10) !important;
}
</style>
"""


def _render_kpi_summary(
    gdf_map: gpd.GeoDataFrame,
    status_filter_local: str | int,
) -> set[int] | None:
    """
    Renderiza os cards de KPI com cabeçalho contextualizando o total.

    Para visões agregadas (status string: 'Somente criticas', 'Com atraso',
    'Urnas em contingência'), os cards são <b>clicáveis</b> e funcionam como
    filtro por nível de criticidade: clique para ativar, clique novamente
    para remover. Seleção vazia = todos os níveis exibidos (padrão).

    Para visões de nível único (status int 0-4), apenas um card informativo
    é exibido, sem interação.

    Returns
    -------
    set[int] | None
        - None quando não há filtro por nível ativo (mostrar todos)
        - set de inteiros com os níveis selecionados quando o usuário
          clicou em algum card para restringir a visualização
    """
    total_secoes = len(gdf_map)

    # Conta locais únicos (vários registros podem compartilhar coordenadas)
    if {"NR_LATITUDE", "NR_LONGITUDE"}.issubset(gdf_map.columns):
        locais_unicos = gdf_map[["NR_LATITUDE", "NR_LONGITUDE"]].drop_duplicates().shape[0]
    else:
        locais_unicos = total_secoes

    st.markdown(
        f'<div style="display:flex;align-items:baseline;gap:10px;margin:0.2rem 0 0.6rem 0;">'
        f'<span style="font-size:0.7rem;font-weight:800;text-transform:uppercase;'
        f'letter-spacing:0.08em;color:var(--color-ink-soft);">Resumo da seleção</span>'
        f'<span style="font-size:0.78rem;color:var(--color-ink-mid);">'
        f'<b style="color:var(--color-ink);">{total_secoes:,}</b> seções em '
        f'<b style="color:var(--color-ink);">{locais_unicos:,}</b> locais de votação'
        f'</span></div>',
        unsafe_allow_html=True,
    )

    # ── Visão de nível único (int): card único, sem interação ────────────
    if isinstance(status_filter_local, int):
        cor = _COR_STATUS.get(int(status_filter_local), "#6c757d")
        label = STATUS_LABELS.get(int(status_filter_local), f"Nível {status_filter_local}")
        qtd = len(gdf_map)
        st.markdown(
            f'<div style="display:flex;gap:6px;">{_kpi_card(cor, label, qtd)}</div>',
            unsafe_allow_html=True,
        )
        return None

    # ── Visão agregada (string): cards clicáveis por nível ───────────────
    counts = gdf_map["STATUS"].value_counts().sort_index()
    available_levels = set(int(s) for s in counts.index)

    # Reset da seleção quando o status_filter_local muda — os níveis
    # disponíveis mudam, então uma seleção antiga poderia apontar para
    # níveis que não existem mais na nova visão.
    prev_status = st.session_state.get("_geo_prev_status_for_levels")
    if prev_status != status_filter_local:
        st.session_state["_geo_prev_status_for_levels"] = status_filter_local
        st.session_state["_geo_selected_levels"] = []

    selected_levels: list[int] = st.session_state.setdefault("_geo_selected_levels", [])
    # Limpa níveis que sumiram (ex.: município selecionado não tem aquele nível)
    selected_levels = [s for s in selected_levels if s in available_levels]
    st.session_state["_geo_selected_levels"] = selected_levels

    # Texto de ajuda contextual
    if selected_levels:
        nomes = ", ".join(STATUS_LABELS.get(s, f"N{s}") for s in selected_levels)
        hint = (
            f'Filtrando por: <b style="color:var(--color-brand,#0072B2);">{nomes}</b>. '
            f'Clique em um card ativo para remover o filtro.'
        )
    else:
        hint = (
            'Clique em um card para filtrar apenas aquele nível de criticidade. '
            'Clique em vários para combinar.'
        )
    st.markdown(
        f'<div style="font-size:0.72rem;color:var(--color-ink-muted);margin-bottom:0.55rem;">{hint}</div>',
        unsafe_allow_html=True,
    )

    # CSS para os botões de toggle abaixo de cada card
    st.markdown(_KPI_CARD_BTN_CSS, unsafe_allow_html=True)

    with st.container(key="geo_kpi_cards"):
        cols = st.columns(len(counts))
        for i, (status_val, qtd) in enumerate(counts.items()):
            status_val = int(status_val)
            cor = _COR_STATUS.get(status_val, "#6c757d")
            label = STATUS_LABELS.get(status_val, f"Nível {status_val}")
            # Quando selected_levels está vazio, todos os cards estão ativos
            is_active = status_val in selected_levels if selected_levels else True

            with cols[i]:
                # ── Card visual (ativo/inativo) ────────────────────────────
                opacity = "1.0" if is_active else "0.4"
                filter_css = "none" if is_active else "grayscale(0.6)"
                glow = f"box-shadow:0 0 0 2px {cor}40, var(--shadow-card);" if is_active else "box-shadow:var(--shadow-card);"
                checkmark = '<span style="color:#16a34a;font-weight:800;">✓ </span>' if is_active else ''

                st.markdown(
                    f'<div style="background:var(--color-surface);border:1px solid var(--color-border);'
                    f'border-radius:var(--radius-card);padding:1.1rem 0.6rem;text-align:center;'
                    f'{glow}border-top:3px solid {cor};min-width:0;'
                    f'opacity:{opacity};filter:{filter_css};transition:all 0.2s;'
                    f'margin-bottom:0.3rem;">'
                    f'<div style="font-size:0.6rem;font-weight:700;text-transform:uppercase;'
                    f'letter-spacing:0.08em;color:{cor};margin-bottom:0.3rem;white-space:nowrap;'
                    f'overflow:hidden;text-overflow:ellipsis;">{checkmark}{label}</div>'
                    f'<div style="font-size:1.3rem;font-weight:800;color:var(--color-ink);line-height:1.1;">{qtd:,}</div>'
                    f'<div style="font-size:0.6rem;color:var(--color-ink-muted);margin-top:0.2rem;">Locais</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # ── Botão funcional de toggle ─────────────────────────────
                # O card HTML é só visual; o botão Streamlit abaixo é que
                # captura o clique, atualiza o session_state e dispara o rerun.
                btn_label = "✓ Ativo" if is_active else "+ Filtrar"
                if st.button(
                    btn_label,
                    key=f"_geo_card_btn_{status_val}",
                    use_container_width=True,
                    help=f"Clique para {'remover' if is_active else 'adicionar'} o filtro de {label}",
                ):
                    if status_val in selected_levels:
                        selected_levels.remove(status_val)
                    else:
                        selected_levels.append(status_val)
                    st.session_state["_geo_selected_levels"] = selected_levels
                    st.rerun()

    # Retorna o conjunto de níveis para filtrar, ou None para mostrar todos
    return set(selected_levels) if selected_levels else None


# ══════════════════════════════════════════════════════════════════════════════
# MAPA — renderização principal
# ══════════════════════════════════════════════════════════════════════════════

def _build_popup_html(
    local: str,
    municipio: str,
    cor_principal: str,
    qtd_secoes: int,
    status_maximo: int,
    selo_conting: str,
    itens_secoes_html: str,
) -> str:
    """Constrói o HTML do popup de um local de votação no mapa."""
    texto_secoes = "seções com atraso" if status_maximo > 1 else "seções sem atraso"
    return f"""
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


def _build_section_cards_html(df_local: pd.DataFrame, cols_lista: list[str]) -> str:
    """Gera a lista de cards individuais (uma por seção/urna) dentro do popup."""
    if not {"NR_ZONA", "NR_SECAO"}.issubset(cols_lista):
        return ""

    df_local_sorted = df_local.sort_values("STATUS", ascending=False)
    tem_modelo = "modelo" in cols_lista
    tem_atraso = "ATRASO_FILA_MINUTOS" in cols_lista
    tem_conting = ("HOUVE_TROCA_POR_CONTINGENCIA" in cols_lista) or ("EH_URNA_CONTINGENCIA" in cols_lista)
    tem_t_voto = "TEMPO_SECAO_PRIMEIRO_ULTIMO_VOTO_SEG" in cols_lista

    cards = []
    for _, row in df_local_sorted.iterrows():
        st_row = int(row["STATUS"])
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
            eh_conting = bool(row.get("EH_URNA_CONTINGENCIA", False))
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

    return (
        '<div style="max-height:220px;overflow-y:auto;margin-top:6px;'
        'padding-top:4px;border-top:1px dashed #e2e8f0;">'
        + "".join(cards) +
        '</div>'
    )


def _add_critical_markers(
    m: folium.Map,
    gdf_map: gpd.GeoDataFrame,
    agrupar_pontos: bool,
) -> None:
    """Adiciona os CircleMarkers dos locais críticos (com cluster opcional)."""
    if agrupar_pontos:
        container_marcadores = MarkerCluster(name="Locais Votação", overlay=True, control=False).add_to(m)
    else:
        container_marcadores = folium.FeatureGroup(name="Locais Votação", overlay=True, control=False).add_to(m)

    gdf_sorted = gdf_map.sort_values(by="STATUS", ascending=False)
    cols_agrupamento = ["NR_LATITUDE", "NR_LONGITUDE", "NM_LOCAL_VOTACAO", "NM_MUNICIPIO"]
    grupos_locais = gdf_sorted.groupby(cols_agrupamento)

    cols_lista = [
        c for c in [
            "NR_ZONA", "NR_SECAO", "STATUS", "modelo", "ATRASO_FILA_MINUTOS",
            "HOUVE_TROCA_POR_CONTINGENCIA", "EH_URNA_CONTINGENCIA",
            "TEMPO_SECAO_PRIMEIRO_ULTIMO_VOTO_SEG",
        ] if c in gdf_sorted.columns
    ]

    for (lat, lon, local, municipio), df_local in grupos_locais:
        status_maximo = int(df_local["STATUS"].max())
        cor_principal = _COR_STATUS.get(status_maximo, "#6c757d")
        label_principal = STATUS_LABELS.get(status_maximo, f"Status {status_maximo}")
        qtd_secoes = len(df_local)

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

        itens_secoes_html = _build_section_cards_html(df_local, cols_lista)

        popup_html = _build_popup_html(
            local, municipio, cor_principal, qtd_secoes,
            status_maximo, selo_conting, itens_secoes_html,
        )

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


def _add_non_critical_markers(
    m: folium.Map,
    gdf_nao_criticos: gpd.GeoDataFrame,
    agrupar_pontos: bool,
) -> None:
    """Adiciona os CircleMarkers cinzas dos pontos não-críticos (referência)."""
    if gdf_nao_criticos is None or gdf_nao_criticos.empty:
        return

    if agrupar_pontos:
        container_nc = MarkerCluster(
            name="Seções Não Críticas", overlay=True, control=True,
        ).add_to(m)
    else:
        container_nc = folium.FeatureGroup(
            name="Seções Não Críticas", overlay=True, control=True,
        ).add_to(m)

    cols_nc = ["NR_LATITUDE", "NR_LONGITUDE", "NM_LOCAL_VOTACAO", "NM_MUNICIPIO"]
    grupos_nc = gdf_nao_criticos.groupby(cols_nc)

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


def _inject_bounds_guard(m: folium.Map) -> None:
    """
    Injeta JavaScript que impede o usuário de arrastar/zoomar para fora dos
    limites de Sergipe. Sem isso, o mapa podia ser arrastado para o oceano
    ou reduzido a um zoom que mostra todo o Brasil.
    """
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


def _render_map(
    ano: str,
    status_filter: str | int,
    gdf_map: gpd.GeoDataFrame,
    gdf_nao_criticos: gpd.GeoDataFrame | None,
    estilo_mapa: str,
    agrupar_pontos: bool,
    exibir_voronoi: bool,
) -> None:
    """Monta e renderiza o mapa Folium com todos os layers configurados."""
    # Prefixo usado como key do componente folium (único por ano+status)
    ss_prefix = f"geo_{ano}_{status_filter}"

    info_card(
        "Cada ponto no mapa representa um local de votação (vários pontos podem "
        "aglomerar seções da mesma zona). A cor indica o nível de criticidade "
        "do atraso no encerramento. Clique em um ponto para ver a lista de "
        "seções individualmente com modelo de urna, atraso e tempo de votação."
    )

    dicionario_tiles = {
        "Claro (Positron)":    "CartoDB positron",
        "Escuro (Dark Matter)": "CartoDB dark_matter",
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
    m.options["maxBounds"] = bounds
    m.options["maxBoundsViscosity"] = 1.0
    m.options["minZoom"] = SERGIPE_MIN_ZOOM

    # ── Camada base: municípios de Sergipe ──────────────────────────────
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

    # ── Camada Voronoi (opcional) ───────────────────────────────────────
    if exibir_voronoi and geojson_se:
        if len(gdf_map) < 4:
            st.warning("São necessários ao menos 4 pontos para a tesselação de Voronoi.")
        else:
            with st.spinner("Calculando tesselação de Voronoi…"):
                grupo_vor = _gerar_voronoi_layer(gdf_map, geojson_se)
            if grupo_vor is not None:
                grupo_vor.add_to(m)

    # ── Camada de marcadores críticos ───────────────────────────────────
    _add_critical_markers(m, gdf_map, agrupar_pontos)

    # ── Camada de marcadores não-críticos (referência) ──────────────────
    _add_non_critical_markers(m, gdf_nao_criticos, agrupar_pontos)

    folium.LayerControl(collapsed=True).add_to(m)

    # ── Guard JS para limites/zoom ──────────────────────────────────────
    _inject_bounds_guard(m)

    # ── Renderização final ──────────────────────────────────────────────
    st_folium(
        m,
        use_container_width=True,
        height=MAPA_ALTURA_PX,
        returned_objects=[],
        key=f"{ss_prefix}_folium",
    )

    del m
    gc.collect()


# ══════════════════════════════════════════════════════════════════════════════
# DICAS DE USO — rodapé explicativo
# ══════════════════════════════════════════════════════════════════════════════

def _render_helper_tips(exibir_voronoi: bool, agrupar_pontos: bool) -> None:
    """Pequeno bloco de dicas abaixo do mapa, ajudando o usuário a explorar."""
    dicas = [
        "<b>Clique nos pontos</b> para ver a lista de seções com modelo de urna, atraso e tempo de votação.",
        "<b>Use o filtro de municípios</b> para focar em uma região específica do estado.",
    ]
    if agrupar_pontos:
        dicas.append(
            "<b>Agrupamento ativado</b>: pontos próximos são reunidos em clusters. "
            "Aproxime o zoom para expandi-los individualmente."
        )
    else:
        dicas.append(
            "<b>Agrupamento desativado</b>: todos os pontos aparecem individuais. "
            "Pode ser mais lento em grandes volumes."
        )
    if exibir_voronoi:
        dicas.append(
            "<b>Voronoi ativado</b>: as células coloridas mostram a área de influência "
            "teórica de cada local — útil para identificar regiões com cobertura rarefeita."
        )

    dicas_html = "".join(
        f'<li style="margin-bottom:4px;">{d}</li>' for d in dicas
    )
    st.markdown(
        f"""
        <div style="margin-top:0.8rem;padding:0.8rem 1rem;background:var(--color-surface-2,#f8fafc);
                    border:1px solid var(--color-border,#e2e8f0);border-radius:var(--radius-card,12px);">
            <div style="font-size:0.7rem;font-weight:800;text-transform:uppercase;
                        letter-spacing:0.08em;color:var(--color-brand,#0072B2);margin-bottom:0.45rem;">
                💡 Dicas de uso
            </div>
            <ul style="margin:0;padding-left:1.1rem;font-size:0.78rem;color:var(--color-ink-mid,#334155);
                       line-height:1.5;">{dicas_html}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# ORQUESTRADOR — ponto de entrada da aba
# ══════════════════════════════════════════════════════════════════════════════

def render_tab_geo(ano: str, status_filter: str | int, estado_means: dict | None = None) -> None:
    # ── 1. Cabeçalho ──────────────────────────────────────────────────────
    st.markdown(
        section_header(
            "Distribuição Geoespacial dos Locais Críticos",
            f"Mapa interativo de Sergipe mostrando a localização das seções "
            f"eleitorais coloridas por nível de criticidade (atraso no encerramento). "
            f"Cada ponto agrega as seções de um mesmo local de votação — {ano}.",
        ),
        unsafe_allow_html=True,
    )

    # ── 2. Carregar dados iniciais ────────────────────────────────────────
    gdf_geo, erro_geo = carregar_dados_geograficos(ano, status_filter)
    if erro_geo:
        st.warning(f"Dados geográficos indisponíveis: {erro_geo}")
        return

    # ── 3. Legenda de status (sempre visível) ─────────────────────────────
    _render_status_legend()

    # ── 4. Painel de controles ────────────────────────────────────────────
    controles = _render_control_panel(ano, status_filter, gdf_geo)
    if controles is None:
        return  # erro já exibido dentro do painel

    status_filter_local = controles["status_filter_local"]
    gdf_geo_status = controles["gdf_geo_status"]
    selected_munis = controles["selected_munis"]
    estilo_mapa = controles["estilo_mapa"]
    agrupar_pontos = controles["agrupar_pontos"]
    exibir_voronoi = controles["exibir_voronoi"]

    # ── 5. Aplicar filtro de município ────────────────────────────────────
    # O filtro por nível de criticidade NÃO é aplicado aqui — ele é definido
    # pelos cards de KPI clicáveis abaixo e aplicado depois, sobre o resultado
    # desta função. Assim, os cards sempre mostram o total por nível dentro
    # da seleção de municípios, mesmo quando o usuário filtra só um nível.
    gdf_map_all = _apply_muni_filter(gdf_geo_status, selected_munis)
    if gdf_map_all.empty:
        st.info("Nenhum ponto corresponde aos filtros selecionados.")
        return

    # ── 6. Carregar pontos não-críticos (apenas para nível 0) ─────────────
    gdf_nao_criticos = _load_nao_criticos_if_needed(ano, status_filter_local, selected_munis)

    # ── 7. Resumo de KPIs clicáveis (define o filtro por nível) ───────────
    selected_levels = _render_kpi_summary(gdf_map_all, status_filter_local)

    # ── 8. Aplicar filtro de nível (se algum card foi clicado) ────────────
    if selected_levels is not None:
        gdf_map = gdf_map_all[gdf_map_all["STATUS"].isin(selected_levels)].copy()
        if gdf_map.empty:
            st.info("Nenhum local de votação com o nível selecionado. Clique novamente no card para voltar.")
            return
    else:
        gdf_map = gdf_map_all

    st.markdown("<div style='height:0.9rem;'></div>", unsafe_allow_html=True)

    # ── 9. Mapa ───────────────────────────────────────────────────────────
    _render_map(
        ano, status_filter, gdf_map, gdf_nao_criticos,
        estilo_mapa, agrupar_pontos, exibir_voronoi,
    )

    # ── 9. Dicas de uso ───────────────────────────────────────────────────
    #_render_helper_tips(exibir_voronoi, agrupar_pontos)

    # ── Limpeza de memória ────────────────────────────────────────────────
    del gdf_map
    if gdf_nao_criticos is not None:
        del gdf_nao_criticos
    gc.collect()
