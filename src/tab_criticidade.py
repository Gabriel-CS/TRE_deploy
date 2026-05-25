from __future__ import annotations

import gc

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analysis import OKABE_ITO, STATUS_LABELS, STATUS_PALETTE
from src.charts import apply_base_layout


# ──────────────────────────────────────────────────────────────────────────────
# Renderização da aba
# ──────────────────────────────────────────────────────────────────────────────

def render_tab_criticidade(
    df_secoes: pd.DataFrame | None,
    status_filter,
    estado_means: dict | None = None,
) -> None:
    """Renderiza o conteúdo completo da aba 'Análise por Criticidade'.
    """
    if df_secoes is None or df_secoes.empty:
        st.error("Dados de seções não disponíveis para este filtro.")
        return

    if status_filter is None or status_filter == "Todas":
        _render_visao_geral(df_secoes)
    elif status_filter in [0, 1, 2, 3]:
        _render_detalhamento_nivel(df_secoes, status_filter, estado_means or {})
    elif status_filter == 4:
  
        # TÍTULOS DA SEÇÃO
        st.markdown("""
            <div class="section-header"><h2>Diagnóstico Detalhado por Nível</h2></div>
            <div class="section-desc">Análise comparativa do nível selecionado contra a média estadual.</div>
        """, unsafe_allow_html=True)
        
        st.markdown(
            "<h3 style='color: #1a3a5c; font-weight: 600; margin-bottom: 1rem;'>Detalhamento: Urnas Super Críticas (Nível 4)</h3>",
            unsafe_allow_html=True,
        )
        
        # 1. FUNÇÃO COM BUSCA BLINDADA (Força o tempo a aparecer mesmo sem a coluna)
        def _get_metrics_nivel4(col_ocorr: str, col_tempo: str | None = None):
            m_niv = df_secoes[col_ocorr].mean() if col_ocorr in df_secoes.columns else 0
            m_est = (estado_means or {}).get(col_ocorr, m_niv)
            delta = ((m_niv / m_est) - 1) * 100 if m_est > 0 else 0
            
            tempo_str = ""
            if col_tempo:
                seg = df_secoes.get(col_tempo, pd.Series([0])).mean()
                if pd.notna(seg):
                    tempo_str = f"Tempo total: ~{int(seg)//60}m {int(seg)%60}s"
            return m_niv, delta, tempo_str

        # Renderizando os 3 Cartões de Métricas (KPIs)
       # Renderizando os 3 Cartões de Métricas (KPIs) com Dica Visual (Tooltip)
        col_k1, col_k2, col_k3 = st.columns(3)

        # 1. Média do Estado para Inatividade
        v, d, t = _get_metrics_nivel4("INATIVIDADE", "TTPISEC")
        m_est_inat = (estado_means or {}).get("INATIVIDADE", 0) # Puxa o valor real do estado
        with col_k1:
            st.metric(
                label="Inatividade", 
                value=f"{v:.1f} ocorr.", 
                delta=f"{d:+.1f}% vs Estado", 
                delta_color="inverse",
                help=f"Média do Estado: {m_est_inat:.2f} ocorrências por seção." # ---> DICA AQUI
            )
            if t: 
                st.caption(f"**{t}**")

        # 2. Média do Estado para Timeout Biometria
        v, d, t = _get_metrics_nivel4("TIMEOUT_BIOMETRIA", "TPBSEC")
        m_est_time = (estado_means or {}).get("TIMEOUT_BIOMETRIA", 0) # Puxa o valor real do estado
        with col_k2:
            st.metric(
                label="Timeout Bio", 
                value=f"{v:.1f} ocorr.", 
                delta=f"{d:+.1f}% vs Estado", 
                delta_color="inverse",
                help=f"Média do Estado: {m_est_time:.2f} ocorrências por seção." # ---> DICA AQUI
            )
            if t: 
                st.caption(f"**{t}**")

        # 3. Teclas Indevidas (Mantendo o padrão)
        v, d, _ = _get_metrics_nivel4("TECLA_INDEVIDA")
        m_est_tecla = (estado_means or {}).get("TECLA_INDEVIDA", 0)
        with col_k3:
            st.metric(
                label="Teclas Indevidas", 
                value=f"{v:.2f} ocorr.", 
                delta=f"{d:+.1f}% vs Estado", 
                delta_color="inverse",
                help=f"Média do Estado: {m_est_tecla:.2f} ocorrências por seção."
            )
            st.caption("Erros de digitação")

        st.write("<br>", unsafe_allow_html=True)


        # 3. GRÁFICOS DEMOGRÁFICOS
        col_d1, col_d2 = st.columns(2)
        
        with col_d1:
            st.markdown("<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>Perfil por Faixa Etária (Total Nível 4)</h4>", unsafe_allow_html=True)
            cols_idade = [c for c in df_secoes.columns if "IDADE_" in c and "Inválido" not in c]
            sums = df_secoes[cols_idade].sum()
            fig = go.Figure(go.Bar(
                x=sums.values, y=[c.replace("IDADE_", "").strip() for c in sums.index],
                orientation="h", marker_color="#1b5e20",
            ))
            fig = apply_base_layout(fig, height=400)
            fig.update_layout(yaxis=dict(tickfont=dict(color="black", size=13), categoryorder="total ascending"))
            st.plotly_chart(fig, use_container_width=True)
            
        with col_d2:
            st.markdown("<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>Perfil por Escolaridade (Total Nível 4)</h4>", unsafe_allow_html=True)
            cols_esc = [c for c in df_secoes.columns if "ESC_" in c]
            sums_esc = df_secoes[cols_esc].sum()
            fig = go.Figure(go.Bar(
                x=sums_esc.values, y=[c.replace("ESC_", "").title() for c in sums_esc.index],
                orientation="h", marker_color="#0d47a1",
            ))
            fig = apply_base_layout(fig, height=400)
            fig.update_layout(yaxis=dict(tickfont=dict(color="black", size=13), categoryorder="total ascending"))
            st.plotly_chart(fig, use_container_width=True)

        # Proporção PCD
        st.markdown("<br>", unsafe_allow_html=True)
        _, col_pcd, _ = st.columns([1, 2, 1])
        with col_pcd:
            st.markdown("<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>Proporção de Eleitores PCD (Total Nível 4)</h4>", unsafe_allow_html=True)
            cols_idade_all = [c for c in df_secoes.columns if "IDADE_" in c]
            total_votos = df_secoes[cols_idade_all].sum().sum()
            qtd_pcd = df_secoes.get("QTD_PCD", pd.Series([0])).sum()
            fig = go.Figure(go.Pie(
                labels=["PCD", "Não PCD"], values=[qtd_pcd, total_votos - qtd_pcd],
                hole=0.45, marker=dict(colors=["#d62728", "#bcbd22"]), textinfo="percent+value",
            ))
            st.plotly_chart(apply_base_layout(fig, height=400), use_container_width=True)

        # Linha divisória para separar o macro do individual
        st.markdown("<hr style='margin: 3rem 0; border-top: 2px dashed #dc3545;'>", unsafe_allow_html=True)
        
        # 4. CHAMADA DO PRONTUÁRIO INDIVIDUAL
        _render_estudo_caso_nivel4(df_secoes)


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
        m_timeout = df.groupby("STATUS")["TIMEOUT_BIOMETRIA"].mean()
        if "TPBSEC" in df.columns:
            m_tempo = df.groupby("STATUS")["TPBSEC"].mean()
            text_timeout = [
                f"{v:.1f} ocorr. (~{int(t)//60}m{int(t)%60}s)"
                for v, t in zip(m_timeout.values, m_tempo.values)
            ]
            del m_tempo
        else:
            text_timeout = [f"{v:.1f} ocorr." for v in m_timeout.values]

        fig = go.Figure(go.Bar(
            x=m_timeout.values,
            y=[STATUS_LABELS.get(int(s), f"Nível {int(s)}") for s in m_timeout.index],
            orientation="h",
            marker_color=[STATUS_PALETTE.get(int(s), "#6c757d") for s in m_timeout.index],
            text=text_timeout,
            textposition="outside",
        ))
        fig = apply_base_layout(fig, height=350)
        fig.update_layout(yaxis=dict(tickfont=dict(color="black", size=13)))
        st.plotly_chart(fig, use_container_width=True)
        del m_timeout, fig

    with col_v2:
        st.markdown(
            "<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>"
            "Média de Inatividade do Eleitor</h4>",
            unsafe_allow_html=True,
        )
        m_inat = df.groupby("STATUS")["INATIVIDADE"].mean()
        if "TTPISEC" in df.columns:
            m_t_inat = df.groupby("STATUS")["TTPISEC"].mean()
            text_inat = [
                f"{v:.1f} ocorr. (~{int(t)//60}m{int(t)%60}s)"
                for v, t in zip(m_inat.values, m_t_inat.values)
            ]
            del m_t_inat
        else:
            text_inat = [f"{v:.1f} ocorr." for v in m_inat.values]

        fig = go.Figure(go.Bar(
            x=m_inat.values,
            y=[STATUS_LABELS.get(int(s), f"Nível {int(s)}") for s in m_inat.index],
            orientation="h",
            marker_color=[STATUS_PALETTE.get(int(s), "#6c757d") for s in m_inat.index],
            text=text_inat,
            textposition="outside",
        ))
        fig = apply_base_layout(fig, height=350)
        fig.update_layout(yaxis=dict(tickfont=dict(color="black", size=13)))
        st.plotly_chart(fig, use_container_width=True)
        del m_inat, fig

    col_p1, col_p2 = st.columns(2)

    with col_p1:
        st.markdown(
            "<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>"
            "Distribuição de PCDs por Status</h4>",
            unsafe_allow_html=True,
        )
        pcd_sum = df.groupby("STATUS")["QTD_PCD"].sum()
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
        m_teclas = df.groupby("STATUS")["TECLA_INDEVIDA"].mean()
        fig = go.Figure(go.Bar(
            x=m_teclas.values,
            y=[STATUS_LABELS.get(int(s), f"Nível {int(s)}") for s in m_teclas.index],
            orientation="h",
            marker_color=[STATUS_PALETTE.get(int(s), "#6c757d") for s in m_teclas.index],
            text=[f"{v:.2f}" for v in m_teclas.values],
            textposition="outside",
        ))
        fig = apply_base_layout(fig, height=350)
        fig.update_layout(yaxis=dict(tickfont=dict(color="black", size=13)))
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

            # NOTA: nível 0 removido do filtro. Código original comentado:
        # titulo = (
        #     f"Detalhamento: {STATUS_LABELS.get(status_filter, f'Nível {status_filter}')}"
        #     if status_filter > 0
        #     else "Urnas Sem Atraso (Nível 0)"
        # )
    titulo = f"Detalhamento: {STATUS_LABELS.get(status_filter, f'Nível {status_filter}')}"
    st.markdown(
        f"<h3 style='color: #1a3a5c; font-weight: 600; margin-bottom: 1rem;'>{titulo}</h3>",
        unsafe_allow_html=True,
    )

    # ── KPIs com delta vs média estadual ─────────────────────────────────────
    def _get_metrics(col_ocorr: str, col_tempo: str | None = None):
        m_niv = df[col_ocorr].mean()
        # Usa média estadual pré-computada (sobre todas as seções críticas).
        # Recai no próprio DF apenas se estado_means não tiver a coluna.
        m_est = estado_means.get(col_ocorr, m_niv)
        delta = ((m_niv / m_est) - 1) * 100 if m_est > 0 else 0
        tempo_str = ""
        if col_tempo and col_tempo in df.columns:
            seg = df[col_tempo].mean()
            tempo_str = f"Tempo total: ~{int(seg)//60}m {int(seg)%60}s"
        return m_niv, delta, tempo_str

    col_k1, col_k2, col_k3 = st.columns(3)

    v, d, t = _get_metrics("INATIVIDADE", "TTPISEC")
    with col_k1:
        st.metric("Inatividade", f"{v:.1f} ocorr.", f"{d:+.1f}% vs Estado", delta_color="inverse")
        st.caption(t)

    v, d, t = _get_metrics("TIMEOUT_BIOMETRIA", "TPBSEC")
    with col_k2:
        st.metric("Timeout Bio", f"{v:.1f} ocorr.", f"{d:+.1f}% vs Estado", delta_color="inverse")
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
        sums = df[cols_idade].sum()
        fig = go.Figure(go.Bar(
            x=sums.values,
            y=[c.replace("IDADE_", "").strip() for c in sums.index],
            orientation="h",
            marker_color=STATUS_PALETTE.get(status_filter, "#0EA5E9"),
        ))
        fig = apply_base_layout(fig, height=400)
        fig.update_layout(yaxis=dict(
            tickfont=dict(color="black", size=13), categoryorder="total ascending"
        ))
        st.plotly_chart(fig, use_container_width=True)
        del sums, fig

    with col_d2:
        st.markdown(
            "<h4 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.95rem;'>"
            "Perfil por Escolaridade</h4>",
            unsafe_allow_html=True,
        )
        cols_esc = [c for c in df.columns if "ESC_" in c]
        sums_esc = df[cols_esc].sum()
        fig = go.Figure(go.Bar(
            x=sums_esc.values,
            y=[c.replace("ESC_", "").title() for c in sums_esc.index],
            orientation="h",
            marker_color=STATUS_PALETTE.get(status_filter, "#0EA5E9"),
        ))
        fig = apply_base_layout(fig, height=400)
        fig.update_layout(yaxis=dict(
            tickfont=dict(color="black", size=13), categoryorder="total ascending"
        ))
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
        total_votos = df[cols_idade_all].sum().sum()
        qtd_pcd = df["QTD_PCD"].sum()
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
# Visão 3 — Estudo de caso nível 4 (supercríticas)
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

    st.markdown(f"""
        <div style="background: #fee2e2; padding: 1rem 1.25rem; border-radius: 8px;
                    border-left: 4px solid #EF4444; margin-bottom: 1.25rem;">
            <h3 style="color: #721c24; margin-top: 0; font-size: 1.1rem; font-weight: 700;">
                Prontuário: {urna['NM_MUNICIPIO']} (Z: {urna['NR_ZONA']} | S: {urna['NR_SECAO']})
            </h3>
            <p style="color: #721c24; margin-bottom: 0; font-size: 0.9rem;">
                <b>Atraso Fila:</b> {urna.get('ATRASO_FILA_MINUTOS', 'N/A')} minutos
            </p>
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            "<h5 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.9rem;'>"
            "Ocorrências Operacionais</h5>",
            unsafe_allow_html=True,
        )
        metricas   = ["TIMEOUT_BIOMETRIA", "INATIVIDADE", "TECLA_INDEVIDA"]
        labels_op  = ["Timeout Biometria", "Inatividade", "Tecla Indevida"]
        valores_op = [urna[m] for m in metricas]
        textos = []
        for m, v in zip(metricas, valores_op):
            if m == "TIMEOUT_BIOMETRIA" and "TPBSEC" in df_sorted.columns:
                t = urna["TPBSEC"]
                textos.append(f"{int(v)} ocorr.<br>(~{int(t)//60}m{int(t)%60}s)")
            elif m == "INATIVIDADE" and "TTPISEC" in df_sorted.columns:
                t = urna["TTPISEC"]
                textos.append(f"{int(v)} ocorr.<br>(~{int(t)//60}m{int(t)%60}s)")
            else:
                textos.append(f"{int(v)} ocorr.")
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
        st.markdown(
            "<h5 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.9rem;'>"
            "Faixa Etária</h5>",
            unsafe_allow_html=True,
        )
        vals_idade  = urna[cols_idade].values
        total_idade = vals_idade.sum()
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
        fig.update_layout(yaxis=dict(categoryorder="total ascending", tickfont=dict(color="black", size=13)))
        st.plotly_chart(fig, use_container_width=True)
        del fig, vals_idade

    st.write("<br>", unsafe_allow_html=True)
    col3, col4 = st.columns(2)

    with col3:
        st.markdown(
            "<h5 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.9rem;'>"
            "Escolaridade</h5>",
            unsafe_allow_html=True,
        )
        vals_esc  = urna[cols_esc].values
        total_esc = vals_esc.sum()
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
        fig.update_layout(yaxis=dict(categoryorder="total ascending", tickfont=dict(color="black", size=13)))
        st.plotly_chart(fig, use_container_width=True)
        del fig, vals_esc

    with col4:
        st.markdown(
            "<h5 style='text-align: center; color: #1a3a5c; font-weight: 600; font-size: 0.9rem;'>"
            "Proporção PCD</h5>",
            unsafe_allow_html=True,
        )
        total_el = sum(urna[c] for c in cols_idade)
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

    del df_sorted, urna
    gc.collect()