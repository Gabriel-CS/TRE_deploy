from __future__ import annotations

import html
import re

import streamlit as st

# ──────────────────────────────────────────────────────────────────────────────
# Utilitário interno — o parser Markdown do Streamlit trata qualquer linha
# indentada com 4+ espaços como um bloco de código, mesmo dentro de
# st.markdown(..., unsafe_allow_html=True). Como as funções abaixo montam HTML
# a partir de f-strings triplas (que herdam a indentação do código-fonte),
# isso fazia o HTML "vazar" como texto puro em vez de renderizar. Esta função
# remove quebras de linha + espaços de indentação antes de devolver o HTML,
# eliminando o gatilho do bloco de código.
# ──────────────────────────────────────────────────────────────────────────────

_LEADING_WS_RE = re.compile(r"\n[ \t]*")


def _flatten(fragment: str) -> str:
    """Remove indentação/quebras de linha que confundem o parser Markdown."""
    return _LEADING_WS_RE.sub("", fragment).strip()

# ──────────────────────────────────────────────────────────────────────────────
# Botão informativo interativo — um ícone "ⓘ" que, ao passar o cursor por cima,
# revela um tooltip explicando o que o gráfico/painel logo abaixo representa.
# Puramente CSS (sem JS), reutilizado em todos os gráficos do dashboard.
# ──────────────────────────────────────────────────────────────────────────────

# CSS do tooltip flattenizado (sem quebras de linha) para embutir no markup.
# Usar _flatten garante que o parser Markdown do Streamlit não trate
# nenhuma linha como bloco de código.
_TOOLTIP_CSS_FLAT = _flatten("""\
<style>
.info-tip-wrap {
display: flex;
justify-content: flex-start;
margin: 0 0 0.3rem 0;
}
.info-tip-btn {
position: relative;
display: inline-flex;
align-items: center;
justify-content: center;
width: 20px;
height: 20px;
border-radius: 50%;
background: var(--color-surface-2, #f1f5f9);
border: 1px solid var(--color-border, #e2e8f0);
color: var(--color-brand, #0072B2);
font-size: 0.72rem;
font-weight: 700;
cursor: help;
user-select: none;
transition: background 0.15s ease, transform 0.15s ease;
}
.info-tip-btn:hover {
background: var(--color-brand, #0072B2);
color: #ffffff;
transform: scale(1.08);
}
.info-tip-box {
visibility: hidden;
opacity: 0;
position: absolute;
bottom: 135%;
left: 50%;
transform: translateX(-25%) translateY(4px);
background: var(--color-ink, #0f172a);
color: #f8fafc;
text-align: left;
border-radius: 8px;
padding: 0.55rem 0.75rem;
font-size: 0.74rem;
font-weight: 400;
line-height: 1.4;
width: max-content;
max-width: 260px;
z-index: 9999;
box-shadow: 0 10px 28px rgba(15, 23, 42, 0.28);
transition: opacity 0.15s ease, transform 0.15s ease;
pointer-events: none;
}
.info-tip-box::after {
content: "";
position: absolute;
top: 100%;
left: 25%;
transform: translateX(-50%);
border-width: 5px;
border-style: solid;
border-color: var(--color-ink, #0f172a) transparent transparent transparent;
}
.info-tip-btn:hover .info-tip-box {
visibility: visible;
opacity: 1;
transform: translateX(-25%) translateY(0);
}
</style>
""")


def info_card(texto: str, icon: str = "ⓘ") -> None:
    """
    Renderiza um ícone "ⓘ" com tooltip explicativo.

    O <style> é embutido no mesmo st.markdown do markup para que o
    Streamlit nunca separe o CSS do HTML durante o diff de rerun
    (toggling de checkboxes, filtros, etc.). Sem isso, o <style> era
    removido e os tooltips perdiam visibility:hidden, vazando texto.
    """
    texto_seguro = html.escape(texto)
    markup = (
        _TOOLTIP_CSS_FLAT
        + '<div class="info-tip-wrap">'
        + '<span class="info-tip-btn">' + icon
        + '<span class="info-tip-box">' + texto_seguro + '</span>'
        + '</span>'
        + '</div>'
    )
    st.markdown(markup, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────────────────────
# Section Header — título de seção limpo e padronizado
# ──────────────────────────────────────────────────────────────────────────────

def section_header(title: str, description: str = "") -> str:
    """
    Retorna HTML para um cabeçalho de seção limpo, com título e descrição opcional.
    Substitui os múltiplos st.markdown() repetidos em cada função de render.
    """
    desc_html = f'<div class="section-desc">{html.escape(description)}</div>' if description else ""
    return _flatten(f"""
        <div class="section-header"><h2>{html.escape(title)}</h2></div>
        {desc_html}
    """)


# ──────────────────────────────────────────────────────────────────────────────
# Metric Card Row — cards horizontais de KPI compactos
# ──────────────────────────────────────────────────────────────────────────────

def metric_card_row(metrics: list[dict]) -> str:
    """
    Gera uma linha de cards de métricas compactos (modelo, seções, votantes).

    Parameters
    ----------
    metrics : lista de dicts com chaves:
        - modelo: nome do modelo (ex: "UE2020")
        - cor: cor hex do modelo
        - secoes: quantidade de seções
        - pct_secoes: percentual de seções (float 0-100)
        - votantes: quantidade de votantes
        - pct_votantes: percentual de votantes (float 0-100)
        - specs: lista opcional de tuplas (rótulo, valor) com as configurações
          técnicas do modelo, exibida em tooltip ao passar o mouse sobre o
          nome do modelo (substitui a antiga legenda no topo da aba)
    """
    css = _flatten("""
        <style>
        .metric-row { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:1.5rem; }
        .metric-card {
            flex:1; min-width:180px; background:var(--color-surface,#ffffff);
            border:1px solid var(--color-border,#e2e8f0); border-radius:var(--radius-card,12px);
            padding:0.85rem 1rem 0.75rem; box-shadow:var(--shadow-card,0 1px 4px rgba(15,23,42,0.05));
            transition:box-shadow 0.15s ease, transform 0.15s ease;
        }
        .metric-card:hover { box-shadow:0 4px 14px rgba(15,23,42,0.09); transform:translateY(-1px); }
        .metric-card-head { display:flex; align-items:center; gap:7px; margin-bottom:0.65rem; }
        .metric-card-dot { width:10px; height:10px; border-radius:3px; flex-shrink:0; }
        .metric-card-name-wrap { position:relative; display:inline-flex; }
        .metric-card-name {
            font-size:0.8rem; font-weight:700; color:var(--color-ink-mid,#334155); letter-spacing:0.01em;
        }
        .metric-card-name.has-specs {
            cursor:help; border-bottom:1px dotted var(--color-ink-muted,#94a3b8);
        }
        .metric-card-tooltip {
            visibility:hidden; opacity:0;
            position:absolute; z-index:99; top:130%; left:0;
            width:max-content; max-width:280px;
            background-color:var(--color-ink,#0f172a); color:#f8fafc;
            border-radius:var(--radius-sm,8px); padding:10px 14px;
            font-size:0.74rem; font-weight:500; line-height:1.55;
            text-align:left; white-space:normal;
            box-shadow:0 10px 25px rgba(15,23,42,0.25);
            transition:opacity 0.18s ease, top 0.18s ease;
            pointer-events:none;
        }
        .metric-card-tooltip b { color:#7dd3fc; font-weight:700; }
        .metric-card-tooltip::after {
            content:""; position:absolute; bottom:100%; left:14px;
            border-width:6px; border-style:solid;
            border-color:transparent transparent var(--color-ink,#0f172a) transparent;
        }
        .metric-card-name-wrap:hover .metric-card-tooltip,
        .metric-card-name-wrap:focus-within .metric-card-tooltip { visibility:visible; opacity:1; top:120%; }
        .metric-card-stats { display:flex; gap:14px; }
        .metric-card-stat { flex:1; min-width:0; }
        .metric-card-value { font-size:1.15rem; font-weight:800; color:var(--color-ink,#0f172a); line-height:1.1; }
        .metric-card-label { display:flex; align-items:baseline; gap:5px; margin-top:2px; }
        .metric-card-label span:first-child {
            font-size:0.62rem; color:var(--color-ink-muted,#94a3b8); text-transform:uppercase;
            letter-spacing:0.06em; font-weight:600;
        }
        .metric-card-pct {
            font-size:0.62rem; font-weight:700; padding:1px 5px; border-radius:99px;
            background:var(--color-surface-2,#f1f5f9); color:var(--color-ink-mid,#334155);
        }
        .metric-card-track { width:100%; height:4px; border-radius:99px; background:#eef1f5; margin-top:0.65rem; overflow:hidden; }
        .metric-card-fill { height:4px; border-radius:99px; }
        </style>
    """)

    # CSS embutido junto ao HTML — impede que o Streamlit separe
    # o <style> dos cards durante o diff de rerun.
    cards_html = css + ""
    for m in metrics:
        specs = m.get("specs")
        if specs:
            tooltip_lines = "<br>".join(
                f"<b>{html.escape(str(campo))}:</b> {html.escape(str(valor))}" for campo, valor in specs
            )
        else:
            tooltip_lines = "Configuração técnica não disponível para este modelo."

        name_html = _flatten(f"""
            <div class="metric-card-name-wrap" tabindex="0">
                <span class="metric-card-name has-specs">{m['modelo']}</span>
                <div class="metric-card-tooltip"><b style="color:#fff;">{m['modelo']}</b><br>{tooltip_lines}</div>
            </div>
        """)

        cards_html += _flatten(f"""
            <div class="metric-card" style="border-top:3px solid {m['cor']};">
                <div class="metric-card-head">
                    <div class="metric-card-dot" style="background:{m['cor']};"></div>
                    {name_html}
                </div>
                <div class="metric-card-stats">
                    <div class="metric-card-stat">
                        <div class="metric-card-value">{m['secoes']:,}</div>
                        <div class="metric-card-label">
                            <span>seções</span>
                            <span class="metric-card-pct">{m['pct_secoes']:.1f}%</span>
                        </div>
                    </div>
                    <div class="metric-card-stat">
                        <div class="metric-card-value">{m['votantes']:,}</div>
                        <div class="metric-card-label">
                            <span>votantes</span>
                            <span class="metric-card-pct">{m['pct_votantes']:.1f}%</span>
                        </div>
                    </div>
                </div>
                <div class="metric-card-track">
                    <div class="metric-card-fill" style="width:{min(m['pct_secoes'], 100):.1f}%;background:{m['cor']};"></div>
                </div>
            </div>
        """)

    return _flatten(f'<div class="metric-row">{cards_html}</div>')


# ──────────────────────────────────────────────────────────────────────────────
# Alert Box — caixas de alerta estilizadas
# ──────────────────────────────────────────────────────────────────────────────

def alert_box(message: str, alert_type: str = "warning") -> str:
    """
    Gera HTML para uma caixa de alerta estilizada.

    Parameters
    ----------
    message : texto do alerta (pode conter HTML inline para negrito)
    alert_type : tipo do alerta — "danger" | "success" | "warning" | "info"
    """
    styles = {
        "danger": {
            "bg": "#fef2f2",
            "border": "#dc2626",
            "color": "#991b1b",
            "icon": "&#x26A0;",
        },
        "success": {
            "bg": "#f0fdf4",
            "border": "#16a34a",
            "color": "#15803d",
            "icon": "&#x2714;",
        },
        "warning": {
            "bg": "#fffbeb",
            "border": "#d97706",
            "color": "#92400e",
            "icon": "&#x26A0;",
        },
        "info": {
            "bg": "#f0f9ff",
            "border": "#0ea5e9",
            "color": "#0369a1",
            "icon": "&#x2139;",
        },
    }

    s = styles.get(alert_type, styles["info"])
    return _flatten(f"""
        <div style="
            background: {s['bg']};
            border-left: 4px solid {s['border']};
            border-radius: 0 10px 10px 0;
            padding: 1rem 1.25rem;
            margin-bottom: 1rem;
            color: {s['color']};
            font-size: 0.88rem;
            line-height: 1.5;
        ">
            <span style="font-size:1rem;margin-right:0.3rem;">{s['icon']}</span> {message}
        </div>
    """)


# ──────────────────────────────────────────────────────────────────────────────
# Botão de Contingência — toggle em destaque para o filtro de urnas críticas
# ──────────────────────────────────────────────────────────────────────────────

def contingency_toggle_css(container_key: str) -> str:
    """
    CSS simples para destacar a caixa de seleção do filtro de contingência:
    uma borda colorida e leve realce de fundo quando marcada, sem elementos
    extras. Ancorado ao container Streamlit via `st-key-{container_key}`
    (Streamlit >= 1.31).
    """
    return _flatten(f"""
        <style>
        div.st-key-{container_key},
        div.st-key-{container_key} > div,
        div.st-key-{container_key} div[data-testid="stVerticalBlock"],
        div.st-key-{container_key} div[data-testid="stVerticalBlockBorderWrapper"] {{
            width: fit-content !important;
        }}
        div.st-key-{container_key} {{
            display: inline-flex;
            align-items: center;
            background: #fff8e6;
            border: 1px solid #f2d49a;
            border-radius: 6px;
            padding: 0.1rem 0.55rem;
            transition: background 0.15s ease, border-color 0.15s ease;
        }}
        div.st-key-{container_key}:has(input:checked) {{
            background: #fdf0cc;
            border-color: #e8b95e;
        }}
        div.st-key-{container_key} label[data-testid="stWidgetLabel"] p {{
            font-weight: 600;
            font-size: 0.78rem;
            color: #92700f;
            white-space: nowrap;
        }}
        div.st-key-{container_key} div[data-testid="stCheckbox"] {{
            gap: 0.35rem;
        }}
        </style>
    """)