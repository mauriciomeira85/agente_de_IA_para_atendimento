# ==============================================================================
# ARQUIVO: esquemas/integracao_saida.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Define o formato de dado da aba "Integrações": conexões usadas para
# ENVIAR os dados do Dashboard para um CRM ou aplicação externa. Diferente
# dos outros dois projetos da linhagem, não existe aqui uma conexão na
# direção inversa (trazer contatos de um CRM externo pra dentro) — este
# agente é receptivo, todo Atendimento nasce da própria mensagem do
# cliente no WhatsApp. chave_api nunca aparece em IntegracaoSaidaSaida —
# é um segredo de escrita apenas, nunca devolvido pela API para o navegador.
# ==============================================================================

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class IntegracaoSaidaEntrada(BaseModel):
    """Formulário de conexão com um destino externo para envio dos dados do Dashboard."""

    nome_da_conexao: str
    url_webhook: str
    chave_api: str | None = None


class IntegracaoSaidaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome_da_conexao: str
    url_webhook: str
    criado_em: datetime
    ultimo_envio_em: datetime | None
    ultimo_envio_com_sucesso: bool | None


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define os formatos usados na aba Integrações:
# IntegracaoSaidaEntrada (o que o formulário de conexão envia) e
# IntegracaoSaidaSaida (o que a lista de conexões já cadastradas mostra,
# incluindo o resultado do último envio).
# ==============================================================================
