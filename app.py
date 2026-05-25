import gc
import os

import pandas as pd
import streamlit as st

from src.analysis import (
    GRUPOS_ETARIOS,
    MODEL_COLOR,
    OKABE_ITO,
    STATUS_LABELS,
    URN_MODELS,
    UrnasCriticasAnalysis,
)
from src.tab_criticidade import render_tab_criticidade
from src.tab_geo import render_tab_geo
from src.tab_modelo import render_tab_modelo

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DE DADOS  (v2 — sem datasets gigantes, apenas CSVs particionados)
# ═══════════════════════════════════════════════════════════════════════════════

def _nivel_key(status_filter):
    """Converte status_filter (None ou int) para a chave string/int do dict."""
    return "todas as criticas" if status_filter is None else status_filter


DATA_CONFIG: dict[str, dict] = {
    "2022": {
        "niveis": {
            "todas as criticas": "data/output/nivel_criticidade/df_criticas_all_2022.csv",
            0:    "data/output/nivel_criticidade/df_critica_n0_2022.csv",
            1:    "data/output/nivel_criticidade/df_critica_n1_2022.csv",
            2:    "data/output/nivel_criticidade/df_critica_n2_2022.csv",
            3:    "data/output/nivel_criticidade/df_critica_n3_2022.csv",
            4:    "data/output/nivel_criticidade/df_critica_n4_2022.csv",
        },
        "modelos_urnas": {
            "todas as criticas": "data/output/modelos_urnas/df_completas_all_2022.zip",
            0:    "data/output/modelos_urnas/df_completas_n0_2022.zip",
            1:    "data/output/modelos_urnas/df_completas_n1_2022.zip",
            2:    "data/output/modelos_urnas/df_completas_n2_2022.zip",
            3:    "data/output/modelos_urnas/df_completas_n3_2022.zip",
            4:    "data/output/modelos_urnas/df_completas_n4_2022.zip",
        },
    },
    "2018": {
        "niveis": {
            "todas as criticas": "data/output/nivel_criticidade/df_criticas_all_2018.csv",
            0:    "data/output/nivel_criticidade/df_critica_n0_2018.csv",
            1:    "data/output/nivel_criticidade/df_critica_n1_2018.csv",
            2:    "data/output/nivel_criticidade/df_critica_n2_2018.csv",
            3:    "data/output/nivel_criticidade/df_critica_n3_2018.csv",
            4:    "data/output/nivel_criticidade/df_critica_n4_2018.csv",
        },
        "modelos_urnas": {
            "todas as criticas": "data/output/modelos_urnas/df_completas_all_2018.zip",
            0:    "data/output/modelos_urnas/df_completas_n0_2018.zip",
            1:    "data/output/modelos_urnas/df_completas_n1_2018.zip",
            2:    "data/output/modelos_urnas/df_completas_n2_2018.zip",
            3:    "data/output/modelos_urnas/df_completas_n3_2018.zip",
            4:    "data/output/modelos_urnas/df_completas_n4_2018.zip",
        },
    },
}


# Cores associadas aos níveis de criticidade (para UI / popover)
STATUS_COLORS: dict[int, str] = {
    0: "#0EA5E9",  # azul-céu  — sem atraso
    1: "#22C55E",  # verde     — normal
    2: "#EAB308",  # âmbar     — atenção
    3: "#F97316",  # laranja   — crítico
    4: "#EF4444",  # vermelho  — super crítica
}

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DA PÁGINA
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="UFS-TRE | Análise de Urnas Eletrônicas",
    page_icon=":round_pushpin:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ═══════════════════════════════════════════════════════════════════════════════
# TEMA CORPORATIVO MINIMALISTA
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

        /* ── Header principal ─────────────────────────────────────────── */
        .main-header {
            font-weight: 800; color: #0f172a; letter-spacing: -0.03em;
            margin-bottom: 0.15rem; font-size: 2.1rem; line-height: 1.2;
        }
        .sub-header {
            color: #64748b; font-size: 0.9rem; margin-top: 0; margin-bottom: 1.25rem;
            font-weight: 400; letter-spacing: 0.01em;
        }

        /* ── KPI cards ────────────────────────────────────────────────── */
        .kpi-box {
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 14px;
            
            /* ALTERAÇÃO: Aumente o primeiro valor para esticar em Y (ex: de 1.25rem para 2.1rem) */
            padding: 2.1rem 1rem; 
            
            text-align: center;
            box-shadow: 0 1px 4px rgba(15,23,42,0.05), 0 4px 16px rgba(15,23,42,0.04);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            height: 100%;
            position: relative;
            overflow: hidden;
        }
        .kpi-box::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            background: linear-gradient(90deg, #0072B2, #56B4E9);
            border-radius: 14px 14px 0 0;
        }
        .kpi-box:hover { transform: translateY(-3px); box-shadow: 0 8px 24px rgba(15,23,42,0.10); }
        .kpi-label {
            font-size: 0.65rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.1em; color: #94a3b8; margin-bottom: 0.5rem;
        }
        .kpi-value      { font-size: 1.65rem; font-weight: 800; color: #0f172a; line-height: 1.15; }
        .kpi-accent     { color: #0072B2; }
        .kpi-danger     { color: #dc2626; }
        .kpi-success    { color: #059669; }

        /* ── Seções ───────────────────────────────────────────────────── */
        .section-header {
            border-left: 4px solid #0072B2;
            padding-left: 12px;
            margin: 1.75rem 0 0.6rem 0;
        }
        .section-header h2 {
            margin: 0; font-size: 1.05rem; font-weight: 700; color: #0f172a;
            letter-spacing: -0.01em;
        }
        .section-desc {
            font-size: 0.82rem; color: #64748b; margin-bottom: 1rem;
            padding-left: 16px; line-height: 1.5;
        }

        /* ── Mapa ─────────────────────────────────────────────────────── */
        .folium-map {
            border-radius: 14px; overflow: hidden;
            box-shadow: 0 4px 20px rgba(15,23,42,0.10);
            border: 1px solid #e2e8f0;
        }

        /* ── Resumo cards ─────────────────────────────────────────────── */
        .resumo-card {
            border: 1px solid #f1f5f9; border-radius: 10px; padding: 8px 14px;
            margin-bottom: 6px; background: #fafafa;
            display: flex; align-items: center; justify-content: space-between;
            gap: 10px; transition: background 0.15s, border-color 0.15s;
        }
        .resumo-card:hover       { background: #f0f9ff; border-color: #bae6fd; }
        .resumo-dot              { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
        .resumo-nome             { font-size: 0.8rem; font-weight: 600; color: #0f172a; }
        .resumo-metrica-valor    {
            font-size: 0.82rem; font-weight: 700; color: #1e293b;
            font-family: 'SF Mono', 'Fira Code', Monaco, monospace;
        }
        .resumo-metrica-label    {
            font-size: 0.6rem; color: #94a3b8;
            text-transform: uppercase; letter-spacing: 0.3px;
        }

        /* ── Alertas ──────────────────────────────────────────────────── */
        .alert-box     { padding: 1rem 1.25rem; border-radius: 10px; border-left: 4px solid; margin-bottom: 1rem; }
        .alert-danger  { background: #fef2f2; border-color: #dc2626; color: #991b1b; }
        .alert-success { background: #f0fdf4; border-color: #16a34a; color: #15803d; }
        .alert-warning { background: #fffbeb; border-color: #d97706; color: #92400e; }

        /* ── Status badges ────────────────────────────────────────────── */
        .status-badge {
            display: inline-block; padding: 0.2rem 0.65rem; border-radius: 20px;
            font-size: 0.68rem; font-weight: 700; text-transform: uppercase;
            letter-spacing: 0.06em;
        }
        .status-0 { background: #e0f2fe; color: #0369a1; }
        .status-1 { background: #dcfce7; color: #15803d; }
        .status-2 { background: #fef9c3; color: #a16207; }
        .status-3 { background: #fee2e2; color: #991b1b; }
        .status-4 { background: #fee2e2; color: #B91C1C; }

        /* ── Footer ───────────────────────────────────────────────────── */
        .footer {
            margin-top: 3rem; padding-top: 1.5rem; border-top: 1px solid #f1f5f9;
            text-align: center; color: #94a3b8; font-size: 0.78rem;
        }

        /* ── Tabs ─────────────────────────────────────────────────────── */
        .stTabs [data-baseweb="tab-list"] { gap: 6px; }
        .stTabs [data-baseweb="tab"] {
            padding: 9px 22px; font-weight: 600; font-size: 0.85rem;
            border-radius: 8px 8px 0 0; color: #64748b;
            letter-spacing: 0.01em;
        }
        .stTabs [aria-selected="true"] {
            background: #0f172a !important; color: white !important;
        }
    </style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CACHE DE DADOS — ESTRATÉGIA DE MEMÓRIA (apenas CSVs leves por filtro)
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_data(show_spinner=False, max_entries=2, ttl=300)
def _load_csv_cached(path: str) -> pd.DataFrame:
    """Carrega CSV particionado tentando vírgula e ponto-e-vírgula como separadores."""
    import os

    # Primeiro tenta com vírgula (padrão)
    try:
        df = pd.read_csv(path, sep=",", encoding="utf-8")
        # Se só tiver 1 coluna, provavelmente o separador está errado
        if len(df.columns) <= 1:
            raise ValueError("Possivelmente separador incorreto")
    except Exception:
        # Fallback: tenta com ponto-e-vírgula
        df = pd.read_csv(path, sep=";", encoding="utf-8")

    df.columns = df.columns.str.strip()
    return df


@st.cache_data(show_spinner=False, max_entries=4, ttl=1800)
def _count_rows(path: str) -> int:
    """Conta linhas carregando apenas a primeira coluna — extremamente leve."""
    try:
        df = pd.read_csv(path, sep=",", encoding="utf-8", usecols=[0])
        return len(df)
    except Exception:
        return 0


@st.cache_data(show_spinner=False, max_entries=2, ttl=600)
def _load_estado_means(nivel_all_path: str) -> dict[str, float]:
    """Lê apenas 3 colunas do CSV 'all' para calcular médias estaduais."""
    cols = ["TIMEOUT_BIOMETRIA", "INATIVIDADE", "TECLA_INDEVIDA"]
    try:
        df = pd.read_csv(nivel_all_path, sep=";", encoding="utf-8", usecols=cols)
        return {c: float(df[c].mean()) for c in cols}
    except Exception:
        return {}

# ═══════════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════════
col_title, col_info = st.columns([3, 1])
with col_title:
    st.markdown("""
        <div class="main-header">UFS · TRE</div>
        <div class="sub-header">Análise operacional, sociodemográfica e geoespacial das urnas eletrônicas</div>
    """, unsafe_allow_html=True)
with col_info:
    st.markdown(f"""
        <div style="text-align: right; color: #adb5bd; font-size: 0.85rem; margin-top: 0.5rem;">
            <div style="font-weight: 600; color: #495057;">Última atualização</div>
            <div>{pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown(
    "<hr style='margin: 0.2rem 0 1.2rem 0; border: none; border-top: 1px solid #e9ecef;'>",
    unsafe_allow_html=True,
)

# ═══════════════════════════════════════════════════════════════════════════════
# LINHA MESTRA: FILTROS + KPIs GLOBAIS
# ═══════════════════════════════════════════════════════════════════════════════
col_filtros, k1, k2, k3, k4, k5 = st.columns([1.6, 1, 1, 1, 1, 1])

# ── 1. Renderiza os Filtros ────────────────────────────────────────────────────
with col_filtros:
    anos_disponiveis = sorted(DATA_CONFIG.keys())
    ano_selecionado = st.selectbox("Ano eleitoral", anos_disponiveis, index=len(anos_disponiveis) - 1)

    if 'last_ano' not in st.session_state:
        st.session_state['last_ano'] = ano_selecionado

    if st.session_state['last_ano'] != ano_selecionado:
        st.cache_data.clear()
        st.session_state['last_ano'] = ano_selecionado
        st.rerun()

    col_sel, col_btn = st.columns([5, 1])
    with col_sel:
        status_opcoes = {
            "Todas as críticas": None,
            "0 — Sem Atraso":         0,
            "1 — Normal":             1,
            "2 — Atenção":            2,
            "3 — Crítico":            3,
            "4 — Super Crítica":      4,
        }
        status_label = st.selectbox("Status operacional", list(status_opcoes.keys()))
        status_filter = status_opcoes[status_label]
        
    with col_btn:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        import streamlit.components.v1 as _components

        _STATUS_DESC = {
            0: ("Operação fluida, sem atraso significativo.",          "#0EA5E9", "✔", "< 6,48 min"),
            1: ("Atraso leve dentro da margem de tolerância.",         "#22C55E", "↑", "≥ 6,48 min e < 32,15 min"),
            2: ("Atraso moderado com pequenas interrupções no fluxo.", "#EAB308", "⚠", "≥ 32,15 min e < 89,36 min"),
            3: ("Atraso considerável com impacto no tempo de espera.", "#F97316", "✖", "≥ 89,36 min e < 150 min"),
            4: ("Atraso severo. Intervenção necessária.",              "#EF4444", "‼", "≥ 150 min"),
        }

        _items_html = ""
        for lvl, label in STATUS_LABELS.items():
            # CORREÇÃO: Ordem de extração corrigida! (desc, cor, icone, intervalo)
            desc, cor, icon, intervalo = _STATUS_DESC[lvl]
            _items_html += (
                f'<div style="display:flex;gap:9px;align-items:flex-start;margin-bottom:9px;">'
                f'  <div style="flex-shrink:0;width:28px;height:28px;border-radius:50%;'
                f'              background:{cor};color:white;font-size:14px;font-weight:800;'
                f'              display:flex;align-items:center;justify-content:center;">{lvl}</div>'
                f'  <div>'
                f'    <div style="font-size:14px;font-weight:700;color:{cor};margin-bottom:3px;">{icon}&nbsp;{label}</div>'
                f'    <div style="font-size:13px;color:#6b7280;line-height:1.4;">{desc}</div>'
                f'    <div style="font-size:12px;color:#9ca3af;margin-top:3px;'
                f'                font-family:\'SF Mono\',\'Fira Code\',monospace;letter-spacing:0.01em;">'
                f'      ⏱ {intervalo}</div>'
                f'  </div>'
                f'</div>'
            )

        _components.html(f"""<!DOCTYPE html>
        <html><head>
        <style>
          *{{margin:0;padding:0;box-sizing:border-box;font-family:'Inter',sans-serif;}}
          body{{background:transparent;overflow:visible;}}
          #btn{{
            width:40px;height:40px;border-radius:50%;
            background:#ffffff;color:#0f172a;
            font-size:18px;font-weight:800;line-height:40px;
            text-align:center;cursor:pointer;user-select:none;
            box-shadow:0 2px 8px rgba(15,23,42,0.15);
            transition:background .18s,box-shadow .18s;
            display:inline-block;border:1.5px solid #e2e8f0;
          }}
          #btn:hover{{background:#f1f5f9;box-shadow:0 4px 14px rgba(15,23,42,0.12);}}
        </style>
        </head><body>
        <div id="btn">?</div>
        <script>
          var btn = document.getElementById('btn');
          var timer = null;
          var pDoc = window.parent.document;
          
          var oldPanel = pDoc.getElementById('crit-panel-legend');
          if(oldPanel) oldPanel.remove();

          var panel = pDoc.createElement('div');
          panel.id = 'crit-panel-legend';
          panel.innerHTML = `
            <div id="crit-title" style="font-size:12px;font-weight:700;text-transform:uppercase;
              letter-spacing:.1em;color:#94a3b8;padding-bottom:8px;margin-bottom:10px;
              border-bottom:1px solid #f1f5f9;font-family:Inter,sans-serif;">Níveis de Criticidade</div>
            {_items_html}
            <div style="height:3px;background:#e2e8f0;border-radius:2px;margin-top:8px;overflow:hidden;">
              <div id="crit-bar" style="height:100%;width:100%;background:#0072B2;border-radius:2px;
                transition:width 3s linear;"></div>
            </div>`;

          // 1. DIMENSÕES: Largura ampliada e padding reduzido para encaixe
          Object.assign(panel.style, {{
            position:'fixed', zIndex:'2147483647', background:'#fff', border:'1px solid #e2e8f0', 
            borderRadius:'12px', 
            padding:'12px 18px 10px', 
            width:'380px', 
            boxShadow:'0 12px 40px rgba(15,23,42,0.18)', fontFamily:'Inter,sans-serif',
            opacity:'0', transform:'translateY(-8px)',
            transition:'opacity .28s ease, transform .28s ease',
            pointerEvents:'none', display:'none'
          }});

          pDoc.body.appendChild(panel);
          var fill = pDoc.getElementById('crit-bar');

          function showPanel() {{
            var frame = window.frameElement;
            var fr    = frame.getBoundingClientRect();
            var br    = btn.getBoundingClientRect();
            
            panel.style.display = 'block';
            
            // 2. POSICIONAMENTO: 
            // Left: afasta um pouco do botão para a direita
            // Top: Subtrai ~75px para alinhar o topo da caixa com o input de "Ano Eleitoral"
            panel.style.left    = (fr.left + br.left + 50) + 'px'; 
            panel.style.top     = (fr.top  + br.top - 75) + 'px';

            panel.getBoundingClientRect(); 
            panel.style.opacity       = '1';
            panel.style.transform     = 'translateY(0)';
            panel.style.pointerEvents = 'auto';

            fill.style.transition = 'none';
            fill.style.width      = '100%';
            requestAnimationFrame(function() {{
              requestAnimationFrame(function() {{
                fill.style.transition = 'width 3s linear';
                fill.style.width      = '0%';
              }});
            }});

            clearTimeout(timer);
            timer = setTimeout(hidePanel, 3000);
          }}

          function hidePanel() {{
            panel.style.opacity       = '0';
            panel.style.transform     = 'translateY(-8px)';
            panel.style.pointerEvents = 'none';
            setTimeout(function() {{ panel.style.display = 'none'; }}, 280);
          }}

          btn.addEventListener('click', function() {{
            if (panel.style.display === 'none' || panel.style.opacity === '0') {{
              showPanel();
            }} else {{
              clearTimeout(timer);
              hidePanel();
            }}
          }});
        </script>
        </body></html>""", height=50, scrolling=False)

# ── 2. Validação e Carregamento de Dados ───────────────────────────────────────
cfg = DATA_CONFIG[ano_selecionado]
nivel_path   = cfg["niveis"][_nivel_key(status_filter)]
modelo_path  = cfg["modelos_urnas"][_nivel_key(status_filter)]

for path_check, label in [(nivel_path, "Níveis"), (modelo_path, "Modelos")]:
    if not os.path.exists(path_check):
        st.error(f"Arquivo não encontrado ({label}): `{path_check}`")
        st.stop()

with st.spinner("Carregando dados..."):
    df_secoes = _load_csv_cached(nivel_path)
    df_voter_log = _load_csv_cached(modelo_path)

    n_all_path   = cfg["niveis"][_nivel_key(None)]
    total_secoes_global = _count_rows(n_all_path) if os.path.exists(n_all_path) else 0

    estado_means: dict[str, float] = {}
    if status_filter is not None and os.path.exists(n_all_path):
        estado_means = _load_estado_means(n_all_path)

analise = UrnasCriticasAnalysis.from_dataframes(
    df_2022=df_voter_log,
    df_completas=df_secoes,
    status_filter=status_filter,
    prefiltered=True,
    total_secoes_override=total_secoes_global,
)

overview = analise.get_overview()
pct = overview["total_secoes_criticas"] / max(overview["total_secoes"], 1)

# ── 3. Renderiza os KPIs nas colunas restantes (Centralizados verticalmente) ───
# O estilo com `margin-top: 1.8rem;` empurra a caixa exatamente para o eixo Y
# central das duas caixas de input à esquerda.
with k1:
    st.markdown(f"""
        <div style="margin-top: 1.8rem; height: 100%;">
            <div class="kpi-box">
                <div class="kpi-label">Selecionadas</div>
                <div class="kpi-value kpi-danger">{overview['total_secoes_criticas']:,}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
with k2:
    st.markdown(f"""
        <div style="margin-top: 1.8rem; height: 100%;">
            <div class="kpi-box">
                <div class="kpi-label">Total Seções</div>
                <div class="kpi-value">{overview['total_secoes']:,}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
with k3:
    st.markdown(f"""
        <div style="margin-top: 1.8rem; height: 100%;">
            <div class="kpi-box">
                <div class="kpi-label">Votantes</div>
                <div class="kpi-value kpi-success">{overview['total_votantes']:,}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
with k4:
    st.markdown(f"""
        <div style="margin-top: 1.8rem; height: 100%;">
            <div class="kpi-box">
                <div class="kpi-label">Modelos</div>
                <div class="kpi-value">{len(overview['modelos_presentes'])}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
with k5:
    st.markdown(f"""
        <div style="margin-top: 1.8rem; height: 100%;">
            <div class="kpi-box">
                <div class="kpi-label">Taxa</div>
                <div class="kpi-value kpi-accent">{pct:.1%}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

del overview
gc.collect()

st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# ABAS PRINCIPAIS
# ═══════════════════════════════════════════════════════════════════════════════
tab_geo, tab_criticidade, tab_modelo = st.tabs([
    "Visão Geográfica",
    "Análise por Criticidade",
    "Análise por Modelo de Urna",
])

with tab_geo:
    render_tab_geo(ano_selecionado, status_filter)

with tab_criticidade:
    # df_criticas já é o subconjunto correto para o filtro ativo
    render_tab_criticidade(analise.df_criticas, status_filter, estado_means)

with tab_modelo:
    render_tab_modelo(analise)

# ═══════════════════════════════════════════════════════════════════════════════
# CLEANUP FINAL
# ═══════════════════════════════════════════════════════════════════════════════
del analise, df_secoes, df_voter_log
gc.collect()

# ═══════════════════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
    <div class="footer">
        <div style="font-weight: 600; color: #adb5bd; margin-bottom: 0.35rem;">
            UFS · TRE — Sistema de Análise de Urnas Eletrônicas
        </div>
        <div style="margin-bottom: 0.4rem; color: #64748b; font-size: 0.82rem;">
            Desenvolvido pela equipe da <a href="https://sites.google.com/mat.ufs.br/lame/lame?authuser=0" target="_blank" style="color: #0072B2; text-decoration: none; font-weight: 600; border-bottom: 1px dashed #0072B2;">LAME (Liga Acadêmica de Matemática e Empresa)</a>
        </div>
        <div>Dados: TSE / Urnas Eletrônicas · Eleições Sergipe | Dashboard desenvolvido com Streamlit</div>
    </div>
""", unsafe_allow_html=True)