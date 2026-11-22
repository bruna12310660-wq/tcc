#Pipeline ETL: arquivos -> sql server

from transformacoes import transformar
import time
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.types import NVARCHAR

import config_etl as cfg

from carga_dw import construir_modelo, carregar_dw



# CONEXÃO E LOG

def criar_conexao():
    conn_str = (
        f"DRIVER={{{cfg.DRIVER}}};"
        f"SERVER={cfg.SERVIDOR};"
        f"DATABASE={cfg.BANCO};"
        "Trusted_Connection=yes;"
    )
    return create_engine("mssql+pyodbc:///?odbc_connect=" + quote_plus(conn_str),
                         fast_executemany=True)


def registrar_log(engine, etapa, status, arquivo=None, lidos=None,
                  descartados=None, carregados=None, duracao=None, mensagem=None):
    sql = text("""
        INSERT INTO etl.log_execucao
            (etapa, arquivo, registros_lidos, registros_descartados,
             registros_carregados, duracao_segundos, status, mensagem)
        VALUES (:etapa, :arquivo, :lidos, :descartados, :carregados, :duracao, :status, :mensagem)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {
            "etapa": etapa, "arquivo": arquivo, "lidos": lidos,
            "descartados": descartados, "carregados": carregados,
            "duracao": round(duracao, 2) if duracao is not None else None,
            "status": status, "mensagem": mensagem,
        })



# EXTRAÇÃO

def extrair(engine) -> dict:
    """Lê os arquivos exportados do CRM, preservando tudo como nvarchar."""
    dados = {}
    for nome in cfg.ARQUIVOS:
        inicio = time.time()
        caminho = cfg.DIR_ENTRADA / f"{nome}.csv"
        df = pd.read_csv(caminho, sep=cfg.SEPARADOR, encoding=cfg.ENCODING, dtype=str)
        dados[nome] = df
        registrar_log(engine, "Extração", "Sucesso", arquivo=caminho.name,
                      lidos=len(df), duracao=time.time() - inicio)
        print(f"  Extraído {caminho.name}: {len(df)} linhas")
    return dados



# CARGA NA STAGING

def carregar_stg(engine, dados: dict) -> None:
    for nome, df in dados.items():
        inicio = time.time()
        tipos = {coluna: NVARCHAR(255) for coluna in df.columns}
        df.to_sql(nome, engine, schema="stg", if_exists="replace",
                  index=False, chunksize=1000, dtype=tipos)
        registrar_log(engine, "Carga staging", "Sucesso", arquivo=f"stg.{nome}",
                      carregados=len(df), duracao=time.time() - inicio)
        print(f"  Carregado stg.{nome}: {len(df)} linhas")


# EXECUÇÃO

if __name__ == "__main__":
    inicio_total = time.time()
    engine = criar_conexao()

    try:
        print("EXTRAÇÃO")
        dados = extrair(engine)

        print("\nCARGA STAGING")
        carregar_stg(engine, dados)

        print("\n=== TRANSFORMAÇÃO ===")
        inicio = time.time()
        limpos, relatorio = transformar(dados)

        for item in relatorio:
            registrar_log(engine, f"Regra: {item['regra']}", "Sucesso", arquivo=item["arquivo"],
                          descartados=item["quantidade"] if item["acao"] == "descartado" else None,
                          mensagem=f"{item['acao']}: {item['quantidade']}")

        for nome, df in limpos.items():
            lidos = len(dados[nome])
            registrar_log(engine, "Transformação", "Sucesso", arquivo=nome, lidos=lidos,
                          descartados=lidos - len(df), carregados=len(df),
                          duracao=time.time() - inicio)
            print(f"  {nome}: {lidos} lidos -> {len(df)} válidos")

        print("\n=== REGRAS APLICADAS ===")
        print(pd.DataFrame(relatorio).to_string(index=False))

        print("\n=== CARGA DATA WAREHOUSE ===")
        inicio = time.time()
        modelo = construir_modelo(limpos)
        contagens = carregar_dw(engine, modelo)
        for tabela, quantidade in contagens.items():
            registrar_log(engine, "Carga DW", "Sucesso", arquivo=f"dw.{tabela}",
                          carregados=quantidade)
            print(f"  dw.{tabela}: {quantidade} linhas")
        registrar_log(engine, "Carga DW (total)", "Sucesso", duracao=time.time() - inicio)

        registrar_log(engine, "Pipeline completo", "Sucesso",
                      duracao=time.time() - inicio_total)
        print(f"\n Pipeline concluído em {time.time() - inicio_total:.2f} segundos.")

    except Exception as erro:
        registrar_log(engine, "Pipeline completo.", "Falha.",
                      duracao=time.time() - inicio_total, mensagem=str(erro)[:4000])
        raise