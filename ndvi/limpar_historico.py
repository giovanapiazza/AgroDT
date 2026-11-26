#!/usr/bin/env python3
"""Arquiva resultados de sessoes anteriores do AgroDT sem destruir dados locais.

Usado automaticamente por app.py antes de inicializar cada nova sessao. Pode
tambem ser executado manualmente, sempre com app.py parado.
"""
from datetime import datetime, timezone
from pathlib import Path
import os
import sys
import uuid

HERE = Path(__file__).resolve().parent


def archive_storage(storage_root):
    """Move o armazenamento ativo para uma pasta de backup unica, se existir.

    So opera sobre o armazenamento, sem tocar em imagens na pasta ndvi/data,
    no codigo, no Docker/WebODM nem nos ambientes virtuais.
    """
    path = Path(storage_root).expanduser()
    if path.is_symlink():
        raise ValueError("Armazenamento simbolico nao e aceito para arquivamento automatico.")
    path = path.resolve()
    protected = {Path("/"), Path.home().resolve(), HERE, HERE.parent}
    if path in protected or path.parent == path:
        raise ValueError(f"Caminho inseguro para armazenamento NDVI: {path}")
    if not path.exists():
        return None
    if not path.is_dir():
        raise ValueError(f"Armazenamento nao e um diretorio: {path}")
    backup = path.with_name(
        path.name + "_backup_" +
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f") +
        "_" + uuid.uuid4().hex[:8]
    )
    path.rename(backup)
    return backup


def main():
    root = Path(os.environ.get("AGRODT_NDVI_DATA", HERE / "armazenamento"))
    try:
        backup = archive_storage(root)
    except (ValueError, OSError) as exc:
        print(f"Erro ao arquivar o armazenamento NDVI: {exc}", file=sys.stderr)
        raise SystemExit(1)
    if backup:
        print("Historico anterior arquivado em:", backup)
    else:
        print("Nenhum armazenamento anterior encontrado. O painel ja esta vazio.")
    print("O servidor criara um banco novo e vazio na proxima inicializacao.")


if __name__ == "__main__":
    main()
