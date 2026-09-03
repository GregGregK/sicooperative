import argparse
import os
import random
from datetime import datetime, timedelta

import psycopg2
from faker import Faker
from pymongo import MongoClient

fake = Faker("pt_BR") # definir a api do faker para PTBR

# pre-definição de algumas listas que não vai existir no FAKER
TIPOS_CONTA = ["corrente", "poupanca"]
BANDEIRAS = ["Visa", "Mastercard", "Elo"]
CANAIS = ["app", "whatsapp", "call_center", "email"]
TIPOS_INTERACAO = ["duvida", "reclamacao", "elogio", "solicitacao"]

def get_pg_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )

def get_mongo_collection():
    uri = os.getenv("MONGO_URI")
    client = MongoClient(uri)
    db = client[os.getenv("MONGO_DB")]
    return db["historico_interacoes"]

def random_datetime(start_years_ago=5):
    start = datetime.now() - timedelta(days=365 * start_years_ago)
    delta = datetime.now() - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)

def gerar_dados_sql(conn, args):
    cur = conn.cursor()

    associado_ids = []
    for _ in range(args.n_associados):
        cur.execute(
            """INSERT INTO associado (nome, sobrenome, idade, email, cpf)
               VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (fake.first_name(), fake.last_name(), random.randint(18, 80),
             fake.email(), fake.cpf()),
        )
        associado_ids.append(cur.fetchone()[0])

    conta_ids_por_associado = {}
    for associado_id in associado_ids:
        n_contas = random.randint(1, 2)
        conta_ids = []
        for _ in range(n_contas):
            cur.execute(
                """INSERT INTO conta (tipo, data_criacao, id_associado)
                   VALUES (%s, %s, %s) RETURNING id""",
                (random.choice(TIPOS_CONTA), random_datetime(), associado_id),
            )
            conta_ids.append(cur.fetchone()[0])
        conta_ids_por_associado[associado_id] = conta_ids

    cartao_ids = []
    for associado_id, conta_ids in conta_ids_por_associado.items():
        n_cartoes = random.randint(1, 3)
        for _ in range(n_cartoes):
            conta_id = random.choice(conta_ids)
            cur.execute(
                """INSERT INTO cartao (num_cartao, nom_impresso, bandeira, data_criacao, id_conta, id_associado)
                   VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
                (
                    fake.credit_card_number(),
                    fake.name().upper(),
                    random.choice(BANDEIRAS),
                    random_datetime(),
                    conta_id,
                    associado_id,
                ),
            )
            cartao_ids.append(cur.fetchone()[0])

    total_movs = 0
    for cartao_id in cartao_ids:
        n_movs = random.randint(3, 10)
        for _ in range(n_movs):
            valor = round(random.uniform(5, 3000), 2)
            # ~4% de chance de gerar um valor negativo de propósito
            if random.random() < 0.04:
                valor = -valor
            cur.execute(
                """INSERT INTO movimentacao (vlr_transacao, des_transacao, data_movimentacao, id_cartao)
                   VALUES (%s, %s, %s, %s) RETURNING id""",
                (valor, fake.bs().capitalize(), random_datetime(start_years_ago=2), cartao_id),
            )
            total_movs += 1

    # Duplica propositalmente ~2% das movimentações
    cur.execute("SELECT id_cartao, vlr_transacao, des_transacao, data_movimentacao FROM movimentacao")
    todas_movs = cur.fetchall()
    n_duplicatas = max(1, int(len(todas_movs) * 0.02))
    for id_cartao, vlr, des, data in random.sample(todas_movs, n_duplicatas):
        cur.execute(
            """INSERT INTO movimentacao (vlr_transacao, des_transacao, data_movimentacao, id_cartao)
               VALUES (%s, %s, %s, %s)""",
            (vlr, des, data, id_cartao),
        )

    conn.commit()
    cur.close()

    print(f"[SQL] {len(associado_ids)} associados, "
          f"{sum(len(v) for v in conta_ids_por_associado.values())} contas, "
          f"{len(cartao_ids)} cartões, {total_movs} movimentações "
          f"(+{n_duplicatas} duplicatas propositais).")

    return associado_ids


def gerar_dados_mongo(associado_ids):
    collection = get_mongo_collection()
    collection.delete_many({})  # idempotência em reexecuções locais

    docs = []
    for associado_id in associado_ids:
        n_interacoes = random.randint(0, 5)
        for _ in range(n_interacoes):
            docs.append({
                "associado_id": associado_id,
                "canal": random.choice(CANAIS),
                "tipo_interacao": random.choice(TIPOS_INTERACAO),
                "mensagem": fake.sentence(nb_words=12),
                "data_interacao": random_datetime(start_years_ago=2),
                # campo aninhado, mostrando a natureza semiestruturada do dado
                "metadata": {
                    "dispositivo": random.choice(["ios", "android", "web"]),
                    "satisfacao": random.randint(1, 5),
                },
            })

    if docs:
        collection.insert_many(docs)

    print(f"[MongoDB] {len(docs)} documentos inseridos em historico_interacoes.")


def parse_args():
    parser = argparse.ArgumentParser(description="Gera massa de dados fictícia para o desafio.")
    parser.add_argument("--n-associados", type=int, default=30)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    pg_conn = get_pg_connection()
    try:
        ids = gerar_dados_sql(pg_conn, args)
    finally:
        pg_conn.close()

    gerar_dados_mongo(ids)
