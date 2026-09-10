import os
from translator import TradutorDeCodigo

def rodar_lote():
    if not os.path.exists("output"): os.makedirs("output")
    tradutor = TradutorDeCodigo()
    arquivos = [f for f in os.listdir(".") if f.endswith(".py") and f != "batch_translator.py" and f != "translator.py" and f != "app.py"]
    
    for nome in arquivos:
        print(f"-> Traduzindo: {nome}")
        tradutor.processar_arquivo(nome, os.path.join("output", f"traduzido_{nome}"), "Python", "C++")

if __name__ == "__main__":
    rodar_lote()
