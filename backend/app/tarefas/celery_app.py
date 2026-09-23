# ==============================================================================
# ARQUIVO: tarefas/celery_app.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo cria e configura a instância do Celery — a fila de tarefas
# em segundo plano usada pelo projeto para duas finalidades:
#
#   1) Processar a resposta do agente de IA de forma assíncrona, assim que
#      uma mensagem chega pelo webhook do WhatsApp (ver
#      tarefas/tarefas_conversa.py).
#   2) Rodar, periodicamente, a varredura de atendimentos em silêncio (ver
#      tarefas/tarefas_monitoramento.py e agente/monitoramento.py) — sem
#      nenhum clique humano, e sem um "for" em Python decidindo sozinho o
#      que fazer com cada um: quem decide é o próprio agente, num turno com
#      ferramentas reais.
#
# Diferente dos outros dois projetos da linhagem, não existe aqui uma
# tarefa de sincronização de CRM externo — não há importação de contatos
# neste domínio receptivo (ver Informacoes/Arquitetura.md, seção 2).
#
# O Celery precisa de um "corretor de mensagens" (broker) para funcionar —
# usamos o Redis, que já está no docker-compose do projeto.
# ==============================================================================

from celery import Celery
from celery.schedules import crontab

from app.configuracoes import obter_configuracoes

configuracoes = obter_configuracoes()

aplicativo_celery = Celery(
    "agente_atendimento",
    broker=configuracoes.url_redis,
    backend=configuracoes.url_redis,
    include=[
        "app.tarefas.tarefas_conversa",
        "app.tarefas.tarefas_monitoramento",
    ],
)

aplicativo_celery.conf.timezone = "America/Sao_Paulo"

# Agenda fixa do Celery Beat: a cada 15 minutos, 24h por dia, verifica se
# existe algum atendimento em silêncio há 3+ dias em qualquer empresa.
aplicativo_celery.conf.beat_schedule = {
    "verificar-atendimentos-pendentes-de-atencao": {
        "task": "app.tarefas.tarefas_monitoramento.verificar_atendimentos_pendentes_de_atencao",
        "schedule": crontab(minute="*/15"),
    },
}

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo cria a instância "aplicativo_celery", usada tanto pelo
# processo "worker" (que executa as tarefas) quanto pelo processo "beat"
# (que dispara a varredura periódica de atendimentos em silêncio). Os dois
# processos rodam em containers Docker separados (ver docker-compose.yml),
# mas compartilham o mesmo código da aplicação.
# ==============================================================================
