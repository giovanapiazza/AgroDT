import sys
import os
sys.path.append("output")

# Mude 'funcao_teste' pelo nome real da sua função
from script_origem import funcao_teste
from traduzido_script_origem import funcao_teste as funcao_traduzida

def validar():
    entradas = [(10, 5), (0, 0)]
    for a, b in entradas:
        print(f"Entrada ({a},{b}) -> Orig: {funcao_teste(a,b)} | Trad: {funcao_traduzida(a,b)}")

if __name__ == "__main__":
    validar()
