from __future__ import annotations

import plotly.graph_objects as go
import plotly.express as px

from src.analysis import OKABE_ITO, URN_MODELS

# ──────────────────────────────────────────────────────────────────────────────
# Layout base
# ──────────────────────────────────────────────────────────────────────────────

_LAYOUT_BASE = dict(
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=dict(family="Inter, Segoe UI, sans-serif", color="#444", size=12),
    margin=dict(t=50, b=40, l=50, r=20),
    xaxis=dict(showgrid=False, linecolor="#CCCCCC"),
    yaxis=dict(gridcolor="#EEEEEE", linecolor="#CCCCCC"),
    legend=dict(bgcolor="rgba(255,255,255,0.9)", bordercolor="#CCCCCC", borderwidth=1),
    showlegend=False,
)


def apply_base_layout(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(**_LAYOUT_BASE)
    fig.update_layout(height=height)
    return fig


# ──────────────────────────────────────────────────────────────────────────────
# Gráficos reutilizáveis
# ──────────────────────────────────────────────────────────────────────────────

def bar_chart(
    x, y, text=None, title="", yfmt=None, yrange=None, height=360,
    x_categoryorder: list | None = None,
) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=x, y=y,
        marker_color=OKABE_ITO[:len(x)],
        text=text or [f"{v:.1%}" if isinstance(v, float) and v < 1 else str(v) for v in y],
        textposition="outside",
        textfont=dict(size=11, color="#222"),
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
            linecolor="#CCCCCC",
        ))
    return apply_base_layout(fig, height)


def bar_chart_horizontal(
    y_labels, x_values, text=None, title="", xfmt=None, xrange=None, height=360
) -> go.Figure:
    fig = go.Figure(go.Bar(
        y=y_labels, x=x_values,
        orientation='h',
        marker_color=OKABE_ITO[:len(y_labels)],
        text=text or [f"{v:.1%}" if isinstance(v, float) and v < 1 else str(v) for v in x_values],
        textposition="outside",
        textfont=dict(size=11, color="#222"),
        width=0.55,
    ))
    fig.update_layout(title=title, showlegend=False)
    if xfmt:
        fig.update_layout(xaxis_tickformat=xfmt)
    if xrange:
        fig.update_layout(xaxis_range=xrange)
    return apply_base_layout(fig, height)


def stacked_bar(df_pct, labels, colors, title="", height=420) -> go.Figure:
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
        legend=dict(orientation="h", yanchor="bottom", y=-0.30, xanchor="center", x=0.5),
        margin=dict(t=50, b=80, l=50, r=20),
        showlegend=True,
        xaxis=dict(
            categoryorder="array",
            categoryarray=URN_MODELS,
            showgrid=False,
            linecolor="#CCCCCC",
        ),
    )
    fig.update_layout(yaxis=dict(
        tickformat=".0%", range=[0, 1.0],
        gridcolor="#EEEEEE", linecolor="#CCCCCC"
    ))
    return apply_base_layout(fig, height)