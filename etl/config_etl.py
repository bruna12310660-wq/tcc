from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DIR_ENTRADA = BASE_DIR / "dados" / "brutos"

SEPARADOR = ";"
ENCODING = "utf-8-sig"

SERVIDOR = "localhost"
BANCO = "mkt_tcc"
DRIVER = "ODBC Driver 17 for SQL Server"

ARQUIVOS = ["usuarios", "campanhas", "leads", "oportunidades"]