# ==============================================================================
# ARQUIVO: seguranca.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo cuida de tudo relacionado a "quem pode acessar o quê" na
# plataforma. Como o Agente Comercial SDR é um SaaS multi-empresa (várias
# empresas usam o mesmo sistema, cada uma com seus próprios atendimentos e
# configurações), é fundamental garantir duas coisas:
#
#   1) Só quem tem um usuário e senha válidos consegue entrar (login).
#   2) Depois de logado, o usuário SÓ enxerga os dados da SUA empresa —
#      nunca os dados de outra empresa cadastrada na plataforma.
#
# Para isso, usamos o padrão JWT (JSON Web Token): quando a empresa faz
# login, geramos um "crachá digital" assinado contendo o ID da empresa e do
# usuário. A cada requisição seguinte, o backend confere esse crachá antes
# de responder qualquer coisa.
# ==============================================================================

from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.banco_dados import obter_sessao
from app.configuracoes import obter_configuracoes
from app.modelos.usuario import Usuario

configuracoes = obter_configuracoes()

# Contexto usado para transformar senhas em texto puro em um "hash"
# (uma versão embaralhada e irreversível da senha) antes de salvar no
# banco. Assim, mesmo que alguém tenha acesso ao banco de dados, não
# consegue ler a senha original de ninguém.
contexto_senha = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Diz ao FastAPI onde fica a rota de login, para que a documentação
# automática (/docs) saiba como testar rotas protegidas.
esquema_oauth2 = OAuth2PasswordBearer(tokenUrl="/api/autenticacao/entrar")


def gerar_hash_senha(senha_em_texto_puro: str) -> str:
    """Transforma uma senha digitada pelo usuário em um hash seguro para salvar no banco."""
    return contexto_senha.hash(senha_em_texto_puro)


def senha_confere(senha_em_texto_puro: str, hash_salvo: str) -> bool:
    """Confere se a senha digitada no login bate com o hash salvo no banco."""
    return contexto_senha.verify(senha_em_texto_puro, hash_salvo)


def criar_token_de_acesso(id_usuario: int, id_empresa: int) -> str:
    """
    Gera o "crachá digital" (token JWT) de um usuário logado. O token carrega
    o ID do usuário e o ID da empresa (tenant) dentro dele, assinado com a
    chave secreta do backend — ninguém consegue forjar ou alterar esse
    conteúdo sem conhecer a chave.
    """
    expira_em = datetime.now(timezone.utc) + timedelta(
        minutes=configuracoes.minutos_validade_token
    )
    dados_do_token = {
        "sub": str(id_usuario),
        "id_empresa": id_empresa,
        "exp": expira_em,
    }
    return jwt.encode(
        dados_do_token, configuracoes.chave_secreta_jwt, algorithm=configuracoes.algoritmo_jwt
    )


def usuario_atual(
    token: str = Depends(esquema_oauth2),
    sessao: Session = Depends(obter_sessao),
) -> Usuario:
    """
    Dependência usada em (quase) toda rota protegida da API. Ela lê o token
    enviado pelo navegador, confere a assinatura, encontra o usuário
    correspondente no banco e o devolve pronto para uso. Se o token for
    inválido, expirado ou o usuário não existir mais, a requisição é
    recusada com erro 401 (não autorizado).
    """
    erro_de_credencial = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Não foi possível validar as credenciais.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, configuracoes.chave_secreta_jwt, algorithms=[configuracoes.algoritmo_jwt]
        )
        id_usuario = payload.get("sub")
        if id_usuario is None:
            raise erro_de_credencial
    except JWTError as erro:
        raise erro_de_credencial from erro

    usuario = sessao.get(Usuario, int(id_usuario))
    if usuario is None or not usuario.ativo:
        raise erro_de_credencial
    return usuario


def exigir_id_empresa_do_usuario(usuario: Usuario = Depends(usuario_atual)) -> int:
    """
    Atalho muito usado nas rotas: em vez de repetir "usuario.id_empresa" em
    todo lugar, as rotas pedem diretamente o ID da empresa do usuário
    logado. Isso é o que garante o isolamento entre empresas — toda consulta
    ao banco filtra "WHERE id_empresa = <este valor>", então uma empresa
    nunca vê os dados de outra.
    """
    return usuario.id_empresa


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo implementa a autenticação da plataforma: transforma senhas em
# hashes seguros (gerar_hash_senha / senha_confere), gera tokens JWT no
# login (criar_token_de_acesso) e valida esses tokens em toda rota
# protegida (usuario_atual). A função exigir_id_empresa_do_usuario é a peça
# central do isolamento multi-tenant: toda rota que mexe em dados de atendimentos,
# conversas ou configurações usa esse ID para nunca misturar informações de
# empresas diferentes.
# ==============================================================================
