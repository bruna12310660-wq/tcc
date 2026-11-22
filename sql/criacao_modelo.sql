
IF DB_ID('mkt_tcc') IS NULL
    CREATE DATABASE mkt_tcc;
GO

USE mkt_tcc;
GO

IF SCHEMA_ID('stg') IS NULL EXEC('CREATE SCHEMA stg');
IF SCHEMA_ID('dw')  IS NULL EXEC('CREATE SCHEMA dw');
IF SCHEMA_ID('etl') IS NULL EXEC('CREATE SCHEMA etl');
GO

DROP TABLE IF EXISTS dw.fato_oportunidade;
DROP TABLE IF EXISTS dw.fato_lead;
DROP TABLE IF EXISTS dw.dim_campanha;
DROP TABLE IF EXISTS dw.dim_responsavel;
DROP TABLE IF EXISTS dw.dim_lead;
DROP TABLE IF EXISTS dw.dim_status;
DROP TABLE IF EXISTS dw.dim_data;
DROP TABLE IF EXISTS etl.log_execucao;
GO

-- DIMENSÕES

-- Registro -1 = "Não informado"
CREATE TABLE dw.dim_data (
    sk_data          INT           NOT NULL CONSTRAINT pk_dim_data PRIMARY KEY,  -- AAAAMMDD
    data             DATE          NULL,
    dia              TINYINT       NULL,
    mes              TINYINT       NULL,
    nome_mes         NVARCHAR(20)  NULL,
    trimestre        TINYINT       NULL,
    ano              SMALLINT      NULL,
    semana_ano       TINYINT       NULL,
    dia_semana       TINYINT       NULL,
    nome_dia_semana  NVARCHAR(20)  NULL
);

CREATE TABLE dw.dim_responsavel (
    sk_responsavel   INT            NOT NULL CONSTRAINT pk_dim_responsavel PRIMARY KEY,
    nome             NVARCHAR(100)  NOT NULL,
    email            NVARCHAR(150)  NOT NULL CONSTRAINT uq_responsavel_email UNIQUE,
    perfil           NVARCHAR(30)   NOT NULL
);

CREATE TABLE dw.dim_campanha (
    sk_campanha      INT            NOT NULL CONSTRAINT pk_dim_campanha PRIMARY KEY,
    id_campanha      NVARCHAR(20)   NOT NULL CONSTRAINT uq_campanha_id UNIQUE,
    nome_campanha    NVARCHAR(150)  NOT NULL,
    canal_nome       NVARCHAR(50)   NOT NULL,
    canal_tipo       NVARCHAR(50)   NOT NULL,
    data_inicio      DATE           NOT NULL,
    data_fim         DATE           NOT NULL,
    investimento     DECIMAL(12,2)  NOT NULL,
    sk_responsavel   INT            NOT NULL,
    CONSTRAINT fk_campanha_responsavel FOREIGN KEY (sk_responsavel)
        REFERENCES dw.dim_responsavel (sk_responsavel)
);


CREATE TABLE dw.dim_lead (
    sk_lead          INT            NOT NULL CONSTRAINT pk_dim_lead PRIMARY KEY,
    id_lead          NVARCHAR(20)   NOT NULL CONSTRAINT uq_lead_id UNIQUE,
    cidade           NVARCHAR(100)  NULL,
    uf               CHAR(2)        NULL,
    regiao           NVARCHAR(20)   NULL,
    segmento         NVARCHAR(50)   NOT NULL,
    faixa_etaria     NVARCHAR(20)   NOT NULL
);

CREATE TABLE dw.dim_status (
    sk_status        INT            NOT NULL CONSTRAINT pk_dim_status PRIMARY KEY,
    nome             NVARCHAR(50)   NOT NULL,
    descricao        NVARCHAR(200)  NULL,
    categoria        NVARCHAR(30)   NOT NULL,    
    entidade         NVARCHAR(20)   NOT NULL,    
    CONSTRAINT uq_status_nome_entidade UNIQUE (nome, entidade)
);


--FATOS

-- Granularidade: uma linha por lead
CREATE TABLE dw.fato_lead (
    sk_lead              INT  NOT NULL CONSTRAINT pk_fato_lead PRIMARY KEY,
    sk_campanha          INT  NOT NULL,
    sk_status            INT  NOT NULL,
    sk_data_criacao      INT  NOT NULL,
    sk_data_conversao    INT  NOT NULL,
    indicador_conversao  BIT  NOT NULL,
    dias_ate_conversao   INT  NULL,
    CONSTRAINT fk_fl_lead           FOREIGN KEY (sk_lead)           REFERENCES dw.dim_lead (sk_lead),
    CONSTRAINT fk_fl_campanha       FOREIGN KEY (sk_campanha)       REFERENCES dw.dim_campanha (sk_campanha),
    CONSTRAINT fk_fl_status         FOREIGN KEY (sk_status)         REFERENCES dw.dim_status (sk_status),
    CONSTRAINT fk_fl_data_criacao   FOREIGN KEY (sk_data_criacao)   REFERENCES dw.dim_data (sk_data),
    CONSTRAINT fk_fl_data_conversao FOREIGN KEY (sk_data_conversao) REFERENCES dw.dim_data (sk_data)
);

-- Granularidade: uma linha por oportunidade
CREATE TABLE dw.fato_oportunidade (
    id_oportunidade      NVARCHAR(20)   NOT NULL CONSTRAINT pk_fato_oportunidade PRIMARY KEY,
    sk_lead              INT            NOT NULL,
    sk_campanha          INT            NOT NULL,   
    sk_status            INT            NOT NULL,
    sk_data_criacao      INT            NOT NULL,
    sk_data_fechamento   INT            NOT NULL,
    indicador_ganha      BIT            NOT NULL,
    valor                DECIMAL(12,2)  NOT NULL,
    CONSTRAINT fk_fo_lead            FOREIGN KEY (sk_lead)            REFERENCES dw.dim_lead (sk_lead),
    CONSTRAINT fk_fo_campanha        FOREIGN KEY (sk_campanha)        REFERENCES dw.dim_campanha (sk_campanha),
    CONSTRAINT fk_fo_status          FOREIGN KEY (sk_status)          REFERENCES dw.dim_status (sk_status),
    CONSTRAINT fk_fo_data_criacao    FOREIGN KEY (sk_data_criacao)    REFERENCES dw.dim_data (sk_data),
    CONSTRAINT fk_fo_data_fechamento FOREIGN KEY (sk_data_fechamento) REFERENCES dw.dim_data (sk_data)
);

-- LOG DO PIPELINE
CREATE TABLE etl.log_execucao (
    id_execucao            INT IDENTITY(1,1) CONSTRAINT pk_log_execucao PRIMARY KEY,
    data_execucao          DATETIME2      NOT NULL DEFAULT SYSDATETIME(),
    etapa                  NVARCHAR(100)  NOT NULL,
    arquivo                NVARCHAR(100)  NULL,
    registros_lidos        INT            NULL,
    registros_descartados  INT            NULL,
    registros_carregados   INT            NULL,
    duracao_segundos       DECIMAL(10,2)  NULL,
    status                 NVARCHAR(20)   NOT NULL,
    mensagem               NVARCHAR(4000) NULL
);
GO