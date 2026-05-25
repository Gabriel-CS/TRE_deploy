
import os
import pandas as pd
import geopandas as gpd
from src.analysis import UrnasCriticasAnalysis  # reutiliza a lógica de criticidade

# Configuração dos anos e níveis
YEARS = ["2018", "2022"]
STATUS_LEVELS = [0, 1, 2, 3, 4, None]  # None = todos os críticos (>0)

def preprocess_geo_for_year(year: str):
    """Gera arquivos geográficos particionados para um ano específico."""
    # Caminhos dos dados brutos (ajuste conforme sua estrutura)
    base_path = f"data/output/{year}_1t_SE_urnas_consolidado.zip"
    completas_path = f"data/output/urnas_completas_{year}_1t.zip"
    
    # Carrega o dataset completo de seções (apenas colunas necessárias)
    df_completas = pd.read_csv(completas_path, sep=";", encoding="utf-8", compression="zip")

    # basta filtrar por ano e status.
    geo_raw_path = f"data/data_map/locais_criticos_{year}.csv"
    if os.path.exists(geo_raw_path):
        df_geo = pd.read_csv(geo_raw_path)
        
        for status in STATUS_LEVELS:
            if status is None:
                mask = df_geo["STATUS"] > 0
                suffix = "all"
            else:
                mask = df_geo["STATUS"] == status
                suffix = f"n{status}"
            
            df_filtered = df_geo[mask].copy()
            if not df_filtered.empty:
                # Salva como CSV compactado
                out_path = f"data/geo/{year}_geo_{suffix}.csv.zip"
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                df_filtered.to_csv(out_path, index=False, compression="zip")
                print(f"Gerado: {out_path} ({len(df_filtered)} registros)")
    else:
        print(f"Arquivo {geo_raw_path} não encontrado. Pulando pré-processamento.")

if __name__ == "__main__":
    for year in YEARS:
        preprocess_geo_for_year(year)