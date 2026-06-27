# tab_criticidade.py
from __future__ import annotations

import gc

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analysis import OKABE_ITO, STATUS_LABELS, STATUS_PALETTE
from src.charts import apply_base_layout


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_min_sec(total_seconds: float) -> str:
    """Formata segundos totais em minutos e segundos (~XmYs)."""
    if pd.isna(total_seconds) or total_seconds <= 0:
        return "~0s"
    m = int(total_seconds) // 60
    s = int(total_seconds) % 60
    if m > 0:
        return f"~{m}m{s}s"
    return f"~{s}s"


# ──────────────────────────────────────────────────────────────────────────────
# Renderização da aba
# ──────────────────────────────────────────────────────────────────────────────

def render_tab_criticidade(
    df_secoes: pd.DataFrame | None,
    status_filter,
    estado_means: dict | None = None,
) -> None:
    """Renderiza o conteúdo completo da aba 'Análise por Criticidade'."""
    if df_secoes is None or df_secoes.empty:
        st.error("Dados de seções não disponíveis para este filtro.")
        return

    # CORREÇÃO: filtros agregados (strings) e None roteiam para visão geral
    if status_filter is None or status_filter == "Todas" or isinstance(status_filter, str):
        _render_visao_geral(df_secoes)
    elif status_filter in [0, 1, 2, 3]:
        _render_detalhamento_nivel(df_secoes, status_filter, estado_means or {})
    elif status_filter == 4:
        _render_nivel4(df_secoes, estado_means or {})
    else:
        # Fallback de segurança
        _render_visao_geral(df_secoes)


# ──────────────────────────────────────────────────────────────────────────────
# Visão 1 — Comparação entre todos os níveis
# ──────────────────────────────────────────────────────────────────────────────

def _render_visao_geral(df: pd.DataFrame) -> None:
    st.markdown("""
        <div class="section-header"><h2>Visão por Nível de Criticidade</h2></div>
        <div class="section-desc">Métricas operacionais comparadas entre todos os níveis de criticidade.</div>
    """, unsafe_allow_html=True)

    col_v1, col_v2 = st.columns(2)

    with col_v1:
        st.markdown(
            "<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>"
            "Média de Timeout de Biometria</h4>",
            unsafe_allow_html=True,
        )
        if "TIMEOUT_BIOMETRIA" not in df.columns:
            st.info("Coluna TIMEOUT_BIOMETRIA não disponível.")
        else:
            m_timeout = df.groupby("STATUS")["TIMEOUT_BIOMETRIA"].mean().dropna()
            if m_timeout.empty:
                st.info("Nenhum dado de timeout disponível para os status selecionados.")
            else:
                if "TPBSEC" in df.columns:
                    m_tempo = df.groupby("STATUS")["TPBSEC"].mean().dropna()
                    m_tempo = m_tempo.reindex(m_timeout.index)
                    text_timeout = [
                        f"{v:.1f} ocorr. {_fmt_min_sec(t)}"
                        for v, t in zip(m_timeout.values, m_tempo.values)
                    ]
                    del m_tempo
                else:
                    text_timeout = [f"{v:.1f} ocorr." for v in m_timeout.values]

                y_labels = [STATUS_LABELS.get(int(s), f"Nível {int(s)}") for s in m_timeout.index]
                fig = go.Figure(go.Bar(
                    x=m_timeout.values,
                    y=y_labels,
                    orientation="h",
                    marker_color=[STATUS_PALETTE.get(int(s), "#6c757d") for s in m_timeout.index],
                    text=text_timeout,
                    textposition="outside",
                ))
                fig = apply_base_layout(fig, height=350)
                fig.update_layout(
                    yaxis=dict(
                        type="category",
                        tickfont=dict(color="black", size=13),
                        categoryorder="total ascending",
                        automargin=True,
                    ),
                    xaxis=dict(automargin=True),
                )
                st.plotly_chart(fig, use_container_width=True)
                del m_timeout, fig

    with col_v2:
        st.markdown(
            "<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>"
            "Média de Inatividade do Eleitor</h4>",
            unsafe_allow_html=True,
        )
        if "INATIVIDADE" not in df.columns:
            st.info("Coluna INATIVIDADE não disponível.")
        else:
            m_inat = df.groupby("STATUS")["INATIVIDADE"].mean().dropna()
            if m_inat.empty:
                st.info("Nenhum dado de inatividade disponível para os status selecionados.")
            else:
                if "TTPISEC" in df.columns:
                    m_t_inat = df.groupby("STATUS")["TTPISEC"].mean().dropna()
                    m_t_inat = m_t_inat.reindex(m_inat.index)
                    text_inat = [
                        f"{v:.1f} ocorr. {_fmt_min_sec(t)}"
                        for v, t in zip(m_inat.values, m_t_inat.values)
                    ]
                    del m_t_inat
                else:
                    text_inat = [f"{v:.1f} ocorr." for v in m_inat.values]

                y_labels = [STATUS_LABELS.get(int(s), f"Nível {int(s)}") for s in m_inat.index]
                fig = go.Figure(go.Bar(
                    x=m_inat.values,
                    y=y_labels,
                    orientation="h",
                    marker_color=[STATUS_PALETTE.get(int(s), "#6c757d") for s in m_inat.index],
                    text=text_inat,
                    textposition="outside",
                ))
                fig = apply_base_layout(fig, height=350)
                fig.update_layout(
                    yaxis=dict(
                        type="category",
                        tickfont=dict(color="black", size=13),
                        categoryorder="total ascending",
                        automargin=True,
                    ),
                    xaxis=dict(automargin=True),
                )
                st.plotly_chart(fig, use_container_width=True)
                del m_inat, fig

    col_p1, col_p2 = st.columns(2)

    with col_p1:
        st.markdown(
            "<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>"
            "Distribuição de PCDs por Status</h4>",
            unsafe_allow_html=True,
        )
        if "QTD_PCD" not in df.columns:
            st.info("Coluna QTD_PCD não disponível.")
        else:
            pcd_sum = df.groupby("STATUS")["QTD_PCD"].sum().dropna()
            if pcd_sum.empty:
                st.info("Nenhum dado de PCD disponível.")
            else:
                fig = go.Figure(go.Pie(
                    labels=[STATUS_LABELS.get(int(s), f"Nível {int(s)}") for s in pcd_sum.index],
                    values=pcd_sum.values,
                    hole=0.45,
                    marker=dict(colors=[STATUS_PALETTE.get(int(s), "#6c757d") for s in pcd_sum.index]),
                ))
                st.plotly_chart(apply_base_layout(fig, height=350), use_container_width=True)
                del pcd_sum, fig

    with col_p2:
        st.markdown(
            "<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>"
            "Média de Teclas Indevidas</h4>",
            unsafe_allow_html=True,
        )
        if "TECLA_INDEVIDA" not in df.columns:
            st.info("Coluna TECLA_INDEVIDA não disponível.")
        else:
            m_teclas = df.groupby("STATUS")["TECLA_INDEVIDA"].mean().dropna()
            if m_teclas.empty:
                st.info("Nenhum dado de teclas indevidas disponível.")
            else:
                y_labels = [STATUS_LABELS.get(int(s), f"Nível {int(s)}") for s in m_teclas.index]
                # PADRONIZADO: cada erro = 1 s de atraso, formatado em min e seg
                text_teclas = [
                    f"{v:.2f} ocorr.<br>{_fmt_min_sec(v)}"
                    for v in m_teclas.values
                ]
                fig = go.Figure(go.Bar(
                    x=m_teclas.values,
                    y=y_labels,
                    orientation="h",
                    marker_color=[STATUS_PALETTE.get(int(s), "#6c757d") for s in m_teclas.index],
                    text=text_teclas,
                    textposition="outside",
                ))
                fig = apply_base_layout(fig, height=350)
                fig.update_layout(
                    yaxis=dict(
                        type="category",
                        tickfont=dict(color="black", size=13),
                        automargin=True,
                    ),
                    xaxis=dict(automargin=True),
                )
                st.plotly_chart(fig, use_container_width=True)
                del m_teclas, fig

    gc.collect()


# ──────────────────────────────────────────────────────────────────────────────
# Visão 2 — Diagnóstico detalhado de um nível específico (0–3)
# ──────────────────────────────────────────────────────────────────────────────

def _render_detalhamento_nivel(
    df: pd.DataFrame,
    status_filter: int,
    estado_means: dict,
) -> None:
    st.markdown("""
        <div class="section-header"><h2>Diagnóstico Detalhado por Nível</h2></div>
        <div class="section-desc">Análise comparativa do nível selecionado contra a média estadual (todas as seções críticas).</div>
    """, unsafe_allow_html=True)

    titulo = f"Detalhamento: {STATUS_LABELS.get(status_filter, f'Nível {status_filter}')}"
    st.markdown(
        f"<h3 style='color: #1a3a5c; font-weight: 600; margin-bottom: 1rem;'>{titulo}</h3>",
        unsafe_allow_html=True,
    )

    # ── KPIs com delta vs média estadual ─────────────────────────────────────
    def _get_metrics(col_ocorr: str, col_tempo: str | None = None):
        m_niv = df[col_ocorr].mean() if col_ocorr in df.columns else 0
        m_est = estado_means.get(col_ocorr, m_niv)
        delta = ((m_niv / m_est) - 1) * 100 if m_est > 0 else 0
        tempo_str = ""
        if col_tempo and col_tempo in df.columns:
            seg = df[col_tempo].mean()
            if pd.notna(seg):
                tempo_str = f"Tempo total: {_fmt_min_sec(seg)}"
        return m_niv, delta, tempo_str

    col_k1, col_k2, col_k3 = st.columns(3)

    v, d, t = _get_metrics("INATIVIDADE", "TTPISEC")
    with col_k1:
        st.metric("Inatividade", f"{v:.1f} ocorr.", f"{d:+.1f}% vs Estado", delta_color="inverse")
        st.caption(t)

    v, d, t = _get_metrics("TIMEOUT_BIOMETRIA", "TPBSEC")
    with col_k2:
        st.metric("Timeout Biometria", f"{v:.1f} ocorr.", f"{d:+.1f}% vs Estado", delta_color="inverse")
        st.caption(t)

    v, d, _ = _get_metrics("TECLA_INDEVIDA")
    with col_k3:
        st.metric("Teclas Indevidas", f"{v:.2f} ocorr.", f"{d:+.1f}% vs Estado", delta_color="inverse")
        st.caption("Erros de digitação")

    st.write("<br>", unsafe_allow_html=True)

    # ── Perfis demográficos ───────────────────────────────────────────────────
    col_d1, col_d2 = st.columns(2)

    with col_d1:
        st.markdown(
            "<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>"
            "Perfil por Faixa Etária</h4>",
            unsafe_allow_html=True,
        )
        cols_idade = [c for c in df.columns if "IDADE_" in c and "Inválido" not in c]
        if not cols_idade:
            st.info("Dados de idade não disponíveis.")
        else:
            sums = df[cols_idade].sum()
            if sums.sum() == 0:
                st.info("Todos os valores de idade são zero.")
            else:
                fig = go.Figure(go.Bar(
                    x=sums.values,
                    y=[c.replace("IDADE_", "").strip() for c in sums.index],
                    orientation="h",
                    marker_color=STATUS_PALETTE.get(status_filter, "#0EA5E9"),
                ))
                fig = apply_base_layout(fig, height=400)
                fig.update_layout(
                    yaxis=dict(
                        type="category",
                        tickfont=dict(color="black", size=13),
                        categoryorder="total ascending",
                        automargin=True,
                    ),
                    xaxis=dict(automargin=True),
                )
                st.plotly_chart(fig, use_container_width=True)
                del sums, fig

    with col_d2:
        st.markdown(
            "<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>"
            "Perfil por Escolaridade</h4>",
            unsafe_allow_html=True,
        )
        cols_esc = [c for c in df.columns if "ESC_" in c]
        if not cols_esc:
            st.info("Dados de escolaridade não disponíveis.")
        else:
            sums_esc = df[cols_esc].sum()
            if sums_esc.sum() == 0:
                st.info("Todos os valores de escolaridade são zero.")
            else:
                fig = go.Figure(go.Bar(
                    x=sums_esc.values,
                    y=[c.replace("ESC_", "").title() for c in sums_esc.index],
                    orientation="h",
                    marker_color=STATUS_PALETTE.get(status_filter, "#0EA5E9"),
                ))
                fig = apply_base_layout(fig, height=400)
                fig.update_layout(
                    yaxis=dict(
                        type="category",
                        tickfont=dict(color="black", size=13),
                        categoryorder="total ascending",
                        automargin=True,
                    ),
                    xaxis=dict(automargin=True),
                )
                st.plotly_chart(fig, use_container_width=True)
                del sums_esc, fig

    # ── Proporção PCD ─────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    _, col_pcd, _ = st.columns([1, 2, 1])
    with col_pcd:
        st.markdown(
            "<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>"
            "Proporção de Eleitores PCD</h4>",
            unsafe_allow_html=True,
        )
        cols_idade_all = [c for c in df.columns if "IDADE_" in c]
        if not cols_idade_all:
            st.info("Dados de idade não disponíveis para cálculo de PCD.")
        else:
            total_votos = df[cols_idade_all].sum().sum()
            qtd_pcd = df["QTD_PCD"].sum() if "QTD_PCD" in df.columns else 0
            fig = go.Figure(go.Pie(
                labels=["PCD", "Não PCD"],
                values=[qtd_pcd, total_votos - qtd_pcd],
                hole=0.45,
                marker=dict(colors=["#EF4444", "#CBD5E1"]),
                textinfo="percent+value",
            ))
            st.plotly_chart(apply_base_layout(fig, height=400), use_container_width=True)
            del fig, total_votos, qtd_pcd

    gc.collect()


# ──────────────────────────────────────────────────────────────────────────────
# Visão 3 — Nível 4 (agregado + estudo de caso individual)
# ──────────────────────────────────────────────────────────────────────────────

def _render_nivel4(df: pd.DataFrame, estado_means: dict) -> None:
    st.markdown("""
        <div class="section-header"><h2>Diagnóstico Detalhado por Nível</h2></div>
        <div class="section-desc">Análise comparativa do nível selecionado contra a média estadual.</div>
    """, unsafe_allow_html=True)

    st.markdown(
        "<h3 style='color: #1a3a5c; font-weight: 600; margin-bottom: 1rem;'>"
        "Detalhamento: Urnas Super Críticas (Nível 4)</h3>",
        unsafe_allow_html=True,
    )

    # 1. FUNÇÃO COM BUSCA BLINDADA
    def _get_metrics_nivel4(col_ocorr: str, col_tempo: str | None = None):
        m_niv = df[col_ocorr].mean() if col_ocorr in df.columns else 0
        m_est = estado_means.get(col_ocorr, m_niv)
        delta = ((m_niv / m_est) - 1) * 100 if m_est > 0 else 0

        tempo_str = ""
        if col_tempo:
            seg = df.get(col_tempo, pd.Series([0])).mean()
            if pd.notna(seg):
                tempo_str = f"Tempo total: {_fmt_min_sec(seg)}"
        return m_niv, delta, tempo_str

    # Renderizando os 3 Cartões de Métricas (KPIs)
    col_k1, col_k2, col_k3 = st.columns(3)

    v, d, t = _get_metrics_nivel4("INATIVIDADE", "TTPISEC")
    m_est_inat = estado_means.get("INATIVIDADE", 0)
    with col_k1:
        st.metric(
            label="Inatividade",
            value=f"{v:.1f} ocorr.",
            delta=f"{d:+.1f}% vs Estado",
            delta_color="inverse",
            help=f"Média do Estado: {m_est_inat:.2f} ocorrências por seção.",
        )
        if t:
            st.caption(f"**{t}**")

    v, d, t = _get_metrics_nivel4("TIMEOUT_BIOMETRIA", "TPBSEC")
    m_est_time = estado_means.get("TIMEOUT_BIOMETRIA", 0)
    with col_k2:
        st.metric(
            label="Timeout Bio",
            value=f"{v:.1f} ocorr.",
            delta=f"{d:+.1f}% vs Estado",
            delta_color="inverse",
            help=f"Média do Estado: {m_est_time:.2f} ocorrências por seção.",
        )
        if t:
            st.caption(f"**{t}**")

    v, d, _ = _get_metrics_nivel4("TECLA_INDEVIDA")
    m_est_tecla = estado_means.get("TECLA_INDEVIDA", 0)
    with col_k3:
        st.metric(
            label="Teclas Indevidas",
            value=f"{v:.2f} ocorr.",
            delta=f"{d:+.1f}% vs Estado",
            delta_color="inverse",
            help=f"Média do Estado: {m_est_tecla:.2f} ocorrências por seção.",
        )
        st.caption("Erros de digitação")

    st.write("<br>", unsafe_allow_html=True)

    # 3. GRÁFICOS DEMOGRÁFICOS
    col_d1, col_d2 = st.columns(2)

    with col_d1:
        st.markdown(
            "<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>"
            "Perfil por Faixa Etária (Total Nível 4)</h4>",
            unsafe_allow_html=True,
        )
        cols_idade = [c for c in df.columns if "IDADE_" in c and "Inválido" not in c]
        if not cols_idade:
            st.info("Dados de idade não disponíveis.")
        else:
            sums = df[cols_idade].sum()
            if sums.sum() == 0:
                st.info("Todos os valores de idade são zero.")
            else:
                fig = go.Figure(go.Bar(
                    x=sums.values,
                    y=[c.replace("IDADE_", "").strip() for c in sums.index],
                    orientation="h",
                    marker_color="#1b5e20",
                ))
                fig = apply_base_layout(fig, height=400)
                fig.update_layout(
                    yaxis=dict(
                        type="category",
                        tickfont=dict(color="black", size=13),
                        categoryorder="total ascending",
                        automargin=True,
                    ),
                    xaxis=dict(automargin=True),
                )
                st.plotly_chart(fig, use_container_width=True)
                del sums, fig

    with col_d2:
        st.markdown(
            "<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>"
            "Perfil por Escolaridade (Total Nível 4)</h4>",
            unsafe_allow_html=True,
        )
        cols_esc = [c for c in df.columns if "ESC_" in c]
        if not cols_esc:
            st.info("Dados de escolaridade não disponíveis.")
        else:
            sums_esc = df[cols_esc].sum()
            if sums_esc.sum() == 0:
                st.info("Todos os valores de escolaridade são zero.")
            else:
                fig = go.Figure(go.Bar(
                    x=sums_esc.values,
                    y=[c.replace("ESC_", "").title() for c in sums_esc.index],
                    orientation="h",
                    marker_color="#0d47a1",
                ))
                fig = apply_base_layout(fig, height=400)
                fig.update_layout(
                    yaxis=dict(
                        type="category",
                        tickfont=dict(color="black", size=13),
                        categoryorder="total ascending",
                        automargin=True,
                    ),
                    xaxis=dict(automargin=True),
                )
                st.plotly_chart(fig, use_container_width=True)
                del sums_esc, fig

    # Proporção PCD
    st.markdown("<br>", unsafe_allow_html=True)
    _, col_pcd, _ = st.columns([1, 2, 1])
    with col_pcd:
        st.markdown(
            "<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>"
            "Proporção de Eleitores PCD (Total Nível 4)</h4>",
            unsafe_allow_html=True,
        )
        cols_idade_all = [c for c in df.columns if "IDADE_" in c]
        if not cols_idade_all:
            st.info("Dados de idade não disponíveis.")
        else:
            total_votos = df[cols_idade_all].sum().sum()
            qtd_pcd = df.get("QTD_PCD", pd.Series([0])).sum()
            fig = go.Figure(go.Pie(
                labels=["PCD", "Não PCD"],
                values=[qtd_pcd, total_votos - qtd_pcd],
                hole=0.45,
                marker=dict(colors=["#d62728", "#bcbd22"]),
                textinfo="percent+value",
            ))
            st.plotly_chart(apply_base_layout(fig, height=400), use_container_width=True)
            del fig

    # Linha divisória para separar o macro do individual
    st.markdown("<hr style='margin: 3rem 0; border-top: 2px dashed #dc3545;'>", unsafe_allow_html=True)

    # 4. CHAMADA DO PRONTUÁRIO INDIVIDUAL
    _render_estudo_caso_nivel4(df)


# ──────────────────────────────────────────────────────────────────────────────
# Visão 4 — Estudo de caso nível 4 (supercríticas)
# ──────────────────────────────────────────────────────────────────────────────

def _render_estudo_caso_nivel4(df: pd.DataFrame) -> None:
    st.markdown("""
        <div class="section-header"><h2>Estudo de Caso: Urnas Super Críticas (Nível 4)</h2></div>
        <div class="section-desc">Investigação individualizada das urnas com criticidade máxima.</div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.markdown("""
            <div class="alert-box alert-success">
                <b>Resultado positivo:</b> Não há urnas classificadas como Super Críticas (Nível 4) neste cenário.
            </div>
        """, unsafe_allow_html=True)
        return

    df_sorted = (
        df.sort_values("ATRASO_FILA_MINUTOS", ascending=False)
        if "ATRASO_FILA_MINUTOS" in df.columns
        else df
    )

    st.markdown(f"""
        <div class="alert-box alert-danger">
            <b>Atenção:</b> Foram encontradas <b>{len(df_sorted)}</b> urnas Super Críticas.
            Selecione uma abaixo para investigação detalhada.
        </div>
    """, unsafe_allow_html=True)

    opcoes = []
    for idx, row in df_sorted.iterrows():
        atraso = f" | Atraso: {row.get('ATRASO_FILA_MINUTOS', 0):.0f} min"
        opcoes.append((idx, f"{row['NM_MUNICIPIO']} (Z: {row['NR_ZONA']} - S: {row['NR_SECAO']}){atraso}"))

    idx_sel = st.selectbox(
        "Selecione a Urna (ordenado do maior para o menor atraso):",
        options=[op[0] for op in opcoes],
        format_func=lambda x: next(op[1] for op in opcoes if op[0] == x),
    )

    urna = df_sorted.loc[idx_sel]
    cols_idade = [c for c in df_sorted.columns if c.startswith("IDADE_") and "Inválido" not in c]
    cols_esc   = [c for c in df_sorted.columns if c.startswith("ESC_")]

    # ── MELHORIA: extrair modelo de urna do prontuário ──────────────────────
    modelo_urna = urna.get("modelo", None)
    if pd.isna(modelo_urna) or modelo_urna is None:
        modelo_urna = "Não identificado"
    else:
        modelo_urna = str(modelo_urna)

    st.markdown(f"""
        <div style="background: #fee2e2; padding: 1rem 1.25rem; border-radius: 8px;
                    border-left: 4px solid #EF4444; margin-bottom: 1.25rem;">
            <h3 style="color: #721c24; margin-top: 0; font-size: 1.1rem; font-weight: 700;">
                Prontuário: {urna['NM_MUNICIPIO']} (Z: {urna['NR_ZONA']} | S: {urna['NR_SECAO']})
            </h3>
            <p style="color: #721c24; margin-bottom: 0.4rem; font-size: 0.9rem;">
                <b>Atraso Fila:</b> {urna.get('ATRASO_FILA_MINUTOS', 'N/A')} minutos
                &nbsp;&nbsp;|&nbsp;&nbsp;
                <b>Modelo:</b> <span style="font-family: var(--font-mono); font-weight: 600;">{modelo_urna}</span>
            </p>
        </div>
    """, unsafe_allow_html=True)

    # ── LINHA 1: Ocorrências Operacionais (apenas ocorrências, sem tempo) + Distribuição de Tempos
    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            "<h5 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.9rem;'>"
            "Ocorrências Operacionais</h5>",
            unsafe_allow_html=True,
        )
        metricas   = ["TIMEOUT_BIOMETRIA", "INATIVIDADE", "TECLA_INDEVIDA"]
        labels_op  = ["Timeout Biometria", "Inatividade", "Teclas Indevidas"]
        valores_op = [urna.get(m, 0) for m in metricas]
        # ALTERAÇÃO: apenas quantidade de ocorrências, sem tempo
        textos = [f"{int(v)} ocorr." for v in valores_op]
        fig = go.Figure(go.Bar(
            x=labels_op, y=valores_op,
            marker_color=["#F97316", "#0EA5E9", "#EF4444"],
            text=textos, textposition="outside",
        ))
        fig = apply_base_layout(fig, height=350)
        fig.update_layout(
            yaxis=dict(title="Quantidade", tickfont=dict(color="black", size=13)),
            xaxis=dict(tickfont=dict(color="black", size=13)),
        )
        st.plotly_chart(fig, use_container_width=True)
        del fig

    with col2:
        # Distribuição de Tempos da seção selecionada
        st.markdown(
            "<h5 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.9rem;'>"
            "Distribuição de Tempos — Seção Selecionada</h5>",
            unsafe_allow_html=True,
        )
        
        tempos_data = []
        tempos_labels = []
        tempos_cores = []
        
        if "TPBSEC" in urna.index and pd.notna(urna["TPBSEC"]) and urna["TPBSEC"] > 0:
            tempos_data.append(urna["TPBSEC"])
            tempos_labels.append("Timeout Biometria")
            tempos_cores.append("#F97316")
        
        if "TTPISEC" in urna.index and pd.notna(urna["TTPISEC"]) and urna["TTPISEC"] > 0:
            tempos_data.append(urna["TTPISEC"])
            tempos_labels.append("Inatividade")
            tempos_cores.append("#0EA5E9")
        
        teclas_val = urna.get("TECLA_INDEVIDA", 0)
        if pd.notna(teclas_val) and teclas_val > 0:
            tempos_data.append(teclas_val * 1.0)  # 1 erro = 1s
            tempos_labels.append("Teclas Indevidas")
            tempos_cores.append("#EF4444")
        
        if tempos_data:
            fig = go.Figure(go.Bar(
                x=tempos_labels,
                y=tempos_data,
                marker_color=tempos_cores,
                text=[_fmt_min_sec(v) for v in tempos_data],
                textposition="outside",
            ))
            fig = apply_base_layout(fig, height=350)
            fig.update_layout(
                yaxis=dict(title="Tempo (segundos)", tickfont=dict(color="black", size=13)),
                xaxis=dict(tickfont=dict(color="black", size=13)),
            )
            st.plotly_chart(fig, use_container_width=True)
            del fig
        else:
            st.info("Dados de tempo não disponíveis para esta seção.")

    # ── LINHA 2: Faixa Etária + Escolaridade
    st.write("<br>", unsafe_allow_html=True)
    col3, col4 = st.columns(2)

    with col3:
        st.markdown(
            "<h5 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.9rem;'>"
            "Faixa Etária</h5>",
            unsafe_allow_html=True,
        )
        vals_idade  = [urna.get(c, 0) for c in cols_idade]
        total_idade = sum(vals_idade)
        textos_idade = [
            f"{int(v)} ({v/total_idade*100:.1f}%)" if total_idade > 0 else "0"
            for v in vals_idade
        ]
        fig = go.Figure(go.Bar(
            x=vals_idade,
            y=[c.replace("IDADE_", "").strip() for c in cols_idade],
            orientation="h", marker_color="#0EA5E9",
            text=textos_idade, textposition="outside",
        ))
        fig = apply_base_layout(fig, height=350)
        fig.update_layout(
            yaxis=dict(
                type="category",
                categoryorder="total ascending",
                tickfont=dict(color="black", size=13),
                automargin=True,
            ),
            xaxis=dict(automargin=True),
        )
        st.plotly_chart(fig, use_container_width=True)
        del fig, vals_idade

    with col4:
        st.markdown(
            "<h5 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.9rem;'>"
            "Escolaridade</h5>",
            unsafe_allow_html=True,
        )
        vals_esc  = [urna.get(c, 0) for c in cols_esc]
        total_esc = sum(vals_esc)
        textos_esc = [
            f"{int(v)} ({v/total_esc*100:.1f}%)" if total_esc > 0 else "0"
            for v in vals_esc
        ]
        fig = go.Figure(go.Bar(
            x=vals_esc,
            y=[c.replace("ESC_", "").title() for c in cols_esc],
            orientation="h", marker_color="#8B5CF6",
            text=textos_esc, textposition="outside",
        ))
        fig = apply_base_layout(fig, height=350)
        fig.update_layout(
            yaxis=dict(
                type="category",
                categoryorder="total ascending",
                tickfont=dict(color="black", size=13),
                automargin=True,
            ),
            xaxis=dict(automargin=True),
        )
        st.plotly_chart(fig, use_container_width=True)
        del fig, vals_esc

    # ── LINHA 3: Proporção PCD + Comparativo de Tempos
    st.write("<br>", unsafe_allow_html=True)
    col5, col6 = st.columns(2)

    with col5:
        st.markdown(
            "<h5 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.9rem;'>"
            "Proporção PCD</h5>",
            unsafe_allow_html=True,
        )
        total_el = sum(urna.get(c, 0) for c in cols_idade)
        pcd = urna.get("QTD_PCD", 0)
        fig = go.Figure(go.Pie(
            labels=["PCD", "Não PCD"],
            values=[pcd, total_el - pcd],
            hole=0.45,
            marker=dict(colors=["#EF4444", "#CBD5E1"]),
            textinfo="percent+value",
        ))
        st.plotly_chart(apply_base_layout(fig, height=350), use_container_width=True)
        del fig, total_el, pcd

    with col6:
        # Comparativo de tempos — seção vs média estadual
        st.markdown(
            "<h5 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.9rem;'>"
            "Comparativo de Tempos — Seção vs Estado</h5>",
            unsafe_allow_html=True,
        )
        
        comp_labels = []
        comp_secao = []
        comp_estado = []
        comp_cores = []
        
        if "TPBSEC" in urna.index and pd.notna(urna["TPBSEC"]):
            comp_labels.append("Timeout Bio")
            comp_secao.append(urna["TPBSEC"])
            estado_tpb = df_sorted["TPBSEC"].mean() if "TPBSEC" in df_sorted.columns else 0
            comp_estado.append(estado_tpb)
            comp_cores.append("#F97316")
        
        if "TTPISEC" in urna.index and pd.notna(urna["TTPISEC"]):
            comp_labels.append("Inatividade")
            comp_secao.append(urna["TTPISEC"])
            estado_ttp = df_sorted["TTPISEC"].mean() if "TTPISEC" in df_sorted.columns else 0
            comp_estado.append(estado_ttp)
            comp_cores.append("#0EA5E9")
        
        teclas_val = urna.get("TECLA_INDEVIDA", 0)
        if pd.notna(teclas_val) and teclas_val > 0:
            comp_labels.append("Teclas Indevidas")
            comp_secao.append(teclas_val * 1.0)
            estado_tecla = df_sorted["TECLA_INDEVIDA"].mean() if "TECLA_INDEVIDA" in df_sorted.columns else 0
            comp_estado.append(estado_tecla * 1.0)
            comp_cores.append("#EF4444")
        
        if comp_labels:
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                name="Esta Seção",
                x=comp_labels,
                y=comp_secao,
                marker_color=comp_cores,
                text=[_fmt_min_sec(v) for v in comp_secao],
                textposition="outside",
                opacity=0.9,
            ))
            
            fig.add_trace(go.Bar(
                name="Média Nível 4",
                x=comp_labels,
                y=comp_estado,
                marker_color="#94A3B8",
                text=[_fmt_min_sec(v) for v in comp_estado],
                textposition="outside",
                opacity=0.6,
            ))
            
            fig = apply_base_layout(fig, height=350)
            fig.update_layout(
                barmode="group",
                yaxis=dict(title="Tempo (segundos)", tickfont=dict(color="black", size=13)),
                xaxis=dict(tickfont=dict(color="black", size=13)),
                legend=dict(
                    orientation="h",
                    yanchor="bottom", y=-0.25,
                    xanchor="center", x=0.5,
                ),
            )
            st.plotly_chart(fig, use_container_width=True)
            del fig
        else:
            st.info("Dados insuficientes para comparativo de tempos.")

    del df_sorted, urna
    gc.collect()
