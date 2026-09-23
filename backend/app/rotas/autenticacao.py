# ==============================================================================
# ARQUIVO: rotas/autenticacao.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo implementa as duas rotas por trás das telas de Cadastro e
# Login descritas no projeto. O cadastro cria, em uma única operação, a
# Empresa (o "tenant" do SaaS), o primeiro Usuário dessa empresa e uma
# ConfiguracaoAgente vazia (para a empresa preencher depois, na aba
# "Configuração do Agente"). O login apenas confere as credenciais e
# devolve um token de acesso.
# ==============================================================================

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.banco_dados import obter_sessao
from app.esquemas.autenticacao import CadastroEmpresaEntrada, LoginEntrada, TokenSaida
from app.modelos.configuracao_agente import ConfiguracaoAgente
from app.modelos.empresa import Empresa
from app.modelos.usuario import Usuario
from app.seguranca import criar_token_de_acesso, gerar_hash_senha, senha_confere

roteador = APIRouter(prefix="/api/autenticacao", tags=["Autenticação"])


@roteador.post("/cadastrar", response_model=TokenSaida, status_code=status.HTTP_201_CREATED)
def cadastrar_empresa(dados: CadastroEmpresaEntrada, sessao: Session = Depends(obter_sessao)) -> TokenSaida:
    """
    Cria uma nova empresa na plataforma (tela de Cadastro). Esta é a rota
    que permite o SaaS atender "cinco novos clientes entrando
    simultaneamente" sem nenhuma intervenção manual: cada cadastro monta,
    automaticamente, um ambiente isolado e pronto para uso — a mesma
    aplicação servindo todas as empresas, mas cada uma enxergando só os
    seus próprios dados.
    """
    email_ja_cadastrado = sessao.query(Usuario).filter(Usuario.email == dados.email).first()
    if email_ja_cadastrado:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este e-mail já está em uso.")

    nova_empresa = Empresa(nome_fantasia=dados.nome_fantasia, email_conta=dados.email)
    sessao.add(nova_empresa)
    sessao.flush()  # garante que nova_empresa.id já existe antes de usá-lo abaixo

    novo_usuario = Usuario(
        id_empresa=nova_empresa.id,
        nome=dados.nome_do_responsavel,
        email=dados.email,
        hash_senha=gerar_hash_senha(dados.senha),
    )
    sessao.add(novo_usuario)

    # Toda empresa nasce com uma configuração de agente em branco, pronta
    # para ser preenchida na aba "Configuração do Agente".
    configuracao_inicial = ConfiguracaoAgente(id_empresa=nova_empresa.id)
    sessao.add(configuracao_inicial)

    sessao.commit()
    sessao.refresh(novo_usuario)

    token = criar_token_de_acesso(id_usuario=novo_usuario.id, id_empresa=nova_empresa.id)
    return TokenSaida(
        token_de_acesso=token,
        nome_fantasia=nova_empresa.nome_fantasia,
        nome_do_agente=configuracao_inicial.nome_do_agente,
    )


@roteador.post("/entrar", response_model=TokenSaida)
def entrar(dados: LoginEntrada, sessao: Session = Depends(obter_sessao)) -> TokenSaida:
    """Confere e-mail e senha (tela de Login) e devolve um token de acesso válido."""
    usuario = sessao.query(Usuario).filter(Usuario.email == dados.email).first()

    if not usuario or not senha_confere(dados.senha, usuario.hash_senha):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha inválidos.")

    token = criar_token_de_acesso(id_usuario=usuario.id, id_empresa=usuario.id_empresa)
    return TokenSaida(
        token_de_acesso=token,
        nome_fantasia=usuario.empresa.nome_fantasia,
        nome_do_agente=usuario.empresa.configuracao_agente.nome_do_agente,
    )


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo expõe duas rotas: POST /api/autenticacao/cadastrar (cria a
# empresa, o primeiro usuário e uma configuração de agente em branco, tudo
# em uma única transação) e POST /api/autenticacao/entrar (login). As duas
# devolvem um token JWT que o frontend guarda e reenvia em toda chamada
# seguinte à API.
# ==============================================================================
