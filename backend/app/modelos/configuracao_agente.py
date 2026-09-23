# ==============================================================================
# ARQUIVO: modelos/configuracao_agente.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo é o "cérebro configurável" do agente: guarda tudo que uma
# empresa preenche na aba "Configuração do Agente" da interface. É esse
# conjunto de informações que o LangGraph (ver app/agente/) lê antes de
# cada conversa, para saber como se apresentar e dentro de quais regras
# responder.
#
# Cada empresa tem EXATAMENTE UMA configuração (relação 1-para-1 com a
# tabela "empresas").
#
# Versão ADAPTADA, para o Agente de Atendimento, do mesmo arquivo nos
# outros dois projetos da linhagem — a diferença mais visível: SEM bloco de
# abordagem/follow-up (este agente é receptivo, nunca inicia contato — ver
# Informacoes/Arquitetura.md, seção 2) e SEM "desfecho único" (o
# encaminhamento aqui é dinâmico, por Setor — ver modelos/setor.py). No
# lugar entram as "Regras de Atendimento": o guardrail deste projeto,
# equivalente às Regras de Negociação do Agente de Cobrança.
# ==============================================================================

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco_dados import Base


class ConfiguracaoAgente(Base):
    """Todas as informações que a empresa ensina ao seu Agente de Atendimento."""

    __tablename__ = "configuracoes_agente"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_empresa: Mapped[int] = mapped_column(
        ForeignKey("empresas.id"), nullable=False, unique=True, index=True
    )

    # --- Bloco "Perfil da Empresa" ---
    nome_do_agente: Mapped[str] = mapped_column(String(100), default="Assistente de Atendimento")

    # Contexto geral da empresa — igual ao padrão já usado no Agente de
    # Cobrança: os detalhes de PRODUTO/POLÍTICA específicos não ficam aqui,
    # ficam na Base de Conhecimento (ver modelos/item_de_conhecimento.py);
    # este campo é só a apresentação geral que o prompt usa (quem é a
    # empresa, o que ela faz, em poucas linhas).
    contexto_da_empresa: Mapped[str] = mapped_column(Text, default="")

    # Área de atuação: lista de países, estados e municípios em que a
    # empresa atua. Guardado como JSON porque é uma seleção múltipla.
    area_atuacao: Mapped[dict] = mapped_column(
        JSON, default=lambda: {"paises": [], "estados": [], "municipios": []}
    )

    # Endereço de referência do negócio (usado pelo agente para responder
    # perguntas do tipo "vocês atendem na minha região?").
    endereco_cep: Mapped[str | None] = mapped_column(String(15), nullable=True)
    endereco_rua: Mapped[str | None] = mapped_column(String(150), nullable=True)
    endereco_bairro: Mapped[str | None] = mapped_column(String(100), nullable=True)
    endereco_numero: Mapped[str | None] = mapped_column(String(20), nullable=True)
    endereco_complemento: Mapped[str | None] = mapped_column(String(100), nullable=True)
    endereco_detalhes_adicionais: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Templates Meta (4, não 5 — sem template de abordagem: este agente
    # nunca inicia contato, ver Informacoes/Arquitetura.md, seção 4.5) ---

    # Notificação ao SETOR humano quando um atendimento é encaminhado pela
    # primeira vez — esse contato quase nunca tem uma janela de 24h aberta
    # com o WhatsApp comercial da empresa, então uma mensagem de texto
    # livre falha (Meta código 131047, "re-engagement message"); só um
    # template aprovado garante a entrega.
    nome_do_template_encaminhamento: Mapped[str] = mapped_column(
        String(150), default="notificacao_atendimento_padrao"
    )

    # Retomar contato com um atendimento EM_ATENDIMENTO que ficou 3+ dias
    # sem responder — a janela de 24h também fecha nesse caso.
    nome_do_template_reengajamento: Mapped[str] = mapped_column(
        String(150), default="reengajamento_padrao"
    )

    # Template SEPARADO do de encaminhamento, usado a partir do SEGUNDO
    # encaminhamento em diante (algo novo surgiu depois de já ter sido
    # encaminhado uma vez) — o texto do template original abre com "Novo
    # atendimento", o que não faz sentido pra um atendimento que o setor já
    # está tratando.
    nome_do_template_reencaminhamento: Mapped[str] = mapped_column(
        String(150), default="reencaminhamento_atendimento_padrao"
    )

    # Template usado quando o guardrail de entrada (ver
    # agente/guardrails.py) detecta tentativa de manipulação do agente
    # durante a conversa.
    nome_do_template_atencao: Mapped[str] = mapped_column(
        String(150), default="atencao_manipulacao_padrao"
    )

    # --- Bloco "Roteiro da Conversa" ---
    roteiro_conversa: Mapped[str] = mapped_column(Text, default="")

    # --- Bloco NOVO "Regras de Atendimento" — o guardrail que os outros
    # dois projetos não têm (ver Informacoes/Arquitetura.md, seção 4.3) ---

    # Se True (padrão), qualquer resposta sobre produtos/serviços/políticas
    # da empresa PRECISA vir de um trecho recuperado da Base de
    # Conhecimento (ferramenta consultar_base_de_conhecimento) — reforçado
    # no prompt, nunca respondida "de memória".
    responder_apenas_com_base_no_conhecimento: Mapped[bool] = mapped_column(Boolean, default=True)

    # Texto customizável de "não sei, vou te encaminhar" — usado quando a
    # busca na Base de Conhecimento não encontra nada relevante o
    # suficiente para responder com segurança.
    mensagem_fora_do_escopo: Mapped[str] = mapped_column(
        Text,
        default="Não tenho essa informação no momento, mas vou encaminhar sua dúvida para o setor responsável.",
    )

    # Reengajamento por silêncio (atendimento fica 3+ dias sem resposta do
    # cliente no meio de uma conversa em aberto) não tem campo de
    # configuração aqui — é sempre um disparo ÚNICO por atendimento, mesmo
    # mecanismo fixo dos outros dois projetos (ver
    # Atendimento.reengajamento_por_silencio_enviado). Diferente do SDR/
    # Cobrança, não existe "follow-up de quem nunca respondeu" configurável
    # (número máximo de tentativas, intervalo em dias), porque não existe
    # abordagem — só existe reengajar quem já estava conversando.

    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    empresa: Mapped["Empresa"] = relationship(back_populates="configuracao_agente")


from app.modelos.empresa import Empresa  # noqa: E402

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define a tabela "configuracoes_agente", com um registro por
# empresa: perfil da empresa, área de atuação, roteiro de conversa, os 4
# templates Meta usados por este domínio e o bloco NOVO "Regras de
# Atendimento" (responder_apenas_com_base_no_conhecimento +
# mensagem_fora_do_escopo) — o guardrail que trava a FONTE da resposta do
# agente, em vez de um número (diferente do Agente de Cobrança).
# ==============================================================================
