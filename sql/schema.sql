CREATE TABLE IF NOT EXISTS associado (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    sobrenome varchar(100) NOT NULL,
    idade INT NOT NULL,
    email VARHCAR(150) NOT NULL,
    cpf VARCHAR(14) NOT NULL UNIQUE -- cpf vai ser o dado sensível que vou tratar posteriormente com uma função, lembrar de convsersar sobre na reunião para comentar sobre caso de uso na CGE
);

CREATE TABLE IF NOT EXISTS conta (
    id SERIAL PRIMARY KEY,
    tipo VARCHAR(50) NOT NULL,
    data_criacao TIMESTAMP NOT NULL,
    id_associado INT NOT NULL REFERENCES associado(id) --REFERENCES é a FOREIGN KEY em POSTGRESQL para gerar os chavamentos de forma "automatica" (na criação)

);

CREATE TABLE IF NOT EXISTS cartao (
    id SERIAL PRIMARY KEY,
    num_cartao VARCHAR(20) NOT NULL, --dado sensivel? provavelmente mas vou manter apenas no cpf e nome como foi solicitado
    nom_impesso VARCHAR(100) NOT NULL, --bater com nome do associado? uma boa, mas talvez deixe o projeto complexo
    bandeira VARCHAR(20) NOT NULL,
    data_criacao TIMESTAMP NOT NULL,
    id_conta INT NOT NULL REFERENCES conta(id), --gera chave com a tabela de conta
    id_associado INT NOT NULL REFERENCES associado(id) --gera a relação com associado
);

CREATE TABLE IF NOT EXISTS movimentacao (
    id SERIAL PRIMARY KEY,
    vlr_transacao DECIMAL(15,2) NOT NULL, --na inserção adicionar dados negativos para poder fazer as funções de teste e fazer validação de integridade, decidir 15,2 ou 10,2
    des_transacao VARCHAR(200) NOT NULL,
    data_movimentacao  TIMESTAMP NOT NULL, --timestamp ao inves de date pra poder ver exatamente o momento da inserção ou do contexto
    id_cartao INT NOT NULL REFERENCES cartao(id)
);

CREATE INDEX IF NOT EXISTS idx_conta_associado ON conta(id_associado);
CREATE INDEX IF NOT EXISTS idx_cartao_conta ON cartao(id_conta);
CREATE INDEX IF NOT EXISTS idx_cartao_associado ON cartao(id_associado);
CREATE INDEX IF NOT EXISTS idx_movimentacao_cartao ON movimentacao(id_cartao);
