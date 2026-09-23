# ==============================================================================
# ARQUIVO: configuracoes.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo é o "painel de controle" do backend. Em vez de espalhar
# senhas, endereços e chaves de API pelo código, todo mundo lê essas
# informações a partir daqui. Os valores reais nunca ficam escritos neste
# arquivo: eles vêm de variáveis de ambiente (o arquivo ".env" na raiz do
# projeto), que por sua vez NUNCA é enviado ao GitHub (ele está listado no
# .gitignore). Isso é o que garante que tokens e senhas não vazem no
# repositório público.
#
# Usamos a biblioteca "pydantic-settings", que lê as variáveis de ambiente
# automaticamente e já valida se elas têm o formato esperado (texto, número,
# etc.), avisando cedo se alguma configuração obrigatória estiver faltando.
#
# Versão ADAPTADA, para o Agente de Atendimento, do mesmo arquivo no Agente
# Comercial SDR — as diferenças: (1) nome/URL padrão da aplicação e do
# banco; (2) removidas as configurações de Resend e de reuniões (Google
# Calendar/Microsoft Teams/Zoom) — nenhuma se aplica aqui (ver
# Informacoes/Arquitetura.md); (3) NOVO bloco de embeddings — a Base de
# Conhecimento (RAG) precisa gerar um vetor pra cada item cadastrado e pra
# cada pergunta recebida. OpenAI reaparece aqui só por causa disso (mesma
# conta do SDR, reaproveitada) — não para texto/visão do agente em si
# (isso continua sendo só a DeepSeek).
# ==============================================================================

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracoes(BaseSettings):
    """Reúne todas as configurações do backend em um único lugar."""

    # --- Identidade da aplicação ---
    nome_da_aplicacao: str = "Agente de Atendimento"
    ambiente: str = "desenvolvimento"  # "desenvolvimento" ou "producao"

    # --- Banco de dados PostgreSQL ---
    # Formato esperado: postgresql+psycopg://usuario:senha@host:porta/banco
    # A imagem do container precisa ser "pgvector/pgvector:pg16" (não
    # "postgres:16-alpine") — a Base de Conhecimento guarda os embeddings
    # numa coluna vetorial (extensão "pgvector", ver alembic/versions/ e
    # modelos/item_de_conhecimento.py).
    url_banco_de_dados: str = (
        "postgresql+psycopg://agente:agente@postgres:5432/agente_atendimento"
    )

    # --- Redis (usado pelo Celery para o reengajamento por silêncio) ---
    url_redis: str = "redis://redis:6379/0"

    # --- Autenticação (login das empresas que usam a plataforma) ---
    # "chave_secreta_jwt" assina os tokens de sessão. Em produção, DEVE ser
    # trocada por um valor aleatório e único, DIFERENTE do usado nos outros
    # dois projetos da mesma linhagem (SDR e Cobrança) — são plataformas
    # separadas.
    chave_secreta_jwt: str = "troque-esta-chave-antes-de-ir-para-producao"
    algoritmo_jwt: str = "HS256"
    minutos_validade_token: int = 60 * 24 * 7  # 7 dias de sessão

    # --- DeepSeek ---
    # Cérebro do agente (conversa + ferramentas) e também a interpretação
    # de imagem (foto, sticker, frame de vídeo, página de PDF escaneada).
    deepseek_chave_api: str = ""
    deepseek_url_base: str = "https://api.deepseek.com/v1"
    deepseek_modelo_texto: str = "deepseek-flash"
    deepseek_modelo_visao: str = "deepseek-flash"

    # --- WhatsApp Business Cloud API (Meta) ---
    meta_versao_api: str = "v26.0"
    # Segredo compartilhado com o Worker do Cloudflare que valida a
    # assinatura da Meta antes de repassar o evento para este backend.
    backend_webhook_secret: str = ""

    # --- Conexão do WhatsApp via "Conectar WhatsApp" (WhatsApp Embedded
    # Signup) — ver app/integracoes_externas/meta_embedded_signup.py e a
    # aba "Canais" da interface. Credenciais de um app da Meta PRÓPRIO
    # deste projeto ("Agente de Atendimento"), separado dos outros dois.
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_id_configuracao_embedded_signup: str = ""

    # E-mail da ÚNICA conta que enxerga, na aba Canais, o formulário de
    # conexão manual do WhatsApp (Phone Number ID/WABA ID/token colados à
    # mão) — usado só enquanto não há um número comercial de verdade
    # disponível para concluir o "Conectar WhatsApp" (Embedded Signup) até
    # o fim. Em branco, ninguém vê essa opção extra.
    email_com_acesso_a_conexao_manual_whatsapp: str = ""

    # --- Together AI (transcrição de áudio) ---
    together_chave_api: str = ""
    together_modelo_transcricao: str = "openai/whisper-large-v3"

    # --- Base de Conhecimento (RAG) — embeddings via OpenAI ---
    # Mesma conta OpenAI já usada no Agente Comercial SDR (gpt-luna, para
    # imagem/PDF) — reaproveitamento de credencial. NÃO usa a Together AI
    # (como a versão original deste arquivo previa): um teste real mostrou
    # que a Together não oferece mais nenhum modelo de embeddings em modo
    # serverless, só endpoint dedicado com custo fixo por hora — ver
    # Informacoes/Memoria.md para o histórico completo dessa decisão.
    openai_chave_api: str = ""
    openai_modelo_embeddings: str = "text-embedding-3-small"

    # --- Endereço público da plataforma (o mesmo domínio usado pelo Caddy
    # e pelo build do frontend — ver docker-compose.yml e .env.exemplo).
    # Usado aqui para restringir o CORS em produção, aceitando chamadas
    # apenas do próprio domínio da aplicação.
    url_publica_da_plataforma: str = "http://localhost"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def obter_configuracoes() -> Configuracoes:
    """
    Retorna sempre a MESMA instância de Configuracoes (carregada uma única
    vez). Isso evita reler o arquivo .env toda vez que alguma parte do
    sistema precisa de uma configuração — mais rápido e mais previsível.
    """
    return Configuracoes()


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define a classe Configuracoes, que carrega — a partir de
# variáveis de ambiente — tudo que o backend precisa para funcionar: acesso
# ao banco de dados (pgvector), ao Redis, chaves de autenticação,
# credenciais da DeepSeek, da Meta (app próprio "Agente de Atendimento"),
# da Together AI (só transcrição de áudio) e da OpenAI (só embeddings da
# Base de Conhecimento). A função obter_configuracoes() é o jeito padrão
# de pegar essas informações em qualquer outro arquivo do projeto:
#   from app.configuracoes import obter_configuracoes
#   configuracoes = obter_configuracoes()
# ==============================================================================
