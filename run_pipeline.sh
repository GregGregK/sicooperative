#!/bin/bash
set -e

echo ">> Aguardando o Postgres ficar disponível..."
until python -c "
import psycopg2, os
psycopg2.connect(
    host=os.getenv('DB_HOST', 'db'),
    port=os.getenv('DB_PORT', '5432'),
    dbname=os.getenv('DB_NAME', 'sicooperative'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', 'postgres'),
)
" 2>/dev/null; do
  sleep 2
done
echo ">> Postgres disponível."

echo ">> Aguardando o MongoDB ficar disponível..."
until python -c "
import os
from pymongo import MongoClient
MongoClient(os.getenv('MONGO_URI', 'mongodb://mongo:27017'), serverSelectionTimeoutMS=2000).admin.command('ping')
" 2>/dev/null; do
  sleep 2
done
echo ">> MongoDB disponível."

echo ">> Criando schema no Postgres..."
python -c "
import psycopg2, os
conn = psycopg2.connect(
    host=os.getenv('DB_HOST', 'db'),
    port=os.getenv('DB_PORT', '5432'),
    dbname=os.getenv('DB_NAME', 'sicooperative'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD', 'postgres'),
)
with open('sql/schema.sql') as f:
    conn.cursor().execute(f.read())
conn.commit()
conn.close()
"

echo ">> Gerando massa de dados fictícia (SQL + MongoDB)..."
python scripts/generate_fake_data.py --n-associados "${N_ASSOCIADOS:-30}"

echo ">> Rodando o ETL com Spark..."
cd etl && python spark_etl.py --output-dir "${OUTPUT_DIR:-/app/data/output}"

echo ">> Pipeline concluído."