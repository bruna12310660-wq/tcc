import unicodedata

import pandas as pd

import config_etl as cfg

FORMATOS_DATA = ["%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"]



# FUNÇÕES AUXILIARES

def normalizar_chave(texto):
    """'  INDICAÇÃO ' -> 'indicacao' (usado para comparar grafias)."""
    if pd.isna(texto):
        return texto
    sem_acento = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().split())


def criar_mapa(valores_oficiais, sinonimos=None) -> dict:
    mapa = {normalizar_chave(v): v for v in valores_oficiais}
    for oficial, lista in (sinonimos or {}).items():
        mapa.update({normalizar_chave(s): oficial for s in lista})
    return mapa


MAPA_CANAIS = criar_mapa(cfg.CANAIS.keys(), cfg.CANAIS)
MAPA_SEGMENTOS = criar_mapa(cfg.SEGMENTOS)
MAPA_STATUS_LEAD = criar_mapa(cfg.STATUS_LEAD)
MAPA_STATUS_OPORTUNIDADE = criar_mapa(cfg.STATUS_OPORTUNIDADE)


def padronizar(serie: pd.Series, mapa: dict) -> pd.Series:
    return serie.map(normalizar_chave).map(mapa)


def limpar_texto(serie: pd.Series) -> pd.Series:
    """Remove espaços nas pontas e espaços repetidos no meio."""
    return serie.str.split().str.join(" ")


def contar_alterados(original: pd.Series, novo: pd.Series) -> int:
    return int((original.notna() & (original != novo)).sum())


def converter_data(serie: pd.Series):
    """Tenta os formatos conhecidos em ordem. Retorna (datas, n_alternativos, n_invalidos)."""
    resultado = pd.to_datetime(serie, format=FORMATOS_DATA[0], errors="coerce")
    formato_padrao = resultado.notna()
    for formato in FORMATOS_DATA[1:]:
        faltantes = resultado.isna() & serie.notna()
        resultado.loc[faltantes] = pd.to_datetime(serie[faltantes], format=formato, errors="coerce")
    alternativos = int((resultado.notna() & ~formato_padrao).sum())
    invalidos = int((resultado.isna() & serie.notna()).sum())
    return resultado, alternativos, invalidos


def converter_moeda(serie: pd.Series) -> pd.Series:
    """'R$ 1.234,50' -> 1234.50"""
    limpo = (serie.str.replace("R$", "", regex=False)
                  .str.replace(".", "", regex=False)
                  .str.replace(",", ".", regex=False)
                  .str.strip())
    return pd.to_numeric(limpo, errors="coerce")


def registrar(relatorio: list, arquivo: str, regra: str, acao: str, quantidade) -> None:
    relatorio.append({"arquivo": arquivo, "regra": regra, "acao": acao, "quantidade": int(quantidade)})


def remover_duplicados(df, coluna_id, arquivo, relatorio):
    antes = len(df)
    df = df.drop_duplicates(subset=coluna_id, keep="first")
    registrar(relatorio, arquivo, "Registro duplicado (mesmo ID)", "descartado", antes - len(df))
    return df


def converter_datas_tabela(df, colunas, arquivo, relatorio):
    for coluna in colunas:
        df[coluna], alternativos, invalidos = converter_data(df[coluna])
        registrar(relatorio, arquivo, f"Data em formato alternativo ({coluna})", "corrigido", alternativos)
        if invalidos:
            registrar(relatorio, arquivo, f"Data inválida ({coluna})", "anulado", invalidos)
    return df


def descartar(df, mascara, arquivo, regra, relatorio):
    registrar(relatorio, arquivo, regra, "descartado", mascara.sum())
    return df[~mascara]



# TRANSFORMAÇÕES POR TABELA

def transformar_usuarios(df, relatorio):
    df = df.copy()
    df["nome"] = limpar_texto(df["nome"])
    df["email"] = df["email"].str.strip().str.lower()
    df["perfil"] = limpar_texto(df["perfil"])
    return df


def transformar_campanhas(df, relatorio):
    arq = "campanhas"
    df = df.copy()
    df = converter_datas_tabela(df, ["data_inicio", "data_fim"], arq, relatorio)

    nome = limpar_texto(df["nome_campanha"])
    registrar(relatorio, arq, "Espaços extras no nome da campanha", "corrigido",
              contar_alterados(df["nome_campanha"], nome))
    df["nome_campanha"] = nome

    canal = padronizar(df["canal"], MAPA_CANAIS)
    registrar(relatorio, arq, "Canal com grafia não padronizada", "corrigido",
              contar_alterados(df["canal"], canal))
    df["canal"] = canal

    df["tipo_canal"] = limpar_texto(df["tipo_canal"])
    df["investimento"] = converter_moeda(df["investimento"])
    registrar(relatorio, arq, "Investimento convertido de texto para número", "corrigido", len(df))
    df["responsavel_email"] = df["responsavel_email"].str.strip().str.lower()

    invalidos = df[["canal", "data_inicio", "data_fim", "investimento"]].isna().any(axis=1)
    return descartar(df, invalidos, arq, "Campo obrigatório inválido", relatorio)


def transformar_leads(df, campanhas, relatorio):
    arq = "leads"
    df = df.copy()

    # Datas antes da deduplicação: cópias podem ter formatos diferentes
    df = converter_datas_tabela(df, ["data_nascimento", "data_criacao", "data_conversao"], arq, relatorio)
    df = remover_duplicados(df, "id_lead", arq, relatorio)

    segmento = padronizar(df["segmento"], MAPA_SEGMENTOS)
    registrar(relatorio, arq, "Segmento com grafia não padronizada", "corrigido",
              contar_alterados(df["segmento"], segmento))
    df["segmento"] = segmento

    status = padronizar(df["status"], MAPA_STATUS_LEAD)
    registrar(relatorio, arq, "Status com grafia não padronizada", "corrigido",
              contar_alterados(df["status"], status))
    df["status"] = status

    # UF inferida a partir da cidade (dicionário construído com os próprios dados)
    df["cidade"] = limpar_texto(df["cidade"])
    df["uf"] = df["uf"].str.strip().str.upper()
    mapa_uf = df.dropna(subset=["uf"]).groupby("cidade")["uf"].agg(lambda s: s.mode().iat[0])
    nulas_antes = df["uf"].isna().sum()
    df.loc[df["uf"].isna(), "uf"] = df.loc[df["uf"].isna(), "cidade"].map(mapa_uf)
    registrar(relatorio, arq, "UF ausente inferida a partir da cidade", "corrigido",
              nulas_antes - df["uf"].isna().sum())
    df["regiao"] = df["uf"].map(cfg.REGIOES)

    # Faixa etária calculada na data de criação do lead
    idade = (df["data_criacao"] - df["data_nascimento"]).dt.days / 365.25
    faixa = pd.cut(idade, bins=cfg.FAIXAS_ETARIAS_LIMITES,
                   labels=cfg.FAIXAS_ETARIAS_ROTULOS, right=False)
    df["faixa_etaria"] = faixa.astype(object).fillna("Não informada")
    registrar(relatorio, arq, "Data de nascimento ausente (faixa 'Não informada')", "marcado",
              df["data_nascimento"].isna().sum())

    # Minimização de dados pessoais (LGPD)
    df = df.drop(columns=["nome", "email", "telefone", "data_nascimento"])
    registrar(relatorio, arq, "Dados pessoais removidos (LGPD)", "anonimizado", len(df))

    df = descartar(df, ~df["id_campanha"].isin(campanhas["id_campanha"]), arq,
                   "Lead sem campanha válida", relatorio)
    invalidos = df[["status", "segmento", "data_criacao"]].isna().any(axis=1)
    return descartar(df, invalidos, arq, "Campo obrigatório inválido", relatorio)


def transformar_oportunidades(df, leads, relatorio):
    arq = "oportunidades"
    df = df.copy()

    df = converter_datas_tabela(df, ["data_criacao", "data_fechamento"], arq, relatorio)
    df = remover_duplicados(df, "id_oportunidade", arq, relatorio)

    status = padronizar(df["status"], MAPA_STATUS_OPORTUNIDADE)
    registrar(relatorio, arq, "Status com grafia não padronizada", "corrigido",
              contar_alterados(df["status"], status))
    df["status"] = status

    df["valor"] = converter_moeda(df["valor"])
    registrar(relatorio, arq, "Valor convertido de texto para número", "corrigido", len(df))
    df["ganha"] = df["ganha"].str.strip().str.lower().eq("true")

    # Regras de negócio definidas
    df = descartar(df, ~df["id_lead"].isin(leads["id_lead"]), arq,
                   "Oportunidade órfã (lead inexistente)", relatorio)
    df = descartar(df, df["valor"] < 0, arq, "Valor negativo (não confiável)", relatorio)

    convertidos = leads.loc[leads["status"] == "Convertido", "id_lead"]
    df = descartar(df, ~df["id_lead"].isin(convertidos), arq,
                   "Oportunidade de lead não convertido", relatorio)

    incoerente = df["data_fechamento"] < df["data_criacao"]
    df.loc[incoerente, "data_fechamento"] = pd.NaT
    registrar(relatorio, arq, "Fechamento anterior à criação (data 'não informada')", "corrigido",
              incoerente.sum())

    # A campanha é herdada do lead (permite ROI por campanha e RLS)
    df = df.merge(leads[["id_lead", "id_campanha"]], on="id_lead", how="left")

    invalidos = df[["status", "valor", "data_criacao"]].isna().any(axis=1)
    return descartar(df, invalidos, arq, "Campo obrigatório inválido", relatorio)



# ORQUESTRAÇÃO

def transformar(dados: dict):
    relatorio = []
    usuarios = transformar_usuarios(dados["usuarios"], relatorio)
    campanhas = transformar_campanhas(dados["campanhas"], relatorio)
    leads = transformar_leads(dados["leads"], campanhas, relatorio)
    oportunidades = transformar_oportunidades(dados["oportunidades"], leads, relatorio)
    limpos = {"usuarios": usuarios, "campanhas": campanhas,
              "leads": leads, "oportunidades": oportunidades}
    return limpos, relatorio