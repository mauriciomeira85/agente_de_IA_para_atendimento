# ==============================================================================
# ARQUIVO: midia/leitor_pdf.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Lê um PDF recebido de um cliente no WhatsApp (ver agente/nos.py:
# interpretar_midia) — SEM nenhuma IA, na maioria dos casos: a maior parte
# dos PDFs de verdade (orçamento, ficha técnica, contrato) tem uma camada
# de texto embutida, igual um .docx — basta extrair. Só quando o PDF é uma
# imagem escaneada (sem nenhum texto embutido, ex.: foto de um documento
# salva como PDF) é que não sobra texto nenhum pra extrair; nesse caso,
# quem chama (agente/nos.py) renderiza a PRIMEIRA página como imagem (ver
# renderizar_primeira_pagina_como_imagem abaixo) e manda pra IA de visão
# (integracoes_externas/deepseek.py:descrever_imagem) — mesmo caminho já
# usado pra foto/sticker/frame de vídeo.
#
# Usa PyMuPDF (importado como "fitz") — biblioteca C++ com bindings
# Python, rápida e sem dependência de nenhum serviço externo.
# ==============================================================================

import fitz
import structlog

logger = structlog.get_logger(__name__)


def extrair_texto_de_pdf(conteudo_do_pdf: bytes) -> str | None:
    """Extrai o texto embutido de um PDF, página por página. Devolve None se o PDF não tiver texto nenhum (provavelmente escaneado) ou estiver corrompido."""
    try:
        documento = fitz.open(stream=conteudo_do_pdf, filetype="pdf")
    except Exception as erro:  # noqa: BLE001 — PDF corrompido/malformado não deve quebrar a conversa
        logger.error("falha_ao_abrir_pdf", erro=str(erro))
        return None

    try:
        texto = "\n".join(pagina.get_text().strip() for pagina in documento).strip()
    finally:
        documento.close()

    return texto or None


def renderizar_primeira_pagina_como_imagem(conteudo_do_pdf: bytes) -> bytes | None:
    """Renderiza a primeira página de um PDF como PNG — usado como fallback quando o PDF não tem texto embutido (provavelmente escaneado)."""
    try:
        documento = fitz.open(stream=conteudo_do_pdf, filetype="pdf")
    except Exception as erro:  # noqa: BLE001 — mesmo motivo de extrair_texto_de_pdf acima
        logger.error("falha_ao_abrir_pdf_para_renderizar", erro=str(erro))
        return None

    try:
        if documento.page_count == 0:
            return None
        pixmap = documento[0].get_pixmap(dpi=150)
        return pixmap.tobytes("png")
    except Exception as erro:  # noqa: BLE001 — mesmo motivo acima
        logger.error("falha_ao_renderizar_pagina_de_pdf", erro=str(erro))
        return None
    finally:
        documento.close()


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# extrair_texto_de_pdf() é o caminho principal (sem IA, texto embutido);
# renderizar_primeira_pagina_como_imagem() é o fallback pra quando não
# sobra texto nenhum (PDF escaneado) — nesse caso, agente/nos.py manda o
# resultado pra descrever_imagem() (DeepSeek), o mesmo caminho já usado
# pra foto/sticker/frame de vídeo extraído.
# ==============================================================================
