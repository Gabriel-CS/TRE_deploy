from __future__ import annotations

import gc

import plotly.express as px
import streamlit as st

from src.analysis import OKABE_ITO, URN_MODELS
from src.charts import (
    apply_base_layout,
    bar_chart,
    bar_chart_horizontal,
    stacked_bar,
)


def render_tab_modelo(analise) -> None:
    """Renderiza o conteúdo completo da aba 'Análise por Modelo de Urna'."""

    _render_distribuicao(analise)
    _render_falhas_biometricas(analise)
    _render_inatividade(analise)
    _render_teclas_indevidas(analise)
    _render_escolaridade(analise)
    _render_faixa_etaria(analise)
    _render_pcd(analise)


# ──────────────────────────────────────────────────────────────────────────────
# Seções individuais
# ──────────────────────────────────────────────────────────────────────────────


def _build_resumo_table(
    col_headers: list[str],
    rows: list[tuple],
    title: str = "Resumo por Modelo",
) -> str:
    """
    Gera HTML de cards de resumo com mini barra de proporção.

    rows: lista de (cor_hex, model_name, v1_display, v2_display, v1_raw, v2_raw)
      - v1_raw / v2_raw são numéricos usados para calcular a barra (v1/v2 * 100%).
        Passe v1_raw=0 para ocultar a barra.
    """
    css = """
<style>
.rm-wrap{padding:4px 0;}
.rm-section-title{
  font-size:11px;font-weight:500;color:#888;
  text-transform:uppercase;letter-spacing:.06em;
  margin:0 0 8px;padding:0;
}
.rm-header{
  display:flex;align-items:center;
  padding:0 10px 5px;border-bottom:1px solid #e8e8e8;margin-bottom:4px;
}
.rm-hmodel{flex:1.4;font-size:10px;font-weight:500;color:#aaa;text-transform:uppercase;letter-spacing:.05em;}
.rm-hcol{flex:1;font-size:10px;font-weight:500;color:#aaa;text-align:center;text-transform:uppercase;letter-spacing:.05em;}
.rm-hcol.right{text-align:right;}
.rm-row{
  display:flex;align-items:center;
  padding:7px 10px;border-radius:8px;margin-bottom:3px;
  background:#f9f9fb;border:.5px solid #ebebef;gap:0;
  transition:background .15s;
}
.rm-row:hover{background:#fff;border-color:#d5d5e0;}
.rm-model{display:flex;align-items:center;gap:8px;flex:1.4;min-width:0;}
.rm-dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;}
.rm-name{font-size:12.5px;font-weight:500;color:#222;}
.rm-col{flex:1;display:flex;flex-direction:column;align-items:center;gap:1px;}
.rm-col.right{align-items:flex-end;}
.rm-val{font-size:12.5px;font-weight:500;color:#1a1a1a;}
.rm-sub{font-size:10px;color:#aaa;letter-spacing:.02em;}
.rm-bar-track{width:100%;height:3px;background:#e4e4ea;border-radius:99px;margin-top:3px;overflow:hidden;}
.rm-bar-fill{height:3px;border-radius:99px;}
</style>
"""
    # cabeçalho
    h1, h2 = col_headers[1], col_headers[2]
    header = (
        f'<div class="rm-header">'
        f'<div class="rm-hmodel">{col_headers[0]}</div>'
        f'<div class="rm-hcol">{h1}</div>'
        f'<div class="rm-hcol right">{h2}</div>'
        f'</div>'
    )

    # calcula max de v1_raw para normalizar barras
    raws = [r[4] for r in rows if len(r) > 4]
    max_raw = max(raws) if raws else 1
    if max_raw == 0:
        max_raw = 1

    cards = ""
    for row in rows:
        cor, model, v1_disp, v2_disp = row[0], row[1], row[2], row[3]
        v1_raw = row[4] if len(row) > 4 else 0
        v2_raw = row[5] if len(row) > 5 else 0

        pct = min(v1_raw / max_raw * 100, 100) if max_raw else 0
        bar_html = (
            f'<div class="rm-bar-track">'
            f'<div class="rm-bar-fill" style="width:{pct:.1f}%;background:{cor};"></div>'
            f'</div>'
        ) if v1_raw > 0 else ""

        total_label = f'<span class="rm-sub">do total</span>' if v2_raw else ""

        cards += (
            f'<div class="rm-row">'
            f'<div class="rm-model">'
            f'  <span class="rm-dot" style="background:{cor};"></span>'
            f'  <span class="rm-name">{model}</span>'
            f'</div>'
            f'<div class="rm-col">'
            f'  <span class="rm-val">{v1_disp}</span>'
            f'  {bar_html}'
            f'</div>'
            f'<div class="rm-col right">'
            f'  {total_label}'
            f'  <span class="rm-val">{v2_disp}</span>'
            f'</div>'
            f'</div>'
        )

    title_html = (
        f'<p class="rm-section-title">{title}</p>'
        if title else ""
    )
    return f'{css}<div class="rm-wrap">{title_html}{header}{cards}</div>'



def _render_distribuicao(analise) -> None:
    st.markdown("""
        <div class="section-header"><h2>Distribuição de Modelos</h2></div>
        <div class="section-desc">Proporção e quantidade absoluta de seções por modelo de urna.</div>
    """, unsafe_allow_html=True)

    dist = analise.get_model_distribution()
    col1, col2 = st.columns(2)

    with col1:
        fig = bar_chart(
            URN_MODELS, dist["proportions"],
            text=[f"{v*100:.1f}%" for v in dist["proportions"]],
            title="Proporção de Urnas por Modelo", yfmt=".0%", yrange=[0, 1.0],
        )
        st.plotly_chart(fig, use_container_width=True)
        del fig

    with col2:
        fig = bar_chart(
            URN_MODELS, dist["counts"],
            text=[f"{v:,}" for v in dist["counts"]],
            title="Total de Seções por Modelo",
            yrange=[0, max(dist["counts"]) * 1.25 or 1],
        )
        st.plotly_chart(fig, use_container_width=True)
        del fig

    del dist
    gc.collect()


def _render_falhas_biometricas(analise) -> None:
    st.markdown("""
        <div class="section-header"><h2>Falhas Biométricas na Pré-Habilitação</h2></div>
        <div class="section-desc">Proporção de votantes com falha biométrica, entre os que tiveram biometria solicitada.</div>
    """, unsafe_allow_html=True)

    bio = analise.get_bio_failure_rates()
    col_bio1, col_bio2 = st.columns([3, 1])

    with col_bio1:
        fig = bar_chart(
            URN_MODELS, bio["rates"],
            text=[f"{v*100:.1f}%" for v in bio["rates"]],
            title="Falha Biométrica por Modelo", yfmt=".0%", yrange=[0, 1.0],
        )
        st.plotly_chart(fig, use_container_width=True)
        del fig

    with col_bio2:
        _rows = []
        for i, m in enumerate(URN_MODELS):
            vm = analise.voters[m]
            bio_m = vm[vm["bio_solicitada"] == True]
            n_sol = len(bio_m)
            falhas = int((bio_m["n_falhas_bio"] > 0).sum())
            _rows.append((OKABE_ITO[i], m, f"{n_sol:,}", f"{falhas:,}", n_sol, falhas))
            del vm, bio_m
        st.markdown(
            _build_resumo_table(["Modelo", "Solicitada", "Falhas"], _rows, title="Resumo por Modelo"),
            unsafe_allow_html=True,
        )

    del bio
    gc.collect()


def _render_inatividade(analise) -> None:
    st.markdown("""
        <div class="section-header"><h2>Tempo de Inatividade durante a Seção</h2></div>
        <div class="section-desc">Média e desvio padrão do tempo de inatividade no processo de votação (excluindo zeros).</div>
    """, unsafe_allow_html=True)

    inat = analise.get_inactivity_times()
    fig = bar_chart_horizontal(
        URN_MODELS, inat["means"],
        text=[f"{m:.1f}s (±{s:.1f})" for m, s in zip(inat["means"], inat["stds"])],
        title="Tempo de Inatividade (média ± DP)",
        xrange=[0, max(m + s for m, s in zip(inat["means"], inat["stds"])) * 1.25 or 1],
    )
    st.plotly_chart(fig, use_container_width=True)
    del fig, inat
    gc.collect()


def _render_teclas_indevidas(analise) -> None:
    st.markdown("""
        <div class="section-header"><h2>Proporção de Teclas Indevidas</h2></div>
        <div class="section-desc">Parcela do total de teclas indevidas concentrada por modelo.</div>
    """, unsafe_allow_html=True)

    inv_keys = analise.get_invalid_keys()
    total_kp = analise.df_log["n_teclas_inv"].sum()
    col1, col2 = st.columns([3, 1])

    with col1:
        fig = bar_chart(
            URN_MODELS, inv_keys["proportions"],
            text=[f"{v*100:.1f}%" for v in inv_keys["proportions"]],
            title="Teclas Indevidas por Modelo", yfmt=".0%", yrange=[0, 1.0],
        )
        st.plotly_chart(fig, use_container_width=True)
        del fig

    with col2:
        _rows = []
        total_kp_int = int(total_kp)
        for i, m in enumerate(URN_MODELS):
            vm = analise.voters[m]
            qtd = int(vm[vm["n_teclas_inv"] > 0]["n_teclas_inv"].sum())
            _rows.append((OKABE_ITO[i], m, f"{qtd:,}", f"{total_kp_int:,}", qtd, total_kp_int))
            del vm
        st.markdown(
            _build_resumo_table(["Modelo", "Indevidas", "Total"], _rows, title="Resumo por Modelo"),
            unsafe_allow_html=True,
        )

    del inv_keys, total_kp
    gc.collect()


def _render_escolaridade(analise) -> None:
    st.markdown("""
        <div class="section-header"><h2>Escolaridade</h2></div>
        <div class="section-desc">Distribuição por grau de escolaridade e proporção de baixa escolaridade.</div>
    """, unsafe_allow_html=True)

    edu = analise.get_education_distribution()
    low_edu = analise.get_low_education()
    col1, col2 = st.columns(2)

    with col1:
        fig = stacked_bar(
            edu["df_proportions"], edu["labels"],
            px.colors.qualitative.Pastel,
            title="Distribuição por Escolaridade",
        )
        st.plotly_chart(fig, use_container_width=True)
        del fig

    with col2:
        fig = bar_chart(
            URN_MODELS, low_edu["proportions"],
            text=[f"{v*100:.1f}%" for v in low_edu["proportions"]],
            title="Baixa Escolaridade por Modelo", yfmt=".0%", yrange=[0, 1.0],
            x_categoryorder=URN_MODELS,
            height=420,
        )
        st.plotly_chart(fig, use_container_width=True)
        del fig

    del edu, low_edu
    gc.collect()


def _render_faixa_etaria(analise) -> None:
    st.markdown("""
        <div class="section-header"><h2>Faixa Etária</h2></div>
        <div class="section-desc">Distribuição etária e proporção de eleitores idosos (≥ 60 anos).</div>
    """, unsafe_allow_html=True)

    age = analise.get_age_distribution()
    elderly = analise.get_elderly_proportion()
    col1, col2 = st.columns(2)

    with col1:
        fig = stacked_bar(
            age["df_proportions"], age["groups"],
            px.colors.qualitative.Safe,
            title="Distribuição por Faixa Etária",
        )
        st.plotly_chart(fig, use_container_width=True)
        del fig

    with col2:
        fig = bar_chart(
            URN_MODELS, elderly["proportions"],
            text=[f"{v*100:.1f}%" for v in elderly["proportions"]],
            title="Eleitores Idosos (≥ 60 anos)", yfmt=".0%", yrange=[0, 1.0],
            x_categoryorder=URN_MODELS,
            height=420,
        )
        st.plotly_chart(fig, use_container_width=True)
        del fig

    del age, elderly
    gc.collect()


def _render_pcd(analise) -> None:
    st.markdown("""
        <div class="section-header"><h2>Eleitores PCD</h2></div>
        <div class="section-desc">Quantidade absoluta, taxa e relação com falhas biométricas.</div>
    """, unsafe_allow_html=True)

    pcd = analise.get_pcd_stats()
    col1, col2 = st.columns(2)

    with col1:
        fig = bar_chart(
            URN_MODELS, pcd["totals"],
            text=[f"{v:,}" for v in pcd["totals"]],
            title="Total de Eleitores PCD",
            yrange=[0, max(pcd["totals"]) * 1.25 or 1],
        )
        st.plotly_chart(fig, use_container_width=True)
        del fig

    with col2:
        fig = bar_chart(
            URN_MODELS, pcd["taxas"],
            text=[f"{v*100:.2f}%" for v in pcd["taxas"]],
            title="Taxa de Eleitores PCD", yfmt=".2%", yrange=[0, 1.0],
        )
        st.plotly_chart(fig, use_container_width=True)
        del fig

    del pcd
    gc.collect()