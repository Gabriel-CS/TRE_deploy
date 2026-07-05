from __future__ import annotations

import gc
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.analysis import MODEL_COLOR, OKABE_ITO, URN_MODELS
from src.charts import (
    apply_base_layout,
    bar_chart,
    bar_chart_with_error,
    stacked_bar,
    donut_chart,
    bullet_gauge_chart,
)
from src.ui_components import info_card, section_header, metric_card_row

# Caminho do dataset de configurações técnicas por modelo de urna.
CAMINHO_CONFIG_MODELOS = "data/datasets/Tabela_Configuracoes.csv"

# Rótulos amigáveis para as colunas técnicas (ordem de exibição no tooltip)
_CAMPOS_CONFIG: list[str] = [
    "Processador", "Memoria RAM", "Memoria armazenamento interno",
    "Perimetro criptografico na CPU", "Fonte inteligente", "Teclado do TM",
    "Display do TE", "Teclado do TE", "Impressora", "Leitor biometrico", "Bateria",
]
_LABELS_CONFIG: dict[str, str] = {
    "Processador": "Processador",
    "Memoria RAM": "Memória RAM",
    "Memoria armazenamento interno": "Armazenamento",
    "Perimetro criptografico na CPU": "Perímetro criptográfico na CPU",
    "Fonte inteligente": "Fonte inteligente",
    "Teclado do TM": "Teclado do mesário",
    "Display do TE": "Display do eleitor",
    "Teclado do TE": "Teclado do eleitor",
    "Impressora": "Impressora",
    "Leitor biometrico": "Leitor biométrico",
    "Bateria": "Bateria",
}


@st.cache_data(show_spinner=False, ttl=3600)
def _carregar_config_modelos(caminho: str = CAMINHO_CONFIG_MODELOS) -> dict[str, list[tuple[str, str]]]:
    """
    Lê o dataset de configurações técnicas (Tabela_Configuracoes.csv) e monta,
    para cada modelo de urna, a lista de pares (rótulo, valor) prontos para
    renderização na caixa informativa (tooltip) da legenda de modelos.
    """
    if not os.path.exists(caminho):
        return {}
    try:
        df_config = pd.read_csv(caminho)
    except Exception:
        return {}

    df_config = df_config.set_index("Modelo")
    specs: dict[str, list[tuple[str, str]]] = {}
    for modelo, row in df_config.iterrows():
        specs[str(modelo)] = [
            (_LABELS_CONFIG.get(campo, campo), row[campo])
            for campo in _CAMPOS_CONFIG
            if campo in df_config.columns and pd.notna(row.get(campo))
        ]
    return specs


def render_tab_modelo(analise) -> None:
    """Renderiza a aba 'Análise por Modelo de Urna' com visual limpo e gráficos variados."""
    _render_kpi_resumo(analise)
    _render_distribuicao(analise)
    _render_tempos_medios(analise)
    _render_falhas_biometricas(analise)
    _render_inatividade(analise)
    _render_teclas_indevidas(analise)
    _render_escolaridade(analise)
    _render_faixa_etaria(analise)
    _render_pcd(analise)


# ──────────────────────────────────────────────────────────────────────────────
# KPIs de Resumo — Visão rápida antes dos gráficos
# ──────────────────────────────────────────────────────────────────────────────

def _render_kpi_resumo(analise) -> None:
    """Cards de KPI resumidos por modelo para visão rápida.

    Cada card exibe, ao passar o mouse sobre o nome do modelo, as
    configurações técnicas do dataset `Tabela_Configuracoes.csv` — função
    antes desempenhada pela legenda de modelos no topo da aba.
    """
    dist = analise.get_model_distribution()
    total_voters = sum(len(analise.voters[m]) for m in URN_MODELS)
    config_modelos = _carregar_config_modelos()

    metrics = []
    for i, m in enumerate(URN_MODELS):
        if dist["counts"][i] == 0:
            continue
        pct_sec = dist["proportions"][i] * 100
        voters = len(analise.voters[m])
        pct_vot = (voters / total_voters * 100) if total_voters else 0
        metrics.append({
            "modelo": m,
            "cor": MODEL_COLOR.get(m, OKABE_ITO[i % len(OKABE_ITO)]),
            "secoes": dist["counts"][i],
            "pct_secoes": pct_sec,
            "votantes": voters,
            "pct_votantes": pct_vot,
            "specs": config_modelos.get(m),
        })

    if not metrics:
        return

    st.markdown(
        metric_card_row(metrics),
        unsafe_allow_html=True,
    )
    gc.collect()


# ──────────────────────────────────────────────────────────────────────────────
# Componentes Auxiliares
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# Seções individuais — com gráficos de representatividade e design limpo
# ──────────────────────────────────────────────────────────────────────────────

def _render_distribuicao(analise) -> None:
    st.markdown(
        section_header("Distribuição de Modelos", "Proporção e quantidade absoluta de seções por modelo de urna."),
        unsafe_allow_html=True,
    )

    dist = analise.get_model_distribution()
    col1, col2 = st.columns([3, 2])

    with col1:
        # Barra vertical com quantidades absolutas por modelo — mesmo padrão
        # visual do restante do dashboard, com rótulo de contagem + %.
        fig = bar_chart(
            [m for i, m in enumerate(URN_MODELS) if dist["counts"][i] > 0],
            [c for c in dist["counts"] if c > 0],
            text=[f"{v:,}<br>({dist['proportions'][i]*100:.1f}%)" for i, v in enumerate(dist["counts"]) if v > 0],
            title="Total de Seções por Modelo",
            yrange=[0, max(dist["counts"]) * 1.3 or 1],
        )
        info_card(
            "Quantidade absoluta de seções atendidas por cada modelo de urna. "
            "O rótulo de cada barra traz também o percentual que ela representa "
            "no total geral de seções."
        )
        st.plotly_chart(fig, width='stretch')
        del fig

    with col2:
        # Donut chart: proporção percentual
        df_donut = pd.DataFrame({
            "Modelo": [m for i, m in enumerate(URN_MODELS) if dist["counts"][i] > 0],
            "Seções": [c for c in dist["counts"] if c > 0],
        })
        fig = donut_chart(
            df_donut,
            label_col="Modelo",
            value_col="Seções",
            title="Proporção de Seções (%)",
            color_map=MODEL_COLOR,
        )
        info_card(
            "Cada fatia representa a fatia (%) do total de seções atendida por um "
            "modelo de urna. O número no centro é o total geral de seções somando "
            "todos os modelos."
        )
        st.plotly_chart(fig, width='stretch')
        del fig, df_donut

    del dist
    gc.collect()


def _render_tempos_medios(analise) -> None:
    st.markdown(
        section_header("Distribuição de Tempo Médio Operacional", "Composição em segundos do tempo médio por eleitor (Fila, Autenticação e Inatividade) por modelo."),
        unsafe_allow_html=True,
    )

    fila = analise.get_queue_times()
    auth = analise.get_auth_duration()
    inat = analise.get_inactivity_times()

    # Calcular totais para representatividade
    totals = [f + a + ii for f, a, ii in zip(fila["means"], auth["means"], inat["means"])]
    total_geral = sum(totals)

    col1, col2 = st.columns([3, 2])

    with col1:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=URN_MODELS, y=inat["means"], name="T. Inatividade",
            marker_color="#E69F00",
            text=[f"{v:.1f}s" if v > 0 else "" for v in inat["means"]],
            textposition="inside", insidetextanchor="middle",
        ))
        fig.add_trace(go.Bar(
            x=URN_MODELS, y=auth["means"], name="T. Autenticação",
            marker_color="#009E73",
            text=[f"{v:.1f}s" if v > 0 else "" for v in auth["means"]],
            textposition="inside", insidetextanchor="middle",
        ))
        fig.add_trace(go.Bar(
            x=URN_MODELS, y=fila["means"], name="T. Fila",
            marker_color="#56B4E9",
            text=[f"{v:.1f}s" if v > 0 else "" for v in fila["means"]],
            textposition="inside", insidetextanchor="middle",
        ))

        fig = apply_base_layout(fig, height=450)
        fig.update_layout(
            barmode="stack",
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
            showlegend=True,
            xaxis=dict(categoryorder="array", categoryarray=URN_MODELS),
            yaxis=dict(title="Tempo Médio Total (segundos)"),
        )
        info_card(
            "Cada barra é a soma do tempo médio (em segundos) gasto nas três "
            "etapas do processo de votação — Fila, Autenticação e Inatividade — "
            "por eleitor de cada modelo de urna. A altura total da barra é o "
            "tempo médio operacional completo daquele modelo."
        )
        st.plotly_chart(fig, width='stretch')
        del fig

    with col2:
        # Bullet gauge: representatividade do tempo de cada modelo no total
        df_gauge = pd.DataFrame({
            "Modelo": URN_MODELS,
            "Tempo Total (s)": totals,
        })
        df_gauge = df_gauge[df_gauge["Tempo Total (s)"] > 0]
        if total_geral > 0:
            df_gauge["% do Total"] = (df_gauge["Tempo Total (s)"] / total_geral * 100).round(1)
            fig = bullet_gauge_chart(
                df_gauge,
                label_col="Modelo",
                value_col="% do Total",
                title="Representatividade do Tempo (%)",
                color_map=MODEL_COLOR,
                suffix="%",
            )
            info_card(
                "A barra colorida mostra, para cada modelo, o percentual que ele "
                "representa no tempo operacional total acumulado (soma de Fila, "
                "Autenticação e Inatividade de todos os modelos). A barra cinza "
                "de fundo indica a escala máxima do gráfico."
            )
            st.plotly_chart(fig, width='stretch')
            del fig
        del df_gauge

    del fila, auth, inat, totals
    gc.collect()


def _render_falhas_biometricas(analise) -> None:
    st.markdown(
        section_header("Falhas Biométricas na Pré-Habilitação", "Proporção de votantes com falha biométrica, entre os que tiveram biometria solicitada."),
        unsafe_allow_html=True,
    )

    bio = analise.get_bio_failure_rates()
    col_bio1, col_bio2 = st.columns([3, 2])

    with col_bio1:
        # Gráfico de barras vertical + linha de referência
        fig = bar_chart(
            URN_MODELS, bio["rates"],
            text=[f"{v*100:.1f}%" for v in bio["rates"]],
            title="Taxa de Falha Biométrica por Modelo", yfmt=".0%", yrange=[0, 1.0],
        )
        # Adicionar linha de média geral
        avg_rate = sum(bio["rates"]) / len([r for r in bio["rates"] if r > 0]) if any(r > 0 for r in bio["rates"]) else 0
        fig.add_hline(
            y=avg_rate,
            line_dash="dash",
            line_color="#94A3B8",
            annotation_text=f"Média geral: {avg_rate*100:.1f}%",
            annotation_position="right",
        )
        info_card(
            "Taxa de falha na leitura biométrica, calculada apenas sobre os "
            "eleitores para os quais a biometria foi solicitada (não sobre o "
            "total de votantes). A linha tracejada marca a média geral entre "
            "os modelos com solicitação de biometria."
        )
        st.plotly_chart(fig, width='stretch')
        del fig

    with col_bio2:
        # Donut com representatividade das falhas no total
        _rows = []
        total_falhas_geral = 0
        # Nem todo dataset traz as colunas de biometria no log consolidado —
        # o filtro de contingência, por exemplo, pode usar um arquivo sem
        # 'bio_solicitada'/'n_falhas_bio'. Sem essa checagem, o acesso direto
        # a essas colunas gerava KeyError e derrubava a aba inteira.
        bio_cols_ausentes = False
        for i, m in enumerate(URN_MODELS):
            vm = analise.voters[m]
            if "bio_solicitada" not in vm.columns or "n_falhas_bio" not in vm.columns:
                bio_cols_ausentes = True
                _rows.append((OKABE_ITO[i], m, "0", "0", 0, 0))
                del vm
                continue
            bio_m = vm[vm["bio_solicitada"] == True]
            n_sol = len(bio_m)
            falhas = int((bio_m["n_falhas_bio"] > 0).sum())
            total_falhas_geral += falhas
            _rows.append((OKABE_ITO[i], m, f"{n_sol:,}", f"{falhas:,}", n_sol, falhas))
            del vm, bio_m

        if total_falhas_geral > 0:
            df_falhas = pd.DataFrame({
                "Modelo": [r[1] for r in _rows if r[5] > 0],
                "Falhas": [r[5] for r in _rows if r[5] > 0],
            })
            fig = donut_chart(
                df_falhas,
                label_col="Modelo",
                value_col="Falhas",
                title="Distribuição das Falhas (%)",
                color_map=MODEL_COLOR,
            )
            info_card(
                "Do total de falhas biométricas registradas (somando todos os "
                "modelos), esta fatia mostra quanto cada modelo concentra."
            )
            st.plotly_chart(fig, width='stretch')
            del fig, df_falhas
        elif bio_cols_ausentes:
            st.info(
                "Dados de biometria (solicitação/falhas) não estão disponíveis "
                "para o filtro selecionado."
            )

    del bio
    gc.collect()


def _render_inatividade(analise) -> None:
    st.markdown(
        section_header("Tempo de Inatividade e Desvio Padrão", "Média e desvio padrão do tempo de inatividade no processo de votação (excluindo zeros)."),
        unsafe_allow_html=True,
    )

    inat = analise.get_inactivity_times()
    col1, col2 = st.columns([3, 2])

    with col1:
        fig = bar_chart_with_error(
            URN_MODELS, inat["means"], inat["stds"],
            text=[f"{m:.1f}s" for m in inat["means"]],
            title="Tempo de Inatividade (média ± DP)",
            error_suffix="s",
        )
        info_card(
            "Barra = tempo médio de inatividade do eleitor na urna, em "
            "segundos, por modelo (excluindo casos com inatividade zero). "
            "A linha vertical no topo de cada barra é o desvio padrão: "
            "quanto mais longa, mais variável é o tempo de inatividade entre "
            "os eleitores daquele modelo."
        )
        st.plotly_chart(fig, width='stretch')
        del fig

    with col2:
        # Bullet gauge com representatividade do tempo de inatividade no total
        total_inat = sum(inat["means"])
        if total_inat > 0:
            df_inat = pd.DataFrame({
                "Modelo": [m for i, m in enumerate(URN_MODELS) if inat["means"][i] > 0],
                "% do Total": [round(inat["means"][i] / total_inat * 100, 1) for i in range(len(URN_MODELS)) if inat["means"][i] > 0],
            })
            fig = bullet_gauge_chart(
                df_inat,
                label_col="Modelo",
                value_col="% do Total",
                title="Representatividade da Inatividade (%)",
                color_map=MODEL_COLOR,
                suffix="%",
            )
            info_card(
                "Percentual que cada modelo contribui para o tempo total de "
                "inatividade acumulado (soma do tempo médio de inatividade de "
                "todos os modelos), somando 100% entre os modelos exibidos."
            )
            st.plotly_chart(fig, width='stretch')
            del fig, df_inat

    del inat
    gc.collect()


def _render_teclas_indevidas(analise) -> None:
    st.markdown(
        section_header("Proporção de Teclas Indevidas", "Parcela do total de teclas indevidas concentrada por modelo."),
        unsafe_allow_html=True,
    )

    inv_keys = analise.get_invalid_keys()
    total_kp = analise.df_log["n_teclas_inv"].sum() if "n_teclas_inv" in analise.df_log.columns else 0
    col1, col2 = st.columns([3, 2])

    with col1:
        fig = bar_chart(
            URN_MODELS, inv_keys["proportions"],
            text=[f"{v*100:.1f}%" for v in inv_keys["proportions"]],
            title="Teclas Indevidas por Modelo", yfmt=".0%", yrange=[0, 1.0],
        )
        info_card(
            "Proporção de teclas inválidas (digitação incorreta) em relação ao "
            "total de teclas digitadas nos votos registrados em cada modelo de "
            "urna."
        )
        st.plotly_chart(fig, width='stretch')
        del fig

    with col2:
        _rows = []
        total_kp_int = int(total_kp)
        for i, m in enumerate(URN_MODELS):
            vm = analise.voters[m]
            if "n_teclas_inv" not in vm.columns:
                _rows.append((OKABE_ITO[i], m, "0", f"{total_kp_int:,}", 0, total_kp_int))
                del vm
                continue
            qtd = int(vm[vm["n_teclas_inv"] > 0]["n_teclas_inv"].sum())
            _rows.append((OKABE_ITO[i], m, f"{qtd:,}", f"{total_kp_int:,}", qtd, total_kp_int))
            del vm

        # Donut com representatividade
        if total_kp_int > 0:
            df_teclas = pd.DataFrame({
                "Modelo": [r[1] for r in _rows if int(r[4]) > 0],
                "Quantidade": [int(r[4]) for r in _rows if int(r[4]) > 0],
            })
            fig = donut_chart(
                df_teclas,
                label_col="Modelo",
                value_col="Quantidade",
                title="Distribuição das Teclas Indevidas (%)",
                color_map=MODEL_COLOR,
            )
            info_card(
                "Do total de teclas indevidas registradas somando todos os "
                "modelos, esta fatia mostra quanto cada modelo concentra."
            )
            st.plotly_chart(fig, width='stretch')
            del fig, df_teclas
        elif "n_teclas_inv" not in analise.df_log.columns:
            st.info(
                "Dados de teclas indevidas não estão disponíveis para o "
                "filtro selecionado."
            )

    del inv_keys, total_kp
    gc.collect()


def _render_escolaridade(analise) -> None:
    st.markdown(
        section_header("Escolaridade", "Distribuição por grau de escolaridade e proporção de baixa escolaridade."),
        unsafe_allow_html=True,
    )

    edu = analise.get_education_distribution()
    low_edu = analise.get_low_education()
    col1, col2 = st.columns([3, 2])

    with col1:
        fig = stacked_bar(
            edu["df_proportions"], edu["labels"],
            px.colors.qualitative.Pastel,
            title="Distribuição por Escolaridade (%)",
        )
        info_card(
            "Cada barra soma 100% e mostra como os eleitores atendidos por "
            "cada modelo se distribuem entre os níveis de escolaridade. "
            "Passe o mouse sobre um segmento para ver o nível e o percentual."
        )
        st.plotly_chart(fig, width='stretch')
        del fig

    with col2:
        # Barra com a proporção de baixa escolaridade por modelo
        df_low = pd.DataFrame({
            "Modelo": URN_MODELS,
            "Baixa Escolaridade (%)": [v * 100 for v in low_edu["proportions"]],
        })
        df_low = df_low[df_low["Baixa Escolaridade (%)"] > 0]
        if not df_low.empty:
            fig = bar_chart(
                df_low["Modelo"].tolist(),
                (df_low["Baixa Escolaridade (%)"] / 100).tolist(),
                text=[f"{v:.1f}%" for v in df_low["Baixa Escolaridade (%)"]],
                title="Baixa Escolaridade por Modelo",
                yfmt=".0%",
                yrange=[0, 1.0],
                x_categoryorder=URN_MODELS,
                height=420,
            )
            info_card(
                "Proporção de eleitores com baixa escolaridade (até o ensino "
                "fundamental incompleto) em relação ao total de eleitores "
                "atendidos por cada modelo de urna."
            )
            st.plotly_chart(fig, width='stretch')
            del fig
        del df_low

    del edu, low_edu
    gc.collect()


def _render_faixa_etaria(analise) -> None:
    st.markdown(
        section_header("Faixa Etária", "Distribuição etária e proporção de eleitores idosos (≥ 60 anos)."),
        unsafe_allow_html=True,
    )

    age = analise.get_age_distribution()
    elderly = analise.get_elderly_proportion()
    col1, col2 = st.columns([3, 2])

    with col1:
        fig = stacked_bar(
            age["df_proportions"], age["groups"],
            px.colors.qualitative.Safe,
            title="Distribuição por Faixa Etária (%)",
        )
        info_card(
            "Cada barra soma 100% e mostra como os eleitores atendidos por "
            "cada modelo se distribuem entre as faixas etárias. Passe o "
            "mouse sobre um segmento para ver a faixa e o percentual."
        )
        st.plotly_chart(fig, width='stretch')
        del fig

    with col2:
        fig = bar_chart(
            URN_MODELS, elderly["proportions"],
            text=[f"{v*100:.1f}%" for v in elderly["proportions"]],
            title="Eleitores Idosos (≥ 60 anos)", yfmt=".0%", yrange=[0, 1.0],
            x_categoryorder=URN_MODELS,
            height=420,
        )
        info_card(
            "Proporção de eleitores idosos (60 anos ou mais) em relação ao "
            "total de eleitores atendidos por cada modelo de urna."
        )
        st.plotly_chart(fig, width='stretch')
        del fig

    del age, elderly
    gc.collect()


def _render_pcd(analise) -> None:
    st.markdown(
        section_header("Eleitores PCD", "Quantidade absoluta, taxa e relação com falhas biométricas."),
        unsafe_allow_html=True,
    )

    pcd = analise.get_pcd_stats()
    col1, col2 = st.columns([1, 1])

    with col1:
        fig = bar_chart(
            URN_MODELS, pcd["totals"],
            text=[f"{v:,}" for v in pcd["totals"]],
            title="Total de Eleitores PCD",
            yrange=[0, max(pcd["totals"]) * 1.25 or 1],
        )
        info_card(
            "Quantidade absoluta de eleitores com deficiência (PCD) atendidos "
            "por cada modelo de urna."
        )
        st.plotly_chart(fig, width='stretch')
        del fig

    with col2:
        fig = bar_chart(
            URN_MODELS, pcd["taxas"],
            text=[f"{v*100:.2f}%" for v in pcd["taxas"]],
            title="Taxa de Eleitores PCD", yfmt=".2%", yrange=[0, 1.0],
        )
        info_card(
            "Taxa de eleitores PCD: percentual de eleitores com deficiência "
            "em relação ao total de votantes atendidos por cada modelo de "
            "urna (diferente do gráfico ao lado, que mostra a quantidade "
            "absoluta)."
        )
        st.plotly_chart(fig, width='stretch')
        del fig

    del pcd
    gc.collect()
