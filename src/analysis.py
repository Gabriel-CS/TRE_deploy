from __future__ import annotations

import numpy as np
import pandas as pd

# ──────────────────────────────────────────────────────────────────────────────
# Constantes de Filtro Operacional (Single Source of Truth)
# ──────────────────────────────────────────────────────────────────────────────
FILTER_SOMENTE_CRITICAS = "Somente criticas"
FILTER_COM_ATRASO = "Com atraso"

# Mantém exatamente as opções visuais do seu Selectbox (Imagem 2)
STATUS_OPCOES: dict[str, str | int] = {
    "Somente criticas":     FILTER_SOMENTE_CRITICAS,
    "Com atraso":           FILTER_COM_ATRASO,
    "Nível 0 — Sem Atraso": 0,
    "Nível 1 — Sem Atraso": 1,
    "Nível 2 — Com Atraso": 2,
    "Nível 3 — Com Atraso": 3,
    "Nível 4 — Com Atraso": 4,
}

# ──────────────────────────────────────────────────────────────────────────────
# Constantes compartilhadas
# ──────────────────────────────────────────────────────────────────────────────

URN_MODELS: list[str] = ["UE2009", "UE2010", "UE2011", "UE2013", "UE2015", "UE2020"]

OKABE_ITO: list[str] = [
    "#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9",
]

MODEL_COLOR: dict[str, str] = dict(zip(URN_MODELS, OKABE_ITO))

# REVERTIDO: Mantém a granularidade para a aba de criticidade não quebrar
STATUS_LABELS: dict[int, str] = {
    0: "Sem Atraso",
    1: "Normal",
    2: "Atenção",
    3: "Crítico",
    4: "Super Crítica",
}

STATUS_PALETTE: dict[int, str] = {
    0: "#0EA5E9",  # azul-céu
    1: "#22C55E",  # verde
    2: "#EAB308",  # âmbar
    3: "#F97316",  # laranja
    4: "#EF4444",  # vermelho
}

# REVERTIDO: Mantém o detalhamento rico para a tooltip (Imagem 1)
STATUS_DETALHES: dict[int, dict] = {
    0: {
        "label": "Sem Atraso",    "cor": "#0EA5E9", "icon": "✔", 
        "desc": "Operação fluida e contínua, sem atrasos registrados.", 
        "intervalo": "< 6,48 min"
    },
    1: {
        "label": "Normal",        "cor": "#22C55E", "icon": "↑", 
        "desc": "Atraso leve, mantendo-se dentro da tolerância operacional esperada.", 
        "intervalo": "≥ 6,48 min e < 32,15 min"
    },
    2: {
        "label": "Atenção",       "cor": "#EAB308", "icon": "⚠", 
        "desc": "Atraso moderado. O fluxo apresenta interrupções que requerem monitoramento.", 
        "intervalo": "≥ 32,15 min e < 89,36 min"
    },
    3: {
        "label": "Crítico",       "cor": "#F97316", "icon": "✖", 
        "desc": "Atraso elevado. Impacto sensível na formação de filas e retenção de eleitores.", 
        "intervalo": "≥ 89,36 min e < 150 min"
    },
    4: {
        "label": "Super Crítica", "cor": "#EF4444", "icon": "‼", 
        "desc": "Atraso severo. Risco iminente de não encerramento da votação no horário limite.", 
        "intervalo": "≥ 150 min"
    },
}


COLS_LOG: list[str] = [
    "zona", "secao", "modelo", "t_intervalo_s", "n_tit_invalidos",
    "t_fila_s", "bio_solicitada", "n_tent_bio", "n_falhas_bio",
    "score_bio", "hab_cancelada", "hab_manual", "ts_titulo",
    "ts_habilitado", "ts_computado", "n_teclas_inv",
    "t_inatividade_s", "t_habilitacao_s", "completo",
    "ts_cod_encerramento", "ts_encerramento", "ts_gerando_resultado",
]

ESC_COLS: list[str] = [
    "ESC_ANALFABETO", "ESC_LÊ E ESCREVE",
    "ESC_ENSINO FUNDAMENTAL INCOMPLETO", "ESC_ENSINO FUNDAMENTAL COMPLETO",
    "ESC_ENSINO MÉDIO INCOMPLETO",       "ESC_ENSINO MÉDIO COMPLETO",
    "ESC_SUPERIOR INCOMPLETO",           "ESC_SUPERIOR COMPLETO",
]
ESC_LABELS: dict[str, str] = {
    "ESC_ANALFABETO":                    "Analfabeto",
    "ESC_LÊ E ESCREVE":                  "Lê/Escreve",
    "ESC_ENSINO FUNDAMENTAL INCOMPLETO": "Fund. Incomp.",
    "ESC_ENSINO FUNDAMENTAL COMPLETO":   "Fund. Comp.",
    "ESC_ENSINO MÉDIO INCOMPLETO":       "Médio Incomp.",
    "ESC_ENSINO MÉDIO COMPLETO":         "Médio Comp.",
    "ESC_SUPERIOR INCOMPLETO":           "Sup. Incomp.",
    "ESC_SUPERIOR COMPLETO":             "Sup. Comp.",
}
BAIXA_ESC: list[str] = [
    "ESC_ANALFABETO", "ESC_LÊ E ESCREVE", "ESC_ENSINO FUNDAMENTAL INCOMPLETO",
]

GRUPOS_ETARIOS: dict[str, list[str]] = {
    "Jovem (16-24)": [
        "IDADE_16 anos", "IDADE_17 anos", "IDADE_18 anos",
        "IDADE_19 anos", "IDADE_20 anos", "IDADE_21 a 24 anos",
    ],
    "Adulto (25-44)": [
        "IDADE_25 a 29 anos", "IDADE_30 a 34 anos",
        "IDADE_35 a 39 anos", "IDADE_40 a 44 anos",
    ],
    "Meia-idade (45-59)": [
        "IDADE_45 a 49 anos", "IDADE_50 a 54 anos", "IDADE_55 a 59 anos",
    ],
    "Idoso (60-74)": [
        "IDADE_60 a 64 anos", "IDADE_65 a 69 anos", "IDADE_70 a 74 anos",
    ],
    "Muito idoso (75+)": [
        "IDADE_75 a 79 anos", "IDADE_80 a 84 anos", "IDADE_85 a 89 anos",
        "IDADE_90 a 94 anos", "IDADE_95 a 99 anos", "IDADE_100 anos ou mais",
    ],
}

# ──────────────────────────────────────────────────────────────────────────────
# Helpers de normalização de colunas
# ──────────────────────────────────────────────────────────────────────────────

def _normalizar_colunas_zona_secao(df: pd.DataFrame) -> pd.DataFrame:
    import warnings
    cols_upper = {c.upper().strip().replace(" ", "_"): c for c in df.columns}
    candidatos = {
        "NR_ZONA":  ["NR_ZONA", "ZONA", "COD_ZONA", "CD_ZONA", "NUM_ZONA", "NR_ZONA_ELEITORAL", "ZONA_ELEITORAL"],
        "NR_SECAO": ["NR_SECAO", "SECAO", "COD_SECAO", "CD_SECAO", "NUM_SECAO", "SEÇÃO", "NR_SEÇÃO", "NR_SECAO_ELEITORAL", "SECAO_ELEITORAL", "SEÇÃO_ELEITORAL"],
    }
    renames = {}
    for padrao, alternativas in candidatos.items():
        if padrao in df.columns:
            continue
        for alt in alternativas:
            alt_norm = alt.upper().strip().replace(" ", "_")
            if alt_norm in cols_upper:
                renames[cols_upper[alt_norm]] = padrao
                break

    if renames:
        df = df.rename(columns=renames)

    if "NR_ZONA" not in df.columns:
        for c in df.columns:
            c_upper = c.upper().strip()
            if "ZON" in c_upper and ("NR" in c_upper or "NUM" in c_upper or "COD" in c_upper):
                df = df.rename(columns={c: "NR_ZONA"})
                break
            elif c_upper in ("ZONA", "ZONA_ELEITORAL"):
                df = df.rename(columns={c: "NR_ZONA"})
                break

    if "NR_SECAO" not in df.columns:
        for c in df.columns:
            c_upper = c.upper().strip()
            if "SEC" in c_upper and ("NR" in c_upper or "NUM" in c_upper or "COD" in c_upper):
                df = df.rename(columns={c: "NR_SECAO"})
                break
            elif c_upper in ("SECAO", "SEÇÃO", "SECAO_ELEITORAL", "SEÇÃO_ELEITORAL"):
                df = df.rename(columns={c: "NR_SECAO"})
                break

    if "NR_SECAO" not in df.columns:
        for c in df.columns:
            if "SEC" in c.upper():
                df = df.rename(columns={c: "NR_SECAO"})
                break

    if "NR_ZONA" not in df.columns:
        for c in df.columns:
            if "ZON" in c.upper():
                df = df.rename(columns={c: "NR_ZONA"})
                break

    return df


# ──────────────────────────────────────────────────────────────────────────────
# Classe principal
# ──────────────────────────────────────────────────────────────────────────────

class UrnasCriticasAnalysis:
    def __init__(
        self,
        path_consolidado: str,
        path_urnas_completas: str,
        status_filter: int | str | None = None,
        prefiltered: bool = False,
        total_secoes_override: int | None = None,
    ) -> None:
        df_2022 = pd.read_csv(
            path_consolidado, sep=",", encoding="utf-8", compression="zip"
        )
        df_completas = pd.read_csv(
            path_urnas_completas, sep=";", encoding="utf-8", compression="zip"
        )
        self.status_filter = status_filter
        self._total_secoes_override = total_secoes_override
        self._prepare(df_2022, df_completas, prefiltered=prefiltered)

    @classmethod
    def from_dataframes(
        cls,
        df_2022: pd.DataFrame,
        df_completas: pd.DataFrame,
        status_filter: int | str | None = None,
        prefiltered: bool = False,
        total_secoes_override: int | None = None,
    ) -> "UrnasCriticasAnalysis":
        obj = object.__new__(cls)
        obj.status_filter = status_filter
        obj._total_secoes_override = total_secoes_override
        obj._prepare(df_2022, df_completas, prefiltered=prefiltered)
        return obj


    def _prepare(
        self,
        df_2022: pd.DataFrame,
        df_completas: pd.DataFrame,
        prefiltered: bool = False,
    ) -> None:
        import warnings
        df_completas = _normalizar_colunas_zona_secao(df_completas)
        df_2022 = _normalizar_colunas_zona_secao(df_2022)

        if "NR_SECAO" not in df_completas.columns and "NR_ZONA" in df_completas.columns:
            df_completas["NR_SECAO"] = df_completas["NR_ZONA"].astype(str) + "_sec"
            
        if "NR_ZONA" in df_2022.columns and "zona" not in df_2022.columns:
            df_2022 = df_2022.rename(columns={"NR_ZONA": "zona", "NR_SECAO": "secao"})

        if prefiltered:
            df_criticas = df_completas.copy()
        else:
            if isinstance(self.status_filter, str) or self.status_filter is None:
                df_criticas = df_completas[df_completas["STATUS"] > 0].copy()
            else:
                df_criticas = df_completas[df_completas["STATUS"] == self.status_filter].copy()

        idade_raw = [c for c in df_criticas.columns if c.startswith("IDADE_")]
        df_criticas = df_criticas.rename(columns={c: c.strip() for c in idade_raw})

        if "zona" not in df_2022.columns or "secao" not in df_2022.columns:
            raise KeyError("Colunas 'zona' ou 'secao' não encontradas em df_2022.")
        if "NR_ZONA" not in df_criticas.columns or "NR_SECAO" not in df_criticas.columns:
            raise KeyError("Colunas 'NR_ZONA' ou 'NR_SECAO' não encontradas em df_criticas.")

        df_modelo_secao = (
            df_2022[["zona", "secao", "modelo"]]
            .drop_duplicates(subset=["zona", "secao"])
            .rename(columns={"zona": "NR_ZONA", "secao": "NR_SECAO"})
        )
        df_criticas = df_criticas.merge(
            df_modelo_secao, on=["NR_ZONA", "NR_SECAO"], how="left"
        )

        cols_available = [c for c in COLS_LOG if c in df_2022.columns]
        zs = df_criticas[["NR_ZONA", "NR_SECAO"]].rename(
            columns={"NR_ZONA": "zona", "NR_SECAO": "secao"}
        )
        df_log = df_2022[cols_available].merge(zs, on=["zona", "secao"], how="inner")

        df_criticas_urnas = (
            df_log.drop_duplicates(subset=["zona", "secao"])[["zona", "secao", "modelo"]]
            .reset_index(drop=True)
        )

        self.df_criticas = df_criticas
        self.df_log = df_log
        self.df_completas = df_completas

        self.models: dict[str, pd.DataFrame] = {
            m: df_criticas_urnas[df_criticas_urnas["modelo"] == m].reset_index(drop=True)
            for m in URN_MODELS
        }
        self.voters: dict[str, pd.DataFrame] = {
            m: df_log[df_log["modelo"] == m].reset_index(drop=True)
            for m in URN_MODELS
        }
        self.secao: dict[str, pd.DataFrame] = {
            m: df_criticas[df_criticas["modelo"] == m].reset_index(drop=True)
            for m in URN_MODELS
        }


    def get_overview(self) -> dict:
        total_secoes = (
            self._total_secoes_override
            if self._total_secoes_override is not None
            else len(self.df_completas)
        )
        status_counts = (
            self.df_completas["STATUS"]
            .value_counts()
            .sort_index()
            .rename(STATUS_LABELS)
            .to_dict()
        )
        return {
            "total_secoes_criticas": len(self.df_criticas),
            "total_secoes":          total_secoes,
            "total_votantes":        len(self.df_log),
            "modelos_presentes":     [m for m in URN_MODELS if len(self.models[m]) > 0],
            "status_counts":         status_counts,
        }

    def get_model_distribution(self) -> dict:
        counts = [len(self.models[m]) for m in URN_MODELS]
        total  = sum(counts) or 1
        return {
            "models":      URN_MODELS,
            "counts":      counts,
            "proportions": [c / total for c in counts],
        }

    def get_bio_failure_rates(self) -> dict:
        rates = []
        for m in URN_MODELS:
            vm    = self.voters[m]
            bio_m = vm[vm["bio_solicitada"] == True]
            taxa  = (bio_m["n_falhas_bio"] > 0).sum() / len(bio_m) if len(bio_m) else 0
            rates.append(taxa)
        return {"models": URN_MODELS, "rates": rates}

    def get_queue_times(self) -> dict:
        means, stds = [], []
        for m in URN_MODELS:
            d = self.voters[m][self.voters[m]["t_fila_s"] > 0]["t_fila_s"]
            means.append(float(d.mean()) if len(d) else 0.0)
            stds.append(float(d.std())  if len(d) else 0.0)
        return {"models": URN_MODELS, "means": means, "stds": stds}

    def get_auth_duration(self) -> dict:
        means, stds = [], []
        for m in URN_MODELS:
            d = self.voters[m][self.voters[m]["t_habilitacao_s"] > 0]["t_habilitacao_s"]
            means.append(float(d.mean()) if len(d) else 0.0)
            stds.append(float(d.std())  if len(d) else 0.0)
        return {"models": URN_MODELS, "means": means, "stds": stds}

    def get_inactivity_times(self) -> dict:
        means, stds = [], []
        for m in URN_MODELS:
            d = self.voters[m][self.voters[m]["t_inatividade_s"] > 0]["t_inatividade_s"]
            means.append(float(d.mean()) if len(d) else 0.0)
            stds.append(float(d.std())  if len(d) else 0.0)
        return {"models": URN_MODELS, "means": means, "stds": stds}

    def get_invalid_keys(self) -> dict:
        total_kp = self.df_log["n_teclas_inv"].sum()
        props = [
            self.voters[m][self.voters[m]["n_teclas_inv"] > 0]["n_teclas_inv"].sum() / total_kp
            if total_kp > 0 else 0
            for m in URN_MODELS
        ]
        return {"models": URN_MODELS, "proportions": props}

    def get_education_distribution(self) -> dict:
        esc_cols_available = [c for c in ESC_COLS if c in self.df_criticas.columns]
        df_esc = pd.DataFrame(
            {m: self.secao[m][esc_cols_available].sum() for m in URN_MODELS}
        ).T
        df_esc.columns = [ESC_LABELS.get(c, c) for c in esc_cols_available]
        df_esc_pct = df_esc.div(df_esc.sum(axis=1), axis=0)
        return {
            "df_counts":      df_esc,
            "df_proportions": df_esc_pct,
            "models":         URN_MODELS,
            "labels":         list(df_esc.columns),
        }

    def get_low_education(self) -> dict:
        baixa_available = [c for c in BAIXA_ESC if c in self.df_criticas.columns]
        esc_available   = [c for c in ESC_COLS   if c in self.df_criticas.columns]
        props = []
        for m in URN_MODELS:
            sm  = self.secao[m]
            tot = sm[esc_available].sum().sum()
            props.append(sm[baixa_available].sum().sum() / tot if tot else 0)
        return {"models": URN_MODELS, "proportions": props}

    def get_age_distribution(self) -> dict:
        df_idade = pd.DataFrame({
            m: {
                g: self.secao[m][[c for c in cols if c in self.secao[m].columns]].sum().sum()
                for g, cols in GRUPOS_ETARIOS.items()
            }
            for m in URN_MODELS
        }).T
        df_idade_pct = df_idade.div(df_idade.sum(axis=1), axis=0)
        return {
            "df_counts":      df_idade,
            "df_proportions": df_idade_pct,
            "models":         URN_MODELS,
            "groups":         list(GRUPOS_ETARIOS.keys()),
        }

    def get_elderly_proportion(self) -> dict:
        age = self.get_age_distribution()
        df  = age["df_proportions"]
        idoso_pct = (
            df.get("Idoso (60-74)", 0) + df.get("Muito idoso (75+)", 0)
        ).values.tolist()
        return {"models": URN_MODELS, "proportions": idoso_pct}

    def get_pcd_stats(self) -> dict:
        totals, eleitores, taxas = [], [], []
        for m in URN_MODELS:
            sm = self.secao[m]
            p  = sm["QTD_PCD"].sum()              if "QTD_PCD"               in sm.columns else 0
            t  = sm["QTD_PERFIL_BIOMETRIA"].sum() if "QTD_PERFIL_BIOMETRIA" in sm.columns else 0
            totals.append(int(p))
            eleitores.append(int(t))
            taxas.append(p / t if t else 0.0)
        return {"models": URN_MODELS, "totals": totals, "eleitores": eleitores, "taxas": taxas}

    def get_operational_summary(self) -> pd.DataFrame:
        bio  = self.get_bio_failure_rates()
        fila = self.get_queue_times()
        auth = self.get_auth_duration()
        inat = self.get_inactivity_times()
        rows = []
        for i, m in enumerate(URN_MODELS):
            vm = self.voters[m]
            rows.append({
                "Modelo":                m,
                "Seções":                len(self.models[m]),
                "Votantes":              len(vm),
                "Falha Bio (%)":         round(bio["rates"][i]  * 100, 1),
                "T. Fila (s)":           round(fila["means"][i], 1),
                "T. Auth (s)":           round(auth["means"][i], 1),
                "T. Inatividade (s)":    round(inat["means"][i], 1),
            })
        return pd.DataFrame(rows)

    def get_pcd_summary(self) -> pd.DataFrame:
        pcd = self.get_pcd_stats()
        rows = [
            {
                "Modelo":      m,
                "PCD Total":   pcd["totals"][i],
                "Eleitores":   pcd["eleitores"][i],
                "Taxa PCD (%)": round(pcd["taxas"][i] * 100, 2),
            }
            for i, m in enumerate(URN_MODELS)
        ]
        return pd.DataFrame(rows)
