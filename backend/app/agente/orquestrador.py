# ==============================================================================
# ARQUIVO: agente/orquestrador.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo é a "cola" entre três partes que, até aqui, foram
# construídas separadamente: o banco de dados (atendimentos, conversas,
# mensagens), o grafo de IA do LangGraph (agente/grafo.py) e o envio real
# de mensagens pela WhatsApp Cloud API (integracoes_externas/whatsapp.py).
#
# A função principal, processar_mensagem_recebida, é chamada de forma
# ASSÍNCRONA por uma tarefa do Celery (ver app/tarefas/tarefas_conversa.py)
# sempre que uma nova mensagem de um cliente é gravada no banco (o
# atendimento em si já foi criado, se necessário, pelo webhook — ver
# rotas/whatsapp_webhook.py). Ela:
#
#   1. Carrega o contexto necessário (atendimento, empresa, configuração, histórico)
#   2. Roda o grafo do agente, passando também os objetos reais (atendimento,
#      empresa, configuração, credenciais do WhatsApp, sessão do banco) —
#      dentro do turno, o próprio modelo decide E EXECUTA a ação que julgar
#      apropriada (ver agente/nos.py e agente/ferramentas.py): consultar a
#      Base de Conhecimento, encaminhar para um setor humano (o WhatsApp
#      real já sai na hora, com o texto que o próprio modelo escreveu), ou
#      marcar como resolvido
#   3. Grava a resposta do agente como uma nova Mensagem
#   4. Envia a resposta de fato pelo WhatsApp, para o cliente
#   5. Atualiza o status do atendimento no funil
#
# Diferente dos outros dois projetos da linhagem, este arquivo NÃO tem
# nenhuma função de "abordagem"/"follow-up" — este agente é receptivo, não
# existe primeiro contato iniciado pela plataforma (ver
# Informacoes/Arquitetura.md, seção 2). A única mensagem que a empresa
# inicia por conta própria é o reengajamento por silêncio (ver
# enviar_reengajamento_por_silencio, mais abaixo), quando um atendimento em
# aberto fica sem resposta do cliente.
# ==============================================================================

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agente.estados import EstadoConversa, PerfilDaEmpresa
from app.agente.ferramentas import ContextoDoTurno, RodadaDoTurno, enviar_notificacao_ao_setor
from app.agente.grafo import grafo_do_agente
from app.agente.guardrails import detectar_tentativa_de_manipulacao_do_atendimento
from app.integracoes_externas.meta_templates import TEXTO_PADRAO_DO_TEMPLATE_DE_REENGAJAMENTO
from app.integracoes_externas.whatsapp import (
    enviar_mensagem_de_template,
    enviar_mensagem_de_texto,
    normalizar_numero_brasileiro,
)
from app.modelos.configuracao_agente import ConfiguracaoAgente
from app.modelos.conversa import Conversa, Mensagem, RemetenteMensagem, TipoConteudoMensagem
from app.modelos.atendimento import Atendimento, StatusAtendimento
from app.modelos.integracao import IntegracaoWhatsApp
from app.modelos.setor import Setor
from app.tempo_real import publicar_evento_de_conversa

logger = structlog.get_logger(__name__)

# Mapa entre o nome interno de cada desfecho (usado no grafo) e o texto
# humano que aparece no histórico da conversa quando ele é acionado.
NOMES_DOS_DESFECHOS = {
    "encaminhado": "Encaminhado para um setor humano",
    "resolvido": "Resolvido com a Base de Conhecimento",
}


def _montar_perfil_da_empresa(sessao: Session, configuracao: ConfiguracaoAgente) -> PerfilDaEmpresa:
    """
    Transforma as colunas da tabela ConfiguracaoAgente (mais os setores
    cadastrados, consultados aqui) em um resumo de texto para o prompt da
    IA. Diferente dos outros dois projetos, não há "desfecho único" — os
    nomes dos setores disponíveis é que entram no perfil, para o modelo
    escolher um nome válido de primeira (o guardrail confere de qualquer
    jeito, ver agente/guardrails_de_atendimento.py).
    """
    nomes_dos_setores = list(
        sessao.scalars(select(Setor.nome).where(Setor.id_empresa == configuracao.id_empresa))
    )

    return PerfilDaEmpresa(
        nome_do_agente=configuracao.nome_do_agente,
        contexto_da_empresa=configuracao.contexto_da_empresa,
        roteiro_conversa=configuracao.roteiro_conversa,
        responder_apenas_com_base_no_conhecimento=configuracao.responder_apenas_com_base_no_conhecimento,
        mensagem_fora_do_escopo=configuracao.mensagem_fora_do_escopo,
        nomes_dos_setores=nomes_dos_setores,
    )


def _montar_historico(conversa: Conversa, excluindo_id_mensagem: int) -> list[dict]:
    """Converte as mensagens já salvas da conversa para o formato simples esperado pelo grafo."""
    historico = []
    for mensagem in conversa.mensagens:
        if mensagem.id == excluindo_id_mensagem:
            continue
        papel = "cliente" if mensagem.remetente == RemetenteMensagem.CLIENTE else "agente"
        historico.append({"papel": papel, "conteudo": mensagem.conteudo})
    return historico


async def processar_mensagem_recebida(sessao: Session, id_mensagem_recebida: int) -> None:
    """
    Função principal do orquestrador: recebe o ID de uma Mensagem já salva
    no banco (remetente = cliente) e conduz todo o processamento de
    resposta, do carregamento de contexto até o envio real pelo WhatsApp.
    """
    mensagem_recebida = sessao.get(Mensagem, id_mensagem_recebida)
    if mensagem_recebida is None:
        logger.warning("mensagem_nao_encontrada", id_mensagem=id_mensagem_recebida)
        return

    conversa = mensagem_recebida.conversa
    atendimento = conversa.atendimento
    empresa = atendimento.empresa
    configuracao = empresa.configuracao_agente

    # SILÊNCIO DEFINITIVO: este atendimento já foi reencaminhado UMA VEZ
    # para o setor humano depois do encaminhamento original — a partir
    # daqui, nunca mais chamamos a IA para ele, mesmo que escreva de novo.
    # A mensagem já foi salva no banco pelo webhook (preserva o
    # histórico), só não é processada — custo zero, garantido em código.
    if atendimento.encaminhamento_definitivo:
        atendimento.ultima_atividade_em = datetime.now(timezone.utc)
        sessao.commit()
        logger.info("mensagem_ignorada_apos_encaminhamento_definitivo", id_atendimento=atendimento.id)
        return

    # O cliente acabou de escrever — se ele tinha recebido um reengajamento
    # por silêncio antes, esse reengajamento já cumpriu seu papel único
    # (disparo único NA VIDA do atendimento, não por episódio de silêncio)
    # — a flag NÃO é resetada aqui de propósito.

    atendimento_ja_estava_encaminhado = atendimento.status == StatusAtendimento.ENCAMINHADO

    # Guardrail de ENTRADA (ver agente/guardrails.py): verifica se esta
    # mensagem contém um sinal de tentativa de manipulação do agente — só
    # para mensagens de texto puro, já que é o vetor real desse tipo de
    # ataque.
    if not atendimento.houve_tentativa_de_manipulacao and mensagem_recebida.tipo_conteudo == TipoConteudoMensagem.TEXTO:
        padrao_detectado = detectar_tentativa_de_manipulacao_do_atendimento(mensagem_recebida.conteudo)
        if padrao_detectado:
            atendimento.houve_tentativa_de_manipulacao = True
            logger.warning("tentativa_de_manipulacao_detectada", id_atendimento=atendimento.id, padrao_detectado=padrao_detectado)

    integracao_whatsapp = sessao.scalar(
        select(IntegracaoWhatsApp).where(IntegracaoWhatsApp.id_empresa == empresa.id)
    )
    if integracao_whatsapp is None:
        logger.error("integracao_whatsapp_ausente", id_empresa=empresa.id)
        return

    estado_inicial: EstadoConversa = {
        "id_empresa": empresa.id,
        "id_atendimento": atendimento.id,
        "id_conversa": conversa.id,
        "perfil_da_empresa": _montar_perfil_da_empresa(sessao, configuracao),
        "historico_mensagens": _montar_historico(conversa, excluindo_id_mensagem=mensagem_recebida.id),
        "status_atual_atendimento": atendimento.status.value,
        "tipo_mensagem_recebida": mensagem_recebida.tipo_conteudo.value,  # type: ignore[typeddict-item]
        "conteudo_bruto_recebido": mensagem_recebida.conteudo,
        "id_midia_whatsapp": mensagem_recebida.id_midia_whatsapp,
        "mime_type_da_midia": mensagem_recebida.mime_type_da_midia,
        "nome_do_arquivo_da_midia": mensagem_recebida.nome_do_arquivo_da_midia,
        "mensagens_livres_ja_enviadas": atendimento.mensagens_livres_desde_ultimo_template,
        # Objetos reais (ver introdução de agente/estados.py): permitem que
        # as ferramentas de ação (agente/ferramentas.py) executem o
        # encaminhamento de verdade durante o próprio turno.
        "atendimento": atendimento,
        "empresa": empresa,
        "configuracao_agente": configuracao,
        "integracao_whatsapp": integracao_whatsapp,
        "sessao": sessao,
    }

    resultado = await grafo_do_agente.ainvoke(estado_inicial)

    # Persiste o conteúdo REAL interpretado da mídia (transcrição de
    # áudio, descrição de imagem/vídeo, texto extraído de PDF/Word/txt) de
    # volta na mensagem já salva — sem isso, o histórico reenviado a cada
    # turno futuro (_montar_historico, acima) só veria o placeholder
    # genérico gravado pelo webhook. Não afeta mensagem de texto puro.
    if mensagem_recebida.tipo_conteudo != TipoConteudoMensagem.TEXTO:
        texto_interpretado = resultado.get("mensagem_recebida_em_texto")
        if texto_interpretado:
            mensagem_recebida.conteudo = texto_interpretado

    # resposta_para_envio == None é SILÊNCIO PROPOSITAL: o modelo decidiu
    # que esta mensagem (uma cortesia repetida) não precisa de resposta.
    if resultado.get("resposta_para_envio") is None:
        atendimento.ultima_atividade_em = datetime.now(timezone.utc)
        sessao.commit()
        logger.info("mensagem_processada_sem_resposta", id_atendimento=atendimento.id)
        return

    # --- Grava a resposta do agente como uma nova mensagem da conversa ---
    mensagem_do_agente = Mensagem(
        id_conversa=conversa.id,
        remetente=RemetenteMensagem.AGENTE_IA,
        tipo_conteudo=TipoConteudoMensagem.TEXTO,
        conteudo=resultado["resposta_para_envio"],
    )
    sessao.add(mensagem_do_agente)

    # O status do atendimento (EM_ATENDIMENTO/ENCAMINHADO/RESOLVIDO) já foi
    # atualizado DIRETAMENTE pela ferramenta que o modelo chamou (ver
    # agente/ferramentas.py) — aqui só resta registrar a mensagem de
    # sistema que marca o desfecho no histórico da conversa.
    texto_para_envio = resultado["resposta_para_envio"]

    desfecho = resultado.get("desfecho_acionado")
    if desfecho == "encaminhado":
        # Se o atendimento JÁ estava encaminhado antes deste turno, isso é
        # o REENCAMINHAMENTO — o cliente voltou a escrever depois de já ter
        # sido passado adiante, trazendo algo novo e relevante (ver
        # agente/ferramentas.py:montar_ferramentas_de_reengajamento).
        # Reencaminhamento só pode acontecer UMA VEZ por conversa: assim
        # que acontece, marcamos Atendimento.encaminhamento_definitivo, o
        # que faz processar_mensagem_recebida ignorar qualquer mensagem
        # futura deste atendimento antes mesmo de chegar ao grafo (ver o
        # topo desta função) — silêncio definitivo, sem mais chamada de IA.
        eh_reencaminhamento = atendimento_ja_estava_encaminhado
        if eh_reencaminhamento:
            atendimento.encaminhamento_definitivo = True
        sessao.add(
            Mensagem(
                id_conversa=conversa.id,
                remetente=RemetenteMensagem.SISTEMA,
                tipo_conteudo=TipoConteudoMensagem.TEXTO,
                conteudo=(
                    "Reencaminhado para o setor humano (silêncio definitivo a partir daqui)"
                    if eh_reencaminhamento
                    else NOMES_DOS_DESFECHOS["encaminhado"]
                ),
            )
        )
    elif desfecho == "resolvido":
        sessao.add(
            Mensagem(
                id_conversa=conversa.id,
                remetente=RemetenteMensagem.SISTEMA,
                tipo_conteudo=TipoConteudoMensagem.TEXTO,
                conteudo=NOMES_DOS_DESFECHOS["resolvido"],
            )
        )

    # Conta esta resposta como mais uma das mensagens LIVRES do orçamento
    # pré-encaminhamento — só enquanto o atendimento ainda não estava
    # encaminhado ANTES deste turno.
    if not atendimento_ja_estava_encaminhado:
        atendimento.mensagens_livres_desde_ultimo_template += 1

    atendimento.ultima_atividade_em = datetime.now(timezone.utc)
    sessao.commit()

    # --- Envia a resposta de fato pelo WhatsApp ---
    # Se o desfecho foi "encaminhado", o WhatsApp real para o setor já foi
    # enviado pela própria ferramenta, DENTRO do turno que acabou de rodar
    # (ver agente/ferramentas.py) — não há nada a executar aqui além de
    # mandar a resposta combinada ao cliente.
    await enviar_mensagem_de_texto(
        id_numero_telefone=integracao_whatsapp.id_numero_telefone_meta,
        token_de_acesso=integracao_whatsapp.token_de_acesso,
        numero_destino=normalizar_numero_brasileiro(atendimento.whatsapp),
        texto=texto_para_envio,
    )

    # Avisa, em tempo real, quem estiver com a tela de Conversas aberta.
    await publicar_evento_de_conversa(
        empresa.id,
        {"tipo": "resposta_do_agente", "id_conversa": conversa.id, "id_atendimento": atendimento.id},
    )

    logger.info(
        "mensagem_processada",
        id_atendimento=atendimento.id,
        novo_status=atendimento.status.value,
        desfecho_acionado=desfecho,
    )


async def enviar_fallback_apos_falha_permanente(sessao: Session, id_mensagem_recebida: int) -> None:
    """
    Último recurso: chamado só quando processar_mensagem_recebida falhou em
    TODAS as tentativas de retry do Celery (ver tarefas/tarefas_conversa.py).

    Faz DUAS coisas, cada uma isolada na própria falha:
      1. Manda uma mensagem de texto simples pro CLIENTE, direto pela
         WhatsApp Cloud API, SEM passar pela IA.
      2. Notifica um SETOR humano, best-effort (usa o primeiro setor
         cadastrado pela empresa — sem como saber qual seria o certo sem o
         modelo decidir, melhor avisar alguém do que ninguém).

    Nunca levanta exceção: se as duas também falharem, só loga o erro.
    """
    mensagem_recebida = sessao.get(Mensagem, id_mensagem_recebida)
    if mensagem_recebida is None:
        return

    conversa = mensagem_recebida.conversa
    atendimento = conversa.atendimento
    empresa = atendimento.empresa
    configuracao = empresa.configuracao_agente
    integracao_whatsapp = sessao.scalar(
        select(IntegracaoWhatsApp).where(IntegracaoWhatsApp.id_empresa == empresa.id)
    )
    if integracao_whatsapp is None:
        return

    if atendimento.whatsapp:
        try:
            texto_de_fallback = (
                "Desculpe a demora! Tivemos uma instabilidade técnica agora e não consegui processar "
                "sua última mensagem direito. Já ficou registrado por aqui e volto a te responder em "
                "breve — pode escrever de novo se quiser."
            )
            await enviar_mensagem_de_texto(
                id_numero_telefone=integracao_whatsapp.id_numero_telefone_meta,
                token_de_acesso=integracao_whatsapp.token_de_acesso,
                numero_destino=normalizar_numero_brasileiro(atendimento.whatsapp),
                texto=texto_de_fallback,
            )
            sessao.add(
                Mensagem(
                    id_conversa=conversa.id,
                    remetente=RemetenteMensagem.AGENTE_IA,
                    tipo_conteudo=TipoConteudoMensagem.TEXTO,
                    conteudo=texto_de_fallback,
                )
            )
            sessao.commit()
            logger.error("fallback_apos_falha_permanente_enviado_ao_cliente", id_atendimento=atendimento.id, id_mensagem=id_mensagem_recebida)
        except Exception as erro:  # noqa: BLE001 — último recurso: se isso falhar, só loga, tenta notificar o humano do mesmo jeito
            sessao.rollback()
            logger.error("falha_ao_enviar_fallback_ao_cliente", id_mensagem=id_mensagem_recebida, erro=str(erro))

    if configuracao is not None:
        try:
            setor = sessao.scalar(select(Setor).where(Setor.id_empresa == empresa.id).order_by(Setor.id))
            if setor is not None:
                contexto = ContextoDoTurno(
                    perfil=_montar_perfil_da_empresa(sessao, configuracao),
                    rodada=RodadaDoTurno(),
                    atendimento=atendimento,
                    empresa=empresa,
                    configuracao=configuracao,
                    integracao_whatsapp=integracao_whatsapp,
                    sessao=sessao,
                )
                await enviar_notificacao_ao_setor(
                    contexto,
                    setor.contato_telefone,
                    f"⚠️ Falha técnica automática: não consegui processar a última mensagem de {atendimento.nome} "
                    f"depois de várias tentativas. Dá uma olhada na conversa direto pelo WhatsApp — pode "
                    "precisar de um retorno manual.",
                )
                logger.error(
                    "fallback_apos_falha_permanente_notificou_setor",
                    id_atendimento=atendimento.id,
                    id_mensagem=id_mensagem_recebida,
                    setor=setor.nome,
                )
        except Exception as erro:  # noqa: BLE001 — último recurso: se até isso falhar, só loga, nunca propaga
            logger.error("falha_ao_notificar_setor_apos_falha_permanente", id_mensagem=id_mensagem_recebida, erro=str(erro))


async def enviar_reengajamento_por_silencio(sessao: Session, atendimento: Atendimento, empresa_id: int) -> None:
    """
    Retoma contato com um atendimento EM_ATENDIMENTO que ficou 3+ dias sem
    responder à última mensagem do agente. A janela de atendimento de 24h
    está fechada nesse caso, então o envio obrigatoriamente usa um template
    pré-aprovado.

    Chamada pela ferramenta "reengajar_atendimento_silencioso" que o agente
    usa durante a varredura periódica (ver agente/ferramentas_monitoramento.py)
    — o próprio modelo decide QUANDO chamar; esta função só executa o
    envio de verdade. NÃO mexe no status do atendimento (continua
    EM_ATENDIMENTO) — só marca reengajamento_por_silencio_enviado, que
    NUNCA mais é resetada: este atendimento já usou sua ÚNICA chance de
    reengajamento por silêncio, pra sempre.
    """
    configuracao = sessao.scalar(select(ConfiguracaoAgente).where(ConfiguracaoAgente.id_empresa == empresa_id))
    integracao_whatsapp = sessao.scalar(
        select(IntegracaoWhatsApp).where(IntegracaoWhatsApp.id_empresa == empresa_id)
    )
    if configuracao is None or integracao_whatsapp is None or not atendimento.whatsapp:
        logger.warning("reengajamento_nao_enviado_configuracao_incompleta", id_atendimento=atendimento.id)
        return

    conversa = next(iter(atendimento.conversas), None)
    if conversa is None:
        logger.warning("reengajamento_sem_conversa_existente", id_atendimento=atendimento.id)
        return

    nome_da_empresa = atendimento.empresa.nome_fantasia
    parametros = [atendimento.nome, configuracao.nome_do_agente, nome_da_empresa]

    resultado_envio = await enviar_mensagem_de_template(
        id_numero_telefone=integracao_whatsapp.id_numero_telefone_meta,
        token_de_acesso=integracao_whatsapp.token_de_acesso,
        numero_destino=normalizar_numero_brasileiro(atendimento.whatsapp),
        nome_do_template=configuracao.nome_do_template_reengajamento,
        idioma="pt_BR",
        parametros=parametros,
    )

    # Grava o texto REAL enviado (não um placeholder) — esta Mensagem
    # entra no histórico que _montar_historico() monta pro modelo no
    # próximo turno.
    texto_preenchido = TEXTO_PADRAO_DO_TEMPLATE_DE_REENGAJAMENTO
    for indice, valor in enumerate(parametros, start=1):
        texto_preenchido = texto_preenchido.replace(f"{{{{{indice}}}}}", valor)

    sessao.add(
        Mensagem(
            id_conversa=conversa.id,
            remetente=RemetenteMensagem.AGENTE_IA,
            tipo_conteudo=TipoConteudoMensagem.TEXTO,
            conteudo=texto_preenchido,
            id_mensagem_whatsapp=resultado_envio.get("messages", [{}])[0].get("id"),
        )
    )

    atendimento.reengajamento_por_silencio_enviado = True
    # Concede 1 crédito extra de mensagem livre (ao invés de resetar pra 0
    # — o orçamento continua de onde parou, já que o atendimento já vinha
    # numa conversa de verdade).
    atendimento.mensagens_livres_desde_ultimo_template = max(0, atendimento.mensagens_livres_desde_ultimo_template - 1)
    atendimento.ultima_atividade_em = datetime.now(timezone.utc)
    sessao.commit()

    await publicar_evento_de_conversa(
        empresa_id,
        {"tipo": "reengajamento_enviado", "id_conversa": conversa.id, "id_atendimento": atendimento.id},
    )

    logger.info("reengajamento_por_silencio_enviado", id_atendimento=atendimento.id)


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo conecta banco de dados, grafo de IA e envio de WhatsApp em
# um único fluxo assíncrono: processar_mensagem_recebida primeiro checa o
# SILÊNCIO DEFINITIVO (se marcado, ignora a mensagem sem gastar nenhuma
# chamada de IA), monta o contexto da conversa (incluindo os setores
# cadastrados e a sessão do banco, que as ferramentas deste domínio
# precisam — ver agente/estados.py), roda o grafo do agente, grava e envia
# a resposta ao cliente, e atualiza o status do atendimento — o
# encaminhamento para um setor humano já aconteceu de verdade DENTRO do
# grafo, executado pela própria ferramenta que o modelo chamou. Diferente
# dos outros dois projetos da linhagem, não há nenhuma função de
# abordagem/follow-up: a única mensagem iniciada pela empresa é o
# reengajamento por silêncio (enviar_reengajamento_por_silencio), usada
# pela varredura periódica quando um atendimento em aberto fica sem
# resposta do cliente.
# ==============================================================================
