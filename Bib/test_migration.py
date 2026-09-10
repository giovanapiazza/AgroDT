import sys
import os
import pytest

# Adiciona a pasta output ao caminho do sistema
sys.path.append(os.path.abspath("output"))

# ATENÇÃO: Ajuste estes nomes para o que você descobriu nos passos acima
from script_origem import NOME_REAL_DA_FUNCAO as original
from translated_script_origem import NOME_REAL_DA_FUNCAO as traduzido

def test_paridade_logica():
    """Verifica se os resultados são idênticos."""
    # Exemplo de dados de teste (ajuste conforme os argumentos da sua função)
    dados_de_teste = [(10, 5), (0, 0), (-1, 1)]
    
    for a, b in dados_de_teste:
        resultado_orig = original(a, b)
        resultado_trad = traduzido(a, b)
        
        assert resultado_orig == resultado_trad, f"Falha na paridade para ({a}, {b})"
