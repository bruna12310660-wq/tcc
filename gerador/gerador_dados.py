
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



# Execução

if __name__ == "__main__":
    usuarios = gerar_usuarios()
    campanhas = gerar_campanhas(usuarios)

    print("=== USUÁRIOS ===")
    print(usuarios.to_string(index=False))

    print("\n=== CAMPANHAS (5 primeiras) ===")
    print(campanhas.drop(columns="eficiencia").head().to_string(index=False))

    print("\n=== CAMPANHAS POR GERENTE ===")
    print(campanhas["responsavel_nome"].value_counts().to_string())

    print("\n=== INVESTIMENTO POR CANAL ===")
    print(campanhas.groupby("canal")["investimento"].agg(["count", "sum"]).to_string())