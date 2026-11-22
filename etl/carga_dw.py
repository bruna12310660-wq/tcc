import pandas as pd
from sqlalchemy import text

import config_etl as cfg

SK_NAO_INFORMADO = -1

# Ordem de carga respeitando as chaves estrangeiras (dimensões antes dos fatos)
ORDEM_CARGA = ["dim_data", "dim_responsavel", "dim_status", "dim_campanha",
               "dim_lead", "fato_lead", "fato_oportunidade"]



# FUNÇÕES AUXILIARES

def data_para_sk(serie: pd.Series) -> pd.Series:
    """2026-03-15 -> 20260315 | data ausente -> -1"""
    sk = serie.dt.year * 10000 + serie.dt.month * 100 + serie.dt.day
    return sk.fillna(SK_NAO_INFORMADO).astype(int)


def atribuir_sk(df: pd.DataFrame, coluna_id: str, nome_sk: str) -> pd.DataFrame:
    """Gera chaves substitutas sequenciais, ordenadas pela chave natural."""
    df = df.sort_values(coluna_id).reset_index(drop=True)
    df.insert(0, nome_sk, range(1, len(df) + 1))
    return df



# DIMENSÕES

def construir_dim_data(limpos: dict) -> pd.DataFrame:
    camp, leads, opps = limpos["campanhas"], limpos["leads"], limpos["oportunidades"]
    todas = pd.concat([camp["data_inicio"], camp["data_fim"],
                       leads["data_criacao"], leads["data_conversao"],
                       opps["data_criacao"], opps["data_fechamento"]]).dropna()

    dim = pd.DataFrame({"data": pd.date_range(todas.min(), todas.max(), freq="D")})
    dim["sk_data"] = data_para_sk(dim["data"])
    dim["dia"] = dim["data"].dt.day
    dim["mes"] = dim["data"].dt.month
    dim["nome_mes"] = dim["mes"].map(lambda m: cfg.MESES[m - 1])
    dim["trimestre"] = dim["data"].dt.quarter
    dim["ano"] = dim["data"].dt.year
    dim["semana_ano"] = dim["data"].dt.isocalendar().week.astype(int)
    dim["dia_semana"] = dim["data"].dt.dayofweek + 1          # 1 = segunda-feira
    dim["nome_dia_semana"] = dim["dia_semana"].map(lambda d: cfg.DIAS_SEMANA[d - 1])
    dim["data"] = dim["data"].dt.date

    nao_informado = pd.DataFrame([{"sk_data": SK_NAO_INFORMADO,
                                   "nome_mes": "Não informado",
                                   "nome_dia_semana": "Não informado"}])
    dim = pd.concat([nao_informado, dim], ignore_index=True)

    for coluna in ["dia", "mes", "trimestre", "ano", "semana_ano", "dia_semana"]:
        dim[coluna] = dim[coluna].astype("Int64")

    return dim[["sk_data", "data", "dia", "mes", "nome_mes", "trimestre",
                "ano", "semana_ano", "dia_semana", "nome_dia_semana"]]


def construir_dim_status() -> pd.DataFrame:
    dim = pd.DataFrame(cfg.STATUS, columns=["nome", "descricao", "categoria", "entidade"])
    dim.insert(0, "sk_status", range(1, len(dim) + 1))
    return dim



# MODELO COMPLETO

def construir_modelo(limpos: dict) -> dict:
    usuarios, campanhas = limpos["usuarios"], limpos["campanhas"]
    leads, opps = limpos["leads"], limpos["oportunidades"]

    # --- Dimensões ---
    dim_data = construir_dim_data(limpos)
    dim_status = construir_dim_status()

    dim_responsavel = atribuir_sk(usuarios, "email", "sk_responsavel")[
        ["sk_responsavel", "nome", "email", "perfil"]]
    mapa_responsavel = dict(zip(dim_responsavel["email"], dim_responsavel["sk_responsavel"]))

    dim_campanha = atribuir_sk(campanhas, "id_campanha", "sk_campanha")
    dim_campanha["sk_responsavel"] = dim_campanha["responsavel_email"].map(mapa_responsavel)
    if dim_campanha["sk_responsavel"].isna().any():
        raise ValueError("Existem campanhas com responsável não cadastrado em usuarios.csv")
    dim_campanha = dim_campanha.rename(columns={"canal": "canal_nome", "tipo_canal": "canal_tipo"})
    dim_campanha["data_inicio"] = dim_campanha["data_inicio"].dt.date
    dim_campanha["data_fim"] = dim_campanha["data_fim"].dt.date
    dim_campanha["sk_responsavel"] = dim_campanha["sk_responsavel"].astype(int)
    dim_campanha = dim_campanha[["sk_campanha", "id_campanha", "nome_campanha", "canal_nome",
                                 "canal_tipo", "data_inicio", "data_fim", "investimento",
                                 "sk_responsavel"]]

    dim_lead = atribuir_sk(leads, "id_lead", "sk_lead")[
        ["sk_lead", "id_lead", "cidade", "uf", "regiao", "segmento", "faixa_etaria"]]

    # --- Mapas de chave natural -> chave substituta ---
    mapa_campanha = dict(zip(dim_campanha["id_campanha"], dim_campanha["sk_campanha"]))
    mapa_lead = dict(zip(dim_lead["id_lead"], dim_lead["sk_lead"]))
    status_lead = dim_status[dim_status["entidade"] == "Lead"].set_index("nome")["sk_status"]
    status_opp = dim_status[dim_status["entidade"] == "Oportunidade"].set_index("nome")["sk_status"]

    # --- Fato lead ---
    fato_lead = pd.DataFrame({
        "sk_lead": leads["id_lead"].map(mapa_lead),
        "sk_campanha": leads["id_campanha"].map(mapa_campanha),
        "sk_status": leads["status"].map(status_lead),
        "sk_data_criacao": data_para_sk(leads["data_criacao"]),
        "sk_data_conversao": data_para_sk(leads["data_conversao"]),
        # Convertido = status registrado no CRM (valor real de conversão)
        "indicador_conversao": leads["status"] == "Convertido",
        "dias_ate_conversao": (leads["data_conversao"] - leads["data_criacao"]).dt.days.astype("Int64"),
    })

    # --- Fato oportunidade  ---
    fato_oportunidade = pd.DataFrame({
        "id_oportunidade": opps["id_oportunidade"],
        "sk_lead": opps["id_lead"].map(mapa_lead),
        "sk_campanha": opps["id_campanha"].map(mapa_campanha),
        "sk_status": opps["status"].map(status_opp),
        "sk_data_criacao": data_para_sk(opps["data_criacao"]),
        "sk_data_fechamento": data_para_sk(opps["data_fechamento"]),
        "indicador_ganha": opps["ganha"],
        "valor": opps["valor"],
    })

    return {
        "dim_data": dim_data, "dim_responsavel": dim_responsavel, "dim_status": dim_status,
        "dim_campanha": dim_campanha, "dim_lead": dim_lead,
        "fato_lead": fato_lead, "fato_oportunidade": fato_oportunidade,
    }



# CARGA TRANSACIONAL

def carregar_dw(engine, modelo: dict) -> dict:
    """Apaga e recarrega o DW em uma única transação (tudo ou nada)."""
    contagens = {}
    with engine.begin() as conn:
        for tabela in reversed(ORDEM_CARGA):
            conn.execute(text(f"DELETE FROM dw.{tabela}"))
        for tabela in ORDEM_CARGA:
            modelo[tabela].to_sql(tabela, conn, schema="dw", if_exists="append",
                                  index=False, chunksize=1000)
            contagens[tabela] = len(modelo[tabela])
    return contagens