# ==============================================================================
# ARQUIVO: esquemas/autenticacao.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# "Esquemas" (schemas) são os formatos de dados que a API aceita e devolve.
# Enquanto os "modelos" (pasta modelos/) descrevem como a informação é
# guardada no banco de dados, os esquemas descrevem como ela trafega pela
# internet, entre o navegador e o backend — em formato JSON.
#
# Este arquivo, especificamente, define o formato das telas de Cadastro e
# Login descritas no pedido do projeto.
# ==============================================================================

from pydantic import BaseModel, EmailStr, Field


class CadastroEmpresaEntrada(BaseModel):
    """Dados enviados pela tela de Cadastro (cria a empresa e o primeiro usuário)."""

    nome_fantasia: str = Field(min_length=2, max_length=150)
    nome_do_responsavel: str = Field(min_length=2, max_length=150)
    email: EmailStr
    senha: str = Field(min_length=8, description="Mínimo de 8 caracteres.")


class LoginEntrada(BaseModel):
    """Dados enviados pela tela de Login."""

    email: EmailStr
    senha: str


class TokenSaida(BaseModel):
    """O que a API devolve depois de um cadastro ou login bem-sucedido."""

    token_de_acesso: str
    tipo_token: str = "bearer"
    nome_fantasia: str
    nome_do_agente: str


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define os três formatos de dado usados na autenticação:
# CadastroEmpresaEntrada (o que a tela de cadastro envia), LoginEntrada (o
# que a tela de login envia) e TokenSaida (o "crachá digital" que a API
# devolve depois de validar as credenciais, usado pelo frontend em todas as
# chamadas seguintes).
# ==============================================================================
