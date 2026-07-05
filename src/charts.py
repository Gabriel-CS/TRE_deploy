from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.analysis import OKABE_ITO, URN_MODELS

# Dicionário de cores por modelo — garantia de consistência visual em todos os gráficos
MODEL_COLOR: dict[str, str] = dict(zip(URN_MODELS, OKABE_ITO))

# ──────────────────────────────────────────────────────────────────────────────
# Layout base — espelha os tokens do design system definidos em app.py
# ──────────────────────────────────────────────────────────────────────────────

_LAYOUT_BASE = dict(
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=dict(family="Inter, Segoe UI, sans-serif", color="#444444", size=12),
    margin=dict(t=50, b=40, l=50, r=20),
    xaxis=dict(showgrid=False, linecolor="#e2e8f0"),
    yaxis=dict(gridcolor="#f1f5f9", linecolor="#e2e8f0"),
    legend=dict(
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor="#e2e8f0",
        borderwidth=1,
    ),
    showlegend=False,
)


def apply_base_layout(fig: go.Figure, height: int = 360) -> go.Figure:
    """Aplica o layout base padronizado ao gráfico e define a altura."""
    fig.update_layout(**_LAYOUT_BASE)
    fig.update_layout(height=height)
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Gráficos reutilizáveis — básicos
# ──────────────────────────────────────────────────────────────────────────────

def bar_chart(
    x,
    y,
    text=None,
    title: str = "",
    yfmt: str | None = None,
    yrange: list | None = None,
    height: int = 360,
    x_categoryorder: list | None = None,
) -> go.Figure:
    """
    Gráfico de barras vertical (trace único, sem legenda redundante — a
    categoria já é identificada pelo eixo X). Cores seguem MODEL_COLOR
    quando a categoria é um modelo de urna conhecido, com fallback para
    a paleta OKABE_ITO.
    """
    cores = [MODEL_COLOR.get(str(cat), OKABE_ITO[i % len(OKABE_ITO)]) for i, cat in enumerate(x)]

    fig = go.Figure(go.Bar(
        x=x, y=y,
        marker_color=cores,
        text=text or [f"{v:.1%}" if isinstance(v, float) and v < 1 else str(v) for v in y],
        textposition="outside",
        textfont=dict(size=11, color="#222222"),
        width=0.55,
    ))
    fig.update_layout(title=title, showlegend=False)

    if yfmt:
        fig.update_layout(yaxis_tickformat=yfmt)
    if yrange:
        fig.update_layout(yaxis_range=yrange)
    if x_categoryorder is not None:
        fig.update_layout(xaxis=dict(
            categoryorder="array",
            categoryarray=x_categoryorder,
            showgrid=False,
            linecolor="#e2e8f0",
        ))

    return apply_base_layout(fig, height)


def bar_chart_with_error(
    x,
    y,
    errors,
    text=None,
    title: str = "",
    yfmt: str | None = None,
    yrange: list | None = None,
    height: int = 360,
    error_suffix: str = "",
) -> go.Figure:
    """
    Gráfico de barras vertical com barra de erro nativa (desvio padrão) —
    a forma padrão em análises estatísticas de mostrar média + variabilidade
    por categoria, mais direta de ler do que texto "média ± DP" embutido no
    rótulo. Mesma paleta de cores e estilo do bar_chart padrão.
    """
    cores = [MODEL_COLOR.get(str(cat), OKABE_ITO[i % len(OKABE_ITO)]) for i, cat in enumerate(x)]
    text_labels = text or [f"{v:.1f}" for v in y]

    fig = go.Figure(go.Bar(
        x=x, y=y,
        marker_color=cores,
        error_y=dict(
            type="data",
            array=list(errors),
            visible=True,
            color="#475569",
            thickness=1.5,
            width=6,
        ),
        text=text_labels,
        textposition="outside",
        textfont=dict(size=11, color="#222222"),
        width=0.55,
        hovertemplate=(
            "<b>%{x}</b><br>Média: %{y:.1f}" + error_suffix +
            "<br>Desvio padrão: %{error_y.array:.1f}" + error_suffix +
            "<extra></extra>"
        ),
    ))
    fig.update_layout(title=title, showlegend=False)

    if yfmt:
        fig.update_layout(yaxis_tickformat=yfmt)
    if yrange:
        fig.update_layout(yaxis_range=yrange)
    else:
        max_val = max((v + (e or 0) for v, e in zip(y, errors)), default=1)
        fig.update_layout(yaxis_range=[0, max_val * 1.3 or 1])

    return apply_base_layout(fig, height)


def stacked_bar(
    df_pct,
    labels: list[str],
    colors: list[str],
    title: str = "",
    height: int = 420,
) -> go.Figure:
    """
    Gráfico de barras empilhadas (100%) por modelo de urna.
    Os rótulos internos só aparecem quando a fatia é visível (> 4%).
    """
    fig = go.Figure()

    for i, col in enumerate(labels):
        if col not in df_pct.columns:
            continue
        vals = df_pct[col].values
        fig.add_trace(go.Bar(
            name=col,
            x=URN_MODELS,
            y=vals,
            marker_color=colors[i % len(colors)],
            text=[f"{v*100:.1f}%" if v > 0.04 else "" for v in vals],
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(size=9, color="white"),
        ))

    fig.update_layout(
        barmode="stack",
        title=title,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.30,
            xanchor="center", x=0.5,
        ),
        margin=dict(t=50, b=80, l=50, r=20),
        showlegend=True,
        xaxis=dict(
            categoryorder="array",
            categoryarray=URN_MODELS,
            showgrid=False,
            linecolor="#e2e8f0",
        ),
    )
    fig.update_layout(yaxis=dict(
        tickformat=".0%",
        range=[0, 1.0],
        gridcolor="#f1f5f9",
        linecolor="#e2e8f0",
    ))

    return apply_base_layout(fig, height)


# ──────────────────────────────────────────────────────────────────────────────
# Gráficos de representatividade — novos tipos visuais
# ──────────────────────────────────────────────────────────────────────────────

def donut_chart(
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    title: str = "",
    color_map: dict[str, str] | None = None,
    height: int = 380,
    show_legend: bool = True,
    hole: float = 0.55,
) -> go.Figure:
    """
    Gráfico de donut (pizza com furo central) para representar proporções
    de um todo. Ideal para "quanto X representa do total".

    Parameters
    ----------
    df : DataFrame com pelo menos duas colunas (rótulo e valor)
    label_col : nome da coluna com os rótulos
    value_col : nome da coluna com os valores numéricos
    color_map : dict opcional mapeando rótulo → cor hex
    hole : tamanho do furo central (0 = pizza cheia, 0.7 = quase vazio)
    """
    cores = None
    if color_map is not None:
        cores = [color_map.get(str(lbl), OKABE_ITO[i % len(OKABE_ITO)]) for i, lbl in enumerate(df[label_col])]

    fig = go.Figure(go.Pie(
        labels=df[label_col],
        values=df[value_col],
        hole=hole,
        marker=dict(
            colors=cores or px.colors.qualitative.Safe,
            line=dict(color="white", width=2),
        ),
        textinfo="percent+label" if len(df) <= 6 else "percent",
        textposition="outside",
        textfont=dict(size=11, color="#333"),
        insidetextfont=dict(size=10, color="white"),
        pull=[0.02] * len(df),
        hovertemplate=(
            "<b>%{label}</b><br>" +
            "Valor: %{value:,}<br>" +
            "Proporção: %{percent}<br>" +
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        title=title,
        showlegend=show_legend,
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
            font=dict(size=11),
        ),
        # Margens maiores em cima/baixo — os rótulos "outside" (nome + %)
        # ocupam espaço vertical extra fora da rosca; com margem curta eles
        # eram cortados pelo container, forçando uma barra de rolagem interna
        # no card do gráfico. Margens generosas garantem que o SVG renderizado
        # caiba inteiro na altura declarada, deixando o gráfico estático.
        margin=dict(t=60, b=60, l=40, r=130),
    )

    # Altura mínima proporcional ao número de fatias, para dar espaço
    # suficiente aos rótulos externos sem precisar de scroll.
    height = max(height, 70 * len(df) + 160)

    # Central label com total
    total = df[value_col].sum()
    fig.add_annotation(
        text=f"<b>{total:,.0f}</b><br>total",
        showarrow=False,
        font=dict(size=14, color="#64748b"),
        x=0.5, y=0.5,
    )

    return apply_base_layout(fig, height)


# ──────────────────────────────────────────────────────────────────────────────
# Bullet Gauge — barras horizontais compactas com escala
# ──────────────────────────────────────────────────────────────────────────────

def bullet_gauge_chart(
    df: pd.DataFrame,
    label_col: str,
    value_col: str,
    title: str = "",
    color_map: dict[str, str] | None = None,
    suffix: str = "%",
    max_val: float | None = None,
    height: int = 380,
) -> go.Figure:
    """
    Indicadores tipo "bullet gauge" — barras horizontais compactas que
    mostram o valor e sua representatividade, um abaixo do outro.
    Ideal para comparar muitos itens de forma compacta.

    Parameters
    ----------
    df : DataFrame com os dados
    label_col : coluna dos rótulos
    value_col : coluna dos valores
    color_map : dict de cores por rótulo
    suffix : sufixo do valor (ex: "%", "s", "min")
    max_val : valor máximo para escala (auto se None)
    """
    if max_val is None:
        max_val = df[value_col].max() * 1.2 if len(df) > 0 else 100

    # Defensive: color_map é opcional — se None, usa fallback da paleta OKABE_ITO.
    color_map = color_map or {}

    fig = go.Figure()

    # Barra de fundo cinza (máximo)
    fig.add_trace(go.Bar(
        y=df[label_col],
        x=[max_val] * len(df),
        orientation="h",
        marker_color="#f1f5f9",
        width=0.4,
        hoverinfo="skip",
        showlegend=False,
    ))

    # Barra de valor colorida
    cores = [color_map.get(str(lbl), OKABE_ITO[i % len(OKABE_ITO)]) for i, lbl in enumerate(df[label_col])]
    fig.add_trace(go.Bar(
        y=df[label_col],
        x=df[value_col],
        orientation="h",
        marker_color=cores,
        width=0.4,
        text=[f"{v:.1f}{suffix}" for v in df[value_col]],
        textposition="outside",
        textfont=dict(size=11, color="#222"),
        hovertemplate=(
            "<b>%{y}</b><br>" +
            f"{value_col}: %{{x:.1f}}{suffix}<br>" +
            "<extra></extra>"
        ),
        showlegend=False,
    ))

    fig.update_layout(
        title=title,
        barmode="overlay",
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Inter, Segoe UI, sans-serif", color="#444", size=12),
        margin=dict(t=50, b=40, l=100, r=80),
        xaxis=dict(
            showgrid=False,
            linecolor="#e2e8f0",
            range=[0, max_val * 1.15],
            ticksuffix=suffix,
        ),
        yaxis=dict(
            showgrid=False,
            linecolor="#e2e8f0",
            categoryorder="total ascending",
            automargin=True,
        ),
        height=height,
    )

    return fig
