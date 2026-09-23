# ==============================================================================
# ARQUIVO: agente/grafo.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo monta o GRAFO do agente usando o LangGraph: liga os dois
# nós definidos em agente/nos.py em uma sequência (interpretar mídia ->
# executar o turno do agente) e "compila" esse desenho em um objeto pronto
# para ser executado a cada mensagem recebida.
#
# Antes de uma mudança de arquitetura, havia um terceiro nó
# ("decidir_desfecho") que lia um campo booleano decidido pelo modelo e
# escolhia a ação em Python. Esse nó foi removido: agora é o modelo quem
# decide E executa (chamando uma ferramenta de verdade) dentro do próprio
# nó "executar_turno_do_agente" — ver a introdução de agente/nos.py para o
# raciocínio completo por trás dessa mudança.
#
# Repare que este grafo NÃO usa um "checkpointer" (o mecanismo do
# LangGraph para lembrar automaticamente o estado entre execuções). Isso é
# proposital: o histórico completo da conversa já é a fonte da verdade no
# PostgreSQL (tabelas conversas/mensagens), então cada execução do grafo
# recebe o histórico inteiro como entrada e roda do zero ao fim. Isso evita
# ter "duas memórias" diferentes (uma no banco, outra escondida dentro do
# LangGraph) que poderiam ficar dessincronizadas.
# ==============================================================================

from langgraph.graph import END, StateGraph

from app.agente.estados import EstadoConversa
from app.agente.nos import executar_turno_do_agente, interpretar_midia


def montar_grafo_do_agente():
    """
    Constrói e compila o grafo de estados do Agente Comercial SDR.
    Chamado uma vez, quando a aplicação sobe (ver app/main.py), e
    reutilizado em todas as mensagens processadas depois.
    """
    grafo = StateGraph(EstadoConversa)

    grafo.add_node("interpretar_midia", interpretar_midia)
    grafo.add_node("executar_turno_do_agente", executar_turno_do_agente)

    grafo.set_entry_point("interpretar_midia")
    grafo.add_edge("interpretar_midia", "executar_turno_do_agente")
    grafo.add_edge("executar_turno_do_agente", END)

    return grafo.compile()


# Instância única do grafo compilado, importada pelo restante do backend
# (ver app/rotas/whatsapp_webhook.py).
grafo_do_agente = montar_grafo_do_agente()


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define montar_grafo_do_agente(), que conecta os dois nós do
# agente em sequência e devolve um grafo compilado e pronto para uso. A
# variável grafo_do_agente, no fim do arquivo, é a instância que o resto do
# sistema chama (grafo_do_agente.ainvoke(estado_inicial)) para processar
# cada mensagem recebida de um atendimento.
# ==============================================================================
