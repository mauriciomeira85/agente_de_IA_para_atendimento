# ==============================================================================
# ARQUIVO: agente/estados.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# O LangGraph organiza um agente de IA como um "grafo de estados": uma
# série de etapas (nós) que vão passando adiante um pacote de informação —
# o "estado" — cada uma fazendo sua parte do trabalho e atualizando esse
# pacote. Este arquivo define o FORMATO desse pacote de informação para o
# Agente de Atendimento: tudo que é necessário para processar UM turno de
# conversa (uma mensagem que chegou do cliente, do início ao fim, até a
# resposta pronta para envio).
#
# Por que um "TypedDict" e não uma classe Pydantic? Porque é o formato que
# o LangGraph espera nativamente para representar o estado que circula
# entre os nós do grafo — mantemos a validação "de verdade" (Pydantic) só
# nas bordas do sistema (entrada da API, saída do modelo de IA).
#
# Versão ADAPTADA, para o Agente de Atendimento, do mesmo arquivo nos
# outros dois projetos da linhagem — SEM os campos de "avaliação de
# interesse/desfecho comercial" (não existe qualificação de interesse
# neste domínio, ver Informacoes/Arquitetura.md): o que importa aqui é se o
# atendimento foi encaminhado (e para qual setor) ou resolvido. TAMBÉM
# carrega a `sessao` do banco (Session do SQLAlchemy) — diferente dos
# outros dois projetos, as ferramentas deste domínio
# (consultar_base_de_conhecimento, encaminhar_para_setor) precisam
# consultar o banco DENTRO do próprio turno (busca vetorial, validação de
# setor), então o nó que roda o turno (agente/nos.py:executar_turno_do_agente)
# precisa da sessão — e o LangGraph só passa o `estado` para cada nó, sem
# parâmetros extras, daí ela entrar aqui em vez de ser um argumento
# separado da função do nó.
# ==============================================================================

from typing import Literal, TypedDict

from sqlalchemy.orm import Session

# Import "de verdade" (não só TYPE_CHECKING): o LangGraph inspeciona este
# TypedDict em tempo de execução via typing.get_type_hints() para montar o
# grafo (ver agente/grafo.py) — um import condicional faria essa inspeção
# falhar com NameError assim que a aplicação subisse.
from app.modelos.atendimento import Atendimento
from app.modelos.configuracao_agente import ConfiguracaoAgente
from app.modelos.empresa import Empresa
from app.modelos.integracao import IntegracaoWhatsApp


class MensagemDoHistorico(TypedDict):
    """Uma mensagem passada da conversa, no formato que o modelo de IA espera."""

    papel: Literal["cliente", "agente"]
    conteudo: str


class PerfilDaEmpresa(TypedDict):
    """
    Um resumo, em texto, de tudo que a empresa configurou na aba
    "Configuração do Agente" — montado antes de entrar no grafo (ver
    agente/prompts.py) para que os nós não precisem saber nada sobre banco
    de dados, apenas sobre texto.

    Diferente dos outros dois projetos da linhagem, não existe um "desfecho
    único" aqui — o destino de um atendimento é escolhido dinamicamente
    entre os Setores cadastrados (ver nomes_dos_setores abaixo), e qualquer
    afirmação sobre a empresa precisa vir da Base de Conhecimento, não
    deste resumo (ver responder_apenas_com_base_no_conhecimento).
    """

    nome_do_agente: str
    contexto_da_empresa: str
    roteiro_conversa: str
    responder_apenas_com_base_no_conhecimento: bool
    mensagem_fora_do_escopo: str
    # Nomes dos setores já cadastrados pela empresa — o prompt lista essa
    # opções pro modelo escolher um nome válido de primeira; o guardrail
    # (agente/guardrails_de_atendimento.py) confere de qualquer jeito antes
    # de agir de verdade.
    nomes_dos_setores: list[str]


class EstadoConversa(TypedDict, total=False):
    """O pacote de informação que percorre todos os nós do grafo do agente."""

    # --- Entrada (preenchido antes de o grafo começar a rodar) ---
    id_empresa: int
    id_atendimento: int
    id_conversa: int
    perfil_da_empresa: PerfilDaEmpresa
    historico_mensagens: list[MensagemDoHistorico]
    status_atual_atendimento: str
    tipo_mensagem_recebida: Literal["texto", "audio", "imagem", "documento"]
    conteudo_bruto_recebido: str  # texto puro, ou a legenda (se houver) quando for mídia
    # Quantas mensagens LIVRES o agente já mandou pra este atendimento desde
    # o último template (ver Atendimento.mensagens_livres_desde_ultimo_template)
    # — usado por agente/nos.py e agente/prompts.py para saber quando esta é
    # a ÚLTIMA mensagem livre permitida antes do encaminhamento forçado
    # (ver agente/ferramentas.py:NUMERO_MAXIMO_DE_MENSAGENS_LIVRES_ANTES_DO_ENCAMINHAMENTO).
    mensagens_livres_ja_enviadas: int
    # Só preenchidos quando tipo_mensagem_recebida != "texto" — necessários
    # pra baixar o arquivo de verdade da WhatsApp Cloud API antes de
    # interpretar (ver agente/nos.py:interpretar_midia).
    id_midia_whatsapp: str | None
    mime_type_da_midia: str | None
    nome_do_arquivo_da_midia: str | None
    # Sessão de banco ativa durante este turno — ver nota na introdução.
    sessao: Session

    # --- Objetos reais, não apenas texto (ver introdução acima) ---
    # Diferente dos demais campos deste TypedDict, estes não são dados
    # "textuais" prontos para o prompt — são os objetos do ORM que as
    # ferramentas de ação precisam para agir de verdade durante o próprio
    # turno (mandar o WhatsApp real para um setor humano — ver
    # agente/ferramentas.py). Como este grafo não usa checkpointer (ver
    # agente/grafo.py), não há nenhuma exigência de que o estado seja
    # serializável, então isso é seguro.
    atendimento: Atendimento
    empresa: Empresa
    configuracao_agente: ConfiguracaoAgente
    integracao_whatsapp: IntegracaoWhatsApp

    # --- Preenchido durante a execução do grafo ---
    mensagem_recebida_em_texto: str  # depois de interpretar áudio/imagem, sempre vira texto
    # Só preenchido quando interpretar_midia baixou uma imagem de verdade
    # (foto, sticker, frame extraído de vídeo, ou página de PDF escaneado
    # renderizada) — um data URI (data:image/jpeg;base64,...) anexado à
    # mensagem do turno ATUAL, além da descrição em texto acima (que vai
    # pro histórico). Assim o cérebro principal enxerga a imagem de
    # verdade nesta chamada, em vez de só uma paráfrase — mas turnos
    # FUTUROS (histórico reenviado) continuam vendo só o texto, nunca a
    # imagem de novo (ver agente/prompts.py:montar_mensagens_para_o_modelo).
    imagem_para_anexar_no_turno: str | None
    # Preenchido pela ferramenta que encerrou o turno (encaminhar_para_setor
    # ou marcar_como_resolvido), ver agente/ferramentas.py:RodadaDoTurno —
    # None enquanto nenhuma delas foi chamada ainda neste turno.
    desfecho_acionado: str | None
    # None é SILÊNCIO PROPOSITAL: o atendimento já tinha sido encaminhado
    # antes, e o modelo decidiu que a mensagem atual (uma cortesia
    # repetida) não precisa de resposta — ver agente/ferramentas.py
    # (ferramenta "nao_responder") e agente/orquestrador.py, que não envia
    # nada ao cliente nesse caso.
    resposta_para_envio: str | None


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo define os formatos de dado (TypedDict) que circulam dentro
# do grafo LangGraph do agente: EstadoConversa é o "pacote" principal, que
# começa com o que chegou do WhatsApp e termina com a resposta pronta para
# envio, passando pela interpretação de mídia e pela eventual ação de
# encaminhar para um setor ou marcar como resolvido.
# ==============================================================================
