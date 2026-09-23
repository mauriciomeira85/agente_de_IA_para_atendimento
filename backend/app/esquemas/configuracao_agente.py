# ==============================================================================
# ARQUIVO: esquemas/configuracao_agente.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Define o formato de dado da aba "Configuração do Agente". Versão
# ADAPTADA, para o Agente de Atendimento, do mesmo arquivo nos outros dois
# projetos da linhagem: sem bloco de abordagem/follow-up (agente
# receptivo) e sem "desfecho único" (o encaminhamento é dinâmico, por
# Setor — ver esquemas/setor.py). No lugar entra o bloco "Regras de
# Atendimento" (ver Informacoes/Arquitetura.md, seção 4.3).
# ==============================================================================

from pydantic import BaseModel, ConfigDict, Field


class AreaDeAtuacao(BaseModel):
    """Seleção múltipla de países, estados e municípios atendidos."""

    paises: list[str] = Field(default_factory=list)
    estados: list[str] = Field(default_factory=list)
    municipios: list[str] = Field(default_factory=list)


class ConfiguracaoAgenteEntrada(BaseModel):
    """Formato enviado pelo formulário da aba Configuração do Agente ao salvar."""

    # Perfil da Empresa
    nome_do_agente: str
    contexto_da_empresa: str = ""
    area_atuacao: AreaDeAtuacao = Field(default_factory=AreaDeAtuacao)
    endereco_cep: str | None = None
    endereco_rua: str | None = None
    endereco_bairro: str | None = None
    endereco_numero: str | None = None
    endereco_complemento: str | None = None
    endereco_detalhes_adicionais: str | None = None

    nome_do_template_encaminhamento: str = "notificacao_atendimento_padrao"
    nome_do_template_reengajamento: str = "reengajamento_padrao"
    nome_do_template_reencaminhamento: str = "reencaminhamento_atendimento_padrao"
    nome_do_template_atencao: str = "atencao_manipulacao_padrao"

    # Roteiro da Conversa
    roteiro_conversa: str = ""

    # Regras de Atendimento (bloco novo — guardrail deste projeto)
    responder_apenas_com_base_no_conhecimento: bool = True
    mensagem_fora_do_escopo: str = (
        "Não tenho essa informação no momento, mas vou encaminhar sua dúvida para o setor responsável."
    )


class ConfiguracaoAgenteSaida(ConfiguracaoAgenteEntrada):
    """Mesmo formato de entrada, acrescido de metadados só de leitura."""

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define ConfiguracaoAgenteEntrada/Saida, que representam
# exatamente os campos do formulário da aba Configuração do Agente: Perfil
# da Empresa, Roteiro da Conversa e as Regras de Atendimento (bloco novo).
# É a "fonte da verdade" que o LangGraph consulta antes de cada conversa
# (ver app/agente/prompts.py) para saber como se comportar.
# ==============================================================================
