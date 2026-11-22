#Validação automática do pipeline: compara o Data Warehouse com os dados limpos e com o log de problemas inseridos pelo gerador.

import json
import sys
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine

RAIZ = Path(__file__).resolve().parent.parent
sys.path.append(str(RAIZ / "etl"))
import config_etl as cfg  # noqa: E402

DIR_GABARITO = RAIZ / "dados" / "gabarito"
ARQ_LOG = RAIZ / "dados" / "log_problemas.json"
ARQ_RESULTADO = RAIZ / "dados" / "resultado_validacao.csv"

resultados = []



# FUNÇÕES AUXILIARES

def verificar(categoria, descricao, esperado, obtido):
    resultados.append({"categoria": categoria, "verificacao": descricao,
                       "esperado": esperado, "obtido": obtido,
                       "status": "OK" if esperado == obtido else "FALHA"})


def iguais(a, b, tipo="texto"):
    if tipo == "numero":
        return (a.astype(float) - b.astype(float)).abs() < 0.005
    if tipo == "data":
        return pd.to_datetime(a) == pd.to_datetime(b)
    return a == b


def ler_gabarito(nome, datas=()):
    return pd.read_csv(DIR_GABARITO / f"{nome}.csv", sep=";", encoding="utf-8-sig",
                       parse_dates=list(datas))


def ids_do_log(log, arquivo, problema):
    return set().union(*[set(item["ids_afetados"]) for item in log
                         if item["arquivo"] == arquivo and item["problema"] == problema])


def criar_conexao():
    conn_str = (f"DRIVER={{{cfg.DRIVER}}};SERVER={cfg.SERVIDOR};"
                f"DATABASE={cfg.BANCO};Trusted_Connection=yes;")
    return create_engine("mssql+pyodbc:///?odbc_connect=" + quote_plus(conn_str))


def calcular_roi(opps, campanhas, col_campanha, col_invest):
    receita = opps[opps["ganha"]].groupby(col_campanha)["valor"].sum()
    roi = campanhas.set_index(col_campanha)[[col_invest]].join(receita.rename("receita"))
    roi["receita"] = roi["receita"].fillna(0).astype(float)
    roi[col_invest] = roi[col_invest].astype(float)
    return (roi["receita"] - roi[col_invest]) / roi[col_invest]



# CARGA DOS DADOS DE REFERÊNCIA E DO DW

log = json.loads(ARQ_LOG.read_text(encoding="utf-8"))
gab_usuarios = ler_gabarito("usuarios")
gab_camp = ler_gabarito("campanhas", ["data_inicio", "data_fim"])
gab_leads = ler_gabarito("leads", ["data_criacao"])
gab_opps = ler_gabarito("oportunidades", ["data_criacao"])
gab_roi = ler_gabarito("roi_campanhas").set_index("id_campanha")["roi"]

engine = criar_conexao()
dw_resp = pd.read_sql("SELECT * FROM dw.dim_responsavel", engine)
dw_camp = pd.read_sql("""
    SELECT c.id_campanha, c.nome_campanha, c.canal_nome, c.investimento,
           c.data_inicio, c.data_fim, r.email AS responsavel_email
    FROM dw.dim_campanha c
    JOIN dw.dim_responsavel r ON r.sk_responsavel = c.sk_responsavel""", engine)
dw_leads = pd.read_sql("""
    SELECT l.id_lead, l.uf, l.segmento, s.nome AS status,
           d.data AS data_criacao, f.indicador_conversao
    FROM dw.fato_lead f
    JOIN dw.dim_lead l   ON l.sk_lead = f.sk_lead
    JOIN dw.dim_status s ON s.sk_status = f.sk_status
    JOIN dw.dim_data d   ON d.sk_data = f.sk_data_criacao""", engine)
dw_opps = pd.read_sql("""
    SELECT o.id_oportunidade, l.id_lead, c.id_campanha, s.nome AS status,
           o.indicador_ganha AS ganha, o.valor, o.sk_data_fechamento,
           d.data AS data_criacao
    FROM dw.fato_oportunidade o
    JOIN dw.dim_lead l     ON l.sk_lead = o.sk_lead
    JOIN dw.dim_campanha c ON c.sk_campanha = o.sk_campanha
    JOIN dw.dim_status s   ON s.sk_status = o.sk_status
    JOIN dw.dim_data d     ON d.sk_data = o.sk_data_criacao""", engine)
colunas_dim_lead = set(pd.read_sql("""
    SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'dw' AND TABLE_NAME = 'dim_lead'""", engine)["COLUMN_NAME"])

# Oportunidades que as regras de negócio devem descartar
orfas = ids_do_log(log, "oportunidades.csv", "oportunidade_orfa")
negativas = ids_do_log(log, "oportunidades.csv", "valor_negativo")
descartadas = orfas | negativas
gab_opps_validas = gab_opps[~gab_opps["id_oportunidade"].isin(descartadas)]



# 1. VOLUME

verificar("Volume", "Usuários", len(gab_usuarios), len(dw_resp))
verificar("Volume", "Campanhas", len(gab_camp), len(dw_camp))
verificar("Volume", "Leads", len(gab_leads), len(dw_leads))
verificar("Volume", "Oportunidades (gabarito - descartadas pelas regras)",
          len(gab_opps_validas), len(dw_opps))


# 2. UNICIDADE

verificar("Unicidade", "Leads sem ID repetido", True, bool(dw_leads["id_lead"].is_unique))
verificar("Unicidade", "Oportunidades sem ID repetido", True,
          bool(dw_opps["id_oportunidade"].is_unique))


# 3. REGRAS DE NEGÓCIO

ids_dw_opps = set(dw_opps["id_oportunidade"])
verificar("Regra", "Oportunidades órfãs ausentes do DW", 0, len(orfas & ids_dw_opps))
verificar("Regra", "Oportunidades com valor negativo ausentes do DW", 0, len(negativas & ids_dw_opps))

ids_fech = ids_do_log(log, "oportunidades.csv", "fechamento_antes_criacao") - descartadas
fech_dw = dw_opps[dw_opps["id_oportunidade"].isin(ids_fech)]
verificar("Regra", "Fechamento incoerente gravado como 'não informado' (-1)",
          len(ids_fech), int((fech_dw["sk_data_fechamento"] == -1).sum()))

ids_uf = ids_do_log(log, "leads.csv", "uf_nula")
uf = dw_leads[dw_leads["id_lead"].isin(ids_uf)].merge(gab_leads, on="id_lead", suffixes=("_dw", "_gab"))
verificar("Regra", "UF ausente recuperada com o valor correto",
          len(ids_uf), int(iguais(uf["uf_dw"], uf["uf_gab"]).sum()))


# 4. FIDELIDADE (campo a campo com o gabarito)

c = dw_camp.merge(gab_camp, on="id_campanha", suffixes=("_dw", "_gab"))
ok_camp = (iguais(c["canal_nome"], c["canal"]) &
           iguais(c["nome_campanha_dw"], c["nome_campanha_gab"]) &
           iguais(c["investimento_dw"], c["investimento_gab"], "numero") &
           iguais(c["data_inicio_dw"], c["data_inicio_gab"], "data") &
           iguais(c["data_fim_dw"], c["data_fim_gab"], "data") &
           iguais(c["responsavel_email_dw"], c["responsavel_email_gab"]))
verificar("Fidelidade", "Campanhas idênticas ao gabarito", len(gab_camp), int(ok_camp.sum()))

l = dw_leads.merge(gab_leads, on="id_lead", suffixes=("_dw", "_gab"))
ok_leads = (iguais(l["segmento_dw"], l["segmento_gab"]) &
            iguais(l["status_dw"], l["status_gab"]) &
            iguais(l["uf_dw"], l["uf_gab"]) &
            iguais(l["data_criacao_dw"], l["data_criacao_gab"], "data"))
verificar("Fidelidade", "Leads idênticos ao gabarito", len(gab_leads), int(ok_leads.sum()))

o = dw_opps.merge(gab_opps, on="id_oportunidade", suffixes=("_dw", "_gab"))
ok_opps = (iguais(o["valor_dw"], o["valor_gab"], "numero") &
           iguais(o["status_dw"], o["status_gab"]) &
           iguais(o["ganha_dw"].astype(bool), o["ganha_gab"].astype(bool)) &
           iguais(o["id_lead_dw"], o["id_lead_gab"]) &
           iguais(o["data_criacao_dw"], o["data_criacao_gab"], "data"))
verificar("Fidelidade", "Oportunidades idênticas ao gabarito", len(gab_opps_validas), int(ok_opps.sum()))


# 5. LGPD

pessoais = {"nome", "email", "telefone", "data_nascimento"}
verificar("LGPD", "Colunas de dados pessoais em dw.dim_lead", 0, len(pessoais & colunas_dim_lead))


# 6. FUNIL E ROI

verificar("Funil", "Leads convertidos",
          int((gab_leads["status"] == "Convertido").sum()), int(dw_leads["indicador_conversao"].sum()))
verificar("Funil", "Oportunidades ganhas",
          int(gab_opps_validas["ganha"].sum()), int(dw_opps["ganha"].astype(bool).sum()))

gab_opps_camp = gab_opps_validas.merge(gab_leads[["id_lead", "id_campanha"]], on="id_lead")
roi_esperado = calcular_roi(gab_opps_camp, gab_camp, "id_campanha", "investimento")
dw_opps["ganha"] = dw_opps["ganha"].astype(bool)
roi_dw = calcular_roi(dw_opps, dw_camp, "id_campanha", "investimento")
comparacao = (roi_esperado - roi_dw.reindex(roi_esperado.index)).abs() < 1e-6
verificar("ROI", "ROI por campanha idêntico ao cálculo independente",
          len(roi_esperado), int(comparacao.sum()))

campanhas_afetadas = int(((gab_roi - roi_dw.reindex(gab_roi.index)).abs() > 1e-6).sum())



# RESULTADO

resultado = pd.DataFrame(resultados)
resultado.to_csv(ARQ_RESULTADO, sep=";", encoding="utf-8-sig", index=False)

print(resultado.to_string(index=False))
falhas = int((resultado["status"] == "FALHA").sum())
print(f"\nInformativo: {campanhas_afetadas} campanha(s) tiveram o ROI alterado "
      f"pelas regras de descarte em relação ao gabarito bruto.")
print(f"\n{len(resultado) - falhas} de {len(resultado)} verificações aprovadas.")
sys.exit(1 if falhas else 0)