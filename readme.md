# Desafio técnico: (SiCooperative) 
  

Pipeline de ingestão, transformação e disponibilização de dados que consolida

associados, contas e movimentações financeiras (fonte relacional) e histórico

de interações do associado (fonte semiestruturada, MongoDB) em uma visão

analítica única, com validação de integridade, anonimização de dados

sensíveis e métricas de qualidade.


## Estrutura do projeto

  

```

.

├── sql/schema.sql                 # DDL: associado, conta, cartao (extensão), movimentacao

├── scripts/generate_fake_data.py  # gera dados fictícios no Postgres e no MongoDB

├── etl/

│   ├── quality.py                 # anonimização, validação de integridade, métricas de qualidade

│   └── spark_etl.py               # job principal: leitura, join, escrita CSV/Parquet/relatório

├── tests/test_etl.py              # testes unitários de quality.py e da lógica de join

├── docker-compose.yml             # Postgres + MongoDB + ETL

├── Dockerfile

├── run_pipeline.sh                # orquestra schema -> dados -> ETL

├── gerar-bi-qualidade.py          # Gera o bi com os dados de qualidade 

├── gerar-bi.py                    # Gera bi com os dados de movimento_flat.csv

└── requirements.txt

```

  

## Como rodar o projeto

  

### Opção 1 — Docker (recomendado)

  

```bash

docker compose up --build

```

  

Sobe Postgres e MongoDB, aguarda os dois ficarem saudáveis, cria o schema,

gera a massa de dados fictícia em ambas as fontes, e roda o ETL completo.

Saída em `./data/output/`.

Derruba o container (Reseta todos os dados)
```bash
docker compose down -v
```

Log de container especifico
```bash
docker compose logs etl
docker compose logs db
docker compose logs mongo
```

Acompanhar logs
```bash
docker compose logs -f etl
```

Mais comandos úteis:
 
| Eu quero... | Comando |
|---|---|
| Rodar o projeto pela primeira vez | `docker compose up --build` |
| Rodar de novo sem mudar código | `docker compose up` |
| Rodar sem travar o terminal | `docker compose up --build -d` |
| Ver se está tudo de pé | `docker compose ps` |
| Ver os logs do ETL | `docker compose logs etl` |
| Acompanhar logs ao vivo | `docker compose logs -f etl` |
| Parar tudo (mantendo dados) | `docker compose down` |
| Parar tudo E zerar os dados | `docker compose down -v` |
| Rodar SQL no Postgres | `docker exec -it sicooperative_db psql -U postgres -d sicooperative` |
| Rodar comandos no Mongo | `docker exec -it sicooperative_mongo mongosh sicooperative` |
| Forçar rebuild sem cache | `docker compose build --no-cache` |

### Opção 2 — Local, sem Docker

  

Pré-requisitos: Python 3.11+, Java (Spark), Postgres e MongoDB rodando localmente.

  

```bash

python -m venv .venv && source .venv/bin/activate

pip install -r requirements.txt

  

cp .env.example .env

export $(cat .env | xargs)

  

psql -h localhost -U postgres -d sicooperative -f sql/schema.sql

python scripts/generate_fake_data.py --n-associados 30

cd etl && python spark_etl.py --output-dir ../data/output

```

  

### Testes

  

```bash

pytest tests/ -v

```

### Bi's (Dashboards)

```bash
python gerar-bi.py —output-dir data/output

python gerar-bi-qualidade.py —output-dir data/output

```

## O que o ETL entrega

  

- **`movimento_flat.csv`**: visão única (movimentação → cartão → conta →

  associado), enriquecida com a quantidade de interações do MongoDB por

  associado, com CPF e sobrenome já anonimizados (Usado posteriormente no bi de amostra).

- **`movimento_flat.parquet`**: mesma visão, em um único arquivo Parquet (não uma pasta) — importável diretamente no Power BI ou lido com `pandas.read_parquet()`.

- **`analise_negocio_movimentacoes_por_bandeira.csv`**: exemplo de entrega

  analítica para a área de negócio: quantidade e valor total de

  movimentações agrupadas por bandeira do cartão (Visa/Mastercard/Elo).

- **`data_quality_report.json`**: percentual de movimentações descartadas

  por valor inválido, e percentual de nulos/duplicados no dado bruto de

  movimentação. (Usado posteriormente no bi de qualidade)

- **`star_schema/`**: modelo dimensional (star schema) pronto para consumo

  direto no Power BI — `dim_associado.parquet`, `dim_conta.parquet`,

  `dim_cartao.parquet` (cada uma aparecendo uma única vez, sem repetição) e

  `fato_movimentacao.parquet` (com FKs diretas para as 3 dimensões, no grão

  de uma linha por movimentação). Cada um é um **arquivo único**: para

  importar no Power BI: Obter Dados → Parquet → selecione o arquivo

  diretamente (não uma pasta). A dimensão associado já sai anonimizada (CPF

  e sobrenome), então nenhum consumidor posterior do dado precisa reaplicar

  essa lógica. Preferi essa camada ao invés de subir o `movimento_flat.csv`

  direto no Power BI, porque o flat repete os dados de

  associado/conta/cartão em cada linha de movimentação, o que piora a

  performance do motor de análise (VertiPaq) e deixa medidas como contagem

  de associados distintos mais complicadas de escrever em DAX.

  

  > **Nota técnica**: por padrão, o Spark escreve Parquet como uma *pasta*

  > contendo um `part-*.parquet` por partição, mais um arquivo `_SUCCESS`

  > (marcador vazio confirmando que a escrita terminou sem erro) e arquivos

  > `.crc` (checksums). Isso é o formato correto para um data lake real

  > (onde outro job Spark ou o Athena vai ler a pasta inteira), mas quebra

  > a importação direta no Power BI, que espera um arquivo `.parquet`

  > único. Por isso, a função `write_single_parquet()` força 1 partição e

  > renomeia o resultado para um nome de arquivo fixo, eliminando os

  > arquivos auxiliares — uma troca aceitável dado o volume pequeno de

  > dados fictícios deste desafio; em um cenário de produção com grande

  > volume, o formato particionado (múltiplos arquivos) seria mantido, e o

  > Power BI se conectaria a uma camada de warehouse no lugar do arquivo

  > bruto.

  

## Qualidade e segurança dos dados

  

- **Validação de integridade**: movimentações com `vlr_transacao <= 0` são

  filtradas antes do join principal (`etl/quality.py::validar_movimentacoes`),

  e o percentual descartado é registrado no relatório de qualidade. A massa

  de dados fictícia insere propositalmente ~4% de valores negativos e ~7% de dados nulos em des_transacao para

  exercitar essa validação de ponta a ponta.

- **Anonimização**: CPF é mascarado mantendo só os 2 últimos dígitos

  (`***.***.**-XX`); sobrenome é reduzido à inicial. Nome completo não é

  necessário para os casos de uso analíticos previstos (agregações,

  segmentação), então optei por não expor o dado completo mesmo

  internamente no data lake.

- **Métricas de qualidade**: percentual de nulos por coluna e percentual de

  duplicados (usando `id_cartao + vlr_transacao + des_transacao +

  data_movimentacao` como chave de negócio). A massa fictícia insere ~2% de

  duplicatas propositais para validar essa métrica.

  

## Decisões de design

  

- **Postgres + MongoDB**: Postgres para o dado transacional/relacional

  (associado, conta, cartão, movimentação: com integridade referencial

  garantida por FK); MongoDB para o histórico de interações, que é

  naturalmente semiestruturado (cada canal pode gerar um formato de

  metadata diferente) e não se beneficiaria de um schema relacional rígido.

- **Extensão do modelo — tabela `cartao`**: o enunciado pedia só

  associado/conta/movimentação, mas mantive `cartao` como entidade

  intermediária, porque (a) movimentações em uma cooperativa financeira

  tipicamente acontecem via cartão, e (b) isso viabiliza diretamente o

  exemplo de entrega analítica pedido no desafio ("movimentações por tipo

  de cartão"), usando a coluna `bandeira`.

- **Módulo `quality.py` separado do job principal**: isolei as funções de

  anonimização, validação e métricas de qualidade num módulo próprio,

  puramente funcional (recebe DataFrame, devolve DataFrame/dicionário), para

  poder testá-las unitariamente sem precisar montar um cenário de join

  completo a cada teste.

- **Parquet em vez de Delta Lake**: o desafio aceita qualquer um dos dois.

  Optei por Parquet puro para não adicionar a dependência extra do

  `delta-spark` e simplificar o setup do ambiente. Documentando aqui que,

  em um cenário real de produção, Delta Lake (ou Iceberg) seria preferível

  por trazer transações ACID e time travel, importante justamente para um

  histórico financeiro auditável.

- **CPF fictício via Faker**: usei o provider `pt_BR` do Faker, que já gera

  CPFs em formato válido (mas fictício), para deixar o mascaramento mais

  realista.

  

## Pontos de melhoria e limitações

  

- A anonimização atual é aplicada só na camada final (flat). Em um cenário

  real, a camada raw do data lake também deveria ter controle de acesso

  restrito, já que guardaria o dado sensível original.

- O relatório de qualidade é escrito como um único JSON por execução; em

  produção, isso evoluiria para série histórica (ex: uma tabela/partição por

  execução), permitindo acompanhar a qualidade dos dados ao longo do tempo.

- A leitura do MongoDB usa o Spark Mongo Connector; não há retry configurado

  para falhas transitórias de conexão além do "aguarde o serviço subir" no

  `run_pipeline.sh`.

- Os testes unitários cobrem a lógica de qualidade e o join com dados

  sintéticos em memória; não há teste de integração real contra Postgres/Mongo

  (ex: via `testcontainers`), o que eu adicionaria com mais tempo.

- Pensar em outra forma de inserção de dados caso não fosse um desafio técnico, trocar para 'on conflict', gerar truncate antes dos dados, ou alguma outra forma melhor e performatica. (No momento sempre ao rodar o etl se não derrubar o container vai gerar mais e mais dados todas as vezes)

- Pensar em frequencia de recebimento e ingestão de novos dados.

## Dificuldades encontradas

  

- Configurar o Spark para ler de duas fontes diferentes (JDBC + Mongo

  Connector) na mesma sessão exigiu declarar os dois pacotes Maven juntos em

  `spark.jars.packages`: inicialmente tentei configurá-los separadamente e

  o Spark só carregava o primeiro.

- Definir a chave de "duplicidade" para a métrica de qualidade não é trivial

  sem uma chave natural de negócio explícita na tabela de movimentação (ela

  usa `id` autoincremental, o que por si só não protege os dados de serem duplicados): optei por usar a combinação de

  cartão+valor+descrição+data como proxy de duplicidade real de negócio.


Nota de comentário: Usei para a criação dos dados mockup a mesma api que conheci recentemente para criar um gerador de dados falso web o projeto tá aqui: https://github.com/GregGregK/Gerador-De-Dados e também está hospedado em um vercel.
