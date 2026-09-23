# ==============================================================================
# ARQUIVO: modelos/integracao.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo define as tabelas usadas pela conexão do WhatsApp de cada
# empresa (IntegracaoWhatsApp) e pelo envio de dados do Dashboard para fora
# (IntegracaoSaida, aba "Integrações").
#
# Diferente do Agente Comercial SDR e do Agente de Cobrança, este projeto
# NÃO tem uma "IntegracaoCRM" (conexão para TRAZER contatos de fora para
# dentro) — não existe importação de contatos neste domínio: todo
# atendimento nasce automaticamente da primeira mensagem recebida de um
# cliente (ver Informacoes/Arquitetura.md, seção 2). Só sobrou a direção de
# SAÍDA (mandar os dados do Dashboard para um sistema externo da empresa).
#
# Um ponto importante de arquitetura: como o backend atende várias
# empresas ao mesmo tempo, cada IntegracaoWhatsApp guarda o Phone Number ID
# e o token de acesso DAQUELA empresa — é assim que uma mensagem recebida
# no webhook (ver app/rotas/whatsapp_webhook.py) consegue ser direcionada
# para a empresa correta, mesmo que várias empresas estejam usando a
# plataforma simultaneamente.
# ==============================================================================

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.banco_dados import Base


class IntegracaoWhatsApp(Base):
    """Credenciais da WhatsApp Cloud API de UMA empresa específica."""

    __tablename__ = "integracoes_whatsapp"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_empresa: Mapped[int] = mapped_column(
        ForeignKey("empresas.id"), nullable=False, unique=True, index=True
    )

    # Identificadores fornecidos pela Meta ao configurar o app no
    # Meta for Developers (ver documentação em infra/cloudflare-webhook).
    id_numero_telefone_meta: Mapped[str] = mapped_column(String(50), nullable=False)
    id_waba_meta: Mapped[str | None] = mapped_column(String(50), nullable=True)
    numero_exibicao: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # Token de acesso do System User da Meta. Em produção, o recomendado é
    # guardar esse valor em um cofre de segredos (ex: variável de ambiente
    # do próprio container, ou um serviço como o Vault); aqui ele fica no
    # banco de dados por simplicidade do projeto, sempre atrás do
    # isolamento por empresa e nunca exposto pela API para o navegador.
    token_de_acesso: Mapped[str] = mapped_column(String(500), nullable=False)

    conectado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    empresa: Mapped["Empresa"] = relationship()


class IntegracaoSaida(Base):
    """
    Uma conexão externa configurada por uma empresa para ENVIAR os dados do
    Dashboard (aba Painel) para um sistema externo. O envio em si é feito
    via POST de JSON pra url_webhook (ver
    integracoes_externas/envio_dashboard.py), disparado manualmente pelo
    botão "Enviar agora" da aba Integrações.
    """

    __tablename__ = "integracoes_saida"

    id: Mapped[int] = mapped_column(primary_key=True)
    id_empresa: Mapped[int] = mapped_column(ForeignKey("empresas.id"), nullable=False, index=True)

    nome_da_conexao: Mapped[str] = mapped_column(String(100), nullable=False)
    url_webhook: Mapped[str] = mapped_column(String(500), nullable=False)
    chave_api: Mapped[str | None] = mapped_column(String(500), nullable=True)

    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ultimo_envio_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ultimo_envio_com_sucesso: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    empresa: Mapped["Empresa"] = relationship()


from app.modelos.empresa import Empresa  # noqa: E402

# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define como cada empresa se conecta a sistemas externos:
# IntegracaoWhatsApp guarda as credenciais da WhatsApp Cloud API de cada
# empresa (permitindo que várias empresas usem números diferentes na mesma
# plataforma) e IntegracaoSaida guarda os destinos configurados para
# enviar os dados do Dashboard para fora.
# ==============================================================================
