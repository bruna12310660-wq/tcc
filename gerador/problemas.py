"""
Insere problemas de qualidade controlados no gabarito e gera os arquivos brutos,
simulando o export de um CRM. Cada problema inserido é registrado no log,
que servirá de referência para validar o ETL.
"""

import json
import unicodedata
from datetime import timedelta

import numpy as np
import pandas as pd

import config as cfg

rng = np.random.default_rng(cfg.SEED + 1)
P = cfg.PROBLEMAS
log = []

COLUNAS_DATA = {
    "campanhas": ["data_inicio", "data_fim"],
    "leads": ["data_nascimento", "data_criacao", "data_conversao"],
    "oportunidades": ["data_criacao", "data_fechamento"],
}
COLUNA_ID = {"campanhas": "id_campanha", "leads": "id_lead", "oportunidades": "id_oportunidade"}

# Sinônimos e grafias que aparecem em campos de texto livre de um CRM
VARIACOES_CANAL = {
    "Google Ads": ["google ads", "GOOGLE ADS", "Google", "Adwords"],
    "Meta Ads": ["meta ads", "Facebook/Instagram", "META", "Facebook Ads"],
    "LinkedIn Ads": ["Linkedin", "linkedin ads", "LINKEDIN"],
    "E-mail Marketing": ["Email Marketing", "e-mail mkt", "EMAIL"],
    "Eventos": ["eventos", "Evento", "EVENTOS"],
    "Indicação": ["Indicacao", "indicação", "INDICAÇÃO"],
}


# Funções Auxiliares
def ler_gabarito(nome: str) -> pd.DataFrame:
    return pd.read_csv(cfg.DIR_GABARITO / f"{nome}.csv", sep=cfg.SEPARADOR,
                       encoding=cfg.ENCODING, parse_dates=COLUNAS_DATA.get(nome, []))


def sortear(df: pd.DataFrame, pct: float, filtro=None) -> np.ndarray:
    """Sorteia uma fração dos registros (opcionalmente dentro de um filtro)."""
    candidatos = df.index if filtro is None else df.index[np.asarray(filtro)]
    n = int(round(len(candidatos) * pct))
    return rng.choice(candidatos, size=n, replace=False)


def registrar(arquivo: str, problema: str, coluna: str, quantidade: int, ids=None) -> None:
    log.append({
        "arquivo": f"{arquivo}.csv",
        "problema": problema,
        "coluna": coluna,
        "quantidade": int(quantidade),
        "ids_afetados": [str(i) for i in ids] if ids is not None else [],
    })


def remover_acentos(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def variar_texto(texto: str) -> str:
    variacoes = [str.lower, str.upper, lambda s: f"  {s} ", remover_acentos]
    return variacoes[int(rng.integers(len(variacoes)))](texto)


def formatar_moeda(valor: float) -> str:
    """1234.5 -> 'R$ 1.234,50' (padrão brasileiro, como em exports de CRM)."""
    texto = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def duplicar(df: pd.DataFrame, nome: str, pct: float, problema: str) -> pd.DataFrame:
    idx = sortear(df, pct)
    registrar(nome, problema, COLUNA_ID[nome], len(idx), df.loc[idx, COLUNA_ID[nome]])
    resultado = pd.concat([df, df.loc[idx]], ignore_index=True)
    return resultado.iloc[rng.permutation(len(resultado))].reset_index(drop=True)


def formatar_datas(df: pd.DataFrame, nome: str) -> pd.DataFrame:
    """Converte datas para texto no padrão dd/mm/aaaa, com parte em formatos alternativos."""
    for coluna in COLUNAS_DATA[nome]:
        texto = df[coluna].dt.strftime("%d/%m/%Y")
        idx = sortear(df, P["formato_data_variado"], df[coluna].notna())
        formatos = rng.choice(["%Y-%m-%d", "%d.%m.%Y"], size=len(idx))
        texto.loc[idx] = [d.strftime(f) for d, f in zip(df.loc[idx, coluna], formatos)]
        df[coluna] = texto
        registrar(nome, "formato_data_variado", coluna, len(idx), df.loc[idx, COLUNA_ID[nome]])
    return df


# Problemas por arquivo
def sujar_campanhas(df: pd.DataFrame) -> pd.DataFrame:
    idx = sortear(df, P["canal_texto_variado"])
    df.loc[idx, "canal"] = [str(rng.choice(VARIACOES_CANAL[c])) for c in df.loc[idx, "canal"]]
    registrar("campanhas", "canal_texto_variado", "canal", len(idx), df.loc[idx, "id_campanha"])

    idx = sortear(df, P["nome_campanha_espacos"])
    df.loc[idx, "nome_campanha"] = [f"  {n.replace(' - ', '  -  ')} " for n in df.loc[idx, "nome_campanha"]]
    registrar("campanhas", "nome_campanha_espacos", "nome_campanha", len(idx), df.loc[idx, "id_campanha"])

    df["investimento"] = df["investimento"].map(formatar_moeda)
    registrar("campanhas", "moeda_como_texto", "investimento", len(df))

    return formatar_datas(df, "campanhas")


def sujar_leads(df: pd.DataFrame) -> pd.DataFrame:
    idx = sortear(df, P["uf_nula"])
    df.loc[idx, "uf"] = np.nan
    registrar("leads", "uf_nula", "uf", len(idx), df.loc[idx, "id_lead"])

    idx = sortear(df, P["data_nascimento_nula"])
    df.loc[idx, "data_nascimento"] = pd.NaT
    registrar("leads", "data_nascimento_nula", "data_nascimento", len(idx), df.loc[idx, "id_lead"])

    idx = sortear(df, P["segmento_texto_variado"])
    df.loc[idx, "segmento"] = df.loc[idx, "segmento"].map(variar_texto)
    registrar("leads", "segmento_texto_variado", "segmento", len(idx), df.loc[idx, "id_lead"])

    idx = sortear(df, P["status_texto_variado"])
    df.loc[idx, "status"] = df.loc[idx, "status"].map(variar_texto)
    registrar("leads", "status_texto_variado", "status", len(idx), df.loc[idx, "id_lead"])

    df = duplicar(df, "leads", P["leads_duplicados"], "registro_duplicado")
    return formatar_datas(df, "leads")


def sujar_oportunidades(df: pd.DataFrame) -> pd.DataFrame:
    idx = sortear(df, P["status_texto_variado"])
    df.loc[idx, "status"] = df.loc[idx, "status"].map(variar_texto)
    registrar("oportunidades", "status_texto_variado", "status", len(idx), df.loc[idx, "id_oportunidade"])

    idx = sortear(df, P["oportunidades_orfas"])
    df.loc[idx, "id_lead"] = [f"LD-9{i:05d}" for i in range(len(idx))]
    registrar("oportunidades", "oportunidade_orfa", "id_lead", len(idx), df.loc[idx, "id_oportunidade"])

    idx = sortear(df, P["fechamento_antes_criacao"], df["data_fechamento"].notna())
    dias = pd.to_timedelta(rng.integers(1, 31, size=len(idx)), unit="D")
    df.loc[idx, "data_fechamento"] = df.loc[idx, "data_criacao"] - dias
    registrar("oportunidades", "fechamento_antes_criacao", "data_fechamento", len(idx),
              df.loc[idx, "id_oportunidade"])

    idx = sortear(df, P["valor_negativo"])
    df.loc[idx, "valor"] = -df.loc[idx, "valor"]
    registrar("oportunidades", "valor_negativo", "valor", len(idx), df.loc[idx, "id_oportunidade"])

    df["valor"] = df["valor"].map(formatar_moeda)
    registrar("oportunidades", "moeda_como_texto", "valor", len(df))

    df = duplicar(df, "oportunidades", P["oportunidades_duplicadas"], "registro_duplicado")
    return formatar_datas(df, "oportunidades")



# Execução
if __name__ == "__main__":
    brutos = {
        "usuarios": ler_gabarito("usuarios"),
        "campanhas": sujar_campanhas(ler_gabarito("campanhas")),
        "leads": sujar_leads(ler_gabarito("leads")),
        "oportunidades": sujar_oportunidades(ler_gabarito("oportunidades")),
    }

    cfg.DIR_BRUTOS.mkdir(parents=True, exist_ok=True)
    for nome, df in brutos.items():
        df.to_csv(cfg.DIR_BRUTOS / f"{nome}.csv", sep=cfg.SEPARADOR, encoding=cfg.ENCODING, index=False)

    with open(cfg.ARQ_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print("=== ARQUIVOS BRUTOS ===")
    for nome, df in brutos.items():
        print(f"  {nome}.csv: {len(df)} linhas")

    print("\n=== PROBLEMAS INSERIDOS ===")
    resumo = pd.DataFrame(log)[["arquivo", "problema", "coluna", "quantidade"]]
    print(resumo.to_string(index=False))