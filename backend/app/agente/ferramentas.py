# ==============================================================================
# ARQUIVO: agente/ferramentas.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo dá ao modelo de IA FERRAMENTAS de verdade — em vez de pedir
# uma resposta em formato fixo (JSON) e o código Python decidir o que fazer
# com ela, o próprio modelo recebe uma lista de ações reais que pode chamar
# quando (e só quando) julgar apropriado, no meio da conversa. Mesmo padrão
# de tool calling livre já usado nos outros dois projetos da linhagem (ver
# Informacoes/Arquitetura.md, seção 3).
#
# Versão ADAPTADA, para o Agente de Atendimento, do mesmo arquivo nos
# outros dois projetos — reescrita quase por completo, porque o conjunto de
# ferramentas muda de verdade neste domínio (ver Arquitetura.md, seção 5):
#
#   - consultar_base_de_conhecimento: NOVA — busca semântica (pgvector) nos
#     itens que a empresa cadastrou, a "FAQ com RAG" do roadmap original,
#     implementada como uma ferramenta a mais no mesmo loop de turno/passo
#     (não um agente CrewAI separado — ver Arquitetura.md, seção 3.1).
#   - encaminhar_para_setor: substitui encaminhar_para_atendimento_humano —
#     agora parametrizada por SETOR (Vendas/Financeiro/Suporte Técnico...),
#     validada em código contra os setores de verdade cadastrados pela
#     empresa (agente/guardrails_de_atendimento.py) antes de mandar
#     qualquer WhatsApp real.
#   - marcar_como_resolvido: NOVA — fecha o atendimento sem precisar de
#     humano, quando a Base de Conhecimento já respondeu a dúvida.
#   - nao_responder: mantida, mesmo padrão de silêncio proposital.
#
# Sem "marcar_como_interessado" (não existe qualificação de interesse
# neste domínio) e sem as ferramentas de agendar_reuniao/enviar_proposta/
# enviar_link_pagamento/enviar_link_app (não existe desfecho único
# configurável — ver Arquitetura.md, seção 4.2).
# ==============================================================================

from dataclasses import dataclass

from langchain_core.tools import BaseTool, tool
from sqlalchemy.orm import Session

import structlog

from app.agente.estados import PerfilDaEmpresa
from app.agente.guardrails_de_atendimento import validar_setor_de_encaminhamento
from app.integracoes_externas.embeddings import gerar_embedding
from app.integracoes_externas.whatsapp import (
    enviar_mensagem_de_template,
    enviar_mensagem_de_texto,
    normalizar_numero_brasileiro,
)
from app.modelos.atendimento import Atendimento, StatusAtendimento
from app.modelos.configuracao_agente import ConfiguracaoAgente
from app.modelos.empresa import Empresa
from app.modelos.integracao import IntegracaoWhatsApp
from app.modelos.item_de_conhecimento import ItemDeConhecimento

logger = structlog.get_logger(__name__)

# Teto de custo por atendimento (mesmo princípio dos outros dois projetos):
# no máximo esta quantidade de mensagens LIVRES (não-template) pode ser
# mandada a um atendimento antes do agente/nos.py forçar um encaminhamento
# — trava de CÓDIGO, não só instrução de prompt. Contada em
# Atendimento.mensagens_livres_desde_ultimo_template.
NUMERO_MAXIMO_DE_MENSAGENS_LIVRES_ANTES_DO_ENCAMINHAMENTO = 5

# Quantos itens da Base de Conhecimento a busca por similaridade devolve
# por chamada — poucos o bastante para caber no contexto do modelo sem
# inflar o prompt, muitos o bastante para cobrir o caso de uma resposta
# precisar combinar mais de um item (ex.: pergunta sobre "troca e reembolso"
# pode ter um item pra cada política).
NUMERO_DE_ITENS_RECUPERADOS_POR_CONSULTA = 4


@dataclass
class RodadaDoTurno:
    """
    Acumula o que as ferramentas decidiram durante um turno de conversa.
    Começa "em branco"; cada ferramenta chamada pelo modelo atualiza os
    campos que fazem sentido para ela. Ao final do turno, agente/nos.py lê
    esses valores para compor o resultado devolvido ao restante do sistema.
    """

    desfecho_acionado: str | None = None  # "encaminhado" ou "resolvido"


@dataclass
class ContextoDoTurno:
    """
    Tudo que as ferramentas de um turno de conversa podem precisar: o texto
    que a empresa configurou (`perfil`), o "bloco de anotações" da rodada
    atual (`rodada`), os objetos reais do atendimento/empresa/credenciais, e
    a `sessao` de banco — necessária aqui porque, diferente dos outros dois
    projetos, a ferramenta de busca na Base de Conhecimento e a validação
    de setor precisam consultar o banco DENTRO do próprio turno (uma
    query ad-hoc de similaridade vetorial, não um objeto já carregado de
    antemão).
    """

    perfil: PerfilDaEmpresa
    rodada: RodadaDoTurno
    atendimento: Atendimento
    empresa: Empresa
    configuracao: ConfiguracaoAgente
    integracao_whatsapp: IntegracaoWhatsApp
    sessao: Session


async def enviar_notificacao_ao_setor(
    contexto: ContextoDoTurno, telefone_do_setor: str, texto_da_notificacao: str, eh_reencaminhamento: bool = False
) -> bool:
    """
    Manda uma notificação de WhatsApp de VERDADE para o contato humano de
    um setor — tenta primeiro o template aprovado dedicado a isso (garante
    entrega mesmo sem uma janela de 24h aberta com esse número — ver
    integracoes_externas/meta_templates.py), com texto livre como plano B.
    Reaproveitada tanto pelo encaminhamento normal quanto pelo
    reengajamento pós-encaminhamento.

    `eh_reencaminhamento=True` troca o template usado para
    `nome_do_template_reencaminhamento` (em vez de
    `nome_do_template_encaminhamento`) — o texto do template original abre
    com "Novo atendimento", errado para um atendimento que o setor já está
    tratando.

    Se `contexto.atendimento.houve_tentativa_de_manipulacao` for True, o
    template de ATENÇÃO tem PRIORIDADE sobre `eh_reencaminhamento` — o
    sinal de "isso pode não ser um atendimento de verdade" é mais
    importante pro setor do que a formalidade de ser um reencaminhamento.
    """
    numero_normalizado = normalizar_numero_brasileiro(telefone_do_setor)
    id_atendimento = contexto.atendimento.id
    if contexto.atendimento.houve_tentativa_de_manipulacao:
        nome_do_template = contexto.configuracao.nome_do_template_atencao
    elif eh_reencaminhamento:
        nome_do_template = contexto.configuracao.nome_do_template_reencaminhamento
    else:
        nome_do_template = contexto.configuracao.nome_do_template_encaminhamento

    # A Meta rejeita (erro 132018) qualquer variável de template com quebra
    # de linha, tab, ou 4+ espaços seguidos (ver precedente nos outros dois
    # projetos da linhagem) — o texto livre (plano B) não tem essa
    # restrição, só a variável do TEMPLATE é normalizada.
    texto_para_variavel_do_template = " ".join(texto_da_notificacao.split())

    try:
        resultado_envio = await enviar_mensagem_de_template(
            id_numero_telefone=contexto.integracao_whatsapp.id_numero_telefone_meta,
            token_de_acesso=contexto.integracao_whatsapp.token_de_acesso,
            numero_destino=numero_normalizado,
            nome_do_template=nome_do_template,
            idioma="pt_BR",
            parametros=[contexto.atendimento.nome, contexto.atendimento.whatsapp, texto_para_variavel_do_template],
        )
        logger.info(
            "notificacao_setor_enviada_via_template",
            id_atendimento=id_atendimento,
            numero_destino=numero_normalizado,
            id_mensagem_whatsapp=(resultado_envio.get("messages") or [{}])[0].get("id"),
        )
        return True
    except ValueError as erro_do_template:
        logger.warning(
            "template_de_notificacao_indisponivel_tentando_texto_livre",
            id_atendimento=id_atendimento,
            erro=str(erro_do_template),
        )
        texto_para_o_setor = (
            f"🔔 {contexto.configuracao.nome_do_agente} ({contexto.empresa.nome_fantasia})\n\n"
            f"Atendimento: {contexto.atendimento.nome}\n"
            f"WhatsApp: {contexto.atendimento.whatsapp}\n\n"
            f"{texto_da_notificacao}"
        )
        try:
            resultado_envio = await enviar_mensagem_de_texto(
                id_numero_telefone=contexto.integracao_whatsapp.id_numero_telefone_meta,
                token_de_acesso=contexto.integracao_whatsapp.token_de_acesso,
                numero_destino=numero_normalizado,
                texto=texto_para_o_setor,
            )
            logger.info(
                "notificacao_setor_aceita_pela_meta_via_texto_livre",
                id_atendimento=id_atendimento,
                numero_destino=numero_normalizado,
                id_mensagem_whatsapp=(resultado_envio.get("messages") or [{}])[0].get("id"),
            )
            return True
        except ValueError as erro:
            logger.error("falha_ao_notificar_setor", id_atendimento=id_atendimento, erro=str(erro))
            return False


def _ferramenta_consultar_base_de_conhecimento(contexto: ContextoDoTurno) -> BaseTool:
    """
    Ferramenta de busca semântica (RAG) — a "FAQ" do fluxo triagem → FAQ →
    roteamento descrito no roadmap original, implementada como uma
    ferramenta comum dentro do mesmo loop de turno/passo. Sempre
    disponível: o modelo pode chamá-la quantas vezes precisar no mesmo
    turno, pra perguntas diferentes.
    """

    @tool
    async def consultar_base_de_conhecimento(pergunta: str) -> str:
        """
        Chame esta ferramenta ANTES de afirmar qualquer coisa específica sobre
        a empresa (produtos, serviços, políticas, preços, prazos, procedimentos)
        — nunca responda esse tipo de pergunta de memória. Passe a pergunta do
        cliente (ou uma reformulação mais clara dela) em `pergunta`. Se a busca
        não devolver nada relevante, diga isso ao cliente com a mensagem
        configurada para "fora do escopo" e considere encaminhar para um setor.
        """
        embedding_da_pergunta = await gerar_embedding(pergunta)
        if embedding_da_pergunta is None:
            logger.warning("embedding_da_pergunta_indisponivel", id_atendimento=contexto.atendimento.id)
            return (
                "A busca na Base de Conhecimento está indisponível no momento (falha ao gerar o "
                f"embedding da pergunta). {contexto.perfil['mensagem_fora_do_escopo']}"
            )

        # Distância de cosseno via pgvector ("<=>") — quanto MENOR, mais
        # parecido em significado. order_by direto na coluna vetorial é o
        # que faz o Postgres usar o índice de similaridade, em vez de trazer
        # a tabela inteira pra comparar em Python.
        consulta = (
            contexto.sessao.query(ItemDeConhecimento)
            .filter(
                ItemDeConhecimento.id_empresa == contexto.empresa.id,
                ItemDeConhecimento.embedding.is_not(None),
            )
            .order_by(ItemDeConhecimento.embedding.cosine_distance(embedding_da_pergunta))
            .limit(NUMERO_DE_ITENS_RECUPERADOS_POR_CONSULTA)
        )
        itens_encontrados = consulta.all()

        if not itens_encontrados:
            return (
                "Nenhum item da Base de Conhecimento foi encontrado para esta pergunta. "
                f"{contexto.perfil['mensagem_fora_do_escopo']} Considere encaminhar para um setor se a "
                "dúvida parecer importante."
            )

        trechos = "\n\n".join(f"### {item.titulo}\n{item.conteudo}" for item in itens_encontrados)
        return (
            f"Trechos encontrados na Base de Conhecimento (use SOMENTE estas informações para responder "
            f"sobre a empresa — não complemente com suposições):\n\n{trechos}"
        )

    return consultar_base_de_conhecimento


# Começo dos resultados de ferramenta que significam "a ação NÃO aconteceu"
# (padronizado a partir do Agente de Cobrança). Usado por agente/nos.py
# junto com loop_de_ferramentas.py (`prefixos_de_falha_da_acao`): quando
# uma ferramenta de fechamento devolve um destes, o texto pré-escrito pelo
# modelo é descartado e ele escreve de novo, já sabendo da falha. Toda nova
# mensagem de falha de ferramenta de fechamento deve começar com um destes
# (o guardrail de setor já começa com "Encaminhamento NÃO enviado").
PREFIXOS_DE_FALHA_DA_ACAO: tuple[str, ...] = ("Encaminhamento NÃO enviado",)


def _ferramenta_encaminhar_para_setor(contexto: ContextoDoTurno, eh_reencaminhamento: bool = False) -> BaseTool:
    """
    Fábrica da ferramenta de encaminhamento — parametrizada por
    `eh_reencaminhamento` para poder ser reaproveitada tanto no fluxo
    normal quanto no reengajamento pós-encaminhamento (ver
    agente/nos.py:montar_ferramentas_de_reengajamento no arquivo
    correspondente do Agente Comercial SDR/Cobrança — aqui a mesma ideia
    fica dentro deste próprio arquivo, ver montar_ferramentas_do_turno).
    """

    @tool
    async def encaminhar_para_setor(nome_do_setor: str, resumo_do_atendimento: str) -> str:
        """
        Chame esta ferramenta quando a dúvida do cliente não puder ser resolvida
        com a Base de Conhecimento (consultar_base_de_conhecimento não trouxe
        nada relevante, ou o pedido exige uma ação humana — ex.: reclamação,
        cancelamento, negociação) — encaminhando para o setor certo entre os
        cadastrados pela empresa.

        Em `nome_do_setor`, use EXATAMENTE um dos nomes de setor listados no
        seu contexto. Em `resumo_do_atendimento`, escreva um resumo real da
        conversa até aqui — como se estivesse repassando o caso para um colega
        assumir: o que o cliente precisa, o que já foi perguntado/respondido, e
        por que está encaminhando agora. Esta mensagem será enviada de verdade,
        agora, para quem vai atender.
        """
        setor, erro_de_validacao = validar_setor_de_encaminhamento(contexto.sessao, contexto.empresa.id, nome_do_setor)
        if erro_de_validacao:
            logger.warning(
                "setor_invalido_tentado_pelo_modelo",
                id_atendimento=contexto.atendimento.id,
                nome_tentado=nome_do_setor,
            )
            return erro_de_validacao

        contexto.rodada.desfecho_acionado = "encaminhado"
        contexto.atendimento.status = StatusAtendimento.ENCAMINHADO
        contexto.atendimento.id_setor = setor.id
        contexto.atendimento.resumo_do_atendimento = resumo_do_atendimento

        sucesso = await enviar_notificacao_ao_setor(
            contexto, setor.contato_telefone, resumo_do_atendimento, eh_reencaminhamento=eh_reencaminhamento
        )
        if not sucesso:
            # Bug real (no Agente de Cobrança, mesmo código): o aviso falhou e o
            # agente afirmou ao cliente que tinha encaminhado — ninguém foi
            # avisado de verdade. Agora a falha é honesta e começa com um
            # PREFIXO_DE_FALHA_DA_ACAO.
            return (
                f"Encaminhamento NÃO enviado: o aviso via WhatsApp para {setor.contato_nome} ({setor.nome}) "
                "falhou, então NINGUÉM foi avisado agora. O atendimento fica registrado para a equipe ver na "
                "plataforma. Diga ao cliente, com honestidade e sem detalhe técnico, que a equipe vai analisar "
                "a solicitação — sem afirmar que alguém já foi avisado."
            )

        return (
            f"Encaminhamento enviado de verdade para {setor.nome} ({setor.contato_nome}) agora, com o "
            "resumo que você escreveu. Informe isso ao cliente de forma natural, agradecendo pela conversa."
        )

    return encaminhar_para_setor


def _ferramenta_marcar_como_resolvido(contexto: ContextoDoTurno) -> BaseTool:
    @tool
    async def marcar_como_resolvido(resumo_do_atendimento: str = "") -> str:
        """
        Chame esta ferramenta quando a Base de Conhecimento já tiver resolvido a
        dúvida do cliente por completo, e não houver necessidade de encaminhar
        para nenhum setor. Em `resumo_do_atendimento`, resuma em uma frase o que
        foi respondido.
        """
        resumo_do_atendimento = resumo_do_atendimento or "Dúvida resolvida com base na Base de Conhecimento."
        contexto.rodada.desfecho_acionado = "resolvido"
        contexto.atendimento.status = StatusAtendimento.RESOLVIDO
        contexto.atendimento.resumo_do_atendimento = resumo_do_atendimento
        return "Atendimento marcado como resolvido. Finalize a conversa de forma cordial."

    return marcar_como_resolvido


def _ferramenta_nao_responder(contexto: ContextoDoTurno) -> BaseTool:
    """
    Ferramenta de "silêncio proposital" — mesmo padrão dos outros dois
    projetos: sem uma forma explícita de dizer "nada a acrescentar", o
    modelo é forçado a sempre gerar algum texto, produzindo uma troca
    infinita de cortesias a cada nova mensagem do cliente.
    """

    @tool
    async def nao_responder() -> str:
        """Chame esta ferramenta quando a mensagem do cliente for uma REPETIÇÃO vazia de uma cortesia que você já respondeu segundos atrás — não para toda cortesia: um agradecimento sincero e distinto ainda merece uma resposta breve e humanizada. Isso encerra sua participação neste turno sem mandar nada para o cliente."""
        return "Registrado: nenhuma resposta será enviada neste turno."

    return nao_responder


async def forcar_encaminhamento_por_limite_de_mensagens(contexto: ContextoDoTurno) -> str:
    """
    Chamada pelo CÓDIGO (não pelo modelo) quando o teto de mensagens
    livres é atingido sem o modelo ter chamado nenhuma ferramenta de ação
    — a rede de segurança que garante o teto de custo por atendimento
    mesmo se o modelo "esquecer" de agir na última mensagem livre
    permitida (ver agente/nos.py). Sempre encaminha para o PRIMEIRO setor
    cadastrado (não há como saber qual seria o certo sem o modelo decidir
    — melhor um encaminhamento genérico do que nenhum).
    """
    from sqlalchemy import select

    from app.modelos.setor import Setor

    setor = contexto.sessao.scalar(
        select(Setor).where(Setor.id_empresa == contexto.empresa.id).order_by(Setor.id)
    )
    contexto.rodada.desfecho_acionado = "encaminhado"

    if setor is None:
        logger.warning("encaminhamento_forcado_sem_setor_cadastrado", id_atendimento=contexto.atendimento.id)
        return (
            "Nenhum setor cadastrado para receber este encaminhamento forçado pelo teto de mensagens. "
            "Informe ao cliente que o caso será acompanhado, sem prometer um contato imediato."
        )

    contexto.atendimento.status = StatusAtendimento.ENCAMINHADO
    contexto.atendimento.id_setor = setor.id
    mensagem_para_o_setor = (
        f"Conversa com {contexto.atendimento.nome} atingiu o limite de "
        f"{NUMERO_MAXIMO_DE_MENSAGENS_LIVRES_ANTES_DO_ENCAMINHAMENTO} mensagens automáticas sem um "
        "próximo passo claramente resolvido — encaminhando para revisão humana."
    )
    contexto.atendimento.resumo_do_atendimento = mensagem_para_o_setor
    sucesso = await enviar_notificacao_ao_setor(contexto, setor.contato_telefone, mensagem_para_o_setor)
    logger.warning(
        "encaminhamento_forcado_por_limite_de_mensagens_livres",
        id_atendimento=contexto.atendimento.id,
        setor=setor.nome,
        sucesso=sucesso,
    )
    if not sucesso:
        return f"Encaminhamento forçado registrado, mas o aviso via WhatsApp para {setor.nome} falhou."
    return f"Encaminhamento forçado enviado de verdade para {setor.nome} agora."


def montar_ferramentas_de_reengajamento(contexto: ContextoDoTurno) -> list[BaseTool]:
    """
    Monta as ferramentas oferecidas quando o atendimento já foi encaminhado
    antes (ver agente/nos.py): "nao_responder" para cortesias e insistência
    sem nada de novo, e a ferramenta de encaminhamento (permite
    reencaminhar quando o cliente volta com algo novo e relevante).
    """
    return [
        _ferramenta_nao_responder(contexto),
        _ferramenta_encaminhar_para_setor(contexto, eh_reencaminhamento=True),
    ]


def montar_ferramentas_do_turno(contexto: ContextoDoTurno) -> list[BaseTool]:
    """
    Monta a lista de ferramentas que o modelo pode chamar nesta conversa:
    consultar a Base de Conhecimento, encaminhar para um setor, marcar como
    resolvido, ou não responder — todas SEMPRE disponíveis, diferente dos
    outros dois projetos da linhagem, que ligavam/desligavam ferramentas
    conforme um "desfecho único" configurado pela empresa. Aqui não existe
    esse conceito: o caminho certo (responder com a base, encaminhar, ou
    resolver) muda a cada atendimento, então o modelo sempre vê as quatro
    opções e decide.
    """
    return [
        _ferramenta_consultar_base_de_conhecimento(contexto),
        _ferramenta_encaminhar_para_setor(contexto),
        _ferramenta_marcar_como_resolvido(contexto),
        _ferramenta_nao_responder(contexto),
    ]


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define as quatro ferramentas do Agente de Atendimento:
# consultar_base_de_conhecimento (busca semântica via pgvector — a "FAQ com
# RAG" do fluxo original, sem precisar de CrewAI), encaminhar_para_setor
# (valida o setor escolhido contra o guardrail antes de mandar WhatsApp de
# verdade), marcar_como_resolvido (fecha sem escalar) e nao_responder
# (silêncio proposital, mesmo padrão dos outros dois projetos). Diferente
# do SDR/Cobrança, todas ficam sempre disponíveis no mesmo turno — não há
# um "desfecho único" pré-configurado limitando as opções.
# forcar_encaminhamento_por_limite_de_mensagens() é a rede de segurança
# chamada pelo CÓDIGO quando o teto de mensagens livres é atingido sem
# nenhuma ferramenta de ação ter sido chamada.
# ==============================================================================
