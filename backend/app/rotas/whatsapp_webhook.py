# ==============================================================================
# ARQUIVO: rotas/whatsapp_webhook.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Esta é a "porta de entrada" de tudo que acontece no WhatsApp: é aqui que
# o backend recebe os eventos que a Meta manda (mensagens novas e
# atualizações de status como "entregue"/"lida"). Esses eventos NÃO vêm
# direto da Meta — eles passam antes por um Worker no Cloudflare (pasta
# infra/cloudflare-webhook/), que confere a assinatura oficial da Meta e só
# então repassa o conteúdo já validado para cá, com um segredo próprio
# (BACKEND_WEBHOOK_SECRET) provando que a chamada realmente veio do Worker
# e não de qualquer lugar da internet.
#
# Ponto-chave de arquitetura multi-tenant: como a plataforma atende várias
# empresas ao mesmo tempo, TODAS elas recebem eventos por este MESMO
# endpoint. É o campo "phone_number_id" que vem dentro do payload da Meta
# que diz a qual empresa aquela mensagem pertence.
#
# Este é o ÚNICO lugar onde um Atendimento nasce (ver
# _localizar_ou_criar_atendimento_e_conversa abaixo) — diferente dos outros
# dois projetos da linhagem, não existe rota de criação manual nem
# importação (este agente é 100% receptivo, ver Informacoes/Arquitetura.md,
# seção 2): a primeira mensagem de um número novo JÁ é o que cria o
# atendimento automaticamente.
#
# Este endpoint responde em milissegundos: ele só grava a mensagem
# recebida no banco (com proteção contra duplicidade) e delega o trabalho
# pesado — pensar e responder — para uma tarefa do Celery rodando em
# segundo plano (ver app/tarefas/tarefas_conversa.py).
# ==============================================================================

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.banco_dados import obter_sessao
from app.configuracoes import obter_configuracoes
from app.integracoes_externas.whatsapp import extrair_mensagens_do_payload, extrair_status_do_payload
from app.modelos.atendimento import Atendimento, StatusAtendimento
from app.modelos.conversa import Conversa, Mensagem, RemetenteMensagem, StatusEntregaMensagem, TipoConteudoMensagem
from app.modelos.integracao import IntegracaoWhatsApp
from app.tarefas.tarefas_conversa import processar_mensagem_em_segundo_plano
from app.tempo_real import publicar_evento_de_conversa

configuracoes = obter_configuracoes()
logger = structlog.get_logger(__name__)

roteador = APIRouter(prefix="/api/webhooks", tags=["Webhook WhatsApp"])

# Traduz o "type" que a Meta usa no payload para o vocabulário interno do
# projeto. "sticker" e "video" viram IMAGEM: um sticker é um webp com o
# mesmo formato de campos (id/mime_type) que uma imagem normal; um vídeo (é
# assim que a Meta entrega um GIF enviado pelo seletor nativo do WhatsApp)
# não tem entrada direta no modelo, então agente/nos.py:interpretar_midia
# extrai um frame dele antes de descrever — nos dois casos, o resultado
# final é uma descrição de imagem, então cai no mesmo tipo aqui.
MAPA_TIPO_DE_MENSAGEM = {
    "text": TipoConteudoMensagem.TEXTO,
    "audio": TipoConteudoMensagem.AUDIO,
    "image": TipoConteudoMensagem.IMAGEM,
    "sticker": TipoConteudoMensagem.IMAGEM,
    "video": TipoConteudoMensagem.IMAGEM,
    "document": TipoConteudoMensagem.DOCUMENTO,
}


def _validar_segredo_do_worker(authorization: str | None) -> None:
    """Confere se a chamada realmente veio do Worker do Cloudflare, e não de outra origem."""
    if not configuracoes.backend_webhook_secret:
        # Em ambiente de desenvolvimento local, sem o segredo configurado,
        # a checagem é pulada — mas isso NUNCA deve acontecer em produção
        # (ver README, seção "Antes de ir para produção").
        return
    esperado = f"Bearer {configuracoes.backend_webhook_secret}"
    if authorization != esperado:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Assinatura do Worker inválida.")


def _variacoes_de_numero_brasileiro(numero: str) -> list[str]:
    """
    Dois problemas reais de formato de número brasileiro precisam ser
    tratados ao comparar o "from" que a Meta manda com o que está salvo em
    Atendimento.whatsapp: (1) o "9" extra entre o DDD e o restante do
    número — a própria Meta é inconsistente sobre incluir ou não esse
    dígito no campo "from"; (2) o código do país "55", que a Meta SEMPRE
    inclui no "from". Sem tratar os dois ao mesmo tempo, o mesmo cliente
    viraria um atendimento novo na base a cada troca de mensagem. Por isso
    normalizamos para a forma "DDD + número" e geramos as quatro
    combinações possíveis (com/sem "9" × com/sem "55") em vez de uma
    igualdade exata.
    """
    sem_prefixo_do_pais = numero[2:] if numero.startswith("55") else numero
    if len(sem_prefixo_do_pais) == 11:  # DDD + 9 dígitos (tem o "9" extra)
        com_nove = sem_prefixo_do_pais
        sem_nove = sem_prefixo_do_pais[:2] + sem_prefixo_do_pais[3:]
    elif len(sem_prefixo_do_pais) == 10:  # DDD + 8 dígitos (sem o "9")
        sem_nove = sem_prefixo_do_pais
        com_nove = sem_prefixo_do_pais[:2] + "9" + sem_prefixo_do_pais[2:]
    else:
        com_nove = sem_nove = sem_prefixo_do_pais

    variacoes = {com_nove, sem_nove}
    variacoes |= {f"55{variacao}" for variacao in variacoes}
    return list(variacoes)


def _forma_canonica_do_numero_brasileiro(numero: str) -> str:
    """
    Devolve o número SEMPRE no formato "55" + DDD + 9 dígitos (com o 9º
    dígito do celular), mesmo quando o "from" que a Meta mandou veio sem
    ele (ver _variacoes_de_numero_brasileiro acima — mesmo quirk, dado na
    outra direção). Usada só na hora de CRIAR um atendimento novo, para
    salvar `Atendimento.whatsapp` sempre correto — bug real encontrado em
    teste: quando o "from" chegava sem o 9º dígito, o número era salvo
    assim mesmo, e toda resposta do agente para aquele atendimento
    tentava enviar para o número ERRADO (sem o 9), que a Meta rejeitava
    com "(#131030) Recipient phone number not in allowed list" — o
    destinatário parecia "não permitido", mas o problema real era o
    número salvo estar errado, não a lista de permissões em si.
    """
    sem_prefixo_do_pais = numero[2:] if numero.startswith("55") else numero
    if len(sem_prefixo_do_pais) == 10:  # DDD + 8 dígitos: celular sem o 9º dígito
        sem_prefixo_do_pais = f"{sem_prefixo_do_pais[:2]}9{sem_prefixo_do_pais[2:]}"
    return f"55{sem_prefixo_do_pais}"


def _localizar_ou_criar_atendimento_e_conversa(sessao: Session, id_empresa: int, numero_do_remetente: str) -> Conversa:
    """
    Encontra o atendimento correspondente ao número que escreveu (dentro
    daquela empresa) e a conversa em aberto com ele. Se o número nunca
    apareceu antes na base daquela empresa, cria um atendimento novo
    automaticamente — este é o ÚNICO jeito de um Atendimento nascer neste
    projeto (ver introdução acima): alguém escreveu para o WhatsApp da
    empresa pela primeira vez.
    """
    atendimento = sessao.scalar(
        select(Atendimento).where(
            Atendimento.id_empresa == id_empresa,
            Atendimento.whatsapp.in_(_variacoes_de_numero_brasileiro(numero_do_remetente)),
        )
    )
    if atendimento is None:
        numero_canonico = _forma_canonica_do_numero_brasileiro(numero_do_remetente)
        atendimento = Atendimento(
            id_empresa=id_empresa,
            nome=numero_canonico,
            whatsapp=numero_canonico,
            status=StatusAtendimento.RECEBIDO,
        )
        sessao.add(atendimento)
        sessao.flush()

    conversa = sessao.scalar(select(Conversa).where(Conversa.id_atendimento == atendimento.id))
    if conversa is None:
        conversa = Conversa(id_empresa=id_empresa, id_atendimento=atendimento.id)
        sessao.add(conversa)
        sessao.flush()

    # Salva a criação do atendimento/conversa em uma transação própria,
    # separada da gravação da mensagem em si — assim, se a mensagem for uma
    # duplicata (ver mais abaixo) e precisar de rollback, o atendimento e a
    # conversa que acabaram de ser criados não são desfeitos junto.
    sessao.commit()
    return conversa


@roteador.post("/whatsapp", status_code=status.HTTP_200_OK)
async def receber_evento_whatsapp(
    request: Request,
    sessao: Session = Depends(obter_sessao),
    authorization: str | None = Header(default=None),
) -> dict:
    """Recebe eventos de mensagem e de status da WhatsApp Cloud API, já validados pelo Worker do Cloudflare."""
    _validar_segredo_do_worker(authorization)
    payload = await request.json()

    # --- 1) Atualizações de status (mensagem entregue / lida / falhou) ---
    for evento in extrair_status_do_payload(payload):
        mensagem = sessao.scalar(
            select(Mensagem).where(Mensagem.id_mensagem_whatsapp == evento["id_mensagem_whatsapp"])
        )
        if mensagem is not None:
            try:
                mensagem.status_entrega = StatusEntregaMensagem(evento["status"])
            except ValueError:
                logger.warning("status_desconhecido", status=evento["status"])
        if evento["status"] == "failed" and evento["erros"]:
            logger.error(
                "mensagem_whatsapp_falhou",
                id_mensagem_whatsapp=evento["id_mensagem_whatsapp"],
                erros=evento["erros"],
                mensagem_rastreada=mensagem is not None,
            )
        else:
            logger.info(
                "status_de_entrega_whatsapp",
                id_mensagem_whatsapp=evento["id_mensagem_whatsapp"],
                status=evento["status"],
                mensagem_rastreada=mensagem is not None,
            )
    sessao.commit()

    # --- 2) Mensagens novas enviadas por um cliente ---
    for bruta in extrair_mensagens_do_payload(payload):
        integracao = sessao.scalar(
            select(IntegracaoWhatsApp).where(
                IntegracaoWhatsApp.id_numero_telefone_meta == bruta["id_numero_telefone_destino"]
            )
        )
        if integracao is None:
            logger.warning("numero_sem_empresa_vinculada", numero=bruta["id_numero_telefone_destino"])
            continue

        conversa = _localizar_ou_criar_atendimento_e_conversa(sessao, integracao.id_empresa, bruta["numero_do_remetente"])

        # Para mídia (imagem/áudio/documento), o "conteúdo" grava a legenda
        # (se o cliente escreveu uma) — o arquivo em si é baixado e
        # interpretado depois, dentro do turno do agente (ver
        # agente/nos.py:interpretar_midia), usando media_id/mime_type
        # guardados abaixo.
        nova_mensagem = Mensagem(
            id_conversa=conversa.id,
            remetente=RemetenteMensagem.CLIENTE,
            tipo_conteudo=MAPA_TIPO_DE_MENSAGEM.get(bruta["tipo"], TipoConteudoMensagem.TEXTO),
            conteudo=bruta["texto"] or bruta.get("legenda") or f"[mensagem do tipo '{bruta['tipo']}' recebida]",
            id_mensagem_whatsapp=bruta["id_mensagem_whatsapp"],
            id_midia_whatsapp=bruta.get("media_id"),
            mime_type_da_midia=bruta.get("mime_type"),
            nome_do_arquivo_da_midia=bruta.get("nome_do_arquivo"),
        )
        sessao.add(nova_mensagem)
        try:
            sessao.commit()
        except IntegrityError:
            # A restrição de unicidade em id_mensagem_whatsapp barrou a
            # gravação: esta mensagem já tinha sido processada antes (a
            # Meta reenviou o mesmo evento de webhook). Ignoramos com
            # segurança — é exatamente para isso que a deduplicação existe.
            sessao.rollback()
            logger.info("mensagem_duplicada_ignorada", id_mensagem_whatsapp=bruta["id_mensagem_whatsapp"])
            continue

        sessao.refresh(nova_mensagem)
        atendimento = conversa.atendimento
        # RECEBIDO -> EM_ATENDIMENTO: primeira mensagem do atendimento.
        # RESOLVIDO -> EM_ATENDIMENTO: o cliente escreveu de novo depois de
        # já ter sido marcado como resolvido — bug real encontrado em
        # teste: sem esta segunda condição, a coluna Status na Base de
        # Atendimentos e os cartões do Dashboard continuavam mostrando
        # "resolvido" mesmo com uma conversa ativa de novo, porque nada
        # reabria o status quando o cliente voltava a escrever. Não inclui
        # ENCAMINHADO de propósito: uma vez encaminhado, quem conduz é o
        # setor humano (ver agente/orquestrador.py, encaminhamento_definitivo).
        if atendimento.status in (StatusAtendimento.RECEBIDO, StatusAtendimento.RESOLVIDO):
            if atendimento.status == StatusAtendimento.RESOLVIDO:
                # Reabertura de verdade: conta pra alimentar a "Taxa de
                # reabertura" do Dashboard (ver rotas/painel.py) — e,
                # olhando à frente, pra cobrança por lead quando a
                # plataforma for comercializada (cada reabertura é um novo
                # ciclo de custo real: mensagens da Meta, tokens de
                # transcrição/modelo — ver Atendimento.numero_de_reaberturas)
                # — e zera o orçamento de mensagens livres, mesmo princípio
                # já usado no Agente Comercial SDR (lead.mensagens_livres_
                # desde_ultimo_template = 0 a cada novo template), só que
                # aqui o "novo ciclo" é a própria mensagem espontânea do
                # cliente (que já abre uma nova janela de atendimento no
                # WhatsApp, sem precisar de template) — sem este reset, um
                # cliente que reabre várias vezes acumula rumo ao teto de
                # mensagens da CONVERSA INTEIRA, e acaba sendo encaminhado
                # à força mesmo com cada reabertura tendo sido bem
                # resolvida sozinha — o oposto do objetivo de depender
                # menos de humano.
                atendimento.numero_de_reaberturas += 1
                atendimento.mensagens_livres_desde_ultimo_template = 0
            atendimento.status = StatusAtendimento.EM_ATENDIMENTO
        atendimento.ultima_atividade_em = datetime.now(timezone.utc)
        sessao.commit()

        # Avisa, em tempo real, quem estiver com a tela de Conversas
        # aberta (ver app/tempo_real.py e app/rotas/tempo_real.py).
        await publicar_evento_de_conversa(
            integracao.id_empresa,
            {"tipo": "mensagem_recebida", "id_conversa": conversa.id, "id_atendimento": atendimento.id},
        )

        # Delega o processamento da resposta (chamada à IA + envio) para o
        # Celery, em segundo plano — o webhook não espera por isso.
        processar_mensagem_em_segundo_plano.delay(nova_mensagem.id)

    return {"recebido": True}


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo recebe, valida e grava os eventos da WhatsApp Cloud API
# (mensagens novas e status de entrega) encaminhados pelo Worker do
# Cloudflare, identifica a qual empresa cada mensagem pertence (pelo
# phone_number_id), CRIA o Atendimento automaticamente na primeira
# mensagem de um número novo (único ponto de entrada deste domínio
# receptivo), evita duplicidade usando a restrição de unicidade da tabela
# de mensagens, e delega o processamento pela IA para uma tarefa
# assíncrona do Celery — respondendo em milissegundos ao Worker.
# ==============================================================================
