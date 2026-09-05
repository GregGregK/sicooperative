from pyspark.sql import DataFrame
from pyspark.sql.functions import col, concat, lit, substring, when, count, countDistinct


def build_star_schema(df_associado: DataFrame, df_conta:DataFrame, df_cartao: DataFrame, 
                      df_mov_valida: DataFrame, df_historico_agg: DataFrame) -> dict: 
    """
    Essa função vai funcionar pra pegar as tabelas da origem já lidas (passando pelas validações) e gerar um modelo estrela 
    em cima dos dados pra que a gente possa usar no power bi    
    
    Retorna um dicionario (como o proprio type hint indica)
    """

    #E como a gente vai rodar a anonimização do cpf e do sobrenome aqui já no dicionario, a gente não vai precisar fazer isso depois em outra etapa de consumo do dado
    #por exemplo, não precisaremos rodar nenhum dax encima do dado, ele já vai sair anonimizado.
    dim_associado = df_associado.select(
        col("id").alias("id_associado"),
        col("nome"),     
        col("sobrenome"),
        col("idade").alias("idade_associado"),
        col("email"),
        col("cpf"),   
    )
    dim_associado = anonimizar_cpf(dim_associado, "cpf")
    dim_associado = anonimizar_nome(dim_associado, "nome", "sobrenome")

    #Aqui vamos enriquecer a tabela de associado com os atributos do mongo (histórico de interações associado)
    dim_associado = (
        dim_associado.alias("da")
        .join(
            df_historico_agg.alias("h"),
            col("da.id_associado") == col("h.associado_id"),
            "left",
        )
        .select(
            col("da.*"),
            col("h.qtd_interacoes").alias("qtd_interacoes_historico"),
        )
        
    )

    dim_conta = df_conta.select(
        col("id").alias("id_conta"),
        col("tipo").alias("tipo_conta"),
        col("data_criacao").alias("data_criacao_conta"),
    )

    dim_cartao = df_cartao.select(
        col("id").alias("id_cartao"),
        col("num_cartao"),
        col("nom_impresso").alias("nome_impresso_cartao"),
        col("bandeira"),
        col("data_criacao").alias("data_criacao_cartao"),
    )


    #Fato modelo starschema (podia ser snowflake mas deixaria o projeto mais complexo)
    #Vamos gerar os relacionamentos aqui, para não depender do power bi
    
    fato_movimentacao = (
        df_mov_valida.alias("mov")
        .join(df_cartao.alias("car"), col("mov.id_cartao") == col("car.id"), "inner")
        .select(
            col("mov.id").alias("id_movimentacao"),
            col("mov.id_cartao"),
            col("car.id_conta"),
            col("car.id_associado"),
            col("mov.vlr_transacao"),
            col("mov.des_transacao"),
            col("mov.data_movimentacao"),
        )
    )
    
    return {
        "dim_associado": dim_associado,
        "dim_conta": dim_conta,
        "dim_cartao": dim_cartao,
        "fato_movimentacao": fato_movimentacao
    }

def anonimizar_cpf(df: DataFrame, coluna:str = "cpf") -> DataFrame:
    """
    Função que vai ajudar a mascarar o CPF e manter só os dois últimos dígitos visíveis. 
    Assim ainda permite a conferência do dado sem expor ele completo.
    """
    return df.withColumn(
        coluna,
        concat(lit("***.***,**-"), substring(col(coluna), -2, 2))
    )


def anonimizar_nome(df: DataFrame, coluna_nome: str = "nome", coluna_sobrenome: str ="sobrenome") -> DataFrame:
    """
    Função para manter o primeiro nome normal e censurar o segundo nome só com a inicial.
    Permite confêrencia de dados,
    """
    #Se houver duas pessoas com nomes parecidos, conferimos pelo final do cpf
    #Se houver duas pessoas com nomes parecidos e final igual do cpf (irmãos)? ai repensamos o modelo
    return df.withColumn (
        coluna_sobrenome,
        concat(substring(col(coluna_sobrenome), 1,1), lit("."))
    )


def validar_movimentacoes(df: DataFrame, coluna_valor: str = "vlr_transacao"): 
    """
    Aqui a gente vai pegar a movimentação que criamos no faker com porcentagem de chance de vir movimentações negativas
    E separar ela em dois tipos: válidas e inválidas
    """

    total = df.count()
    df_invalido = df.filter(col(coluna_valor) <= 0)
    df_valido = df.filter(col(coluna_valor) > 0)

    invalidos = df_invalido.count()
    percentual_invalido = round((invalidos / total) * 100,2) if total > 0 else 0.0

    return df_valido, df_invalido, percentual_invalido

def calcular_metricas_qualidade(df: DataFrame, colunas_chave_duplicidade: list) -> dict:
    """
    Essa função vai servir pra calcular o percentual de nulos por coluna 
    E o percentual de linhas duplicadas(pela chave), e vai retornar um dicionário pronto que vai virar o log/relatório de qualidade
    """

    total = df.count()
    metricas = {"total_registros": total, "percentual_nulos_por_coluna": {}}

    for coluna in df.columns:
        nulos = df.filter(col(coluna).isNull()).count()
        percentual = round((nulos / total) * 100, 2) if total > 0 else 0.0
        metricas["percentual_nulos_por_coluna"][coluna] = percentual

    if total > 0:
        registros_distintos = df.select(colunas_chave_duplicidade).distinct().count()
        duplicados = total - registros_distintos
        metricas["percentual_duplicados"] = round((duplicados / total) * 100,2)
        metricas["total_duplicados"] = duplicados
    else:
        metricas["percentual_duplicados"] = 0.0
        metricas["total_duplicados"] = 0

    return metricas
