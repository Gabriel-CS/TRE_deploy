import os

import pandas as pd

# Importação das constantes da nossa Single Source of Truth
from src.analysis import FILTER_COM_ATRASO, FILTER_CONTINGENCIA, FILTER_SOMENTE_CRITICAS

# Configuração dos anos eleitorais e níveis de filtro (textuais e numéricos)
YEARS = ["2018", "2022"]
STATUS_LEVELS = [0, 1, 2, 3, 4, FILTER_SOMENTE_CRITICAS, FILTER_COM_ATRASO, FILTER_CONTINGENCIA]


def preprocess_geo_for_year(year: str) -> None:
    geo_raw_path = f"data/data_map/locais_criticos_{year}.csv"
    
    if not os.path.exists(geo_raw_path):
        print(f"[AVISO] Arquivo base não encontrado: {geo_raw_path}. Pulando {year}.")
        return

    print(f"\nIniciando particionamento para o ano: {year}...")
    
    # Otimização: tipagem forçada em memória durante a leitura — Int16 é
    # suficiente para STATUS (0–4) e evita upstream casts em callers.
    df_geo = pd.read_csv(geo_raw_path)
    df_geo["STATUS"] = pd.to_numeric(df_geo["STATUS"], errors="coerce").fillna(0).astype("int16")

    for status in STATUS_LEVELS:
        # 1. Definição da Máscara Booleana e do Sufixo do arquivo
        if status == FILTER_SOMENTE_CRITICAS:
            mask = df_geo["STATUS"] > 2
            suffix = "somente_criticas"
        elif status == FILTER_COM_ATRASO:
            mask = df_geo["STATUS"] > 1
            suffix = "com_atraso"
        elif status == FILTER_CONTINGENCIA:
            if "EH_URNA_CONTINGENCIA" in df_geo.columns:
                mask = df_geo["EH_URNA_CONTINGENCIA"].fillna(False).astype(bool)
            else:
                mask = df_geo["STATUS"] > 0
            suffix = "contingencia"
        else:
            mask = df_geo["STATUS"] == status
            suffix = f"n{status}"
        
        # Cria um slice isolado na memória
        df_filtered = df_geo[mask].copy()
        
        if df_filtered.empty:
            print(f"  -> Nenhum registro encontrado para '{status}'. Ignorando exportação.")
            continue

        # 2. Roteamento de Caminho e Compressão
        # Filtros agregados textuais vão para data_map em CSV nativo (para Fallbacks rápidos)
        # Níveis numéricos unitários vão compactados (zip) para poupar espaço em disco
        if isinstance(status, str):
            out_path = f"data/data_map/df_locais_{suffix}_{year}.csv"
            compression = None
        else:
            out_path = f"data/geo/{year}_geo_{suffix}.csv.zip"
            compression = "zip"

        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        # 3. Exportação dos Dados
        if compression:
            df_filtered.to_csv(out_path, index=False, compression=compression)
        else:
            df_filtered.to_csv(out_path, index=False)
            
        print(f"  -> Gerado: {out_path} ({len(df_filtered)} registros)")


def main() -> None:
    """Função orquestradora do script."""
    print("Iniciando pipeline de pré-processamento geográfico...")
    for year in YEARS:
        preprocess_geo_for_year(year)
    print("\nPré-processamento geográfico concluído com sucesso!")


if __name__ == "__main__":
    main()
