from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DIR_ENTRADA = BASE_DIR / "dados" / "brutos"

SEPARADOR = ";"
ENCODING = "utf-8-sig"

SERVIDOR = "localhost"
BANCO = "mkt_tcc"
DRIVER = "ODBC Driver 17 for SQL Server"

ARQUIVOS = ["usuarios", "campanhas", "leads", "oportunidades"]


# Dicionário de padronização

CANAIS = {
    "Google Ads": ["google ads", "google", "adwords"],
    "Meta Ads": ["meta ads", "meta", "facebook/instagram", "facebook ads"],
    "LinkedIn Ads": ["linkedin ads", "linkedin"],
    "E-mail Marketing": ["e-mail marketing", "email marketing", "e-mail mkt", "email"],
    "Eventos": ["eventos", "evento"],
    "Indicação": ["indicacao"],
}

SEGMENTOS = ["Varejo", "Indústria", "Serviços", "Tecnologia", "Saúde", "Educação", "Financeiro"]
STATUS_LEAD = ["Novo", "Em qualificação", "Convertido", "Descartado"]
STATUS_OPORTUNIDADE = ["Em aberto", "Ganha", "Perdida"]

REGIOES = {
    **dict.fromkeys(["AC", "AP", "AM", "PA", "RO", "RR", "TO"], "Norte"),
    **dict.fromkeys(["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"], "Nordeste"),
    **dict.fromkeys(["DF", "GO", "MT", "MS"], "Centro-Oeste"),
    **dict.fromkeys(["ES", "MG", "RJ", "SP"], "Sudeste"),
    **dict.fromkeys(["PR", "RS", "SC"], "Sul"),
}

FAIXAS_ETARIAS_LIMITES = [18, 25, 35, 45, 55, 200]
FAIXAS_ETARIAS_ROTULOS = ["18 a 24", "25 a 34", "35 a 44", "45 a 54", "55 ou mais"]

# Dimensão status

STATUS = [
    ("Novo", "Lead recém-captado", "Em aberto", "Lead"),
    ("Em qualificação", "Lead em avaliação comercial", "Em aberto", "Lead"),
    ("Convertido", "Lead convertido em oportunidade", "Convertido", "Lead"),
    ("Descartado", "Lead sem potencial comercial", "Perdido", "Lead"),
    ("Em aberto", "Oportunidade em negociação", "Em aberto", "Oportunidade"),
    ("Ganha", "Oportunidade concretizada", "Convertido", "Oportunidade"),
    ("Perdida", "Oportunidade não concretizada", "Perdido", "Oportunidade"),
]

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
         "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
DIAS_SEMANA = ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira",
               "Sexta-feira", "Sábado", "Domingo"]