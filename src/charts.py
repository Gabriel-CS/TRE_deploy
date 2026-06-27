from __future__ import annotations

import plotly.graph_objects as go
import plotly.express as px

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
# Gráficos reutilizáveis
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
    Gráfico de barras vertical com uma trace por categoria.
    Cada barra recebe a cor do MODEL_COLOR (quando aplicável) ou a paleta OKABE_ITO.
    A legenda interativa nativa do Plotly é ativada por padrão.
    """
    fig = go.Figure()

    for i, (cat, val) in enumerate(zip(x, y)):
        txt = (
            text[i] if text
            else (f"{val:.1%}" if isinstance(val, float) and val < 1 else str(val))
        )
        cor = MODEL_COLOR.get(str(cat), OKABE_ITO[i % len(OKABE_ITO)])

        fig.add_trace(go.Bar(
            name=str(cat),
            x=[cat],
            y=[val],
            marker_color=cor,
            text=[txt],
            textposition="outside",
            textfont=dict(size=11, color="#222222"),
            width=0.55,
        ))

    fig.update_layout(
        title=title,
        barmode="overlay",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.30,
            xanchor="center", x=0.5,
        ),
        margin=dict(t=50, b=80, l=50, r=20),
    )

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


def bar_chart_horizontal(
    y_labels,
    x_values,
    text=None,
    title: str = "",
    xfmt: str | None = None,
    xrange: list | None = None,
    height: int = 360,
) -> go.Figure:
    """
    Gráfico de barras horizontal com uma trace por categoria.
    Mesma lógica de cores e legenda do bar_chart vertical.
    """
    fig = go.Figure()

    for i, (cat, val) in enumerate(zip(y_labels, x_values)):
        txt = (
            text[i] if text
            else (f"{val:.1%}" if isinstance(val, float) and val < 1 else str(val))
        )
        cor = MODEL_COLOR.get(str(cat), OKABE_ITO[i % len(OKABE_ITO)])

        fig.add_trace(go.Bar(
            name=str(cat),
            y=[cat],
            x=[val],
            orientation="h",
            marker_color=cor,
            text=[txt],
            textposition="outside",
            textfont=dict(size=11, color="#222222"),
            width=0.55,
        ))

    fig.update_layout(
        title=title,
        barmode="overlay",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom", y=-0.30,
            xanchor="center", x=0.5,
        ),
        margin=dict(t=50, b=80, l=50, r=20),
    )

    if xfmt:
        fig.update_layout(xaxis_tickformat=xfmt)
    if xrange:
        fig.update_layout(xaxis_range=xrange)

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
