import math
from datetime import date
from pathlib import Path


# Reprodutibilidade: fixa a semente aleatória para que sejam gerados sempre os mesmos dados.
SEED = 42


# Camminhos:
BASE_DIR = Path(__file__).resolve().parent.parent
DIR_GABARITO = BASE_DIR / "dados" / "gabarito"       #base limpa, verdade de referência.
DIR_BRUTOS = BASE_DIR / "dados" / "brutos"           #base com problemas de qualidade inseridos.
ARQ_LOG = BASE_DIR / "dados" / "log_problemas.json"  

# Formato de exportação (simula o export do CRM)
SEPARADOR = ";"
ENCODING = "utf-8-sig"


# Período de geração dos dados
DATA_INICIO = date(2024, 11, 1)
DATA_FIM = date(2026, 10, 31)


# Usuários do Dashboard (RLS)
N_EXECUTIVOS = 3
N_GERENTES = 5
DOMINIO_EMAIL = "dominio-tcc.com.br"


# Campanhas
N_CAMPANHAS = 40
DURACAO_CAMPANHA_DIAS = (15, 90)
RUIDO_CAMPANHA = 0.5  # lognormal. Para que as campanhas do mesmo canal tenham resultados diferentes.

# Informações dos canais de aquisição
CANAIS = {
    "Google Ads":       {"tipo": "Mídia Paga",     "peso": 0.25, "investimento": (10_000, 40_000), "leads_por_mil": 25, "taxa_conversao": 0.08},
    "Meta Ads":         {"tipo": "Mídia Paga",     "peso": 0.25, "investimento": (8_000, 30_000),  "leads_por_mil": 35, "taxa_conversao": 0.05},
    "LinkedIn Ads":     {"tipo": "Mídia Paga",     "peso": 0.15, "investimento": (10_000, 35_000), "leads_por_mil": 12, "taxa_conversao": 0.12},
    "E-mail Marketing": {"tipo": "Canal Próprio",  "peso": 0.15, "investimento": (2_000, 8_000),   "leads_por_mil": 60, "taxa_conversao": 0.06},
    "Eventos":          {"tipo": "Offline",        "peso": 0.10, "investimento": (20_000, 60_000), "leads_por_mil": 8,  "taxa_conversao": 0.18},
    "Indicação":        {"tipo": "Relacionamento", "peso": 0.10, "investimento": (1_000, 5_000),   "leads_por_mil": 20, "taxa_conversao": 0.25},
}


# Leads

IDADE = (18, 65)
DIAS_ATE_CONVERSAO = (1, 60)

SEGMENTOS = ["Varejo", "Indústria", "Serviços", "Tecnologia", "Saúde", "Educação", "Financeiro"]

CIDADES = [
    ("São Paulo", "SP", 0.22), ("Rio de Janeiro", "RJ", 0.15), ("Belo Horizonte", "MG", 0.09),
    ("Curitiba", "PR", 0.07), ("Porto Alegre", "RS", 0.07), ("Salvador", "BA", 0.06),
    ("Recife", "PE", 0.06), ("Fortaleza", "CE", 0.06), ("Brasília", "DF", 0.07),
    ("Goiânia", "GO", 0.05), ("Manaus", "AM", 0.04), ("Petrópolis", "RJ", 0.06),
]

STATUS_LEAD_CONVERTIDO = "Convertido"
STATUS_LEAD_NAO_CONVERTIDO = {"Novo": 0.20, "Em qualificação": 0.30, "Descartado": 0.50}


# Oportunidades
TAXA_GANHO = 0.25      
VALOR_MEDIANA = 3_000
VALOR_SIGMA = 0.8
DIAS_ATE_FECHAMENTO = (7, 90)
STATUS_OPORTUNIDADE = ["Ganha", "Perdida"]


# Problemas de qualidade de dados (para gerar a base bruta)
PROBLEMAS = {
    "leads_duplicados": 0.03,
    "oportunidades_duplicadas": 0.02,
    "uf_nula": 0.04,
    "data_nascimento_nula": 0.05,
    "formato_data_variado": 0.15,
    "canal_texto_variado": 0.30,
    "segmento_texto_variado": 0.20,
    "status_texto_variado": 0.10,
    "nome_campanha_espacos": 0.10,
    "oportunidades_orfas": 0.01,
    "fechamento_antes_criacao": 0.01,
    "valor_negativo": 0.005,
}



# Conferência dos Parâmetros
if __name__ == "__main__":
    soma_pesos = sum(c["peso"] for c in CANAIS.values())
    assert abs(soma_pesos - 1) < 1e-9, f"Pesos dos canais somam {soma_pesos}, deveriam somar 1"

    soma_cidades = sum(p for _, _, p in CIDADES)
    assert abs(soma_cidades - 1) < 1e-9, f"Pesos das cidades somam {soma_cidades}, deveriam somar 1"

    valor_medio = VALOR_MEDIANA * math.exp(VALOR_SIGMA ** 2 / 2)
    total_leads = total_opps = 0

    print(f"{'Canal':<18}{'Campanhas':>10}{'Leads':>9}{'Opps':>7}{'ROI est.':>10}")
    for nome, c in CANAIS.items():
        n_camp = N_CAMPANHAS * c["peso"]
        inv_medio = sum(c["investimento"]) / 2
        leads = n_camp * inv_medio / 1000 * c["leads_por_mil"]
        opps = leads * c["taxa_conversao"]
        receita = opps * TAXA_GANHO * valor_medio
        roi = (receita - n_camp * inv_medio) / (n_camp * inv_medio)
        total_leads += leads
        total_opps += opps
        print(f"{nome:<18}{n_camp:>10.0f}{leads:>9.0f}{opps:>7.0f}{roi:>9.0%}")

    print(f"\nTotal estimado: {total_leads:,.0f} leads | {total_opps:,.0f} oportunidades")