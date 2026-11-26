#!/usr/bin/env python3
"""Integra fotos originais de um voo AgroDT ao WebODM via API documentada.

Uso: python webodm_ortomosaico.py submit --imagens /caminho/voo --nome voo_01
     python webodm_ortomosaico.py status --projeto-id 1 --tarefa-id <ID-ou-UUID>
     python webodm_ortomosaico.py download --projeto-id 1 --tarefa-id <ID-ou-UUID> --nome voo_01

Requer servidor WebODM e no de processamento ativos. NAO cria mosaico de imagens
NDVI isoladas: use imagens originais JPG/TIFF sobrepostas do mesmo levantamento.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import sys
import uuid

try:
    import requests
except ImportError as exc:
    raise SystemExit("Instale requests: pip install -r requirements-webodm.txt") from exc

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = Path(os.environ.get("AGRODT_NDVI_DATA", HERE / "armazenamento")).resolve() / "ortomosaicos"
ALLOWED_SUFFIXES = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}
STATUSES = {10: "na fila", 20: "processando", 30: "falhou", 40: "concluida", 50: "cancelada"}
SAFE_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class WebODMError(RuntimeError):
    pass


def require_name(name):
    if not SAFE_NAME.fullmatch(name or ""):
        raise ValueError("Nome de voo deve conter 1 a 64 letras, digitos, '_' ou '-'.")
    return name


def collect_images(folder):
    """Somente fotografias originais, sem produtos de analise ou copias ocultas."""
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Pasta nao encontrada: {root}")
    images = sorted(p for p in root.rglob("*")
                    if p.is_file() and p.suffix.lower() in ALLOWED_SUFFIXES
                    and not any(part.lower() in {"analisadas", "processadas", "ortomosaicos", "erros",
                        "ndvi", "previews", "__macosx"} for part in p.relative_to(root).parts)
                    and not p.name.lower().startswith(("ndvi_", "heatmap_", "mascara_", "mapa_areas_",
                                                         "red_preview", "nir_preview"))
                    and not p.name.startswith("."))
    if len(images) < 2:
        raise ValueError("WebODM exige pelo menos duas fotografias originais com sobreposicao.")
    names = [p.name for p in images]
    if len(names) != len(set(names)):
        raise ValueError("Ha nomes de arquivos repetidos em pastas distintas; renomeie antes de enviar.")
    return images


def headers(token):
    return {"Authorization": f"JWT {token}"}


def api_request(method, base, endpoint, token=None, **kwargs):
    url = base.rstrip("/") + endpoint
    response = requests.request(method, url,
                                headers=headers(token) if token else {},
                                timeout=(15, 600), **kwargs)
    if not response.ok:
        raise WebODMError(f"{method} {endpoint}: HTTP {response.status_code}: {response.text[:400]}")
    if "application/json" in response.headers.get("Content-Type", ""):
        return response.json()
    raise WebODMError(f"{endpoint}: WebODM nao retornou JSON")


def authenticate(base, username, password):
    if not username or not password:
        raise ValueError("Configure WEBODM_USER e WEBODM_PASSWORD no ambiente.")
    result = api_request("POST", base, "/api/token-auth/",
                         data={"username": username, "password": password})
    token = result.get("token")
    if not token:
        raise WebODMError("Resposta sem token JWT")
    return token


def parse_webodm_id(value, label):
    """Identificadores API WebODM: projetos costumam ser ints, tarefas podem ser UUIDs.

    Valida antes de interpolar o ID em um caminho HTTP; nunca converte UUID em int.
    """
    if isinstance(value, bool) or value is None:
        raise WebODMError(f"Identificador {label} ausente ou invalido")
    candidate = str(value).strip()
    if candidate.isdecimal() and int(candidate) > 0:
        return int(candidate)
    try:
        return str(uuid.UUID(candidate))
    except (ValueError, AttributeError):
        raise WebODMError(f"Identificador {label} nao suportado: {candidate[:80]}") from None


def project(token, base, name, project_id=None):
    if project_id is not None:
        return parse_webodm_id(project_id, "projeto")
    response = api_request("POST", base, "/api/projects/", token, data={"name": name})
    return parse_webodm_id(response["id"], "projeto")


# Django limita por padrao a 100 arquivos multipart por requisicao.
# Lotes menores protegem o servidor e evitam HTTP 400 em voos multiespectrais.
MAX_IMAGES_PER_REQUEST = 24


def _post_images(token, base, endpoint, images, data=None):
    """Transmite um lote sem alterar os bytes nem os metadados das fotos."""
    with ExitStack() as stack:
        files = []
        for path in images:
            stream = stack.enter_context(path.open("rb"))
            mime = "image/jpeg" if path.suffix.lower() in {".jpg", ".jpeg"} else (
                "image/png" if path.suffix.lower() == ".png" else "image/tiff")
            files.append(("images", (path.name, stream, mime)))
        return api_request("POST", base, endpoint, token, files=files, data=data or {})


def create_task(token, base, project_id, images, name):
    """Cria UMA tarefa para o voo inteiro; usa lotes para missões grandes.

    A tarefa parcial evita processamento prematuro. 'commit' so e enviado
    depois que todas as fotografias tiverem sido aceitas pelo WebODM.
    """
    if len(images) < 2:
        raise ValueError("Uma tarefa WebODM exige pelo menos duas imagens")
    endpoint = f"/api/projects/{project_id}/tasks/"

    # Mantem compatibilidade com o fluxo testado de voos pequenos.
    if len(images) <= MAX_IMAGES_PER_REQUEST:
        response = _post_images(token, base, endpoint, images,
                                {"name": name, "options": "[]"})
        return parse_webodm_id(response["id"], "tarefa")

    response = api_request("POST", base, endpoint, token,
                           data={"name": name, "options": "[]", "partial": "true"})
    task_id = parse_webodm_id(response["id"], "tarefa")
    task_endpoint = f"/api/projects/{project_id}/tasks/{task_id}"
    try:
        for offset in range(0, len(images), MAX_IMAGES_PER_REQUEST):
            batch = images[offset:offset + MAX_IMAGES_PER_REQUEST]
            _post_images(token, base, task_endpoint + "/upload/", batch)
        # A tarefa so inicia com todas as bandas carregadas.
        api_request("POST", base, task_endpoint + "/commit/", token)
    except Exception as exc:
        raise WebODMError(
            f"Envio incompleto da tarefa parcial WebODM {task_id} "
            f"(projeto {project_id}): {exc}. "
            "Confira o painel WebODM antes de tentar novamente."
        ) from exc
    return task_id


def task_status(token, base, project_id, task_id):
    return api_request("GET", base, f"/api/projects/{project_id}/tasks/{task_id}/", token)


def download_orthophoto(token, base, project_id, task_id, output):
    url = base.rstrip("/") + f"/api/projects/{project_id}/tasks/{task_id}/download/orthophoto.tif"
    output.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, headers=headers(token), stream=True, timeout=(15, 600)) as response:
        if response.status_code != 200:
            raise WebODMError(f"Download HTTP {response.status_code}: {response.text[:400]}")
        temp = output.with_suffix(".part")
        try:
            with temp.open("wb") as fp:
                for block in response.iter_content(chunk_size=1024 * 1024):
                    if block:
                        fp.write(block)
            if temp.stat().st_size == 0:
                raise WebODMError("Ortomosaico recebido vazio")
            temp.replace(output)
        finally:
            temp.unlink(missing_ok=True)
    return output


def run(args):
    base = args.url.rstrip("/")
    if not base.startswith(("http://", "https://")):
        raise ValueError("WEBODM_URL deve comecar com http:// ou https://")
    token = authenticate(base, args.usuario, args.senha)
    if args.command == "submit":
        name = require_name(args.nome)
        images = collect_images(args.imagens)
        print(f"Fotos originais encontradas: {len(images)}", flush=True)
        pid = project(token, base, name, args.projeto_id)
        tid = create_task(token, base, pid, images, name)
        metadata = {"webodm_url": base, "project_id": pid, "task_id": tid,
                    "flight_id": name, "images_count": len(images)}
        folder = args.saida / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "webodm_tarefa.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        print(f"Tarefa WebODM enviada: projeto={pid}, tarefa={tid}")
        print(f"Consultar: python webodm_ortomosaico.py status --projeto-id {pid} --tarefa-id {tid}")
        print("O processamento e realizado pelo WebODM, nao pelo receptor NDVI.")
    elif args.command in {"status", "download"}:
        state = task_status(token, base, args.projeto_id, args.tarefa_id)
        status = state.get("status")
        print(f"Projeto {args.projeto_id}, tarefa {args.tarefa_id}: {STATUSES.get(status, str(status))}")
        if state.get("last_error"):
            print("Detalhe:", state["last_error"])
        if args.command == "download":
            if status != 40:
                raise WebODMError("A tarefa precisa estar concluida (status=40) para baixar.")
            available = state.get("available_assets", [])
            if available and "orthophoto.tif" not in available:
                raise WebODMError("Esta tarefa nao possui orthophoto.tif. Confira o GPS e os ativos gerados.")
            name = require_name(args.nome)
            filename = args.saida / name / "orthophoto.tif"
            download_orthophoto(token, base, args.projeto_id, args.tarefa_id, filename)
            print("Ortomosaico salvo em:", filename)
            try:
                from orthomosaic_catalog import build_preview
                detail = build_preview(filename)
                print("Preview PNG gerada:", filename.with_name("preview.png"))
                print("Bandas:", detail["bands"], "| CRS:", detail["crs"])
            except (ImportError, ValueError, RuntimeError, OSError) as exc:
                print("Aviso: GeoTIFF salvo, mas nao foi possivel criar a previa:", exc)
                print("Instale rasterio com: pip install -r requirements-geo.txt")
            print("Recarregue o painel AgroDT para ver o ortomosaico.")
            print("Para calcular NDVI, confirme a ordem das bandas antes de importar o GeoTIFF no AgroDT.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="WebODM -> ortomosaicos do AgroDT")
    parser.add_argument("--url", default=os.getenv("WEBODM_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--usuario", default=os.getenv("WEBODM_USER"))
    parser.add_argument("--senha", default=os.getenv("WEBODM_PASSWORD"))
    parser.add_argument("--saida", type=Path, default=DEFAULT_OUTPUT)
    sub = parser.add_subparsers(dest="command", required=True)
    submit = sub.add_parser("submit", help="Envia fotos originais do voo para WebODM")
    submit.add_argument("--imagens", required=True, type=Path)
    submit.add_argument("--nome", required=True)
    submit.add_argument("--projeto-id", type=lambda v: parse_webodm_id(v, "projeto"))
    for command in ("status", "download"):
        p = sub.add_parser(command)
        p.add_argument("--projeto-id", type=lambda v: parse_webodm_id(v, "projeto"), required=True)
        p.add_argument("--tarefa-id", type=lambda v: parse_webodm_id(v, "tarefa"), required=True)
        if command == "download":
            p.add_argument("--nome", required=True)
    args = parser.parse_args(argv)
    try:
        run(args)
    except (ValueError, OSError, WebODMError, requests.RequestException) as exc:
        parser.exit(1, f"Erro: {exc}\n")


if __name__ == "__main__":
    main()
