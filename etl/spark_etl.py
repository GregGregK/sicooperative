import argparse #passar argumentos
import json
import os 
import shutil #gerenciador de diretórios

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count as spark_count, sum as spark_sum


from quality import (
    anonimizar_cpf,
    anonimizar_nome,
    validar_movimentacoes,
    calcular_metricas_qualidade,
    build_star_schema
)


JDBC_JAR_PACKAGE = "org.postgresql:postgresql:42.7.3"
MONGO_SPARK_PACKAGE = "org.mongodb.spark:mongo-spark-connector_2.12:10.3.0"

def build_spark_session():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    mongo_db = os.getenv("MONGO_DB", "sicooperative")
    return (
        SparkSession.builder
        .appName("SiCooperativeETL")
        .config("spark.jars.packages", f"{JDBC_JAR_PACKAGE},{MONGO_SPARK_PACKAGE}")
        .config("spark.mongodb.read.connection.uri", f"{mongo_uri}/{mongo_db}")
        .getOrCreate()
    )

def jdbc_props():
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    dbname = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    url = f"jdbc:postgresql://{host}:{port}/{dbname}"
    properties = {"user": user, "password": password, "driver": "org.postgresql.Driver"}
    return url, properties


def read_table(spark, table_name, url, properties):
    return spark.read.jdbc(url=url, table=table_name, properties=properties)

def read_historico_interacoes(spark):
    return(
        spark.read.format("mongodb")
        .option("collection", "historico_interacoes")
        .load()
    )

def write_single_csv(df, path):
    tmp_dir = path + "_tmp"
    df.coalesce(1).write.mode("overwrite").option("header", "true").csv(tmp_dir)
    part_file = next(f for f in os.listdir(tmp_dir) if f.startswith("part-") and f.endswith(".csv"))
    shutil.move(os.path.join(tmp_dir, part_file), path)
    shutil.rmtree(tmp_dir)

def write_single_parquet(df, path):
    """
    O Spark excreve Parquet como uma pasta contendo um arquivo part por partição, além de outros arquivos de log
    Então para facilitar e não gerar problema no power bi eu vou compactar os arquivos dentro de 1 partição só
    """

    #Poderia fazer com que o power bi lidasse com todas as partições, mas como quero facilitar o projeto
    #E o escopo de volume de dado não nos obriga a ter várias partições, então esse é o melhor caminho

    tmp_dir = path + "_tmp"
    df.coalesce(1).write.mode("overwrite").parquet(tmp_dir)
    part_file = next(f for f in os.listdir(tmp_dir) if f.startswith("part-") and f.endswith(".parquet"))
    shutil.move(os.path.join(tmp_dir, part_file), path)
    shutil.rmtree(tmp_dir)

def run_etl(output_dir):
    """
    Roda o ETL usando as tabelas criadas no quality que usam o schema.sql com os dados falsos do faker
    """

    spark = build_spark_session()
    url, properties = jdbc_props()
    #Usam as funções e argumentos criados lá em cima

    df_associado = read_table(spark, "associado", url, properties)
    df_conta = read_table(spark, "conta", url, properties)
    df_cartao = read_table(spark, "cartao", url, properties)
    df_movimentacao = read_table(spark, "movimentacao", url, properties)
    df_historico = read_historico_interacoes(spark)

    #1: Qualidade: Validação da integridades das movimentações
    df_mov_valida, df_mov_invalida, pct_invalido = validar_movimentacoes(df_movimentacao)
    print(f"[Qualidade] {pct_invalido}% das movimentações tinham valor <= 0 e foram descartadas.")


    #2 Qualidade: Métricas (de nulos ou duplicados) sobre o dado bruto da movimentação
    metricas_movimentacao = calcular_metricas_qualidade(
        df_movimentacao, colunas_chave_duplicidade=["id_cartao", "vlr_transacao", "des_transacao", "data_movimentacao"]
    )

    #3 Agregação de histórico de interações (que vem do mongo) por associado 
    df_historico_agg = (
        df_historico.groupBy("associado_id")
        .agg(spark_count("*").alias("qtd_interacoes"))
    )

    #4 Join principal: movimentação (apenas as vállidas) -> cartao -> conta -> associado

    df = (
        df_mov_valida.alias("mov")
        .join(df_cartao.alias("car"), col("mov.id_cartao") == col("car.id"), "inner")
        .join(df_conta.alias("cta"), col("car.id_conta") == col("cta.id"), "inner")
        .join(df_associado.alias("assoc"), col("car.id_associado") == col("assoc.id"), "inner")
        .join(df_historico_agg.alias("hist"), col("assoc.id") == col("hist.associado_id"), "left")
        .select(
            col("assoc.id").alias("id_associado"),
            col("assoc.nome").alias("nome"),
            col("assoc.sobrenome").alias("sobrenome"),
            col("assoc.cpf").alias("cpf"),
            col("assoc.idade").cast("string").alias("idade_associado"),
            col("mov.vlr_transacao").cast("string").alias("vlr_transacao_movimento"),
            col("mov.des_transacao").alias("des_transacao_movimento"),
            col("mov.data_movimentacao").cast("string").alias("data_movimentacao"),
            col("car.num_cartao").alias("numero_cartao"),
            col("car.nom_impresso").alias("nome_impresso_cartao"),
            col("car.bandeira").alias("bandeira_cartao"),
            col("cta.tipo").alias("tipo_conta"),
            col("hist.qtd_interacoes").alias("qtd_interacoes_historico"),
        )
    )

    #5. Segurança: anonimização de dados sensíveis
    df_final = anonimizar_cpf(df, "cpf")
    df_final = anonimizar_nome(df_final, "nome", "sobrenome")

    os.makedirs(output_dir, exist_ok=True)


    #6 Escrita de csv e parquet
    write_single_csv(df_final, os.path.join(output_dir, "movimento_flat.csv"))
    write_single_parquet(df_final, os.path.join(output_dir, "movimento_flat.parquet"))

    #7 Visão analítica de négocio: movimentações por bandeira de cartão
    df_negocio = (
        df_final
        .groupBy("bandeira_cartao")
        .agg(
            spark_count("*").alias("qtd_movimentacoes"),
            spark_sum(col("vlr_transacao_movimento").cast("double")).alias("valor_total")
        )
        .orderBy(col("valor_total").desc())
    )
    write_single_csv(df_negocio, os.path.join(output_dir, "analise_negocio_movimentacoes_por_bandeira.csv"))


    #8 Star schema pronto para power bi

    star_schema_dir = os.path.join(output_dir, "star_schema")
    tabelas_star_schema = build_star_schema(
        df_associado, df_conta, df_cartao, df_mov_valida, df_historico_agg
    )
    for nome_tabela, df_tabela in tabelas_star_schema.items():
        write_single_parquet(df_tabela, os.path.join(star_schema_dir, f"{nome_tabela}.parquet"))
    print(f"[OK] Star schema (dimensões + fato) gravado em: {star_schema_dir}")

    # --- 9. Relatório de qualidade ---
    relatorio = {
        "movimentacoes_invalidas_descartadas_pct": pct_invalido,
        "metricas_movimentacao_bruta": metricas_movimentacao,
    }
    with open(os.path.join(output_dir, "data_quality_report.json"), "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2)

    print(f"[OK] Arquivos gerados em: {output_dir}")
    print(f"[OK] Total de registros no flat final: {df_final.count()}")

    spark.stop()


def parse_args():
    parser = argparse.ArgumentParser(description="ETL: Postgres + MongoDB -> flat CSV/Parquet")
    parser.add_argument("--output-dir", type=str, required=True,
                         help="Diretório local onde os arquivos de saída serão escritos")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_etl(args.output_dir)
