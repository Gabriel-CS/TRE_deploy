# tab_criticidade.py
from __future__ import annotations

import gc

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.analysis import STATUS_LABELS, STATUS_PALETTE
from src.charts import apply_base_layout, donut_chart
from src.ui_components import (
    info_card,
    section_header,
    alert_box,
    contingency_toggle_css,
)


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


def _fmt_horas_min(total_seconds: float) -> str:
    """
    Formata segundos totais em horas e minutos (~XhYYmin), adequado para
    durações longas como o tempo total de votação de uma seção.
    """
    if pd.isna(total_seconds) or total_seconds <= 0:
        return "N/D"
    total_seconds = int(total_seconds)
    h, resto = divmod(total_seconds, 3600)
    m, s = divmod(resto, 60)
    if h > 0:
        return f"~{h}h{m:02d}min"
    if m > 0:
        return f"~{m}min{s:02d}s"
    return f"~{s}s"


def _vazio(valor) -> bool:
    """Verifica se um valor vindo do dataset deve ser tratado como ausente."""
    return valor is None or (isinstance(valor, float) and pd.isna(valor)) or valor == ""


def _fmt_valor(valor, sufixo: str = "") -> str:
    """Formata um valor genérico vindo do dataset, tratando NaN/vazio como N/D."""
    if _vazio(valor):
        return "N/D"
    return f"{valor}{sufixo}"


def _chart_title(texto: str) -> None:
    """
    Título padronizado para gráficos individuais dentro de uma coluna.
    Substitui os múltiplos blocos de markdown repetidos, garantindo
    consistência visual (mesma tipografia, alinhamento e espaçamento)
    em toda a aba.
    """
    st.markdown(
        f"<div style='text-align:center;color:#1a3a5c;font-weight:600;"
        f"font-size:0.85rem;letter-spacing:0.01em;margin-bottom:0.35rem;"
        f"padding-bottom:0.35rem;border-bottom:1px solid #e2e8f0;'>{texto}</div>",
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Colunas de contingência
# ──────────────────────────────────────────────────────────────────────────────

_COLS_CONTINGENCIA = [
    "HOUVE_TROCA_POR_CONTINGENCIA", "EH_URNA_CONTINGENCIA",
    "CONTINGENCIA_DESDE_INICIO_VOTACAO", "OBSERVACAO_TROCA_URNA",
    "MODELO_URNA", "MODELO_URNA_PAR_CONTINGENCIA",
    "MODELO_URNA_PRINCIPAL", "MODELO_URNA_PROBLEMATICA", "URNA_ID",
    "URNA_ID_PRINCIPAL", "URNA_ID_PROBLEMATICA",
    "ULTIMO_EVENTO_URNA_PROBLEMATICA_DT", "ULTIMO_EVENTO_URNA_PROBLEMATICA_MSG",
    "INICIO_PROCEDIMENTO_CONTINGENCIA", "CONTINGENCIA_EXECUTADA_COM_SUCESSO",
    "DURACAO_PROCEDIMENTO_INTERNO_CONTINGENCIA_SEG", "URNA_PRONTA_PARA_RECEBER_VOTOS",
    "TEMPO_TOTAL_TROCA_URNA_SEG", "PAREAMENTO_SUSPEITO", "MOTIVO_PAREAMENTO_SUSPEITO",
]


# ──────────────────────────────────────────────────────────────────────────────
# Bloco de Contingência — visual com destaque aprimorado
# ──────────────────────────────────────────────────────────────────────────────

def _render_bloco_contingencia(urna: pd.Series) -> None:
    """
    Renderiza um card premium com as informações de troca de urna por contingência.
    Design com destaque visual superior para fácil identificação.
    """
    houve_troca = bool(urna.get("HOUVE_TROCA_POR_CONTINGENCIA", False))
    eh_conting = bool(urna.get("EH_URNA_CONTINGENCIA", False))
    if not (houve_troca or eh_conting):
        return

    duracao_interna = urna.get("DURACAO_PROCEDIMENTO_INTERNO_CONTINGENCIA_SEG", 0)
    tempo_total_troca = urna.get("TEMPO_TOTAL_TROCA_URNA_SEG", 0)
    suspeito = bool(urna.get("PAREAMENTO_SUSPEITO", False))
    desde_inicio = bool(urna.get("CONTINGENCIA_DESDE_INICIO_VOTACAO", False))

    # Modelo de cada urna do par: a que assumiu a contingência (principal) e
    # a original/problemática — informação essencial para a análise e que
    # antes era descartada (só o modelo da urna de contingência aparecia).
    modelo_contingencia = urna.get("MODELO_URNA_PRINCIPAL")
    if _vazio(modelo_contingencia):
        modelo_contingencia = urna.get("MODELO_URNA")
    if _vazio(modelo_contingencia):
        modelo_contingencia = urna.get("MODELO_URNA_PAR_CONTINGENCIA")

    modelo_problematica = urna.get("MODELO_URNA_PROBLEMATICA")

    # Header com ícone e cor de destaque
    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
            border: 2px solid #f59e0b;
            border-radius: 12px;
            padding: 1rem 1.25rem 0.8rem;
            margin-bottom: 1rem;
            box-shadow: 0 4px 12px rgba(245, 158, 11, 0.15);
        ">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:0.8rem;">
                <div style="
                    width:36px;height:36px;border-radius:50%;
                    background:linear-gradient(135deg, #f59e0b, #d97706);
                    display:flex;align-items:center;justify-content:center;
                    flex-shrink:0;
                ">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M17 2.1l4 4-4 4"/><path d="M3 12.6v-2a4 4 0 0 1 4-4h12.8"/>
                        <path d="M7 21.9l-4-4 4-4"/><path d="M21 11.4v2a4 4 0 0 1-4 4H4.2"/>
                    </svg>
                </div>
                <div>
                    <div style="font-size:1rem;font-weight:800;color:#78350f;">
                        Troca de Urna por Contingência
                    </div>
                    <div style="font-size:0.75rem;color:#92400e;margin-top:1px;">
                        Procedimento de emergência realizado na seção
                    </div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Grid de informações
    aviso_suspeito = ""
    if desde_inicio:
        observacao = urna.get(
            "OBSERVACAO_TROCA_URNA",
            "Urna de contingência já estava em operação desde o início da "
            "votação: não há intervalo de troca a ser medido.",
        )
        aviso_suspeito = (
            f'<div style="margin-top:0.75rem;padding:0.6rem 1rem;background:#eff6ff;'
            f'border:1px solid #bfdbfe;border-radius:8px;font-size:0.82rem;'
            f'color:#1e3a8a;display:flex;align-items:center;gap:8px;">'
            f'<span style="font-size:1rem;">&#8505;</span>'
            f'<div><b>Contingência desde o início da votação:</b> {_fmt_valor(observacao)}</div></div>'
        )
    elif suspeito:
        motivo = urna.get("MOTIVO_PAREAMENTO_SUSPEITO", "")
        aviso_suspeito = (
            f'<div style="margin-top:0.75rem;padding:0.6rem 1rem;background:#fef2f2;'
            f'border:1px solid #fecaca;border-radius:8px;font-size:0.82rem;'
            f'color:#991b1b;display:flex;align-items:center;gap:8px;">'
            f'<span style="font-size:1rem;">&#9888;</span>'
            f'<div><b>Pareamento suspeito:</b> {motivo}</div></div>'
        )

    label_urna_problematica = "Urna original (sem atividade)" if desde_inicio else "Urna problemática"
    label_modelo_problematica = "Modelo (urna original)" if desde_inicio else "Modelo (urna problemática)"
    label_ultimo_evento = "Último evento (urna original)" if desde_inicio else "Último evento"
    label_msg_evento = "Mensagem do último evento (urna original)" if desde_inicio else "Mensagem do último evento"

    if desde_inicio:
        tempo_troca_exibido = "Não se aplica"
        tempo_troca_titulo = "Contingência ativa desde o início"
    else:
        tempo_troca_exibido = _fmt_horas_min(tempo_total_troca)
        tempo_troca_titulo = "Tempo total de troca"

    st.markdown(f"""
        <div style="
            background:#fffbeb;
            border:1px solid #fde68a;
            border-radius:0 0 12px 12px;
            padding:0.9rem 1.1rem;
            margin-bottom:1.25rem;
            margin-top:-1.2rem;
            border-top:none;
        ">
            <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
                        gap:0.7rem 1.4rem;font-size:0.84rem;color:#78350f;">
                <div style="background:rgba(255,255,255,0.6);padding:0.5rem 0.7rem;border-radius:6px;">
                    <div style="font-size:0.65rem;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">Modelo (contingência)</div>
                    <div style="font-weight:600;color:#451a03;">{_fmt_valor(modelo_contingencia)}</div>
                </div>
                <div style="background:rgba(255,255,255,0.6);padding:0.5rem 0.7rem;border-radius:6px;">
                    <div style="font-size:0.65rem;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">{label_modelo_problematica}</div>
                    <div style="font-weight:600;color:#451a03;">{_fmt_valor(modelo_problematica)}</div>
                </div>
                <div style="background:rgba(255,255,255,0.6);padding:0.5rem 0.7rem;border-radius:6px;">
                    <div style="font-size:0.65rem;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">Urna principal</div>
                    <div style="font-weight:600;color:#451a03;">{_fmt_valor(urna.get("URNA_ID_PRINCIPAL"))}</div>
                </div>
                <div style="background:rgba(255,255,255,0.6);padding:0.5rem 0.7rem;border-radius:6px;">
                    <div style="font-size:0.65rem;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">{label_urna_problematica}</div>
                    <div style="font-weight:600;color:#451a03;">{_fmt_valor(urna.get("URNA_ID_PROBLEMATICA"))}</div>
                </div>
                <div style="background:rgba(255,255,255,0.6);padding:0.5rem 0.7rem;border-radius:6px;">
                    <div style="font-size:0.65rem;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">{label_ultimo_evento}</div>
                    <div style="font-weight:600;color:#451a03;">{_fmt_valor(urna.get("ULTIMO_EVENTO_URNA_PROBLEMATICA_DT"))}</div>
                </div>
                <div style="background:rgba(255,255,255,0.6);padding:0.5rem 0.7rem;border-radius:6px;">
                    <div style="font-size:0.65rem;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">Início do procedimento</div>
                    <div style="font-weight:600;color:#451a03;">{_fmt_valor(urna.get("INICIO_PROCEDIMENTO_CONTINGENCIA"))}</div>
                </div>
                <div style="background:rgba(255,255,255,0.6);padding:0.5rem 0.7rem;border-radius:6px;">
                    <div style="font-size:0.65rem;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">Contingência concluída</div>
                    <div style="font-weight:600;color:#451a03;">{_fmt_valor(urna.get("CONTINGENCIA_EXECUTADA_COM_SUCESSO"))}</div>
                </div>
                <div style="background:rgba(255,255,255,0.6);padding:0.5rem 0.7rem;border-radius:6px;">
                    <div style="font-size:0.65rem;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">Urna pronta p/ votos</div>
                    <div style="font-weight:600;color:#451a03;">{_fmt_valor(urna.get("URNA_PRONTA_PARA_RECEBER_VOTOS"))}</div>
                </div>
                <div style="background:rgba(255,255,255,0.6);padding:0.5rem 0.7rem;border-radius:6px;">
                    <div style="font-size:0.65rem;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">Duração interna</div>
                    <div style="font-weight:600;color:#451a03;">{_fmt_horas_min(duracao_interna)}</div>
                </div>
            </div>
            <div style="margin-top:0.7rem;padding:0.5rem 0.7rem;background:rgba(255,255,255,0.6);border-radius:6px;">
                <div style="font-size:0.65rem;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">{label_msg_evento}</div>
                <div style="font-weight:500;color:#451a03;font-size:0.8rem;">{_fmt_valor(urna.get("ULTIMO_EVENTO_URNA_PROBLEMATICA_MSG"))}</div>
            </div>
            <div style="margin-top:0.7rem;display:flex;gap:1rem;">
                <div style="flex:1;background:rgba(255,255,255,0.6);padding:0.5rem 0.7rem;border-radius:6px;text-align:center;">
                    <div style="font-size:0.65rem;color:#92400e;text-transform:uppercase;letter-spacing:0.05em;font-weight:700;">{tempo_troca_titulo}</div>
                    <div style="font-weight:800;color:#451a03;font-size:1.1rem;">{tempo_troca_exibido}</div>
                </div>
            </div>
            {aviso_suspeito}
        </div>
    """, unsafe_allow_html=True)


def _render_bloco_tempo_votacao(urna: pd.Series) -> None:
    """Renderiza métricas de horário do 1º/último voto e tempo total de votação da seção."""
    primeiro = urna.get("PRIMEIRO_VOTO")
    ultimo = urna.get("ULTIMO_VOTO")
    tempo_total = urna.get("TEMPO_SECAO_PRIMEIRO_ULTIMO_VOTO_SEG")

    st.markdown(
        """
        <div style="
            background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
            border: 1px solid #bae6fd;
            border-radius: 12px;
            padding: 1rem 1.25rem;
            margin-bottom: 1rem;
        ">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:0.6rem;">
                <div style="width:26px;height:26px;border-radius:50%;background:#0ea5e9;
                            display:flex;align-items:center;justify-content:center;flex-shrink:0;">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/>
                    </svg>
                </div>
                <div style="font-size:0.95rem;font-weight:700;color:#0c4a6e;">Tempo de Votação da Seção</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Horário do 1º voto", _fmt_valor(primeiro))
    with col_b:
        st.metric("Horário do último voto", _fmt_valor(ultimo))
    with col_c:
        st.metric(
            "Tempo total de votação",
            _fmt_horas_min(tempo_total) if pd.notna(tempo_total) else "N/D",
        )


# ──────────────────────────────────────────────────────────────────────────────
# Filtro de Contingência — novo componente
# ──────────────────────────────────────────────────────────────────────────────

def _render_filtro_contingencia(df: pd.DataFrame) -> pd.DataFrame:
    """
    Renderiza o filtro de urnas de contingência: uma caixa de seleção com
    destaque visual simples (borda âmbar, realce ao marcar) e um ícone
    informativo ao lado explicando o que o filtro faz.

    Retorna o DataFrame filtrado (ou o original, se o filtro estiver desligado).
    """
    tem_col_conting = (
        "HOUVE_TROCA_POR_CONTINGENCIA" in df.columns
        or "EH_URNA_CONTINGENCIA" in df.columns
    )
    if not tem_col_conting:
        return df

    # Máscara calculada sobre o total, para exibir a contagem no card mesmo
    # antes de o filtro ser ativado
    mask_total = pd.Series(False, index=df.index)
    if "HOUVE_TROCA_POR_CONTINGENCIA" in df.columns:
        mask_total |= df["HOUVE_TROCA_POR_CONTINGENCIA"].fillna(False).astype(bool)
    if "EH_URNA_CONTINGENCIA" in df.columns:
        mask_total |= df["EH_URNA_CONTINGENCIA"].fillna(False).astype(bool)
    qtd_conting_total = int(mask_total.sum())

    ativo = st.session_state.get("_chk_filtro_contingencia", False)

    st.markdown("<div style='height:0.5rem;'></div>", unsafe_allow_html=True)
    st.markdown(contingency_toggle_css("filtro_conting"), unsafe_allow_html=True)

    col_grupo, _col_spacer = st.columns([2.75, 7.25])
    with col_grupo:
        with st.container(key="filtro_conting"):
            ativo = st.checkbox(
                f"Mostrar apenas urnas de contingência ({qtd_conting_total})",
                value=ativo,
                key="_chk_filtro_contingencia",
                disabled=(qtd_conting_total == 0 and not ativo),
                help=(
                    "Urnas de contingência são seções onde houve troca de equipamento "
                    "em campo — um evento operacionalmente crítico. Marque para isolar "
                    "apenas essas seções."
                ),
            )

    if not ativo:
        return df

    df_filtrado = df[mask_total].copy()

    if df_filtrado.empty:
        st.markdown(
            alert_box(
                "<b>Nenhuma urna de contingência encontrada</b> no filtro atual. "
                "As seções selecionadas não passaram por procedimento de troca de urna. "
                "Desative este filtro para visualizar todas as seções.",
                alert_type="warning",
            ),
            unsafe_allow_html=True,
        )

    return df_filtrado


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

    # ── Filtro de contingência (sempre visível) ──────────────────────────────
    df_secoes = _render_filtro_contingencia(df_secoes)

    # Se após o filtro de contingência não houver dados, parar aqui
    if df_secoes.empty:
        return

    # CORREÇÃO: filtros agregados (strings) e None roteiam para visão geral
    if status_filter is None or status_filter == "Todas" or isinstance(status_filter, str):
        _render_visao_geral(df_secoes)
        st.markdown("<hr style='margin: 3rem 0; border-top: 2px dashed #94A3B8;'>", unsafe_allow_html=True)
        _render_estudo_caso_secao(df_secoes, status_filter)
    elif status_filter in [0, 1, 2, 3, 4]:
        # Níveis 0-4 agora compartilham o mesmo renderer; o nível 4 apenas
        # acrescenta um separador visual extra antes do estudo de caso.
        _render_detalhamento_nivel(df_secoes, status_filter, estado_means or {})
        if status_filter == 4:
            st.markdown("<hr style='margin: 3rem 0; border-top: 2px dashed #dc3545;'>", unsafe_allow_html=True)
        else:
            st.markdown("<hr style='margin: 3rem 0; border-top: 2px dashed #94A3B8;'>", unsafe_allow_html=True)
        _render_estudo_caso_secao(df_secoes, status_filter)
    else:
        # Fallback de segurança
        _render_visao_geral(df_secoes)


# ──────────────────────────────────────────────────────────────────────────────
# Visão 1 — Comparação entre todos os níveis
# ──────────────────────────────────────────────────────────────────────────────

def _render_visao_geral(df: pd.DataFrame) -> None:
    st.markdown(
        section_header("Visão por Nível de Criticidade", "Métricas operacionais comparadas entre todos os níveis de criticidade."),
        unsafe_allow_html=True,
    )

    col_v1, col_v2 = st.columns(2)

    with col_v1:
        _chart_title("Média de Timeout de Biometria")
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
                info_card("Compara o número médio de timeouts de biometria e o tempo médio perdido com isso em cada nível de criticidade.")
                st.plotly_chart(fig, width='stretch')
                del m_timeout, fig

    with col_v2:
        _chart_title("Média de Inatividade do Eleitor")
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
                info_card("Compara o tempo médio de inatividade do eleitor na urna entre os níveis de criticidade.")
                st.plotly_chart(fig, width='stretch')
                del m_inat, fig

    col_p1, col_p2 = st.columns(2)

    with col_p1:
        _chart_title("Distribuição de PCDs por Status")
        if "QTD_PCD" not in df.columns:
            st.info("Coluna QTD_PCD não disponível.")
        else:
            pcd_sum = df.groupby("STATUS")["QTD_PCD"].sum().dropna()
            if pcd_sum.empty:
                st.info("Nenhum dado de PCD disponível.")
            else:
                fig = donut_chart(
                    pd.DataFrame({
                        "Status": [STATUS_LABELS.get(int(s), f"Nível {int(s)}") for s in pcd_sum.index],
                        "Quantidade": pcd_sum.values,
                    }),
                    label_col="Status",
                    value_col="Quantidade",
                    title=None,
                    color_map={STATUS_LABELS.get(int(s), f"Nível {int(s)}"): STATUS_PALETTE.get(int(s), "#6c757d") for s in pcd_sum.index},
                    height=350,
                )
                info_card("Mostra como o total de eleitores com deficiência (PCD) atendidos se distribui entre os níveis de criticidade.")
                st.plotly_chart(fig, width='stretch')
                del pcd_sum, fig

    with col_p2:
        _chart_title("Média de Teclas Indevidas")
        if "TECLA_INDEVIDA" not in df.columns:
            st.info("Coluna TECLA_INDEVIDA não disponível.")
        else:
            m_teclas = df.groupby("STATUS")["TECLA_INDEVIDA"].mean().dropna()
            if m_teclas.empty:
                st.info("Nenhum dado de teclas indevidas disponível.")
            else:
                y_labels = [STATUS_LABELS.get(int(s), f"Nível {int(s)}") for s in m_teclas.index]
                if "TEMPO_TECLA_INDEVIDA_SEG" in df.columns:
                    m_tempo_teclas = (
                        df.groupby("STATUS")["TEMPO_TECLA_INDEVIDA_SEG"]
                        .mean()
                        .reindex(m_teclas.index)
                    )
                    text_teclas = [
                        f"{v:.2f} ocorr.<br>{_fmt_min_sec(t)}"
                        for v, t in zip(m_teclas.values, m_tempo_teclas.values)
                    ]
                    del m_tempo_teclas
                else:
                    # Sem coluna de tempo — mostra apenas as ocorrências.
                    # Antes aqui havia _fmt_min_sec(v), o que formatava a
                    # quantidade de ocorrências como se fosse tempo (ex.:
                    # "5 ocorr. ~5s" — incorreto e confuso).
                    text_teclas = [
                        f"{v:.2f} ocorr."
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
                info_card("Compara a média de teclas inválidas digitadas em cada nível de criticidade.")
                st.plotly_chart(fig, width='stretch')
                del m_teclas, fig

    gc.collect()


# ──────────────────────────────────────────────────────────────────────────────
# Visão 2 — Diagnóstico detalhado de um nível específico (0–4)
# ──────────────────────────────────────────────────────────────────────────────

def _render_detalhamento_nivel(
    df: pd.DataFrame,
    status_filter: int,
    estado_means: dict,
) -> None:
    st.markdown(
        section_header("Diagnóstico Detalhado por Nível", "Análise comparativa do nível selecionado contra a média estadual (todas as seções críticas)."),
        unsafe_allow_html=True,
    )

    titulo = f"Detalhamento: {STATUS_LABELS.get(status_filter, f'Nível {status_filter}')}"
    st.markdown(
        f"<h3 style='color: #1a3a5c; font-weight: 600; margin-bottom: 1rem;'>{titulo}</h3>",
        unsafe_allow_html=True,
    )

    # ── KPIs com delta vs média estadual ─────────────────────────────────────
    # O acesso a col_tempo usa df.get(..., pd.Series([0])) para ser robusto
    # contra colunas eventualmente ausentes — padrão antes restrito ao nível 4,
    # agora uniformizado para todos os níveis.
    def _get_metrics(col_ocorr: str, col_tempo: str | None = None):
        m_niv = df[col_ocorr].mean() if col_ocorr in df.columns else 0
        m_est = estado_means.get(col_ocorr, m_niv)
        delta = ((m_niv / m_est) - 1) * 100 if m_est > 0 else 0
        tempo_str = ""
        if col_tempo:
            seg = df.get(col_tempo, pd.Series([0])).mean()
            if pd.notna(seg):
                tempo_str = f"Tempo total: {_fmt_min_sec(seg)}"
        return m_niv, delta, tempo_str

    col_k1, col_k2, col_k3 = st.columns(3)

    v, d, t = _get_metrics("INATIVIDADE", "TTPISEC")
    m_est_inat = estado_means.get("INATIVIDADE", 0)
    with col_k1:
        st.metric(
            "Inatividade",
            f"{v:.1f} ocorr.",
            f"{d:+.1f}% vs Estado",
            delta_color="inverse",
            help=f"Média do Estado: {m_est_inat:.2f} ocorrências por seção.",
        )
        st.caption(t)

    v, d, t = _get_metrics("TIMEOUT_BIOMETRIA", "TPBSEC")
    m_est_time = estado_means.get("TIMEOUT_BIOMETRIA", 0)
    with col_k2:
        st.metric(
            "Timeout Biometria",
            f"{v:.1f} ocorr.",
            f"{d:+.1f}% vs Estado",
            delta_color="inverse",
            help=f"Média do Estado: {m_est_time:.2f} ocorrências por seção.",
        )
        st.caption(t)

    v, d, _ = _get_metrics("TECLA_INDEVIDA")
    m_est_tecla = estado_means.get("TECLA_INDEVIDA", 0)
    with col_k3:
        st.metric(
            "Teclas Indevidas",
            f"{v:.2f} ocorr.",
            f"{d:+.1f}% vs Estado",
            delta_color="inverse",
            help=f"Média do Estado: {m_est_tecla:.2f} ocorrências por seção.",
        )
        st.caption("Erros de digitação")

    st.write("<br>", unsafe_allow_html=True)

    # ── Perfis demográficos ───────────────────────────────────────────────────
    # Cor dos gráficos demográficos: usa a paleta oficial para níveis 0–3
    # e tons mais escuros para o nível 4 (Super Crítica) — mantém o realce
    # visual que antes só existia no renderer dedicado.
    cor_demografico_idade = "#1b5e20" if status_filter == 4 else STATUS_PALETTE.get(status_filter, "#0EA5E9")
    cor_demografico_esc   = "#0d47a1" if status_filter == 4 else STATUS_PALETTE.get(status_filter, "#0EA5E9")
    sufixo_titulo = " (Total Nível 4)" if status_filter == 4 else ""

    col_d1, col_d2 = st.columns(2)

    with col_d1:
        _chart_title(f"Perfil por Faixa Etária{sufixo_titulo}")
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
                    marker_color=cor_demografico_idade,
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
                info_card("Mostra quantos eleitores de cada faixa etária votaram nas seções deste nível de criticidade.")
                st.plotly_chart(fig, width='stretch')
                del sums, fig

    with col_d2:
        _chart_title(f"Perfil por Escolaridade{sufixo_titulo}")
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
                    marker_color=cor_demografico_esc,
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
                info_card("Mostra a distribuição de eleitores por grau de escolaridade nas seções deste nível de criticidade.")
                st.plotly_chart(fig, width='stretch')
                del sums_esc, fig

    # ── Proporção PCD ─────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    _, col_pcd, _ = st.columns([1, 2, 1])
    with col_pcd:
        _chart_title(f"Proporção de Eleitores PCD{sufixo_titulo}")
        cols_idade_all = [c for c in df.columns if "IDADE_" in c]
        if not cols_idade_all:
            st.info("Dados de idade não disponíveis para cálculo de PCD.")
        else:
            total_votos = df[cols_idade_all].sum().sum()
            qtd_pcd = df.get("QTD_PCD", pd.Series([0])).sum()
            # Cores do donut PCD: nível 4 mantém o par vermelho/oliva usado
            # anteriormente; demais níveis usam o padrão vermelho/cinza.
            cor_pcd = "#d62728" if status_filter == 4 else "#EF4444"
            cor_nao_pcd = "#bcbd22" if status_filter == 4 else "#CBD5E1"
            fig = donut_chart(
                pd.DataFrame({
                    "Categoria": ["PCD", "Não PCD"],
                    "Quantidade": [qtd_pcd, total_votos - qtd_pcd],
                }),
                label_col="Categoria",
                value_col="Quantidade",
                title=None,
                color_map={"PCD": cor_pcd, "Não PCD": cor_nao_pcd},
                height=400,
            )
            info_card("Mostra a proporção de eleitores PCD em relação ao total de votantes neste nível de criticidade.")
            st.plotly_chart(fig, width='stretch')
            del fig, total_votos, qtd_pcd

    gc.collect()


# ──────────────────────────────────────────────────────────────────────────────
# Visão 3 — Estudo de caso por seção
# ──────────────────────────────────────────────────────────────────────────────
# OBS: A antiga função `_render_nivel4` foi removida — era uma cópia
# quase idêntica de `_render_detalhamento_nivel` com leves diferenças
# visuais (cores e títulos). Agora ambos os casos são cobertos pelo
# mesmo renderer, parametrizado por `status_filter`.


# ──────────────────────────────────────────────────────────────────────────────
# Visão 4 — Estudo de caso por seção
# ──────────────────────────────────────────────────────────────────────────────

def _titulo_contexto(status_filter) -> str:
    """Rótulo amigável do filtro atual, usado nos títulos do estudo de caso."""
    if status_filter is None:
        return "Todas as Seções Críticas"
    if isinstance(status_filter, str):
        return status_filter
    return STATUS_LABELS.get(status_filter, f"Nível {status_filter}")


def _render_estudo_caso_secao(df: pd.DataFrame, status_filter=None) -> None:
    contexto = _titulo_contexto(status_filter)
    cor_tema = (
        STATUS_PALETTE.get(status_filter, "#EF4444")
        if isinstance(status_filter, int)
        else "#EF4444"
    )

    st.markdown(f"""
        <div class="section-header"><h2>Estudo de Caso: {contexto}</h2></div>
        <div class="section-desc">Investigação individualizada de uma seção específica dentro deste filtro.</div>
    """, unsafe_allow_html=True)

    if df.empty:
        st.markdown(f"""
            <div class="alert-box alert-success">
                <b>Resultado positivo:</b> Não há seções em "{contexto}" neste cenário.
            </div>
        """, unsafe_allow_html=True)
        return

    df_sorted = (
        df.sort_values("ATRASO_FILA_MINUTOS", ascending=False)
        if "ATRASO_FILA_MINUTOS" in df.columns
        else df
    )

    st.markdown(f"""
        <div class="alert-box alert-danger" style="border-left-color:{cor_tema};">
            <b>Atenção:</b> Foram encontradas <b>{len(df_sorted)}</b> seções em "{contexto}".
            Selecione uma abaixo para investigação detalhada.
        </div>
    """, unsafe_allow_html=True)

    opcoes = []
    for idx, row in df_sorted.iterrows():
        atraso = f" | Atraso: {row.get('ATRASO_FILA_MINUTOS', 0):.0f} min"
        conting = " [Contingência]" if row.get("HOUVE_TROCA_POR_CONTINGENCIA", False) or row.get("EH_URNA_CONTINGENCIA", False) else ""
        opcoes.append((idx, f"{row['NM_MUNICIPIO']} (Z: {row['NR_ZONA']} - S: {row['NR_SECAO']}){atraso}{conting}"))

    idx_sel = st.selectbox(
        "Selecione a Urna (ordenado do maior para o menor atraso):",
        options=[op[0] for op in opcoes],
        format_func=lambda x: next(op[1] for op in opcoes if op[0] == x),
        key=f"_estudo_caso_select_{contexto}",
    )

    urna = df_sorted.loc[idx_sel]
    cols_idade = [c for c in df_sorted.columns if c.startswith("IDADE_") and "Inválido" not in c]
    cols_esc = [c for c in df_sorted.columns if c.startswith("ESC_")]

    # ── MELHORIA: extrair modelo de urna do prontuário ──────────────────────
    # Defesa em profundidade: se a coluna "modelo" vier vazia (pode acontecer
    # em seções de contingência, onde há 2 urnas para a mesma seção), caímos
    # de volta para o modelo da urna principal/contingência, que é o mesmo
    # dado já exibido logo abaixo no bloco de Contingência.
    modelo_urna = urna.get("modelo", None)
    if _vazio(modelo_urna):
        modelo_urna = urna.get("MODELO_URNA_PRINCIPAL")
    if _vazio(modelo_urna):
        modelo_urna = urna.get("MODELO_URNA")
    if _vazio(modelo_urna):
        modelo_urna = urna.get("MODELO_URNA_PAR_CONTINGENCIA")
    if _vazio(modelo_urna):
        modelo_urna = "Não identificado"
    else:
        modelo_urna = str(modelo_urna)

    st.markdown(f"""
        <div style="background: #fee2e2; padding: 1rem 1.25rem; border-radius: 8px;
                    border-left: 4px solid {cor_tema}; margin-bottom: 1.25rem;">
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

    # ── Contingência (se aplicável) + Tempo de votação ───────────────────────
    _render_bloco_contingencia(urna)
    _render_bloco_tempo_votacao(urna)
    st.write("<br>", unsafe_allow_html=True)

    # ── LINHA 1: Ocorrências Operacionais + Distribuição de Tempos ──────────
    col1, col2 = st.columns(2)

    with col1:
        _chart_title("Ocorrências Operacionais")
        labels_op, tempos_op, ocorr_op, cores_op = [], [], [], []

        if "TPBSEC" in urna.index and pd.notna(urna["TPBSEC"]):
            labels_op.append("Timeout Biometria")
            tempos_op.append(urna["TPBSEC"])
            ocorr_op.append(urna.get("TIMEOUT_BIOMETRIA", 0))
            cores_op.append("#F97316")

        if "TTPISEC" in urna.index and pd.notna(urna["TTPISEC"]):
            labels_op.append("Inatividade")
            tempos_op.append(urna["TTPISEC"])
            ocorr_op.append(urna.get("INATIVIDADE", 0))
            cores_op.append("#0EA5E9")

        teclas_val = urna.get("TECLA_INDEVIDA", 0)
        if pd.notna(teclas_val):
            tempo_teclas_real = urna.get("TEMPO_TECLA_INDEVIDA_SEG", None)
            if tempo_teclas_real is None or pd.isna(tempo_teclas_real):
                tempo_teclas_real = teclas_val * 1.0
            labels_op.append("Teclas Indevidas")
            tempos_op.append(tempo_teclas_real)
            ocorr_op.append(teclas_val)
            cores_op.append("#EF4444")

        if labels_op:
            textos = [
                f"{int(o)} ocorr.<br>{_fmt_min_sec(t)}"
                for o, t in zip(ocorr_op, tempos_op)
            ]
            fig = go.Figure(go.Bar(
                x=labels_op, y=tempos_op,
                marker_color=cores_op,
                text=textos, textposition="outside",
            ))
            fig = apply_base_layout(fig, height=350)
            fig.update_layout(
                yaxis=dict(title="Tempo acumulado (segundos)", tickfont=dict(color="black", size=13)),
                xaxis=dict(tickfont=dict(color="black", size=13)),
            )
            info_card("Mostra o tempo total acumulado por tipo de evento operacional registrado nesta seção.")
            st.plotly_chart(fig, width='stretch')
            del fig
        else:
            st.info("Dados de ocorrências não disponíveis para esta seção.")

    with col2:
        _chart_title("Distribuição de Tempos — Seção Selecionada")

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
            tempo_teclas_real = urna.get("TEMPO_TECLA_INDEVIDA_SEG", None)
            if tempo_teclas_real is None or pd.isna(tempo_teclas_real):
                tempo_teclas_real = teclas_val * 1.0
            tempos_data.append(tempo_teclas_real)
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
            info_card("Compara o tempo gasto com biometria e com teclas indevidas nesta seção específica.")
            st.plotly_chart(fig, width='stretch')
            del fig
        else:
            st.info("Dados de tempo não disponíveis para esta seção.")

    # ── LINHA 2: Faixa Etária + Escolaridade ────────────────────────────────
    st.write("<br>", unsafe_allow_html=True)
    col3, col4 = st.columns(2)

    with col3:
        _chart_title("Faixa Etária")
        vals_idade = [urna.get(c, 0) for c in cols_idade]
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
        info_card("Mostra quantos eleitores de cada faixa etária votaram nesta seção, com o percentual sobre o total.")
        st.plotly_chart(fig, width='stretch')
        del fig, vals_idade

    with col4:
        _chart_title("Escolaridade")
        vals_esc = [urna.get(c, 0) for c in cols_esc]
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
        info_card("Mostra a distribuição de eleitores por escolaridade nesta seção, com o percentual sobre o total.")
        st.plotly_chart(fig, width='stretch')
        del fig, vals_esc

    # ── LINHA 3: Proporção PCD + Comparativo de Tempos ──────────────────────
    st.write("<br>", unsafe_allow_html=True)
    col5, col6 = st.columns(2)

    with col5:
        _chart_title("Proporção PCD")
        total_el = sum(urna.get(c, 0) for c in cols_idade)
        pcd = urna.get("QTD_PCD", 0)
        fig = donut_chart(
            pd.DataFrame({
                "Categoria": ["PCD", "Não PCD"],
                "Quantidade": [pcd, total_el - pcd],
            }),
            label_col="Categoria",
            value_col="Quantidade",
            title=None,
            color_map={"PCD": "#EF4444", "Não PCD": "#CBD5E1"},
            height=350,
        )
        info_card("Mostra a proporção de eleitores PCD em relação ao total de votantes nesta seção.")
        st.plotly_chart(fig, width='stretch')
        del fig, total_el, pcd

    with col6:
        _chart_title("Comparativo de Tempos — Seção vs Estado")

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
            tempo_teclas_real = urna.get("TEMPO_TECLA_INDEVIDA_SEG", None)
            if tempo_teclas_real is None or pd.isna(tempo_teclas_real):
                tempo_teclas_real = teclas_val * 1.0
            comp_labels.append("Teclas Indevidas")
            comp_secao.append(tempo_teclas_real)
            if "TEMPO_TECLA_INDEVIDA_SEG" in df_sorted.columns:
                estado_tecla = df_sorted["TEMPO_TECLA_INDEVIDA_SEG"].mean()
            else:
                estado_tecla = (
                    df_sorted["TECLA_INDEVIDA"].mean() if "TECLA_INDEVIDA" in df_sorted.columns else 0
                )
            comp_estado.append(estado_tecla)
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
                name=f"Média {contexto}",
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
            info_card("Compara os tempos operacionais desta seção com a média do estado para o mesmo nível de criticidade.")
            st.plotly_chart(fig, width='stretch')
            del fig
        else:
            st.info("Dados insuficientes para comparativo de tempos.")

    del df_sorted, urna
    gc.collect()
