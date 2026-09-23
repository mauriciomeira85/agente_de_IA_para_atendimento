# ==============================================================================
# ARQUIVO: agente/guardrails_de_atendimento.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Este arquivo é a peça de arquitetura que o Agente Comercial SDR nunca
# teve, e que o Agente de Cobrança tem uma versão diferente dela
# (guardrails_de_negociacao.py, que trava NÚMEROS — desconto/parcelas).
# Aqui o guardrail trava uma FONTE DE VERDADE: garante, em código
# determinístico, que o agente só encaminha um atendimento para um setor
# que EXISTE DE VERDADE, cadastrado pela empresa — nunca um nome que o
# modelo "inventou" ou confundiu (ex.: o cliente menciona "financeiro" numa
# frase e o modelo tenta usar isso como nome de setor, mesmo que a empresa
# tenha cadastrado esse setor como "Financeiro e Cobrança").
#
# O princípio é o mesmo já usado nos outros dois projetos da linhagem
# (ver Informacoes/Arquitetura.md, seção 4.3): uma instrução de prompt
# nunca é 100% garantida — o prompt já lista os setores reais para o
# modelo escolher certo de primeira (ver agente/prompts.py), mas a
# GARANTIA de verdade vem daqui, checando contra o banco antes de
# qualquer WhatsApp real ser enviado.
# ==============================================================================

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos.setor import Setor


@dataclass
class ViolacaoDeSetor:
    """Descreve por que um nome de setor não pôde ser usado, e o que o modelo deve fazer a respeito."""

    motivo: str
    setores_disponiveis: list[str]

    def como_mensagem_para_o_modelo(self) -> str:
        lista = ", ".join(self.setores_disponiveis) if self.setores_disponiveis else "(nenhum setor cadastrado)"
        return (
            f"Encaminhamento NÃO enviado: {self.motivo} Setores disponíveis de verdade: {lista}. "
            "Chame a ferramenta de novo usando EXATAMENTE um desses nomes."
        )


def validar_setor_de_encaminhamento(
    sessao: Session, id_empresa: int, nome_do_setor: str
) -> tuple[Setor, None] | tuple[None, str]:
    """
    Confere se `nome_do_setor` corresponde a um Setor cadastrado de verdade
    pela empresa — comparação exata primeiro, e uma tentativa
    case-insensitive como tolerância (o modelo pode escrever "vendas" em
    minúsculo mesmo a empresa tendo cadastrado "Vendas"). Se nada bater,
    devolve (None, mensagem_de_erro_pronta_para_o_modelo) — quem chama
    (agente/ferramentas.py:_ferramenta_encaminhar_para_setor) devolve essa
    mensagem como resultado da ferramenta, SEM enviar nenhum WhatsApp real,
    e o modelo tenta de novo com um nome válido.
    """
    todos_os_setores = list(sessao.scalars(select(Setor).where(Setor.id_empresa == id_empresa)))
    nomes_disponiveis = [setor.nome for setor in todos_os_setores]

    if not todos_os_setores:
        return None, ViolacaoDeSetor(
            motivo="esta empresa ainda não cadastrou nenhum setor.", setores_disponiveis=[]
        ).como_mensagem_para_o_modelo()

    for setor in todos_os_setores:
        if setor.nome == nome_do_setor:
            return setor, None

    nome_normalizado = nome_do_setor.strip().lower()
    for setor in todos_os_setores:
        if setor.nome.strip().lower() == nome_normalizado:
            return setor, None

    return None, ViolacaoDeSetor(
        motivo=f'"{nome_do_setor}" não corresponde a nenhum setor cadastrado.',
        setores_disponiveis=nomes_disponiveis,
    ).como_mensagem_para_o_modelo()


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Este arquivo implementa validar_setor_de_encaminhamento(): a garantia em
# CÓDIGO (não só prompt) de que o agente só encaminha um atendimento para
# um setor que existe de verdade no banco daquela empresa. Se o modelo
# tentar usar um nome inválido, a validação rejeita e devolve a lista real
# de setores disponíveis, para o modelo tentar de novo — o mesmo princípio
# de "o código nunca confia cegamente na saída do modelo" já usado no
# Agente de Cobrança para os limites de negociação.
# ==============================================================================
