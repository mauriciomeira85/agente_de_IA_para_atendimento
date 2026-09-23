# ==============================================================================
# ARQUIVO: armazenamento_midia.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Guarda em disco os bytes de uma mídia recebida no WhatsApp (foto, vídeo/
# GIF, áudio, documento) — necessário porque a URL de download que a Meta
# devolve expira em poucos minutos (ver
# integracoes_externas/whatsapp.py:obter_url_de_download_da_midia), então
# não dá pra reexibir a mídia na aba Conversas mais tarde sem guardar uma
# cópia própria. Cada arquivo é nomeado pelo ID da mídia na Meta
# (`id_midia_whatsapp`, já único e já gravado em Mensagem — ver
# modelos/conversa.py), então não precisamos de nenhuma coluna nova só
# para o caminho do arquivo.
#
# Fica num volume Docker nomeado (ver docker-compose.yml), montado tanto no
# backend (quem SERVE a mídia pela API, ver rotas/conversas.py) quanto no
# celery_worker (quem BAIXA e SALVA a mídia, ver agente/nos.py) — os dois
# containers enxergam a mesma pasta.
# ==============================================================================

import re
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

PASTA_DE_MIDIA = Path("/app/midia_armazenada")

# IDs de mídia da Meta são sempre numéricos, mas validamos o formato antes
# de usar como nome de arquivo de qualquer jeito — nunca confiar em um
# valor vindo de fora (ainda que indiretamente) sem checar, para não abrir
# brecha de path traversal (ex.: "../../etc/passwd").
_FORMATO_VALIDO_DE_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def salvar_midia(id_midia_whatsapp: str, conteudo: bytes) -> None:
    """Salva os bytes de uma mídia recebida em disco. Nunca levanta exceção — uma falha aqui não pode derrubar a interpretação da mídia, só significa que ela não poderá ser reexibida depois."""
    if not _FORMATO_VALIDO_DE_ID.match(id_midia_whatsapp):
        logger.error("id_de_midia_com_formato_invalido", id_midia_whatsapp=id_midia_whatsapp)
        return
    try:
        PASTA_DE_MIDIA.mkdir(parents=True, exist_ok=True)
        (PASTA_DE_MIDIA / id_midia_whatsapp).write_bytes(conteudo)
    except OSError as erro:
        logger.error("falha_ao_salvar_midia_em_disco", id_midia_whatsapp=id_midia_whatsapp, erro=str(erro))


def ler_midia(id_midia_whatsapp: str) -> bytes | None:
    """Lê os bytes de uma mídia salva anteriormente. Devolve None se o arquivo não existir (nunca foi salvo, ou é de antes desta funcionalidade existir)."""
    if not _FORMATO_VALIDO_DE_ID.match(id_midia_whatsapp):
        return None
    caminho = PASTA_DE_MIDIA / id_midia_whatsapp
    if not caminho.is_file():
        return None
    return caminho.read_bytes()


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# salvar_midia() e ler_midia() são o par de funções que permite à aba
# Conversas reexibir foto/vídeo/áudio/documento recebidos de um atendimento
# diretamente pela interface, sem depender da URL temporária da Meta
# (que já expirou) nem do WhatsApp do atendimento.
# ==============================================================================
