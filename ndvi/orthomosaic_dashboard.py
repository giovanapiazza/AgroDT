"""Orquestra WebODM a partir do painel AgroDT, preservando TIFFs originais."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import threading
import time
import uuid
import zipfile

SAFE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
EXT = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}
# Artefatos visuais dos datasets não pertencem ao conjunto de capturas do drone.
NON_CAPTURE_DIRS = {"preview", "previews", "analisadas", "processadas", "erros", "__macosx", "orthomosaicos"}
NON_CAPTURE_FILES = {"3d-preview.png", "orthophoto_small.jpg"}


def is_capture_path(value):
    """Exclui prévias, preservando as fotos multiespectrais originais."""
    parts = str(value).replace("\\", "/").split("/")
    return (not any(part.casefold() in NON_CAPTURE_DIRS for part in parts[:-1])
            and parts[-1].casefold() not in NON_CAPTURE_FILES)

MAX_IMAGES = 600
MAX_MEMBER = 80 * 1024 * 1024
MAX_UNCOMPRESSED = 1400 * 1024 * 1024
MAX_ZIP = 600 * 1024 * 1024
ACTIVE = {"queued", "submitting", "processing", "downloading", "generating_preview", "calculating_ndvi"}
_lock = threading.RLock()
_workers: dict[str, threading.Thread] = {}


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validated_flight(flight_id):
    if not isinstance(flight_id, str) or not SAFE.fullmatch(flight_id):
        raise ValueError("Voo invalido: use apenas letras, numeros, '-' e '_' (1-64 caracteres)")
    return flight_id


def output_dir(root, flight_id):
    return Path(root) / "ortomosaicos" / validated_flight(flight_id)


def state_file(root, flight_id):
    return output_dir(root, flight_id) / "processamento.json"


def read_state(root, flight_id):
    path = state_file(root, flight_id)
    if not path.is_file():
        return None
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        return record if isinstance(record, dict) else None
    except (OSError, ValueError):
        return None


def save_state(root, flight_id, **data):
    """Grava atualizacoes atomicamente, evitando JSON parcial no polling."""
    directory = output_dir(root, flight_id)
    directory.mkdir(parents=True, exist_ok=True)
    with _lock:
        state = read_state(root, flight_id) or {"flight_id": flight_id, "created_at": timestamp()}
        state.update(data, updated_at=timestamp())
        destination = state_file(root, flight_id)
        temp = destination.with_name("processamento." + uuid.uuid4().hex + ".tmp")
        try:
            temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(destination)
        finally:
            temp.unlink(missing_ok=True)
    return state


def _images(folder):
    """Encontra imagens originais sem exigir requests/WebODM instalado no catalogo."""
    base = Path(folder)
    if not base.is_dir():
        raise ValueError("Pasta do voo nao encontrada")
    images = sorted(path for path in base.rglob("*")
        if path.is_file() and path.suffix.lower() in EXT
        and not path.name.startswith(".")
        and not path.name.lower().startswith(("ndvi_", "heatmap_", "mascara_",
                                             "mapa_areas_", "red_preview", "nir_preview"))
        and is_capture_path(path.relative_to(base)))
    if not 2 <= len(images) <= MAX_IMAGES:
        raise ValueError("O voo precisa conter entre 2 e 600 fotografias originais")
    names = [path.name.casefold() for path in images]
    if len(names) != len(set(names)):
        raise ValueError("Fotos com nomes repetidos em subpastas; reorganize a pasta")
    return images


def list_sources(root, here):
    sources = []
    for label, base in (("data", Path(here) / "data"),
                        ("upload", Path(root) / "voos_originais")):
        if not base.is_dir():
            continue
        for folder in sorted(base.iterdir()):
            if not folder.is_dir() or not SAFE.fullmatch(folder.name):
                continue
            try:
                images = _images(folder)
            except ValueError:
                continue
            sources.append({"flight_id": folder.name, "source": label, "images_count": len(images)})
    return sources


def resolve_source(root, here, flight_id, source):
    validated_flight(flight_id)
    if source == "data":
        folder = Path(here) / "data" / flight_id
    elif source == "upload":
        folder = Path(root) / "voos_originais" / flight_id
    else:
        raise ValueError("Origem invalida")
    if not folder.is_dir():
        raise ValueError("Pasta do voo nao encontrada; use a lista de voos disponiveis")
    return _images(folder)


def import_zip(upload_path, root, flight_id):
    """Importa ZIP de fotos originais sem modificar bytes, nomes ou metadados."""
    validated_flight(flight_id)
    base = Path(root) / "voos_originais"
    base.mkdir(parents=True, exist_ok=True)
    target = base / flight_id
    if target.exists():
        raise ValueError("Este voo ja existe em voos_originais; escolha outro identificador")
    staging = base / (".import_" + uuid.uuid4().hex)
    staging.mkdir()
    try:
        with zipfile.ZipFile(upload_path) as archive:
            members = [x for x in archive.infolist()
                       if not x.is_dir() and Path(x.filename).suffix.lower() in EXT
                       and is_capture_path(x.filename)]
            if len(members) < 2 or len(members) > MAX_IMAGES:
                raise ValueError("O ZIP deve conter de 2 a 600 fotos originais")
            if sum(x.file_size for x in members) > MAX_UNCOMPRESSED:
                raise ValueError("ZIP descompactado excede 1,4 GiB")
            names = set()
            for item in members:
                if item.file_size > MAX_MEMBER:
                    raise ValueError("Uma imagem excede 80 MiB")
                parts = item.filename.replace("\\", "/").split("/")
                if ".." in parts or item.filename.startswith(("/", "\\")):
                    raise ValueError("Caminho invalido no ZIP")
                if item.flag_bits & 0x1:
                    raise ValueError("ZIP criptografado nao suportado")
                name = Path(parts[-1]).name
                if not name or name.casefold() in names:
                    raise ValueError("Fotos com nomes duplicados; revise a estrutura do ZIP")
                names.add(name.casefold())
                with archive.open(item) as source, (staging / name).open("wb") as dest:
                    shutil.copyfileobj(source, dest, 1024 * 1024)
        images = _images(staging)
        staging.rename(target)
        return {"flight_id": flight_id, "images_count": len(images), "source": "upload"}
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def _credentials():
    address = os.getenv("WEBODM_URL", "http://127.0.0.1:8000").rstrip("/")
    username = os.getenv("WEBODM_USER", "")
    password = os.getenv("WEBODM_PASSWORD", "")
    if not username or not password:
        raise ValueError("Configure WEBODM_USER e WEBODM_PASSWORD no terminal do app.py")
    if not address.startswith(("http://", "https://")):
        raise ValueError("WEBODM_URL deve ser http(s)")
    return address, username, password


def check_webodm_connection():
    """Testa as credenciais do PROCESSO app.py, sem expor senha ou token ao navegador."""
    from webodm_ortomosaico import authenticate, WebODMError
    address, username, password = _credentials()
    try:
        authenticate(address, username, password)
    except WebODMError as exc:
        if "HTTP 400" in str(exc) or "HTTP 401" in str(exc):
            raise ValueError(
                "O WebODM recusou WEBODM_USER/WEBODM_PASSWORD do processo app.py. "
                "A chave API do AgroDT é diferente. Configure o usuário e a senha "
                "reais no mesmo terminal e reinicie app.py."
            ) from exc
        raise ValueError("Falha na API WebODM. Confira a URL e o servidor em execução.") from exc
    except Exception as exc:
        raise ValueError(
            "Não foi possível conectar ao WebODM. Verifique se a porta 8000 está ativa."
        ) from exc
    return {"status": "connected", "message": "Autenticação com WebODM confirmada"}


def _webodm_progress(task):
    for field in ("running_progress", "resize_progress", "upload_progress"):
        try:
            value = float(task.get(field) or 0)
            if value > 0:
                return min(99, max(0, int(value * 100 if value <= 1 else value)))
        except (TypeError, ValueError):
            pass
    return 0


def _worker(root, flight_id, image_paths=None):
    try:
        from orthomosaic_catalog import build_preview
        from webodm_ortomosaico import (authenticate, project, create_task,
                                        task_status, download_orthophoto)
        address, username, password = _credentials()
        try:
            token = authenticate(address, username, password)
        except Exception as exc:
            if "HTTP 400" in str(exc) or "HTTP 401" in str(exc):
                raise ValueError("Login WebODM recusado: WEBODM_USER e WEBODM_PASSWORD pertencem ao processo app.py; confira e reinicie o servidor.") from exc
            raise
        state = read_state(root, flight_id) or {}
        pid, tid = state.get("project_id"), state.get("task_id")
        if not pid or not tid:
            if not image_paths:
                raise ValueError("Nao ha fotos locais para reenviar esta tarefa")
            save_state(root, flight_id, status="submitting",
                       message="Enviando fotos originais ao WebODM")
            pid = project(token, address, flight_id)
            tid = create_task(token, address, pid, image_paths, flight_id,
                              profile=state.get("profile", "low_memory"))
            save_state(root, flight_id, project_id=pid, task_id=tid,
                       status="processing", message="Tarefa criada; acompanhando WebODM")
        while True:
            task = task_status(token, address, pid, tid)
            status = task.get("status")
            if status == 40:
                break
            if status in (30, 50):
                raise RuntimeError("WebODM encerrou a tarefa: " +
                                   str(task.get("last_error") or status))
            save_state(root, flight_id, status="processing", webodm_status=status,
                       progress=_webodm_progress(task), message="WebODM processando voo")
            time.sleep(10)
        save_state(root, flight_id, status="downloading", progress=99,
                   message="Baixando ortomosaico do WebODM")
        out = output_dir(root, flight_id) / "orthophoto.tif"
        download_orthophoto(token, address, pid, tid, out)
        save_state(root, flight_id, status="generating_preview", progress=99,
                   message="Criando previa PNG para o painel")
        try:
            info = build_preview(out)
            save_state(root, flight_id, bands=info.get("bands"),
                       width=info.get("width"), height=info.get("height"),
                       crs=info.get("crs"))
        except Exception as exc:
            save_state(root, flight_id, preview_message="Previa indisponivel: " + str(exc)[:180])
        save_state(root, flight_id, status="calculating_ndvi", progress=99,
                   message="Identificando bandas RED/NIR do ortomosaico...")
        from orthomosaic_ndvi import calculate_orthomosaic_ndvi, BandSelectionRequired
        try:
            ndvi_report = calculate_orthomosaic_ndvi(out, out.parent)
            save_state(root, flight_id, status="completed", progress=100,
                       ndvi_status="ready", ndvi_report=ndvi_report,
                       message="Ortomosaico e NDVI prontos no painel")
        except BandSelectionRequired as exc:
            save_state(root, flight_id, status="completed", progress=100,
                       ndvi_status="needs_bands", ndvi_message=str(exc)[:300],
                       message="Ortomosaico pronto; selecione RED/NIR para calcular NDVI")
        except Exception as exc:
            save_state(root, flight_id, status="completed", progress=100,
                       ndvi_status="failed", ndvi_message=str(exc)[:300],
                       message="Ortomosaico pronto; falha ao calcular NDVI")
    except Exception as exc:
        save_state(root, flight_id, status="failed", message=str(exc)[:300])
    finally:
        with _lock:
            _workers.pop(flight_id, None)


def calculate_existing_ndvi(root, flight_id, red_index, nir_index):
    """Calculo sob demanda para o GeoTIFF existente, sem reenviar fotos ao WebODM."""
    from orthomosaic_ndvi import calculate_orthomosaic_ndvi
    validated_flight(flight_id)
    with _lock:
        state = read_state(root, flight_id) or {}
        if state.get("status") in ACTIVE:
            raise ValueError("A tarefa WebODM ainda esta em andamento")
        source = output_dir(root, flight_id) / "orthophoto.tif"
        if not source.is_file():
            raise ValueError("Ortomosaico nao encontrado; conclua o processamento WebODM primeiro")
        if state.get("ndvi_status") == "processing":
            raise ValueError("O NDVI deste voo ja esta sendo calculado")
        save_state(root, flight_id, ndvi_status="processing", ndvi_message="Calculando NDVI...")
    try:
        result = calculate_orthomosaic_ndvi(source, source.parent, red_index, nir_index)
        save_state(root, flight_id, ndvi_status="ready", ndvi_report=result,
                   ndvi_message="NDVI do ortomosaico pronto")
        return result
    except Exception as exc:
        save_state(root, flight_id, ndvi_status="failed", ndvi_message=str(exc)[:300])
        raise


def start_job(root, here, flight_id, source="data", retry=False, profile="low_memory"):
    if profile not in ("low_memory", "standard"):
        raise ValueError("Perfil WebODM invalido")
    validated_flight(flight_id)
    with _lock:
        active_thread = _workers.get(flight_id)
        if active_thread and active_thread.is_alive():
            raise ValueError("Este voo ja esta em processamento")
        old = read_state(root, flight_id)
        if old and old.get("status") in ACTIVE:
            raise ValueError("Este voo ja possui uma tarefa ativa; consulte o estado")
        if old and old.get("status") == "completed" and not retry:
            raise ValueError("Ortomosaico ja concluido para este voo")
        if (output_dir(root, flight_id) / "orthophoto.tif").exists() and not retry:
            raise ValueError("Este voo ja possui um ortomosaico; nao sera sobrescrito")
        paths = resolve_source(root, here, flight_id, source)
        save_state(root, flight_id, status="queued", progress=0,
                   message="Aguardando WebODM", project_id=None, task_id=None,
                   images_count=len(paths), source=source, profile=profile)
        worker = threading.Thread(target=_worker, args=(root, flight_id, paths),
                                  daemon=True, name="webodm-" + flight_id)
        _workers[flight_id] = worker
        worker.start()
    return read_state(root, flight_id)


def resume_jobs(root):
    """Apos reiniciar servidor, continua acompanhamento de tarefas ja criadas."""
    base = Path(root) / "ortomosaicos"
    if not base.is_dir():
        return
    for folder in base.iterdir():
        if not folder.is_dir() or not SAFE.fullmatch(folder.name):
            continue
        state = read_state(root, folder.name)
        if not state or state.get("status") not in ACTIVE:
            continue
        if not state.get("project_id") or not state.get("task_id"):
            save_state(root, folder.name, status="failed",
                       message="Servidor reiniciado durante o envio. Confirme a tarefa no WebODM e reenvie se necessario.")
            continue
        with _lock:
            if folder.name not in _workers:
                thread = threading.Thread(target=_worker, args=(root, folder.name),
                                          daemon=True)
                _workers[folder.name] = thread
                thread.start()
