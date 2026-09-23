# ==============================================================================
# ARQUIVO: integracoes_externas/video.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# O modelo de visão usado para interpretar mídia recebida no WhatsApp (ver
# integracoes_externas/deepseek.py:descrever_imagem) não aceita vídeo como
# entrada direta, só imagem e PDF. Como um GIF enviado pelo
# seletor nativo do WhatsApp chega como um vídeo curto (mime "video/mp4"),
# extraímos um frame dele com o ffmpeg (instalado na imagem Docker do
# backend, ver Dockerfile) e descrevemos esse frame como se fosse uma
# imagem comum (ver agente/nos.py:interpretar_midia) — um resultado "melhor
# do que nada" que cobre o caso mais comum na prática (vídeos curtos/GIFs),
# mesmo sem entender o vídeo inteiro.
# ==============================================================================

import subprocess
import tempfile
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def extrair_frame_de_video(conteudo_do_video: bytes) -> bytes | None:
    """Extrai o primeiro frame de um vídeo como JPEG. Devolve None se o ffmpeg falhar (vídeo corrompido, formato não suportado etc.)."""
    with tempfile.TemporaryDirectory() as pasta_temporaria:
        caminho_entrada = Path(pasta_temporaria) / "entrada.mp4"
        caminho_saida = Path(pasta_temporaria) / "frame.jpg"
        caminho_entrada.write_bytes(conteudo_do_video)

        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(caminho_entrada), "-frames:v", "1", str(caminho_saida)],
                capture_output=True,
                timeout=20,
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as erro:
            logger.error("falha_ao_extrair_frame_de_video", erro=str(erro))
            return None

        if not caminho_saida.exists():
            logger.error("ffmpeg_nao_gerou_frame_de_video")
            return None

        return caminho_saida.read_bytes()


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# extrair_frame_de_video() roda o ffmpeg como subprocesso para pegar o
# primeiro frame de um vídeo (bytes) e devolvê-lo como JPEG — nunca levanta
# exceção, só devolve None em caso de falha, para o chamador (interpretar_midia)
# poder cair no aviso genérico de "não foi possível interpretar" sem quebrar
# a conversa.
# ==============================================================================
