# ==============================================================================
# ARQUIVO: testes/test_painel.py
# ------------------------------------------------------------------------------
# INTRODUÇÃO
#
# Testa a função que calcula as taxas percentuais do Dashboard
# (_calcular_taxa, em app/rotas/painel.py). É um teste "puro" — não
# precisa de banco de dados nem de nenhum serviço externo no ar — por
# isso roda em menos de um segundo e pode ser executado em qualquer
# máquina com só o Python instalado:
#
#   cd backend && pytest testes/test_painel.py -v
# ==============================================================================

from app.rotas.painel import _calcular_taxa


def test_taxa_com_denominador_zero_nao_quebra():
    """Sem nenhum atendimento na base, a taxa deve ser 0%, nunca um erro de divisão por zero."""
    assert _calcular_taxa(numerador=0, denominador=0) == 0.0


def test_taxa_calculada_corretamente():
    """25 encaminhados em 100 interessados deve dar exatamente 25%."""
    assert _calcular_taxa(numerador=25, denominador=100) == 25.0


def test_taxa_arredonda_para_uma_casa_decimal():
    """1 em 3 deve arredondar para 33.3%, e não ficar com uma dízima infinita."""
    assert _calcular_taxa(numerador=1, denominador=3) == 33.3


def test_taxa_maxima_e_cem_por_cento():
    """Quando todos os atendimentos avançaram para a etapa seguinte, a taxa é 100%."""
    assert _calcular_taxa(numerador=10, denominador=10) == 100.0


# ==============================================================================
# RESUMO
# ------------------------------------------------------------------------------
# Estes testes garantem que o cálculo das taxas de conversão do Dashboard
# (Taxa de Abordados, Engajados, Qualificação e Encaminhamento) nunca
# quebra com uma base vazia e sempre arredonda de forma consistente.
# ==============================================================================
