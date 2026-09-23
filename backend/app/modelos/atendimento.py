# ==============================================================================
# ARQUIVO: modelos/atendimento.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo define a tabela "atendimentos" — cada linha é UM contato de
# suporte de um cliente final com uma empresa, do início ao fim (não uma
# pessoa: o mesmo cliente pode abrir vários atendimentos diferentes ao longo
# do tempo, sobre assuntos sem relação nenhuma entre si — mesmo raciocínio
# já usado no Agente de Cobrança para "um caso não é uma pessoa").
#
# Diferença central em relação ao Lead do Agente Comercial SDR e ao
# CasoDeCobranca do Agente de Cobrança (ver Informacoes/Arquitetura.md,
# seção 2): este é o primeiro agente RECEPTIVO da linhagem — não existe
# "abordagem" nem "follow-up de quem não respondeu". Um Atendimento nasce
# sozinho, automaticamente, na primeira mensagem recebida de um número que
# ainda não tinha um atendimento em aberto. O funil por isso é mais simples:
#
#   RECEBIDO  --(agente começa a responder)-->  EM_ATENDIMENTO
#   EM_ATENDIMENTO  --(agente encaminha pro setor certo)-->  ENCAMINHADO
#   EM_ATENDIMENTO  --(base de conhecimento já resolveu a dúvida)-->  RESOLVIDO
#
# Sem campo de "origem" (não existe importação de arquivo nem CRM externo
# neste domínio — todo atendimento nasce de uma mensagem receptiva) e sem
# os campos financeiros do Cobrança (não se aplicam aqui).
# ==============================================================================

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco_dados import Base


class StatusAtendimento(str, enum.Enum):
    """As quatro fases do funil de atendimento, na ordem em que acontecem."""

    RECEBIDO = "recebido"  # primeira mensagem chegou, ainda não processada
    EM_ATENDIMENTO = "em_atendimento"  # o agente já está conversando/consultando a base de conhecimento
    ENCAMINHADO = "encaminhado"  # foi roteado para um setor humano (ver modelos/setor.py)
    RESOLVIDO = "resolvido"  # a base de conhecimento resolveu a dúvida, sem precisar de humano


class Atendimento(Base):
    """Um contato de suporte — do início ao fim — dentro da Base de Atendimentos de uma empresa."""

    __tablename__ = "atendimentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_empresa: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)

    # --- Dados de contato do cliente final ---
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    whatsapp: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)

    status: Mapped[StatusAtendimento] = mapped_column(
        Enum(StatusAtendimento, name="status_atendimento"), default=StatusAtendimento.RECEBIDO, index=True
    )

    # Setor para onde o atendimento foi encaminhado — nulo até o agente
    # decidir rotear (ferramenta encaminhar_para_setor, ver
    # agente/ferramentas.py). Diferente do "desfecho único" do SDR/Cobrança:
    # aqui o destino muda por atendimento, não é uma configuração fixa da
    # empresa (ver Informacoes/Arquitetura.md, seção 4.2).
    id_setor: Mapped[int | None] = mapped_column(ForeignKey("setores.id"), nullable=True)

    # Resumo gerado pelo agente ao encerrar o atendimento (encaminhar ou
    # resolver) — mesmo padrão do "resumo da pendência" no Cobrança.
    # Bug real encontrado em teste: era String(500), mas o próprio prompt
    # pede um resumo "real, como se estivesse repassando o caso pra um
    # colega" — o modelo às vezes escreve mais que isso, e o INSERT
    # estourava com `StringDataRightTruncation`, derrubando o turno
    # inteiro (nenhuma mensagem chegava ao cliente, e o Celery reprocessava
    # do zero a cada tentativa, sem nunca resolver — o mesmo texto sempre
    # estourava de novo). Text (sem limite) elimina essa classe de erro.
    resumo_do_atendimento: Mapped[str | None] = mapped_column(Text, nullable=True)

    ultima_atividade_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Controla o reengajamento de um atendimento EM_ATENDIMENTO que ficou
    # 3+ dias sem resposta do cliente desde a última mensagem do agente —
    # disparo ÚNICO NA VIDA DO ATENDIMENTO (mesmo princípio do SDR/Cobrança:
    # uma vez True, nunca mais volta para False).
    reengajamento_por_silencio_enviado: Mapped[bool] = mapped_column(Boolean, default=False)

    # Quantas mensagens LIVRES (não-template) o agente já mandou desde o
    # último template enviado (notificação, reengajamento, ou o
    # reencaminhamento) — mesma trava de custo por atendimento já usada nos
    # outros dois projetos (ver
    # agente/ferramentas.py:NUMERO_MAXIMO_DE_MENSAGENS_LIVRES_ANTES_DO_ENCAMINHAMENTO).
    mensagens_livres_desde_ultimo_template: Mapped[int] = mapped_column(Integer, default=0)

    # Flag de "silêncio definitivo": True depois que o atendimento já foi
    # reencaminhado UMA VEZ para o setor humano após o encaminhamento
    # original — a partir daqui, o cliente nunca mais recebe resposta nem
    # gera um novo encaminhamento, mesmo que escreva de novo; a mensagem
    # dele só é registrada no histórico, sem nenhuma chamada de IA (custo
    # zero). Checado ANTES de invocar o grafo em
    # agente/orquestrador.py:processar_mensagem_recebida.
    encaminhamento_definitivo: Mapped[bool] = mapped_column(Boolean, default=False)

    # True assim que o guardrail de entrada (ver
    # agente/guardrails.py:detectar_tentativa_de_manipulacao) detecta, em
    # qualquer mensagem deste atendimento, um sinal de tentativa de
    # manipulação do agente — nunca resetado de volta para False. Usado
    # pra escolher o template de ATENÇÃO em vez do de notificação normal ao
    # encaminhar.
    houve_tentativa_de_manipulacao: Mapped[bool] = mapped_column(Boolean, default=False)

    # Quantas vezes este atendimento, já marcado RESOLVIDO em algum
    # momento, recebeu uma mensagem NOVA do cliente depois (ver
    # rotas/whatsapp_webhook.py — é o mesmo ponto que reabre o status pra
    # EM_ATENDIMENTO e zera mensagens_livres_desde_ultimo_template, de
    # propósito: pra WhatsApp, uma mensagem espontânea do cliente já abre
    # uma janela de atendimento nova, sem precisar de template, então o
    # orçamento de mensagens livres também deveria começar do zero).
    # Nunca decresce. Além de alimentar a "Taxa de reabertura" do
    # Dashboard (ver rotas/painel.py), é a base pra cobrança por lead no
    # futuro comercial da plataforma: cada reabertura consome custos reais
    # de novo (mensagens da Meta, tokens de transcrição/modelo de texto) —
    # era um simples bool (`foi_reaberto`) até esta correção, mas
    # cobrança precisa saber QUANTAS vezes, não só se aconteceu ao menos
    # uma. Era uma boa base o campo, mas incompleto pra faturar por
    # ciclo — se um dia a cobrança precisar de custo REAL por ciclo
    # (tokens, templates), a evolução natural daqui é uma tabela própria
    # de "ciclos de atendimento" (1 linha por reabertura, com os custos
    # daquele ciclo específico) — não implementada ainda, por falta de um
    # consumidor real (nenhuma lógica de cobrança existe ainda no
    # projeto); este contador é o mínimo necessário até lá.
    numero_de_reaberturas: Mapped[int] = mapped_column(Integer, default=0)

    empresa: Mapped["Empresa"] = relationship(back_populates="atendimentos")
    setor: Mapped["Setor | None"] = relationship()
    conversas: Mapped[list["Conversa"]] = relationship(
        back_populates="atendimento", cascade="all, delete-orphan"
    )


from app.modelos.conversa import Conversa  # noqa: E402
from app.modelos.empresa import Empresa  # noqa: E402
from app.modelos.setor import Setor  # noqa: E402

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define a tabela "atendimentos" e StatusAtendimento (as
# quatro fases do funil receptivo: recebido → em atendimento → encaminhado/
# resolvido). Cada atendimento nasce automaticamente na primeira mensagem de
# um cliente, sem precisar de importação prévia, e pode ser roteado para um
# Setor cadastrado pela empresa. É o status, junto com a última atividade,
# que alimenta os cartões do Dashboard e a decisão de reengajamento por
# silêncio tomada pela varredura periódica (app/tarefas/tarefas_monitoramento.py).
# ==============================================================================
