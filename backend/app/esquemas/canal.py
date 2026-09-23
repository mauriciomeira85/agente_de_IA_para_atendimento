# ==============================================================================
# ARQUIVO: esquemas/canal.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Define o formato de dado da aba "Canais" — onde a empresa conecta o seu
# número de WhatsApp através do botão "Conectar WhatsApp" (WhatsApp
# Embedded Signup da Meta), sem precisar copiar nenhuma credencial
# manualmente.
# ==============================================================================

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConfiguracaoEmbeddedSignupSaida(BaseModel):
    """
    Dados públicos (não são segredo) que o navegador precisa para montar o
    botão "Conectar WhatsApp": o ID do nosso app na Meta e o ID da
    configuração de login criada no painel (ver README, seção Meta). Com
    isso, o SDK do Facebook no frontend sabe qual janela de conexão abrir.
    """

    app_id: str
    id_configuracao: str
    versao_api: str
    # Só vem True para a conta autorizada em
    # email_com_acesso_a_conexao_manual_whatsapp (ver configuracoes.py) —
    # é o que decide se a tela mostra o formulário extra de conexão manual.
    mostrar_conexao_manual: bool = False


class ConectarCanalWhatsAppManualEntrada(BaseModel):
    """
    Formulário de conexão manual (Phone Number ID/WABA ID/token colados
    à mão, obtidos direto no painel da Meta) — visível só para a conta
    autorizada, enquanto não há um número comercial de verdade disponível
    para concluir o "Conectar WhatsApp" (Embedded Signup) até o fim.
    """

    id_numero_telefone_meta: str
    id_waba_meta: str | None = None
    numero_exibicao: str | None = None
    token_de_acesso: str


class ConectarCanalWhatsAppEntrada(BaseModel):
    """
    O que o frontend envia depois que a pessoa termina o login na janela
    da Meta: o código de autorização (trocado pelo token aqui no backend,
    nunca no navegador) e o `redirect_uri` EXATO usado para abrir aquele
    login (`biblioteca/embeddedSignup.ts`, `abrirJanelaDeConexao`) — a
    Meta exige que os dois batam na hora de trocar o código, senão recusa
    com "Error validating verification code". `id_numero_telefone`/
    `id_waba` são OPCIONAIS — em teoria a própria janela da Meta informa
    os dois ao frontend por "postMessage" durante o processo
    (`WA_EMBEDDED_SIGNUP`/`FINISH`), mas esse recado é conhecidamente
    instável (falha silenciosamente em vários navegadores/contextos — ver
    `integracoes_externas/meta_embedded_signup.py`,
    `descobrir_waba_e_numero`). Quando não vierem, o backend descobre os
    dois sozinho, direto na Graph API, a partir do próprio token.
    """

    codigo_de_autorizacao: str
    redirect_uri: str
    id_numero_telefone: str | None = None
    id_waba: str | None = None


class CanalWhatsAppSaida(BaseModel):
    """
    Devolvida para a tela — repare que o token de acesso NUNCA é incluído
    aqui. Depois de salvo, o token só é usado internamente pelo backend
    para enviar mensagens; ele nunca volta a trafegar até o navegador.
    """

    model_config = ConfigDict(from_attributes=True)

    id_numero_telefone_meta: str
    numero_exibicao: str | None
    conectado_em: datetime


class TemplateWhatsAppSaida(BaseModel):
    """
    Status de um dos quatro templates daquela empresa na Meta (ver
    integracoes_externas/meta_templates.py). "status" vem None enquanto o
    template ainda nem foi submetido para análise; depois disso, reflete
    exatamente o que a Meta devolve: "PENDING" (em análise), "APPROVED" ou
    "REJECTED".
    """

    nome: str
    status: str | None


class PreviaDoTemplateSaida(BaseModel):
    """
    Texto de VERDADE de um dos quatro templates (com {{1}}..{{3}}
    literais já preenchidos com um exemplo, exatamente como
    montar_previa_do_template_* devolve) — só para conferência antes de
    submeter para análise da Meta. Diferente dos outros dois projetos da
    linhagem, nenhum desses templates é editável pela empresa (o texto é
    fixo, sem uma variável de "resumo do produto"), então não existe um
    formulário de edição nem uma rota de "confirmar texto customizado".
    """

    texto: str


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define os formatos usados pela aba Canais:
# ConfiguracaoEmbeddedSignupSaida (o que o botão "Conectar WhatsApp"
# precisa para abrir a janela da Meta, incluindo se a conexão manual deve
# aparecer), ConectarCanalWhatsAppManualEntrada (o formulário manual,
# visível só para a conta autorizada), ConectarCanalWhatsAppEntrada (o
# que o frontend envia ao final da conexão pelo botão), CanalWhatsAppSaida
# (o status da conexão já salva), PreviaDoTemplateSaida (o texto pronto de
# um dos quatro templates, só para conferência) e TemplateWhatsAppSaida (o
# status de um template já submetido à Meta).
# ==============================================================================
