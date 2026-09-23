# ==============================================================================
# ARQUIVO: agente/loop_de_ferramentas.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo implementa o mecanismo central da arquitetura do agente: o
# loop de "turno/passo" com tool calling livre — chama o modelo, se ele
# pedir uma ferramenta, executa e devolve o resultado, e repete até o
# modelo responder só em texto (ou até bater um teto de segurança).
#
# É o MESMO loop usado tanto na conversa reativa (ver agente/nos.py,
# executar_turno_do_agente — responde uma mensagem do atendimento) quanto na
# varredura periódica (ver agente/monitoramento.py — decide o que fazer
# com os atendimentos pendentes de uma empresa). Só as ferramentas disponíveis
# mudam de um caso para o outro; o mecanismo de "perguntar, executar,
# repetir" é sempre este arquivo.
#
# Esse desenho — um loop genérico e reaproveitável, com o comportamento de
# negócio entrando só através de QUAIS ferramentas são passadas para ele —
# é o padrão encontrado, de forma independente, em quatro agentes de IA de
# programação estudados antes desta arquitetura (deepseek-harness, Kimi
# Code, Codex CLI e opencode — ver Informacoes/Registros_Claude.md): todos
# têm um loop central "burro" (não sabe nada sobre permissão, compactação
# ou qualquer regra de negócio) que só entende "chame o modelo, rode as
# ferramentas pedidas, repita".
#
# IMPORTANTE: as ferramentas nunca são forçadas (bind_tools, sem
# tool_choice fixo) — é o modelo que decide sozinho se/quando/qual chamar.
# Forçar uma ferramenta específica foi o que quebrou o deepseek-v4-flash
# numa tentativa anterior desta plataforma (ver Registros_Claude.md,
# 04/09/2026) — o modo livre, usado pelos quatro agentes de referência,
# funciona sem esse problema.
# ==============================================================================

import structlog
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool

from app.integracoes_externas.deepseek import montar_modelo_de_texto

logger = structlog.get_logger(__name__)

# Teto de segurança do loop: nenhum dos quatro agentes estudados deixa
# esse ciclo rodar indefinidamente — todos têm um limite de passos. Um
# "passo" aqui é uma chamada ao modelo; se ele pedir uma ferramenta, mais
# um passo é gasto para devolver o resultado e ele responder de novo.
NUMERO_MAXIMO_DE_PASSOS_PADRAO = 4


async def rodar_loop_de_ferramentas(
    mensagens: list,
    ferramentas: list[BaseTool],
    numero_maximo_de_passos: int = NUMERO_MAXIMO_DE_PASSOS_PADRAO,
    id_para_log: int | str | None = None,
    ferramentas_terminais: frozenset[str] = frozenset(),
    ferramentas_de_fechamento: frozenset[str] = frozenset(),
) -> str | None:
    """
    Roda o loop de turno/passo até o modelo responder só em texto (sem
    pedir nenhuma ferramenta), até pedir uma ferramenta TERMINAL ou DE
    FECHAMENTO, ou até bater o teto de passos. Devolve o texto final da
    resposta — vazio se o teto foi atingido sem o modelo fechar em texto.

    `ferramentas_terminais`: nomes de ferramentas que, se chamadas,
    encerram o turno IMEDIATAMENTE, sem pedir mais nada ao modelo — usadas
    para um sinal de "nada a fazer/dizer" (ver agente/ferramentas.py,
    "nao_responder"). Diferente das demais, elas nem chegam a ser
    executadas: o próprio pedido já é o sinal suficiente, e o loop devolve
    None (silêncio proposital, diferente de "" que sinaliza teto de passos
    atingido). Sem essa distinção, misturar "nao_responder" com uma
    ferramenta de ação real no mesmo turno teria um problema: depois de
    QUALQUER chamada de ferramenta, o loop naturalmente pede ao modelo uma
    resposta final de texto (para fechar a conversa) — o que faria sentido
    para a ferramenta de ação, mas re-abriria a resposta logo depois de o
    modelo já ter sinalizado silêncio.

    `ferramentas_de_fechamento`: nomes de ferramentas de AÇÃO que
    normalmente marcam o desfecho de um turno (ex.: marcar_como_resolvido,
    encaminhar_para_setor) — DIFERENTE de `ferramentas_terminais`, elas
    SÃO executadas normalmente (têm efeito real). A diferença é só o que
    acontece com o TEXTO: se a mesma resposta do modelo já trouxer
    conteúdo de texto (o prompt pede exatamente isso — "responda e chame a
    ferramenta de ação, na mesma resposta"), esse texto É a resposta final
    pro cliente, e o loop devolve ele direto depois de executar a
    ferramenta, sem pedir mais um passo. Bug real encontrado em teste, sem
    esta checagem: o texto de verdade que o modelo escreveu (a resposta
    substantiva, usando o que achou na Base de Conhecimento) era
    DESCARTADO aqui, o loop pedia mais um passo "pra fechar", e o modelo,
    vendo só a confirmação genérica da ferramenta ("Atendimento marcado
    como resolvido. Finalize a conversa de forma cordial."), escrevia uma
    resposta final SEM NENHUM conteúdo real — tipo "Fico à disposição,
    bons estudos!" — ignorando a pergunta original do cliente. O agente
    parecia superficial e sem memória; a causa real era esta, não falta de
    contexto ou de RAG.

    As ferramentas em si são responsáveis por registrar qualquer decisão
    que o restante do sistema precise conhecer depois (normalmente através
    de um objeto "rodada" capturado no fechamento de cada ferramenta — ver
    agente/ferramentas.py e agente/ferramentas_monitoramento.py); este
    loop só cuida de perguntar ao modelo e executar o que ele pedir.
    """
    ferramentas_por_nome = {ferramenta.name: ferramenta for ferramenta in ferramentas}
    modelo_com_ferramentas = montar_modelo_de_texto().bind_tools(ferramentas)

    tokens_de_entrada_acumulados = 0
    tokens_de_saida_acumulados = 0
    tokens_de_cache_acumulados = 0

    for passo in range(numero_maximo_de_passos):
        resposta = await modelo_com_ferramentas.ainvoke(mensagens)

        # O provedor do cérebro (hoje DeepSeek, compatível com o formato
        # OpenAI — ver integracoes_externas/deepseek.py) devolve o uso de
        # tokens de verdade em CADA resposta — diferente de uma estimativa
        # feita depois com um tokenizador genérico, este número é
        # exatamente o que a conta do provedor cobra. "cache_read" (dentro
        # de input_token_details) é quanto dos tokens de ENTRADA acertou o
        # cache do provedor — crítico para custo real: a DeepSeek cobra
        # 50x menos por token de entrada em cache-hit do que em
        # cache-miss (ver quick_start/pricing na documentação dela), e
        # como esta arquitetura reenvia o histórico inteiro a cada turno,
        # boa parte do prefixo tende a repetir de um turno pro outro.
        uso = resposta.usage_metadata or {}
        tokens_de_cache_do_passo = uso.get("input_token_details", {}).get("cache_read", 0)
        tokens_de_entrada_acumulados += uso.get("input_tokens", 0)
        tokens_de_saida_acumulados += uso.get("output_tokens", 0)
        tokens_de_cache_acumulados += tokens_de_cache_do_passo
        logger.info(
            "uso_de_tokens_do_cerebro",
            id=id_para_log,
            passo=passo + 1,
            tokens_de_entrada=uso.get("input_tokens", 0),
            tokens_de_saida=uso.get("output_tokens", 0),
            tokens_de_entrada_em_cache=tokens_de_cache_do_passo,
        )

        if not resposta.tool_calls:
            logger.info(
                "loop_de_ferramentas_concluido",
                id=id_para_log,
                passos=passo + 1,
                total_tokens_de_entrada=tokens_de_entrada_acumulados,
                total_tokens_de_saida=tokens_de_saida_acumulados,
                total_tokens_de_entrada_em_cache=tokens_de_cache_acumulados,
            )
            return resposta.content

        if any(chamada["name"] in ferramentas_terminais for chamada in resposta.tool_calls):
            logger.info(
                "loop_de_ferramentas_encerrado_por_ferramenta_terminal",
                id=id_para_log,
                passos=passo + 1,
                total_tokens_de_entrada=tokens_de_entrada_acumulados,
                total_tokens_de_saida=tokens_de_saida_acumulados,
                total_tokens_de_entrada_em_cache=tokens_de_cache_acumulados,
            )
            return None

        mensagens.append(resposta)
        for chamada in resposta.tool_calls:
            ferramenta = ferramentas_por_nome.get(chamada["name"])
            resultado_da_ferramenta = (
                await ferramenta.ainvoke(chamada["args"])
                if ferramenta is not None
                else f"Ferramenta '{chamada['name']}' não está disponível agora."
            )
            mensagens.append(ToolMessage(content=resultado_da_ferramenta, tool_call_id=chamada["id"]))

        if resposta.content and any(chamada["name"] in ferramentas_de_fechamento for chamada in resposta.tool_calls):
            logger.info(
                "loop_de_ferramentas_concluido_por_ferramenta_de_fechamento",
                id=id_para_log,
                passos=passo + 1,
                total_tokens_de_entrada=tokens_de_entrada_acumulados,
                total_tokens_de_saida=tokens_de_saida_acumulados,
                total_tokens_de_entrada_em_cache=tokens_de_cache_acumulados,
            )
            return resposta.content

    logger.warning(
        "loop_de_ferramentas_excedeu_o_teto_de_passos",
        id=id_para_log,
        total_tokens_de_entrada=tokens_de_entrada_acumulados,
        total_tokens_de_saida=tokens_de_saida_acumulados,
        total_tokens_de_entrada_em_cache=tokens_de_cache_acumulados,
    )
    return ""


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define rodar_loop_de_ferramentas(), o mecanismo genérico de
# "pergunte ao modelo, execute a ferramenta pedida, repita" reaproveitado
# tanto pela conversa reativa quanto pela varredura periódica de atendimentos.
# Não sabe nada sobre WhatsApp, atendimentos ou desfechos — só orquestra a troca
# de mensagens entre o modelo e as ferramentas que recebe como parâmetro.
# O parâmetro opcional `ferramentas_terminais` permite marcar ferramentas de
# "sinal de parada" (como "nao_responder") que encerram o turno na hora,
# sem o passo extra de pedir uma resposta final de texto. O parâmetro
# opcional `ferramentas_de_fechamento` marca ferramentas de AÇÃO (como
# marcar_como_resolvido/encaminhar_para_setor) cujo texto, quando vem
# JUNTO na mesma resposta que as chama, já é a resposta final — evita
# descartar a resposta de verdade do modelo e trocá-la por um fechamento
# genérico sem conteúdo no passo seguinte.
# ==============================================================================
