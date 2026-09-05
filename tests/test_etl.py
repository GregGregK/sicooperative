import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "etl"))

import pytest
from pyspark.sql import SparkSession

from quality import (
    anonimizar_cpf,
    anonimizar_nome,
    validar_movimentacoes,
    calcular_metricas_qualidade,
    build_star_schema,
)


@pytest.fixture(scope="module")
def spark():
    spark = (
        SparkSession.builder
        .master("local[1]")
        .appName("test-sicooperative-etl")
        .getOrCreate()
    )
    yield spark
    spark.stop()


def test_anonimizar_cpf_mantem_so_os_2_ultimos_digitos(spark):
    df = spark.createDataFrame([("123.456.789-10",)], ["cpf"])
    resultado = anonimizar_cpf(df, "cpf").collect()[0]["cpf"]
    assert resultado == "***.***.**-10"


def test_anonimizar_nome_reduz_sobrenome_a_inicial(spark):
    df = spark.createDataFrame([("Maria", "Silva")], ["nome", "sobrenome"])
    resultado = anonimizar_nome(df, "nome", "sobrenome").collect()[0]
    assert resultado["nome"] == "Maria"          # primeiro nome preservado
    assert resultado["sobrenome"] == "S."         # sobrenome reduzido


def test_validar_movimentacoes_separa_negativos(spark):
    df = spark.createDataFrame(
        [(1, 100.0), (2, -50.0), (3, 30.0), (4, -10.0)],
        ["id", "vlr_transacao"],
    )
    df_valido, df_invalido, pct_invalido = validar_movimentacoes(df)

    assert df_valido.count() == 2
    assert df_invalido.count() == 2
    assert pct_invalido == 50.0


def test_validar_movimentacoes_sem_dados_nao_quebra(spark):
    df = spark.createDataFrame([], "id INT, vlr_transacao DOUBLE")
    df_valido, df_invalido, pct_invalido = validar_movimentacoes(df)
    assert pct_invalido == 0.0


def test_calcular_metricas_qualidade_detecta_nulos(spark):
    df = spark.createDataFrame(
        [(1, "a"), (2, None), (3, "c"), (4, None)],
        ["id", "valor"],
    )
    metricas = calcular_metricas_qualidade(df, colunas_chave_duplicidade=["id"])
    assert metricas["percentual_nulos_por_coluna"]["valor"] == 50.0
    assert metricas["percentual_nulos_por_coluna"]["id"] == 0.0


def test_calcular_metricas_qualidade_detecta_duplicados(spark):
    df = spark.createDataFrame(
        [(1, 100), (1, 100), (2, 200), (3, 300)],
        ["id_cartao", "valor"],
    )
    metricas = calcular_metricas_qualidade(df, colunas_chave_duplicidade=["id_cartao", "valor"])
    # 4 registros, 3 distintos -> 1 duplicado -> 25%
    assert metricas["total_duplicados"] == 1
    assert metricas["percentual_duplicados"] == 25.0


def test_join_movimentacao_ate_associado(spark):
    from pyspark.sql.functions import col

    associado = spark.createDataFrame(
        [(1, "Maria", "Silva", 30, "maria@teste.com", "123.456.789-10")],
        ["id", "nome", "sobrenome", "idade", "email", "cpf"],
    )
    conta = spark.createDataFrame(
        [(10, "corrente", "2023-01-01 10:00:00", 1)],
        ["id", "tipo", "data_criacao", "id_associado"],
    )
    cartao = spark.createDataFrame(
        [(100, "1111222233334444", "MARIA SILVA", "Visa", "2023-02-01 09:00:00", 10, 1)],
        ["id", "num_cartao", "nom_impresso", "bandeira", "data_criacao", "id_conta", "id_associado"],
    )
    movimentacao = spark.createDataFrame(
        [(1000, 150.50, "Compra supermercado", "2024-05-01 12:00:00", 100)],
        ["id", "vlr_transacao", "des_transacao", "data_movimentacao", "id_cartao"],
    )

    df = (
        movimentacao.alias("mov")
        .join(cartao.alias("car"), col("mov.id_cartao") == col("car.id"), "inner")
        .join(conta.alias("cta"), col("car.id_conta") == col("cta.id"), "inner")
        .join(associado.alias("assoc"), col("car.id_associado") == col("assoc.id"), "inner")
    )

    assert df.count() == 1
    row = df.collect()[0]
    assert row["nome"] == "Maria"
    assert row["bandeira"] == "Visa"


def _build_sample_star_schema_inputs(spark):
    associado = spark.createDataFrame(
        [(1, "Maria", "Silva", 30, "maria@teste.com", "123.456.789-10"),
         (2, "João", "Souza", 45, "joao@teste.com", "987.654.321-00")],
        ["id", "nome", "sobrenome", "idade", "email", "cpf"],
    )
    conta = spark.createDataFrame(
        [(10, "corrente", "2023-01-01 10:00:00", 1),
         (20, "poupanca", "2023-03-01 10:00:00", 2)],
        ["id", "tipo", "data_criacao", "id_associado"],
    )
    cartao = spark.createDataFrame(
        [(100, "1111222233334444", "MARIA SILVA", "Visa", "2023-02-01 09:00:00", 10, 1),
         (200, "5555666677778888", "JOAO SOUZA", "Elo", "2023-04-01 09:00:00", 20, 2)],
        ["id", "num_cartao", "nom_impresso", "bandeira", "data_criacao", "id_conta", "id_associado"],
    )
    movimentacao = spark.createDataFrame(
        [(1000, 150.50, "Compra supermercado", "2024-05-01 12:00:00", 100),
         (1001, 80.00, "Farmacia", "2024-05-02 12:00:00", 100),
         (1002, 300.00, "Posto de gasolina", "2024-05-03 12:00:00", 200)],
        ["id", "vlr_transacao", "des_transacao", "data_movimentacao", "id_cartao"],
    )
    historico_agg = spark.createDataFrame(
        [(1, 3)],
        ["associado_id", "qtd_interacoes"],
    )
    return associado, conta, cartao, movimentacao, historico_agg


def test_build_star_schema_gera_as_4_tabelas(spark):
    inputs = _build_sample_star_schema_inputs(spark)
    tabelas = build_star_schema(*inputs)

    assert set(tabelas.keys()) == {"dim_associado", "dim_conta", "dim_cartao", "fato_movimentacao"}


def test_build_star_schema_dim_associado_esta_anonimizada(spark):
    inputs = _build_sample_star_schema_inputs(spark)
    tabelas = build_star_schema(*inputs)

    dim_associado = tabelas["dim_associado"].collect()
    maria = next(r for r in dim_associado if r["nome"] == "Maria")

    assert maria["sobrenome"] == "S."
    assert maria["cpf"] == "***.***.**-10"
    assert maria["qtd_interacoes_historico"] == 3


def test_build_star_schema_dim_associado_sem_historico_fica_nulo(spark):
    inputs = _build_sample_star_schema_inputs(spark)
    tabelas = build_star_schema(*inputs)

    dim_associado = tabelas["dim_associado"].collect()
    joao = next(r for r in dim_associado if r["nome"] == "João")

    assert joao["qtd_interacoes_historico"] is None


def test_build_star_schema_fato_tem_fks_para_as_3_dimensoes(spark):
    inputs = _build_sample_star_schema_inputs(spark)
    tabelas = build_star_schema(*inputs)

    colunas_fato = set(tabelas["fato_movimentacao"].columns)
    assert {"id_cartao", "id_conta", "id_associado"}.issubset(colunas_fato)


def test_build_star_schema_fato_tem_uma_linha_por_movimentacao(spark):
    inputs = _build_sample_star_schema_inputs(spark)
    tabelas = build_star_schema(*inputs)

    # 3 movimentações na massa de teste -> 3 linhas na fato, sem explosão
    # nem perda por causa dos joins com as dimensões
    assert tabelas["fato_movimentacao"].count() == 3


def test_build_star_schema_dimensoes_nao_tem_linhas_repetidas(spark):
    inputs = _build_sample_star_schema_inputs(spark)
    tabelas = build_star_schema(*inputs)

    # 2 associados e 2 cartões na massa de teste -> dimensão não deve
    # crescer por causa do join com o histórico ou com a fato
    assert tabelas["dim_associado"].count() == 2
    assert tabelas["dim_cartao"].count() == 2
