import gc
import os
import zipfile

import gdown
import pandas as pd
import streamlit as st

from src.analysis import (
    FILTER_COM_ATRASO,
    FILTER_SOMENTE_CRITICAS,
    STATUS_DETALHES,
    STATUS_OPCOES,
    URN_MODELS,
    UrnasCriticasAnalysis,
)
from src.tab_criticidade import render_tab_criticidade
from src.tab_geo import render_tab_geo
from src.tab_modelo import render_tab_modelo

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO DE DADOS
# ═══════════════════════════════════════════════════════════════════════════════

def _nivel_key(status_filter):
    return FILTER_SOMENTE_CRITICAS if status_filter is None else status_filter


DATA_CONFIG = {
    "2022": {
        "niveis": {
            FILTER_SOMENTE_CRITICAS: "data/output/nivel_criticidade/df_somente_criticas_2022.csv",
            FILTER_COM_ATRASO:       "data/output/nivel_criticidade/df_com_atraso_2022.csv",
            0:    "data/output/nivel_criticidade/df_critica_n0_2022.csv",
            1:    "data/output/nivel_criticidade/df_critica_n1_2022.csv",
            2:    "data/output/nivel_criticidade/df_critica_n2_2022.csv",
            3:    "data/output/nivel_criticidade/df_critica_n3_2022.csv",
            4:    "data/output/nivel_criticidade/df_critica_n4_2022.csv",
        },
        "modelos_urnas": {
            FILTER_SOMENTE_CRITICAS: "data/output/modelos_urnas/df_somente_criticas_2022.zip",
            FILTER_COM_ATRASO:       "data/output/modelos_urnas/df_com_atraso_2022.zip",
            0:    "data/output/modelos_urnas/df_completas_n0_2022.zip",
            1:    "data/output/modelos_urnas/df_completas_n1_2022.zip",
            2:    "data/output/modelos_urnas/df_completas_n2_2022.zip",
            3:    "data/output/modelos_urnas/df_completas_n3_2022.zip",
            4:    "data/output/modelos_urnas/df_completas_n4_2022.zip",
        },
    },
    "2018": {
        "niveis": {
            FILTER_SOMENTE_CRITICAS: "data/output/nivel_criticidade/df_somente_criticas_2018.csv",
            FILTER_COM_ATRASO:       "data/output/nivel_criticidade/df_com_atraso_2018.csv",
            0:    "data/output/nivel_criticidade/df_critica_n0_2018.csv",
            1:    "data/output/nivel_criticidade/df_critica_n1_2018.csv",
            2:    "data/output/nivel_criticidade/df_critica_n2_2018.csv",
            3:    "data/output/nivel_criticidade/df_critica_n3_2018.csv",
            4:    "data/output/nivel_criticidade/df_critica_n4_2018.csv",
        },
        "modelos_urnas": {
            FILTER_SOMENTE_CRITICAS: "data/output/modelos_urnas/df_somente_criticas_2018.zip",
            FILTER_COM_ATRASO:       "data/output/modelos_urnas/df_com_atraso_2018.zip",
            0:    "data/output/modelos_urnas/df_completas_n0_2018.zip",
            1:    "data/output/modelos_urnas/df_completas_n1_2018.zip",
            2:    "data/output/modelos_urnas/df_completas_n2_2018.zip",
            3:    "data/output/modelos_urnas/df_completas_n3_2018.zip",
            4:    "data/output/modelos_urnas/df_completas_n4_2018.zip",
        },
    },
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
# DESIGN SYSTEM — tokens centralizados, usados em todos os módulos via CSS vars
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
    <style>
        /* ── Tokens globais ────────────────────────────────────────────── */
        :root {
            --color-brand:       #0072B2;
            --color-brand-light: #56B4E9;
            --color-ink:         #0f172a;
            --color-ink-mid:     #334155;
            --color-ink-soft:    #64748b;
            --color-ink-muted:   #94a3b8;
            --color-surface:     #ffffff;
            --color-surface-2:   #f8fafc;
            --color-border:      #e2e8f0;
            --color-danger:      #dc2626;
            --color-success:     #059669;
            --color-warning:     #d97706;
            --radius-card:       12px;
            --radius-sm:         8px;
            --shadow-card:       0 1px 4px rgba(15,23,42,0.05), 0 4px 16px rgba(15,23,42,0.04);
            --shadow-hover:      0 8px 24px rgba(15,23,42,0.10);
            --font-sans:         'Inter', 'Segoe UI', sans-serif;
            --font-mono:         'SF Mono', 'Fira Code', Monaco, monospace;
        }

        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
        html, body, [class*="css"] { font-family: var(--font-sans); }

        /* ── Header principal ─────────────────────────────────────────── */
        .main-header {
            font-weight: 800;
            color: var(--color-ink);
            letter-spacing: -0.03em;
            margin-bottom: 0.15rem;
            font-size: 2.1rem;
            line-height: 1.2;
        }
        .sub-header {
            color: var(--color-ink-soft);
            font-size: 0.9rem;
            margin-top: 0;
            margin-bottom: 1.25rem;
            font-weight: 400;
            letter-spacing: 0.01em;
        }

        /* ── KPI cards ────────────────────────────────────────────────── */
        .kpi-box {
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-card);
            padding: 2.1rem 1rem;
            text-align: center;
            box-shadow: var(--shadow-card);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            height: 100%;
            position: relative;
            cursor: pointer;
            outline: none;
        }
        .kpi-box::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--color-brand), var(--color-brand-light));
            border-radius: var(--radius-card) var(--radius-card) 0 0;
        }
        .kpi-box:hover, .kpi-box:focus {
            transform: translateY(-3px);
            box-shadow: var(--shadow-hover);
        }
        .kpi-label {
            font-size: 0.65rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--color-ink-muted);
            margin-bottom: 0.5rem;
        }
        .kpi-value   { font-size: 1.65rem; font-weight: 800; color: var(--color-ink); line-height: 1.15; }
        .kpi-accent  { color: var(--color-brand); }
        .kpi-danger  { color: var(--color-danger); }
        .kpi-success { color: var(--color-success); }

        /* ── Tooltips ─────────────────────────────────────────────────── */
        .kpi-tooltip {
            visibility: hidden;
            width: max-content;
            max-width: 250px;
            background-color: var(--color-ink);
            color: #f8fafc;
            text-align: center;
            border-radius: var(--radius-sm);
            padding: 10px 14px;
            position: absolute;
            z-index: 99;
            top: 115%;
            left: 50%;
            transform: translateX(-50%);
            opacity: 0;
            transition: opacity 0.2s ease, top 0.2s ease;
            font-size: 0.75rem;
            font-weight: 500;
            line-height: 1.4;
            box-shadow: 0 10px 25px rgba(15,23,42,0.2);
            pointer-events: none;
            white-space: normal;
        }
        .kpi-tooltip::after {
            content: "";
            position: absolute;
            bottom: 100%;
            left: 50%;
            margin-left: -6px;
            border-width: 6px;
            border-style: solid;
            border-color: transparent transparent var(--color-ink) transparent;
        }
        .kpi-box:hover .kpi-tooltip,
        .kpi-box:focus .kpi-tooltip {
            visibility: visible;
            opacity: 1;
            top: 105%;
        }

        /* ── Seções ───────────────────────────────────────────────────── */
        .section-header {
            border-left: 4px solid var(--color-brand);
            padding-left: 12px;
            margin: 1.75rem 0 0.6rem 0;
        }
        .section-header h2 {
            margin: 0;
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--color-ink);
            letter-spacing: -0.01em;
        }
        .section-desc {
            font-size: 0.82rem;
            color: var(--color-ink-soft);
            margin-bottom: 1rem;
            padding-left: 16px;
            line-height: 1.5;
        }

        /* ── Resumo cards ─────────────────────────────────────────────── */
        .resumo-card {
            border: 1px solid #f1f5f9;
            border-radius: 10px;
            padding: 8px 14px;
            margin-bottom: 6px;
            background: var(--color-surface-2);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 10px;
            transition: background 0.15s, border-color 0.15s;
        }
        .resumo-card:hover       { background: #f0f9ff; border-color: #bae6fd; }
        .resumo-dot              { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }
        .resumo-nome             { font-size: 0.8rem; font-weight: 600; color: var(--color-ink); }
        .resumo-metrica-valor    { font-size: 0.82rem; font-weight: 700; color: var(--color-ink-mid); font-family: var(--font-mono); }
        .resumo-metrica-label    { font-size: 0.6rem; color: var(--color-ink-muted); text-transform: uppercase; letter-spacing: 0.3px; }

        /* ── Alertas ──────────────────────────────────────────────────── */
        .alert-box     { padding: 1rem 1.25rem; border-radius: 10px; border-left: 4px solid; margin-bottom: 1rem; }
        .alert-danger  { background: #fef2f2; border-color: var(--color-danger); color: #991b1b; }
        .alert-success { background: #f0fdf4; border-color: #16a34a; color: #15803d; }
        .alert-warning { background: #fffbeb; border-color: var(--color-warning); color: #92400e; }

        /* ── Status badges ────────────────────────────────────────────── */
        .status-badge { display: inline-block; padding: 0.2rem 0.65rem; border-radius: 20px; font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
        .status-0 { background: #e0f2fe; color: #0369a1; }
        .status-1 { background: #dcfce7; color: #15803d; }
        .status-2 { background: #fef9c3; color: #a16207; }
        .status-3 { background: #fee2e2; color: #991b1b; }
        .status-4 { background: #fee2e2; color: #B91C1C; }

        /* ── Mapa ─────────────────────────────────────────────────────── */
        .folium-map { border-radius: var(--radius-card); overflow: hidden; box-shadow: 0 4px 20px rgba(15,23,42,0.10); border: 1px solid var(--color-border); }

        /* ── Painel lateral adaptativo ───────────────────────────────── */
        .side-panel {
            background: var(--color-surface);
            border: 1px solid var(--color-border);
            border-radius: var(--radius-card);
            padding: 0;
            overflow: hidden;
            box-shadow: var(--shadow-card);
            height: 100%;
        }
        .side-panel-header {
            padding: 14px 16px 12px;
            border-bottom: 1px solid var(--color-border);
            background: var(--color-surface-2);
        }
        .side-panel-body {
            padding: 14px 16px;
        }

        /* ── Footer ───────────────────────────────────────────────────── */
        .footer {
            margin-top: 3rem;
            padding-top: 1.5rem;
            border-top: 1px solid #f1f5f9;
            text-align: center;
            color: var(--color-ink-muted);
            font-size: 0.78rem;
        }

        /* ── Tabs ─────────────────────────────────────────────────────── */
        .stTabs [data-baseweb="tab-list"] { gap: 6px; }
        .stTabs [data-baseweb="tab"] {
            padding: 9px 22px;
            font-weight: 600;
            font-size: 0.85rem;
            border-radius: var(--radius-sm) var(--radius-sm) 0 0;
            color: var(--color-ink-soft);
            letter-spacing: 0.01em;
        }
        .stTabs [aria-selected="true"] {
            background: var(--color-ink) !important;
            color: white !important;
        }

        /* ── Streamlit overrides ──────────────────────────────────────── */
        .stSelectbox label, .stMultiSelect label {
            font-family: var(--font-sans) !important;
            font-size: 0.7rem !important;
            font-weight: 700 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.08em !important;
            color: var(--color-ink-soft) !important;
            margin-bottom: 0.25rem !important;
        }
        .stSelectbox > div[data-baseweb="select"],
        .stMultiSelect > div[data-baseweb="select"] {
            border-radius: 10px !important;
            border: 1px solid var(--color-border) !important;
            box-shadow: 0 1px 3px rgba(15,23,42,0.04) !important;
            font-family: var(--font-sans) !important;
            font-size: 0.82rem !important;
            color: var(--color-ink) !important;
            min-height: 38px !important;
        }
        .stSelectbox > div[data-baseweb="select"]:hover,
        .stMultiSelect > div[data-baseweb="select"]:hover {
            border-color: var(--color-brand) !important;
            box-shadow: 0 2px 8px rgba(0,114,178,0.08) !important;
        }
    </style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CACHE DE DADOS
# ═══════════════════════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner=False)
def _download_and_extract_data():
    data_dir = "data"
    if not os.path.exists(data_dir):
        output_zip = "data.zip"
        with st.spinner("Inicializando ambiente e construindo banco de dados (apenas na primeira execução)..."):
            try:
                # ID correto extraído do link compartilhado:
                # https://drive.google.com/file/d/101Gv11AT0cRRwphq9Ozk9qoxtzh5fNf-/view
                file_id  = "101Gv11AT0cRRwphq9Ozk9qoxtzh5fNf-"
                url      = f"https://drive.google.com/uc?export=download&id={file_id}"

                # fuzzy=True: lida automaticamente com a página de confirmação
                # de vírus do Google Drive (comum em arquivos grandes)
                gdown.download(url, output_zip, quiet=False, fuzzy=True, use_cookies=False)

                with zipfile.ZipFile(output_zip, "r") as zip_ref:
                    zip_ref.extractall(".")

            except Exception as exc:
                st.error(
                    f"❌ Falha ao baixar os dados do Google Drive.\n\n"
                    f"**Causa:** {exc}\n\n"
                    "**Verifique:**\n"
                    "1. A permissão do arquivo no Drive está como "
                    "**'Qualquer pessoa com o link'**?\n"
                    "2. O arquivo atingiu o limite de downloads do Google Drive? "
                    "Nesse caso, aguarde algumas horas ou mova os dados para outro host.\n"
                    "3. O `file_id` no código corresponde ao link correto?"
                )
                st.stop()
            finally:
                # Garante remoção do zip mesmo em caso de erro parcial
                if os.path.exists(output_zip):
                    os.remove(output_zip)

_download_and_extract_data()


@st.cache_data(show_spinner=False, max_entries=2, ttl=300)
def _load_csv_cached(path: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(path, sep=",", encoding="utf-8")
        if len(df.columns) <= 1:
            raise ValueError("Possivelmente separador incorreto")
    except Exception:
        df = pd.read_csv(path, sep=";", encoding="utf-8")
    df.columns = df.columns.str.strip()
    return df


@st.cache_data(show_spinner=False, max_entries=4, ttl=1800)
def _count_rows(path: str) -> int:
    try:
        df = pd.read_csv(path, sep=",", encoding="utf-8", usecols=[0])
        return len(df)
    except Exception:
        return 0


@st.cache_data(show_spinner=False, max_entries=2, ttl=600)
def _load_estado_means(nivel_all_path: str) -> dict[str, float]:
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
        <div style="text-align: right; color: var(--color-ink-muted); font-size: 0.85rem; margin-top: 0.5rem;">
            <div style="font-weight: 600; color: var(--color-ink-mid);">Última atualização</div>
            <div>{pd.Timestamp.now().strftime('%d/%m/%Y %H:%M')}</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='margin: 0.2rem 0 1.2rem 0; border: none; border-top: 1px solid var(--color-border);'>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# LINHA MESTRA: FILTROS + KPIs GLOBAIS
# ═══════════════════════════════════════════════════════════════════════════════
col_filtros, k1, k2, k3, k4, k5 = st.columns([1.6, 1, 1, 1, 1, 1])

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
        status_label = st.selectbox("Status operacional", list(STATUS_OPCOES.keys()))
        status_filter = STATUS_OPCOES[status_label]

    with col_btn:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        import streamlit.components.v1 as _components

        _items_html = ""
        for lvl, info in STATUS_DETALHES.items():
            _items_html += (
                f'<div style="display:flex;gap:9px;align-items:flex-start;margin-bottom:9px;">'
                f'  <div style="flex-shrink:0;width:28px;height:28px;border-radius:50%;'
                f'              background:{info["cor"]};color:white;font-size:14px;font-weight:800;'
                f'              display:flex;align-items:center;justify-content:center;">{lvl}</div>'
                f'  <div>'
                f'    <div style="font-size:14px;font-weight:700;color:{info["cor"]};margin-bottom:3px;">{info["icon"]}&nbsp;{info["label"]}</div>'
                f'    <div style="font-size:13px;color:#6b7280;line-height:1.4;">{info["desc"]}</div>'
                f'    <div style="font-size:12px;color:#9ca3af;margin-top:3px;'
                f'                font-family:\'SF Mono\',\'Fira Code\',monospace;letter-spacing:0.01em;">'
                f'      ⏱ {info["intervalo"]}</div>'
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
          var pDoc = window.parent.document;

          var oldPanel = pDoc.getElementById('crit-panel-legend');
          if(oldPanel) oldPanel.remove();

          var panel = pDoc.createElement('div');
          panel.id = 'crit-panel-legend';
          panel.innerHTML = `
            <div id="crit-title" style="font-size:12px;font-weight:700;text-transform:uppercase;
              letter-spacing:.1em;color:#94a3b8;padding-bottom:8px;margin-bottom:10px;
              border-bottom:1px solid #f1f5f9;font-family:Inter,sans-serif;">Níveis de Criticidade</div>
            {_items_html}`;

          Object.assign(panel.style, {{
            position:'fixed', zIndex:'2147483647', background:'#fff', border:'1px solid #e2e8f0',
            borderRadius:'12px', padding:'12px 18px 10px', width:'380px',
            boxShadow:'0 12px 40px rgba(15,23,42,0.18)', fontFamily:'Inter,sans-serif',
            opacity:'0', transform:'translateY(-8px)', transition:'opacity .28s ease, transform .28s ease',
            pointerEvents:'none', display:'none'
          }});

          pDoc.body.appendChild(panel);

          function showPanel() {{
            var frame = window.frameElement;
            var fr    = frame.getBoundingClientRect();
            var br    = btn.getBoundingClientRect();

            panel.style.display = 'block';
            panel.style.left    = (fr.left + br.left + 50) + 'px';
            panel.style.top     = (fr.top  + br.top - 75) + 'px';

            panel.getBoundingClientRect();
            panel.style.opacity       = '1';
            panel.style.transform     = 'translateY(0)';
            panel.style.pointerEvents = 'auto';
          }}

          function hidePanel() {{
            panel.style.opacity       = '0';
            panel.style.transform     = 'translateY(-8px)';
            panel.style.pointerEvents = 'none';
            setTimeout(function() {{ panel.style.display = 'none'; }}, 280);
          }}

          pDoc.addEventListener('mousedown', function(e) {{
            if (panel.style.opacity === '1' && !panel.contains(e.target)) {{
              hidePanel();
            }}
          }});

          btn.addEventListener('click', function(e) {{
            e.preventDefault();
            e.stopPropagation();
            if (panel.style.display === 'none' || panel.style.opacity === '0') {{
              showPanel();
            }} else {{
              hidePanel();
            }}
          }});
        </script>
        </body></html>""", height=45, scrolling=False)

# ── Validação e Carregamento de Dados ─────────────────────────────────────────
cfg = DATA_CONFIG[ano_selecionado]
nivel_path   = cfg["niveis"][_nivel_key(status_filter)]
modelo_path  = cfg["modelos_urnas"][_nivel_key(status_filter)]

for path_check, label in [(nivel_path, "Níveis"), (modelo_path, "Modelos")]:
    if not os.path.exists(path_check):
        st.error(f"Arquivo não encontrado ({label}): `{path_check}`")
        st.stop()

with st.spinner("Carregando dados..."):
    df_secoes    = _load_csv_cached(nivel_path)
    df_voter_log = _load_csv_cached(modelo_path)

    n_all_path = cfg["niveis"][FILTER_SOMENTE_CRITICAS]
    n_0_path   = cfg["niveis"][0]

    count_criticas = _count_rows(n_all_path) if os.path.exists(n_all_path) else 0
    count_n0       = _count_rows(n_0_path)   if os.path.exists(n_0_path)   else 0
    total_secoes_global = count_criticas + count_n0

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

# ── KPIs ───────────────────────────────────────────────────────────────────────
with k1:
    st.markdown(f"""
        <div style="margin-top: 1.8rem; height: 100%;">
            <div class="kpi-box" tabindex="0">
                <div class="kpi-label">Selecionadas</div>
                <div class="kpi-value kpi-danger">{overview['total_secoes_criticas']:,}</div>
                <div class="kpi-tooltip">Total de seções que atendem aos filtros operacionais ativos.</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
with k2:
    st.markdown(f"""
        <div style="margin-top: 1.8rem; height: 100%;">
            <div class="kpi-box" tabindex="0">
                <div class="kpi-label">Total Seções</div>
                <div class="kpi-value">{overview['total_secoes']:,}</div>
                <div class="kpi-tooltip">Universo total de seções mapeadas no estado para este ano.</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
with k3:
    st.markdown(f"""
        <div style="margin-top: 1.8rem; height: 100%;">
            <div class="kpi-box" tabindex="0">
                <div class="kpi-label">Votantes</div>
                <div class="kpi-value kpi-success">{overview['total_votantes']:,}</div>
                <div class="kpi-tooltip">Soma de fluxo total de eleitores processados nas seções selecionadas.</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
with k4:
    modelos_str = ", ".join(overview['modelos_presentes']) if overview['modelos_presentes'] else "Nenhum"
    st.markdown(f"""
        <div style="margin-top: 1.8rem; height: 100%;">
            <div class="kpi-box" tabindex="0">
                <div class="kpi-label">Modelos</div>
                <div class="kpi-value">{len(overview['modelos_presentes'])}</div>
                <div class="kpi-tooltip">Modelos ativos na seleção:<br><b style="color:#0EA5E9;">{modelos_str}</b></div>
            </div>
        </div>
    """, unsafe_allow_html=True)
with k5:
    st.markdown(f"""
        <div style="margin-top: 1.8rem; height: 100%;">
            <div class="kpi-box" tabindex="0">
                <div class="kpi-label">Taxa</div>
                <div class="kpi-value kpi-accent">{pct:.1%}</div>
                <div class="kpi-tooltip">Representatividade percentual da seleção sobre o ecossistema total do estado.</div>
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
    render_tab_geo(ano_selecionado, status_filter, estado_means)

with tab_criticidade:
    render_tab_criticidade(analise.df_criticas, status_filter, estado_means)

with tab_modelo:
    render_tab_modelo(analise)

# ═══════════════════════════════════════════════════════════════════════════════
# CLEANUP
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
        <div style="margin-bottom: 0.4rem; color: var(--color-ink-soft); font-size: 0.82rem;">
            Desenvolvido pela equipe da <a href="https://sites.google.com/mat.ufs.br/lame/lame?authuser=0" target="_blank"
            style="color: var(--color-brand); text-decoration: none; font-weight: 600; border-bottom: 1px dashed var(--color-brand);">LAME (Liga Acadêmica de Matemática e Empresa)</a>
        </div>
        <div>Dados: TSE / Urnas Eletrônicas · Eleições Sergipe | Dashboard desenvolvido com Streamlit</div>
    </div>
""", unsafe_allow_html=True)
