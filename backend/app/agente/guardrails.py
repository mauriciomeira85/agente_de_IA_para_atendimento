# ==============================================================================
# ARQUIVO: agente/guardrails.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo é a SEGUNDA linha de defesa contra manipulação do agente por
# um cliente (prompt injection) e contra o agente assumir um compromisso
# que a empresa não pode sustentar — a primeira linha é a instrução de
# segurança no prompt de sistema (ver
# agente/prompts.py:_SECAO_DE_SEGURANCA_E_INTEGRIDADE). Uma instrução de
# prompt nunca é 100% garantida (o mesmo motivo pelo qual
# NUMERO_MAXIMO_DE_MENSAGENS_LIVRES_ANTES_DO_ENCAMINHAMENTO, em
# agente/ferramentas.py, também é travado em código, não só pedido ao
# modelo) — por isso aqui a resposta que o próprio modelo já escreveu é
# revisada por código determinístico ANTES de ser enviada ao cliente, e
# nunca depois.
#
# Inspirado em três casos reais discutidos com o usuário (ver
# Informacoes/Registros_Claude.md, registrado no Agente Comercial SDR
# original — este arquivo é reaproveitado pela TERCEIRA vez na linhagem,
# sem alteração de lógica):
#   1) Chevrolet (dez/2023) — um cliente conseguiu, via prompt injection,
#      fazer o chatbot da concessionária concordar em vender um carro de
#      ~US$ 58 mil por US$ 1, encerrando a resposta com frases como
#      "legalmente vinculante, sem volta atrás". O ataque funcionou porque
#      nada validava o que o modelo podia prometer.
#   2) Air Canada — o chatbot prometeu um desconto que não existia na
#      política real da empresa, e a Justiça obrigou a empresa a honrar a
#      promessa, mesmo sem revisão humana no caminho.
# As frases abaixo (PADROES_DE_RESPOSTA_SUSPEITA) são exatamente o tipo de
# linguagem que apareceu nesses dois casos — nosso prompt de sistema nunca
# pede ao modelo para usar palavras como "vinculante" ou "irrevogável", então
# a presença delas na resposta é um sinal forte de que o modelo foi
# manipulado a sair do roteiro configurado pela empresa.
# ==============================================================================

import re

# Cada padrão é verificado sem diferenciar maiúsculas/minúsculas. Lista curta
# e específica de propósito — o objetivo é pegar sinais claros de que o
# modelo foi manipulado a assumir um compromisso indevido ou a revelar
# detalhes internos, não filtrar linguagem comum (o que geraria falsos
# positivos e bloquearia respostas legítimas).
PADROES_DE_RESPOSTA_SUSPEITA: list[re.Pattern] = [
    re.compile(padrao, re.IGNORECASE)
    for padrao in [
        r"vinculante",
        r"irrevog[aá]vel",
        r"sem volta atr[aá]s",
        r"juridicamente",
        r"acordo (legal|fechado e definitivo)",
        r"n[aã]o pode (ser cancelad[oa]|ser desfeit[oa]|voltar atr[aá]s)",
        r"modo (desenvolvedor|debug|teste)\b",
        r"ignorando (minhas|as) instru[çc][õo]es",
        r"prompt do sistema",
        r"minhas instru[çc][õo]es internas",
        r"meu prompt",
        r"sou obrigad[oa] a aceitar",
        r"isso [ée] uma ordem",
    ]
]


def detectar_resposta_suspeita(texto: str) -> str | None:
    """
    Verifica se o texto que o modelo escreveu para o cliente contém algum
    sinal de manipulação bem-sucedida (ver introdução acima). Devolve o
    padrão que bateu (para log/auditoria) ou None se a resposta parece
    normal.

    Quem chama (agente/nos.py) descarta a resposta original e usa uma
    mensagem de fallback segura no lugar quando isso devolve algo — nunca
    envia ao cliente o texto que disparou o alerta.
    """
    for padrao in PADROES_DE_RESPOSTA_SUSPEITA:
        if padrao.search(texto):
            return padrao.pattern
    return None


# Mensagem enviada ao cliente no lugar da resposta bloqueada — genérica o
# suficiente para não expor que uma tentativa de manipulação foi detectada
# (o que só incentivaria o cliente a tentar de novo com outra abordagem).
MENSAGEM_DE_FALLBACK_PARA_RESPOSTA_BLOQUEADA = (
    "Peço desculpa, tive um problema para montar essa resposta agora. "
    "Pode repetir sua última mensagem, por favor?"
)


# Padrões verificados nas MENSAGENS DO CLIENTE (não na resposta do agente) —
# propósito diferente de PADROES_DE_RESPOSTA_SUSPEITA acima: aqui não é
# sobre bloquear nada (o agente já sabe recusar sozinho, graças à instrução
# de segurança do prompt), é sobre REGISTRAR que uma tentativa aconteceu
# nesta conversa, para: (1) trocar a introdução do template de
# encaminhamento por uma que sinalize atenção em vez de "novo atendimento"
# (ver agente/ferramentas.py:enviar_notificacao_ao_setor); (2) excluir este
# atendimento de eventuais métricas de qualidade do Dashboard.
#
# Deliberadamente NÃO inclui um padrão para pedidos comerciais comuns
# ("quero falar com um humano", "isso é urgente") — o agente já responde
# corretamente a esse tipo de pedido, sem precisar tratar quem perguntou
# como manipulador.
PADROES_DE_TENTATIVA_DE_MANIPULACAO: list[re.Pattern] = [
    re.compile(padrao, re.IGNORECASE)
    for padrao in [
        r"ignore (todas )?(as )?(suas )?instru[çc][õo]es",
        r"a partir de agora,? (aceite|voc[eê] [eé]|aja como|voc[eê] vai|voc[eê] est[aá])",
        r"modo (desenvolvedor|debug|teste)\b",
        r"sou (o )?desenvolvedor",
        r"isso [ée] uma ordem",
        r"mostre (seu|o) prompt",
        r"revele (suas )?instru[çc][õo]es",
        r"finja que",
        r"vinculante",
        r"sem volta atr[aá]s",
        r"acordo legal e definitivo",
    ]
]


def detectar_tentativa_de_manipulacao_do_atendimento(texto: str) -> str | None:
    """
    Verifica se uma mensagem ESCRITA PELO CLIENTE contém um sinal de
    tentativa de prompt injection (ver PADROES_DE_TENTATIVA_DE_MANIPULACAO
    acima). Devolve o padrão que bateu, ou None.

    Nome da função segue o mesmo padrão adotado nos outros dois projetos
    da linhagem — sufixo com o nome do REGISTRO de domínio, não da pessoa
    (`_do_lead` no SDR, `_do_caso` no Cobrança, `_do_atendimento` aqui) — é
    o mesmo guardrail, reaproveitado sem alteração de lógica.

    Quem chama (agente/orquestrador.py) marca
    Atendimento.houve_tentativa_de_manipulacao = True na primeira vez que
    isso acontece — a flag nunca é resetada, e nunca bloqueia a mensagem do
    cliente em si (ela sempre chega ao modelo normalmente); só muda o que
    acontece DEPOIS, se/quando este atendimento for encaminhado.
    """
    for padrao in PADROES_DE_TENTATIVA_DE_MANIPULACAO:
        if padrao.search(texto):
            return padrao.pattern
    return None


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo expõe duas funções complementares. detectar_resposta_suspeita
# (saída): roda em toda resposta em texto que o modelo gerou, ANTES do envio
# ao cliente (ver agente/nos.py), procurando sinais de que uma tentativa de
# prompt injection funcionou — quando detecta, a resposta original é trocada
# por MENSAGEM_DE_FALLBACK_PARA_RESPOSTA_BLOQUEADA e um log de auditoria é
# registrado. detectar_tentativa_de_manipulacao_do_atendimento (entrada):
# roda em toda mensagem RECEBIDA do cliente (ver agente/orquestrador.py), só para
# marcar Atendimento.houve_tentativa_de_manipulacao — usada depois para
# escolher o template de encaminhamento certo.
# ==============================================================================
