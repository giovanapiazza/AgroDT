#!/usr/bin/env python3
"""Arquiva o armazenamento NDVI atual para reiniciar o painel sem perder o backup.

Pare o app.py e os simuladores antes de usar.
"""
from datetime import datetime
from pathlib import Path
import os
import sys

HERE = Path(__file__).resolve().parent
root = Path(os.environ.get("AGRODT_NDVI_DATA", HERE / "armazenamento")).resolve()

if __name__ == "__main__":
    if not root.exists():
        print(f"Nenhum armazenamento encontrado em {root}. O painel ja pode iniciar vazio.")
        raise SystemExit(0)
    if not root.is_dir():
        print("Erro: caminho de armazenamento nao e um diretorio.", file=sys.stderr)
        raise SystemExit(1)
    if root.name in {"/", ".", ".."}:
        print("Erro: diretório inseguro.", file=sys.stderr)
        raise SystemExit(1)
    backup = root.with_name(root.name + "_backup_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    root.rename(backup)
    print("Historico anterior arquivado em:", backup)
    print("O servidor criara um novo banco vazio ao iniciar. Nenhum arquivo foi excluido.")
