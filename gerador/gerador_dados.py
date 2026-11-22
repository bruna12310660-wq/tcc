
# Gerador de dados sintéticos de marketing.
# Gera as tabelas na ordem das dependências: usuários -> campanhas -> leads -> oportunidades

import unicodedata
from datetime import timedelta

import numpy as np
import pandas as pd
from faker import Faker

import config as cfg


# Inicialização (reprodutibilidade)

rng = np.random.default_rng(cfg.SEED)
Faker.seed(cfg.SEED)
fake = Faker("pt_BR")

def gerar_email(nome: str) -> str:
    """Converte 'Ana Souza' em 'ana.souza@dominio' (sem acentos)."""
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return f"{sem_acento.lower().replace(' ', '.')}@{cfg.DOMINIO_EMAIL}"



# Usuários

def gerar_usuarios() -> pd.DataFrame:
    perfis = ["Executivo"] * cfg.N_EXECUTIVOS + ["Gerente de Campanha"] * cfg.N_GERENTES
    registros = []
    for perfil in perfis:
        nome = f"{fake.unique.first_name()} {fake.unique.last_name()}"
        registros.append({"nome": nome, "email": gerar_email(nome), "perfil": perfil})
    return pd.DataFrame(registros)



# Campanhas

TEMAS = ["Lançamento", "Black Friday", "Webinar", "Remarketing",
         "Institucional", "Captação B2B", "Promoção Sazonal", "Reengajamento"]


def gerar_campanhas(usuarios: pd.DataFrame) -> pd.DataFrame:
    nomes_canais = list(cfg.CANAIS)
    pesos = [c["peso"] for c in cfg.CANAIS.values()]

    # Distribui as campanhas entre os gerentes de campanha (todos recebem ao menos uma)
    gerentes = usuarios[usuarios["perfil"] == "Gerente de Campanha"].reset_index(drop=True)
    indices = [i % len(gerentes) for i in range(cfg.N_CAMPANHAS)]
    rng.shuffle(indices)

    janela_total = (cfg.DATA_FIM - cfg.DATA_INICIO).days
    registros = []

    for i in range(cfg.N_CAMPANHAS):
        canal = str(rng.choice(nomes_canais, p=pesos))
        params = cfg.CANAIS[canal]

        duracao = int(rng.integers(cfg.DURACAO_CAMPANHA_DIAS[0], cfg.DURACAO_CAMPANHA_DIAS[1] + 1))
        inicio = cfg.DATA_INICIO + timedelta(days=int(rng.integers(0, janela_total - duracao + 1)))
        fim = inicio + timedelta(days=duracao)

        investimento = int(round(rng.uniform(*params["investimento"]) / 100) * 100)
        tema = str(rng.choice(TEMAS))
        gerente = gerentes.loc[indices[i]]

        registros.append({
            "id_campanha": f"CMP-{i + 1:04d}",
            "nome_campanha": f"{canal} - {tema} - {inicio:%m/%Y}",
            "canal": canal,
            "tipo_canal": params["tipo"],
            "data_inicio": inicio,
            "data_fim": fim,
            "investimento": investimento,
            "responsavel_nome": gerente["nome"],
            "responsavel_email": gerente["email"],
            # Parâmetro interno: usado para gerar os leads.
            "eficiencia": float(rng.lognormal(0, cfg.RUIDO_CAMPANHA)),
        })

    return pd.DataFrame(registros)

def gerar_leads(campanhas: pd.DataFrame) -> pd.DataFrame:
    cidades = [c for c, _, _ in cfg.CIDADES]
    ufs = [u for _, u, _ in cfg.CIDADES]
    pesos_cidades = [p for _, _, p in cfg.CIDADES]
    status_nao_conv = list(cfg.STATUS_LEAD_NAO_CONVERTIDO)
    pesos_status = list(cfg.STATUS_LEAD_NAO_CONVERTIDO.values())

    registros = []
    contador = 0

    for _, camp in campanhas.iterrows():
        params = cfg.CANAIS[camp["canal"]]

        # Volume de leads proporcional ao investimento e à eficiência da campanha
        esperado = camp["investimento"] / 1000 * params["leads_por_mil"] * camp["eficiencia"]
        n_leads = int(rng.poisson(esperado))
        prob_conversao = min(params["taxa_conversao"] * np.sqrt(camp["eficiencia"]), 0.9)
        duracao = (camp["data_fim"] - camp["data_inicio"]).days

        for _ in range(n_leads):
            contador += 1

            # Regra: lead criado dentro do período da campanha
            criacao = camp["data_inicio"] + timedelta(days=int(rng.integers(0, duracao + 1)))

            idade = int(rng.integers(cfg.IDADE[0], cfg.IDADE[1] + 1))
            nascimento = criacao - timedelta(days=int(idade * 365.25) + int(rng.integers(0, 365)))
            i_cidade = int(rng.choice(len(cidades), p=pesos_cidades))

            # Regra: conversão ocorre depois da criação e dentro do período da base
            convertido = rng.random() < prob_conversao
            data_conversao = None
            if convertido:
                dias = int(rng.integers(cfg.DIAS_ATE_CONVERSAO[0], cfg.DIAS_ATE_CONVERSAO[1] + 1))
                data_conversao = criacao + timedelta(days=dias)
                if data_conversao > cfg.DATA_FIM:
                    convertido, data_conversao = False, None

            status = (cfg.STATUS_LEAD_CONVERTIDO if convertido
                      else str(rng.choice(status_nao_conv, p=pesos_status)))

            registros.append({
                "id_lead": f"LD-{contador:06d}",
                "nome": f"{fake.first_name()} {fake.last_name()}",
                "email": fake.email(),
                "telefone": fake.phone_number(),
                "data_nascimento": nascimento,
                "cidade": cidades[i_cidade],
                "uf": ufs[i_cidade],
                "segmento": str(rng.choice(cfg.SEGMENTOS)),
                "id_campanha": camp["id_campanha"],
                "status": status,
                "data_criacao": criacao,
                "data_conversao": data_conversao,
            })

    return pd.DataFrame(registros)


# OPORTUNIDADES
def gerar_oportunidades(leads: pd.DataFrame) -> pd.DataFrame:
    convertidos = leads[leads["status"] == cfg.STATUS_LEAD_CONVERTIDO]
    registros = []

    for i, lead in enumerate(convertidos.itertuples(index=False), start=1):
        # Regra: a oportunidade nasce na data de conversão do lead
        criacao = lead.data_conversao
        dias = int(rng.integers(cfg.DIAS_ATE_FECHAMENTO[0], cfg.DIAS_ATE_FECHAMENTO[1] + 1))
        fechamento = criacao + timedelta(days=dias)

        if fechamento > cfg.DATA_FIM:
            status, fechamento, ganha = cfg.STATUS_OPORTUNIDADE_ABERTA, None, False
        else:
            ganha = bool(rng.random() < cfg.TAXA_GANHO)
            status = cfg.STATUS_OPORTUNIDADE[0] if ganha else cfg.STATUS_OPORTUNIDADE[1]

        # Regra: valores com distribuição assimétrica (lognormal)
        valor = round(float(rng.lognormal(np.log(cfg.VALOR_MEDIANA), cfg.VALOR_SIGMA)), 2)

        registros.append({
            "id_oportunidade": f"OP-{i:06d}",
            "id_lead": lead.id_lead,
            "data_criacao": criacao,
            "data_fechamento": fechamento,
            "status": status,
            "ganha": ganha,
            "valor": valor,
        })

    return pd.DataFrame(registros)

# Execução

if __name__ == "__main__":
    usuarios = gerar_usuarios()
    campanhas = gerar_campanhas(usuarios)
    leads = gerar_leads(campanhas)
    oportunidades = gerar_oportunidades(leads)

    print("=== VOLUMES ===")
    print(f"Usuários: {len(usuarios)} | Campanhas: {len(campanhas)} | "
          f"Leads: {len(leads)} | Oportunidades: {len(oportunidades)}")

    print("\n=== STATUS DOS LEADS ===")
    print(leads["status"].value_counts().to_string())

    print("\n=== STATUS DAS OPORTUNIDADES ===")
    print(oportunidades["status"].value_counts().to_string())

    # Taxa de conversão por canal
    leads_canal = leads.merge(campanhas[["id_campanha", "canal"]], on="id_campanha")
    conversao = (leads_canal["status"] == cfg.STATUS_LEAD_CONVERTIDO).groupby(leads_canal["canal"]).mean()
    print("\n=== TAXA DE CONVERSÃO POR CANAL ===")
    print(conversao.map("{:.1%}".format).to_string())

    # ROI por campanha
    opp_camp = oportunidades.merge(leads[["id_lead", "id_campanha"]], on="id_lead")
    receita = opp_camp[opp_camp["ganha"]].groupby("id_campanha")["valor"].sum().rename("receita")
    roi = campanhas.set_index("id_campanha")[["canal", "investimento"]].join(receita).fillna({"receita": 0})
    roi["roi"] = (roi["receita"] - roi["investimento"]) / roi["investimento"]
    print("\n=== ROI POR CAMPANHA ===")
    print(f"Campanhas com ROI negativo: {(roi['roi'] < 0).sum()} de {len(roi)}")
    print(f"ROI mínimo: {roi['roi'].min():.0%} | mediano: {roi['roi'].median():.0%} | máximo: {roi['roi'].max():.0%}")

    # Conferência das regras de realismo
    leads_camp = leads.merge(campanhas[["id_campanha", "data_inicio", "data_fim"]], on="id_campanha")
    assert ((leads_camp["data_criacao"] >= leads_camp["data_inicio"]) &
            (leads_camp["data_criacao"] <= leads_camp["data_fim"])).all(), "Lead fora do período da campanha"

    opp_lead = oportunidades.merge(leads[["id_lead", "data_criacao"]], on="id_lead", suffixes=("", "_lead"))
    assert (opp_lead["data_criacao"] >= opp_lead["data_criacao_lead"]).all(), "Oportunidade antes do lead"

    print("\nRegras de realismo conferidas.")