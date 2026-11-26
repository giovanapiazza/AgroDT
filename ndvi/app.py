#!/usr/bin/env python3
"""AgroDT NDVI: recepcao HTTP, analise, SQLite e interface web."""
from __future__ import annotations
import argparse
from io import BytesIO
import zipfile
from collections import deque
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default as mime_policy
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import threading
import time
import uuid
from urllib.parse import unquote, urlsplit
import numpy as np
from PIL import Image, ImageDraw
from image_importer import find_pairs, read_zip, extract_single_band, make_tiff
from orthomosaic_catalog import list_mosaics
from orthomosaic_dashboard import (list_sources as list_orthomosaic_sources,
    import_zip as import_flight_zip, start_job as start_orthomosaic_job,
    resume_jobs as resume_orthomosaic_jobs, read_state as read_orthomosaic_state,
    calculate_existing_ndvi, MAX_ZIP as MAX_FLIGHT_ZIP)

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("AGRODT_NDVI_DATA", HERE / "armazenamento")).resolve()
API_KEY = os.environ.get("AGRODT_API_KEY", "")
SAFE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
EXT = {".png", ".tif", ".tiff"}
MAX_UPLOAD = 60 * 1024 * 1024
MAX_ZIP_UPLOAD = 128 * 1024 * 1024
MAX_ZIP_UNPACKED = 300 * 1024 * 1024
MAX_PIXELS = 8_000_000
LOW_NDVI = float(os.environ.get("AGRODT_NDVI_LIMIAR", "0.40"))
MIN_REGION = max(1, int(os.environ.get("AGRODT_NDVI_MIN_PIXELS", "40")))

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def safe_id(value, name):
    if not SAFE.fullmatch(value or ""):
        raise ValueError(f"{name}: utilize 1-64 letras, numeros, '_' ou '-'.")
    return value

def connection():
    ROOT.joinpath("dados").mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(ROOT / "dados" / "capturas.sqlite3", timeout=20)
    db.row_factory = sqlite3.Row
    return db

def init_db():
    for sub in ("entrada", "analisadas", "processadas", "erros", "dados"):
        (ROOT / sub).mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS captures (
          capture_id TEXT PRIMARY KEY, flight_id TEXT NOT NULL,
          created_at TEXT NOT NULL, captured_at TEXT, latitude REAL, longitude REAL,
          status TEXT NOT NULL, mean_ndvi REAL, min_ndvi REAL, max_ndvi REAL,
          valid_pixels INTEGER, attention_pixels INTEGER, vegetation_pixels INTEGER,
          attention_pct REAL, regions_count INTEGER, width INTEGER, height INTEGER,
          error_message TEXT, processing_seconds REAL
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_flight ON captures(flight_id, created_at)")
        db.execute("""CREATE TABLE IF NOT EXISTS regions (
          capture_id TEXT NOT NULL, region_number INTEGER NOT NULL,
          pixels INTEGER NOT NULL, mean_ndvi REAL,
          center_x_px REAL, center_y_px REAL,
          x0 INTEGER, y0 INTEGER, x1 INTEGER, y1 INTEGER,
          PRIMARY KEY(capture_id, region_number)
        )""")

def get_capture(capture_id):
    with connection() as db:
        row = db.execute("SELECT * FROM captures WHERE capture_id=?", (capture_id,)).fetchone()
        return dict(row) if row else None

def add_capture(capture_id, flight_id, metadata=None):
    metadata = metadata or {}
    def coordinate(key, bound):
        val = metadata.get(key)
        if val in (None, ""):
            return None
        result = float(val)
        if not np.isfinite(result) or abs(result) > bound:
            raise ValueError(f"{key}: coordenada fora da faixa")
        return result
    with connection() as db:
        db.execute("""INSERT INTO captures
            (capture_id,flight_id,created_at,captured_at,latitude,longitude,status)
            VALUES(?,?,?,?,?,?,?)""", (capture_id, flight_id, utc_now(),
                  metadata.get("captured_at"), coordinate("latitude", 90),
                  coordinate("longitude", 180), "received"))

def read_band(path):
    with Image.open(path) as im:
        if getattr(im, "n_frames", 1) != 1 or len(im.getbands()) != 1:
            raise ValueError("RED e NIR precisam ser imagens de banda unica, nao RGB")
        pixels = np.asarray(im)
    if pixels.ndim != 2 or pixels.size > MAX_PIXELS:
        raise ValueError("Dimensao invalida ou acima de 8 milhoes de pixels")
    if not np.issubdtype(pixels.dtype, np.number):
        raise ValueError("Imagem precisa conter valores numericos")
    return pixels.astype(np.float32)

def calculate_ndvi(red, nir):
    if red.shape != nir.shape:
        raise ValueError("RED e NIR devem ter as mesmas dimensoes e estar alinhadas")
    valid = np.isfinite(red) & np.isfinite(nir) & (red >= 0) & (nir >= 0) & ((red + nir) > 0)
    ndvi = np.full(red.shape, np.nan, dtype=np.float32)
    np.divide(nir - red, nir + red, out=ndvi, where=valid)
    return ndvi

def ndvi_image(ndvi):
    valid = np.isfinite(ndvi)
    scaled = np.clip((np.nan_to_num(ndvi, nan=-1.0) + 1.0) / 2.0, 0, 1)
    rgb = np.empty((*ndvi.shape, 3), dtype=np.uint8)
    rgb[:, :, 0] = np.uint8(255 * (1.0 - scaled))
    rgb[:, :, 1] = np.uint8(220 * scaled)
    rgb[:, :, 2] = np.uint8(70 * (1.0 - scaled))
    rgb[~valid] = [68, 73, 83]
    return Image.fromarray(rgb, "RGB")

def band_preview(band):
    """Previa PNG de contraste ajustado para visualizar TIFF de 16 bits no navegador."""
    good = band[np.isfinite(band)]
    if not good.size:
        return Image.fromarray(np.zeros(band.shape, dtype=np.uint8), "L")
    low, high = np.percentile(good, [2, 98])
    if high <= low:
        high = low + 1
    values = np.clip((band - low) / (high - low), 0, 1)
    return Image.fromarray((np.nan_to_num(values) * 255).astype(np.uint8), "L")


def heatmap_ndvi(ndvi):
    """Mapa de calor por pixel: vermelho (baixo), amarelo (medio), verde (alto)."""
    valid = np.isfinite(ndvi)
    points = np.array([-1.0, 0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    colors = np.array([
        [115, 35, 65], [220, 60, 50], [244, 114, 50],
        [246, 205, 62], [130, 200, 70], [28, 145, 78], [8, 96, 70]
    ], dtype=np.float32)
    values = np.nan_to_num(ndvi, nan=-1.0).clip(-1, 1)
    rgb = np.stack([np.interp(values, points, colors[:, index])
                    for index in range(3)], axis=-1).astype(np.uint8)
    rgb[~valid] = [68, 73, 83]
    return Image.fromarray(rgb, "RGB")


def detect_regions(ndvi):
    """Agrupamentos de NDVI baixo sao alertas exploratorios, nao diagnosticos."""
    valid = np.isfinite(ndvi)
    vegetation = valid & (ndvi > 0.20)
    baseline = float(np.median(ndvi[vegetation])) if vegetation.any() else 0.0
    attention = vegetation & ((ndvi < LOW_NDVI) | (ndvi < baseline - 0.15))
    h, w = ndvi.shape
    seen = np.zeros((h, w), dtype=bool)
    regions = []
    for yy, xx in zip(*np.nonzero(attention)):
        y, x = int(yy), int(xx)
        if seen[y, x]:
            continue
        seen[y, x] = True
        queue = deque([(y, x)])
        pixels = 0
        sx = sy = sn = 0.0
        x0 = x1 = x
        y0 = y1 = y
        while queue:
            cy, cx = queue.popleft()
            pixels += 1
            sx += cx
            sy += cy
            sn += float(ndvi[cy, cx])
            x0, x1 = min(x0, cx), max(x1, cx)
            y0, y1 = min(y0, cy), max(y1, cy)
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < h and 0 <= nx < w and attention[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        if pixels >= MIN_REGION:
            regions.append({"region_number": len(regions) + 1, "pixels": pixels,
                            "mean_ndvi": round(sn / pixels, 5),
                            "center_x_px": round(sx / pixels, 2),
                            "center_y_px": round(sy / pixels, 2),
                            "x0": x0, "y0": y0, "x1": x1, "y1": y1})
    return regions, attention, int(vegetation.sum()), baseline

def process_capture(capture_id):
    record = get_capture(capture_id)
    if not record or record["status"] != "received":
        raise ValueError("Captura nao encontrada ou ja processada")
    flight_id = record["flight_id"]
    inbox = ROOT / "entrada" / flight_id / capture_id
    output = ROOT / "analisadas" / flight_id / capture_id
    failed = ROOT / "erros" / flight_id / capture_id
    start = time.perf_counter()
    with connection() as db:
        db.execute("UPDATE captures SET status='processing' WHERE capture_id=?", (capture_id,))
    try:
        redfile = next((p for p in inbox.iterdir() if p.stem.lower() == "red" and p.suffix.lower() in EXT), None)
        nirfile = next((p for p in inbox.iterdir() if p.stem.lower() == "nir" and p.suffix.lower() in EXT), None)
        if not redfile or not nirfile:
            raise ValueError("Par RED/NIR incompleto")
        red, nir = read_band(redfile), read_band(nirfile)
        ndvi = calculate_ndvi(red, nir)
        band_preview(red).save(inbox / "red_preview.png")
        band_preview(nir).save(inbox / "nir_preview.png")
        valid = np.isfinite(ndvi)
        if not valid.any():
            raise ValueError("Nao existem pixels NDVI validos")
        regions, attention, vegetation_pixels, baseline = detect_regions(ndvi)
        vals = ndvi[valid]
        summary = {"capture_id": capture_id, "flight_id": flight_id,
                   "mean_ndvi": float(vals.mean()), "min_ndvi": float(vals.min()),
                   "max_ndvi": float(vals.max()), "valid_pixels": int(valid.sum()),
                   "vegetation_pixels": vegetation_pixels,
                   "attention_pixels": int(attention.sum()),
                   "attention_pct": round(100 * float(attention.sum()) / max(vegetation_pixels, 1), 2),
                   "regions_count": len(regions), "vegetation_median_ndvi": baseline,
                   "note": "NDVI baixo sinaliza possivel estresse, nao comprova deficiencia de nutrientes."}
        np.save(inbox / "ndvi_valores.npy", ndvi)
        ndvi_image(ndvi).save(inbox / "ndvi_mapa.png")
        heatmap_ndvi(ndvi).save(inbox / "heatmap_ndvi.png")
        Image.fromarray((attention * 255).astype(np.uint8), "L").save(inbox / "mascara_atencao.png")
        colored = ndvi_image(ndvi)
        draw = ImageDraw.Draw(colored)
        for region in regions:
            draw.rectangle((region["x0"], region["y0"], region["x1"], region["y1"]), outline=(255, 255, 255), width=2)
        colored.save(inbox / "mapa_areas_atencao.png")
        (inbox / "areas_atencao.json").write_text(json.dumps(regions, indent=2, ensure_ascii=False), encoding="utf-8")
        (inbox / "resumo.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        (inbox / "originais").mkdir()
        shutil.move(str(redfile), str(inbox / "originais" / redfile.name))
        shutil.move(str(nirfile), str(inbox / "originais" / nirfile.name))
        output.parent.mkdir(parents=True, exist_ok=True)
        inbox.rename(output)
        with connection() as db:
            db.execute("""UPDATE captures SET status='processed', mean_ndvi=?,min_ndvi=?,max_ndvi=?,
                        valid_pixels=?,attention_pixels=?,vegetation_pixels=?,attention_pct=?,
                        regions_count=?,width=?,height=?,processing_seconds=? WHERE capture_id=?""",
                       (summary["mean_ndvi"], summary["min_ndvi"], summary["max_ndvi"],
                        summary["valid_pixels"], summary["attention_pixels"], vegetation_pixels,
                        summary["attention_pct"], len(regions), ndvi.shape[1], ndvi.shape[0],
                        time.perf_counter() - start, capture_id))
            db.executemany("""INSERT INTO regions
                (capture_id,region_number,pixels,mean_ndvi,center_x_px,center_y_px,x0,y0,x1,y1)
                VALUES(?,?,?,?,?,?,?,?,?,?)""",
                [(capture_id, r["region_number"], r["pixels"], r["mean_ndvi"], r["center_x_px"],
                  r["center_y_px"], r["x0"], r["y0"], r["x1"], r["y1"]) for r in regions])
        return summary
    except Exception as exc:
        failed.parent.mkdir(parents=True, exist_ok=True)
        if inbox.exists():
            if failed.exists():
                shutil.rmtree(failed)
            inbox.rename(failed)
        with connection() as db:
            db.execute("UPDATE captures SET status='failed',error_message=?,processing_seconds=? WHERE capture_id=?",
                       (str(exc), time.perf_counter() - start, capture_id))
        raise

def parse_multipart(content_type, content):
    if not content_type.lower().startswith("multipart/form-data;"):
        raise ValueError("Envie RED e NIR por multipart/form-data")
    message = BytesParser(policy=mime_policy).parsebytes(
        b"MIME-Version: 1.0\r\nContent-Type: " + content_type.encode("latin-1") + b"\r\n\r\n" + content)
    if not message.is_multipart():
        raise ValueError("Multipart invalido")
    fields, files = {}, {}
    for item in message.iter_parts():
        if item.get_content_disposition() != "form-data":
            continue
        name = item.get_param("name", header="content-disposition")
        if name in ("red", "nir"):
            if name in files:
                raise ValueError("Banda duplicada")
            extension = Path(item.get_filename() or "").suffix.lower()
            if extension not in EXT:
                raise ValueError("Use arquivos PNG ou TIFF para RED/NIR")
            files[name] = (extension, item.get_payload(decode=True))
        elif name in ("capture_id", "flight_id", "captured_at", "latitude", "longitude"):
            fields[name] = (item.get_payload(decode=True) or b"").decode("utf-8")
    if set(files) != {"red", "nir"} or not all(data for _, data in files.values()):
        raise ValueError("Envie um par RED + NIR nao vazio")
    return fields, files

def preserve_original_zip(payload, flight_id):
    """Guarda bytes originais do voo para WebODM; nao usa TIFFs NDVI intermediarios."""
    tmpfolder = ROOT / "temporarios"
    tmpfolder.mkdir(parents=True, exist_ok=True)
    tmp = tmpfolder / (uuid.uuid4().hex + ".zip")
    try:
        tmp.write_bytes(payload)
        return import_flight_zip(tmp, ROOT, flight_id)
    finally:
        tmp.unlink(missing_ok=True)

def import_generic_zip(payload, flight_id, profile="auto"):
    """Identifica e processa pares RED/NIR de arquivos ZIP de sensores distintos."""
    flight_id = safe_id(flight_id, "flight_id")
    files = read_zip(payload)
    pairs, warnings = find_pairs(files, profile=profile)
    if len(pairs) > 100:
        raise ValueError("Limite de 100 pares por ZIP")
    if not pairs:
        raise ValueError("; ".join(warnings))
    imported, failures = [], []
    for pair in pairs:
        capture_id = "img_" + uuid.uuid4().hex[:16]
        inbox = ROOT / "entrada" / flight_id / capture_id
        try:
            red_name, nir_name = pair.red_name, pair.nir_name
            red = extract_single_band(files[red_name], Path(red_name).suffix)
            nir = extract_single_band(files[nir_name], Path(nir_name).suffix)
            if red.shape != nir.shape:
                raise ValueError("RED e NIR precisam ter mesmas dimensoes; verifique alinhamento")
            add_capture(capture_id, flight_id)
            inbox.mkdir(parents=True, exist_ok=False)
            (inbox / "red.tif").write_bytes(make_tiff(red))
            (inbox / "nir.tif").write_bytes(make_tiff(nir))
            summary = process_capture(capture_id)
            imported.append({"capture_id": capture_id, "source": pair.capture,
                             "red": red_name, "nir": nir_name,
                             "mean_ndvi": summary["mean_ndvi"]})
        except Exception as exc:
            failures.append({"source": pair.capture, "error": str(exc)})
            print("Falha ao importar par:", pair.capture, exc, flush=True)
    return {"processed": len(imported), "failed": len(failures),
            "captures": imported, "errors": failures, "warnings": warnings,
            "note": "Importacao automatica nao garante alinhamento ou calibracao; confira antes de interpretar NDVI."}


def import_sequoia_zip(payload, flight_id):
    """Mantem API de testes e codigo anteriores para ZIP Sequoia."""
    return import_generic_zip(payload, flight_id, profile="sequoia")


def import_multiband(payload, flight_id, ext, red_index, nir_index):
    """Extrai as bandas escolhidas explicitamente de um GeoTIFF/JP2 multibanda."""
    flight_id = safe_id(flight_id, "flight_id")
    if ext.lower() not in (".tif", ".tiff", ".jp2", ".j2k"):
        raise ValueError("Use TIFF ou JP2 multibanda")
    if red_index == nir_index:
        raise ValueError("Selecione bandas RED e NIR distintas")
    red = extract_single_band(payload, ext, red_index, force_raster=True)
    nir = extract_single_band(payload, ext, nir_index, force_raster=True)
    if red.shape != nir.shape:
        raise ValueError("As bandas precisam ter as mesmas dimensoes")
    capture_id = "multi_" + uuid.uuid4().hex[:16]
    add_capture(capture_id, flight_id)
    inbox = ROOT / "entrada" / flight_id / capture_id
    inbox.mkdir(parents=True, exist_ok=False)
    (inbox / "red.tif").write_bytes(make_tiff(red))
    (inbox / "nir.tif").write_bytes(make_tiff(nir))
    summary = process_capture(capture_id)
    return {"status": "processed", "capture_id": capture_id, **summary,
            "note": "Bandas selecionadas pelo usuario. Calibracao e alinhamento nao foram verificados."}


def list_captures(limit=200):
    with connection() as db:
        return [dict(row) for row in db.execute(
            "SELECT * FROM captures ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,))]

def capture_details(capture_id):
    capture = get_capture(capture_id)
    if capture is None:
        return None
    with connection() as db:
        capture["regions"] = [dict(r) for r in db.execute(
            "SELECT * FROM regions WHERE capture_id=? ORDER BY pixels DESC", (capture_id,))]
    return capture

def register_manual_pairs():
    for flight in (ROOT / "entrada").iterdir():
        if not flight.is_dir() or not SAFE.fullmatch(flight.name):
            continue
        for folder in flight.iterdir():
            if not folder.is_dir() or not SAFE.fullmatch(folder.name) or get_capture(folder.name):
                continue
            images = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in EXT]
            if not {"red", "nir"} <= {p.stem.lower() for p in images}:
                continue
            if any(time.time() - p.stat().st_mtime < 2 for p in images):
                continue
            try:
                add_capture(folder.name, flight.name)
                process_capture(folder.name)
            except (ValueError, sqlite3.IntegrityError):
                pass
            except Exception as exc:
                print("Erro ao processar pasta:", folder, exc, flush=True)

def watch_folder():
    while True:
        try:
            register_manual_pairs()
        except Exception as exc:
            print("Falha temporaria no monitor:", exc, flush=True)
        time.sleep(3)

class Handler(BaseHTTPRequestHandler):
    def json_response(self, status, value):
        data = json.dumps(value, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_path(self, path, mime):
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == "/" or path == "/index.html":
            return self.serve_path(HERE / "templates" / "index.html", "text/html; charset=utf-8")
        if path == "/health":
            return self.json_response(200, {"status": "ok", "service": "agrodt-ndvi"})
        if path == "/api/v1/orthomosaics/connection":
            try:
                from orthomosaic_dashboard import check_webodm_connection
                return self.json_response(200, check_webodm_connection())
            except Exception as exc:
                return self.json_response(503, {"status": "disconnected", "error": str(exc)[:300]})
        if path == "/api/v1/orthomosaics/sources":
            return self.json_response(200, {"sources": list_orthomosaic_sources(ROOT, HERE)})
        if path.startswith("/api/v1/orthomosaics/bands/"):
            flight = path.removeprefix("/api/v1/orthomosaics/bands/")
            if not SAFE.fullmatch(flight):
                return self.json_response(400, {"error": "Voo invalido"})
            source = ROOT / "ortomosaicos" / flight / "orthophoto.tif"
            if not source.is_file():
                return self.json_response(404, {"error": "Ortomosaico nao encontrado"})
            try:
                from orthomosaic_ndvi import inspect_bands
                return self.json_response(200, {"flight_id": flight, "bands": inspect_bands(source)})
            except Exception as exc:
                return self.json_response(422, {"error": str(exc)[:250]})
        if path == "/api/v1/orthomosaics":
            mosaics = list_mosaics(ROOT)
            for mosaic in mosaics:
                state = read_orthomosaic_state(ROOT, mosaic["flight_id"])
                if state:
                    mosaic.update({k: state[k] for k in ("status", "message",
                        "progress", "project_id", "task_id", "updated_at", "source",
                        "ndvi_status", "ndvi_message")
                        if k in state})
            return self.json_response(200, {"orthomosaics": mosaics})
        if path.startswith("/api/v1/orthomosaics/"):
            flight_id = path.removeprefix("/api/v1/orthomosaics/")
            mosaics = {item["flight_id"]: item for item in list_mosaics(ROOT)}
            if SAFE.fullmatch(flight_id) and flight_id in mosaics:
                state = read_orthomosaic_state(ROOT, flight_id)
                if state:
                    mosaics[flight_id].update({k: state[k] for k in ("status", "message",
                        "progress", "project_id", "task_id", "updated_at", "source")
                        if k in state})
                return self.json_response(200, mosaics[flight_id])
            return self.json_response(404, {"error": "Ortomosaico nao encontrado"})
        if path.startswith("/orthomosaics/"):
            parts = path.strip("/").split("/")
            if len(parts) == 3:
                _, flight_id, filename = parts
                if SAFE.fullmatch(flight_id) and filename in (
                    "preview.png", "ortomosaico_info.json", "ndvi_ortomosaico.png", "ndvi_ortomosaico.json"):
                    target = ROOT / "ortomosaicos" / flight_id / filename
                    if target.is_file():
                        mime = "image/png" if filename.endswith(".png") else "application/json; charset=utf-8"
                        return self.serve_path(target, mime)
        if path == "/api/v1/captures":
            return self.json_response(200, {"captures": list_captures()})
        if path.startswith("/api/v1/captures/"):
            capture_id = path.removeprefix("/api/v1/captures/")
            detail = capture_details(capture_id) if SAFE.fullmatch(capture_id) else None
            return self.json_response(200, detail) if detail else self.json_response(404, {"error": "Captura inexistente"})
        if path.startswith("/media/"):
            parts = path.strip("/").split("/")
            if len(parts) == 3:
                _, capture_id, filename = parts
                capture = get_capture(capture_id) if SAFE.fullmatch(capture_id) else None
                if capture and capture["status"] == "processed":
                    folder = ROOT / "analisadas" / capture["flight_id"] / capture_id
                    if not folder.exists():
                        folder = ROOT / "processadas" / capture["flight_id"] / capture_id
                    whitelist = {"red_preview.png", "nir_preview.png", "ndvi_mapa.png", "heatmap_ndvi.png", "mapa_areas_atencao.png", "mascara_atencao.png", "resumo.json", "areas_atencao.json"}
                    if filename in whitelist:
                        target = folder / filename
                    elif filename in ("red", "nir"):
                        target = next((p for p in (folder / "originais").glob(filename + ".*") if p.suffix.lower() in EXT), None)
                    else:
                        target = None
                    if target and target.is_file():
                        mime = "application/json" if target.suffix == ".json" else ("image/tiff" if target.suffix.lower() in (".tif", ".tiff") else "image/png")
                        return self.serve_path(target, mime)
        return self.json_response(404, {"error": "Recurso nao encontrado"})

    def do_POST(self):
        route = urlsplit(self.path).path
        if route not in ("/api/v1/captures", "/api/v1/import-zip",
                         "/api/v1/import-multiband", "/api/v1/orthomosaics/start",
                         "/api/v1/orthomosaics/upload", "/api/v1/orthomosaics/ndvi"):
            return self.json_response(404, {"error": "Rota nao encontrada"})
        if not API_KEY or not hmac.compare_digest(self.headers.get("X-API-Key", ""), API_KEY):
            return self.json_response(401, {"error": "Chave API ausente ou invalida"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if route == "/api/v1/orthomosaics/ndvi":
                if size <= 0 or size > 4096:
                    return self.json_response(413, {"error": "JSON invalido ou grande demais"})
                if self.headers.get("Content-Type", "").split(";")[0].lower() != "application/json":
                    return self.json_response(415, {"error": "Envie application/json"})
                try:
                    request = json.loads(self.rfile.read(size))
                except (ValueError, UnicodeDecodeError):
                    raise ValueError("JSON invalido")
                if not isinstance(request, dict):
                    raise ValueError("Envie objeto JSON")
                flight = safe_id(request.get("flight_id", ""), "flight_id")
                red_index = request.get("red_band")
                nir_index = request.get("nir_band")
                if red_index is None or nir_index is None:
                    raise ValueError("Selecione as duas bandas RED e NIR")
                result = calculate_existing_ndvi(ROOT, flight, red_index, nir_index)
                return self.json_response(200, {"flight_id": flight, "ndvi": result})
            if route == "/api/v1/orthomosaics/start":
                if size <= 0 or size > 4096:
                    return self.json_response(413, {"error": "JSON invalido ou grande demais"})
                if self.headers.get("Content-Type", "").split(";")[0].lower() != "application/json":
                    return self.json_response(415, {"error": "Envie application/json"})
                try:
                    command = json.loads(self.rfile.read(size))
                except (ValueError, UnicodeDecodeError):
                    raise ValueError("JSON invalido")
                if not isinstance(command, dict):
                    raise ValueError("Envie um objeto JSON")
                flight = safe_id(command.get("flight_id", ""), "flight_id")
                source = command.get("source", "data")
                if source not in ("data", "upload"):
                    raise ValueError("Origem invalida")
                state = start_orthomosaic_job(ROOT, HERE, flight, source=source)
                return self.json_response(202, {"job": state})
            if route == "/api/v1/orthomosaics/upload":
                if size <= 0 or size > MAX_FLIGHT_ZIP:
                    return self.json_response(413, {"error": "ZIP vazio ou acima de 600 MiB"})
                if self.headers.get("Content-Type", "").split(";")[0].lower() not in (
                    "application/zip", "application/octet-stream"):
                    return self.json_response(415, {"error": "Envie um ZIP original (application/zip)"})
                flight = safe_id(self.headers.get("X-Flight-ID", ""), "flight_id")
                # Gravacao incremental para nao alocar o ZIP inteiro em memoria.
                tmpdir = ROOT / "temporarios"
                tmpdir.mkdir(parents=True, exist_ok=True)
                tmppath = tmpdir / (uuid.uuid4().hex + ".zip")
                try:
                    remaining = size
                    with tmppath.open("wb") as destination:
                        while remaining:
                            chunk = self.rfile.read(min(1024 * 1024, remaining))
                            if not chunk:
                                raise ValueError("Upload ZIP incompleto")
                            destination.write(chunk)
                            remaining -= len(chunk)
                    imported = import_flight_zip(tmppath, ROOT, flight)
                finally:
                    tmppath.unlink(missing_ok=True)
                return self.json_response(201, {"flight": imported})
            if route == "/api/v1/import-multiband":
                if size <= 0 or size > MAX_UPLOAD:
                    return self.json_response(413, {"error": "Arquivo vazio ou acima de 60 MiB"})
                profile_flight = safe_id(self.headers.get("X-Flight-ID", "multibanda"), "flight_id")
                ext = self.headers.get("X-File-Extension", ".tif").lower()
                try:
                    red_index = int(self.headers.get("X-Red-Band", "0"))
                    nir_index = int(self.headers.get("X-Nir-Band", "0"))
                except ValueError as exc:
                    raise ValueError("Indices de banda devem ser inteiros") from exc
                result = import_multiband(self.rfile.read(size), profile_flight, ext, red_index, nir_index)
                return self.json_response(201, result)
            if route == "/api/v1/import-zip":
                if size <= 0 or size > MAX_ZIP_UPLOAD:
                    return self.json_response(413, {"error": "ZIP vazio ou acima de 128 MiB"})
                if self.headers.get("Content-Type", "").split(";")[0].lower() not in ("application/zip", "application/octet-stream"):
                    return self.json_response(415, {"error": "Envie ZIP com application/zip"})
                flight = safe_id(self.headers.get("X-Flight-ID", "sequoia_real"), "flight_id")
                profile = self.headers.get("X-Sensor-Profile", "auto").lower()
                if profile not in ("auto", "sequoia", "sentinel2", "micasense_rededge"):
                    raise ValueError("Perfil de sensor invalido")
                payload = self.rfile.read(size)
                result = import_generic_zip(payload, flight, profile=profile)
                result["flight_id"] = flight
                if result["processed"]:
                    try:
                        originals = preserve_original_zip(payload, flight)
                        result["originals_saved"] = True
                        result["original_images_count"] = originals["images_count"]
                    except (ValueError, OSError, zipfile.BadZipFile) as exc:
                        result["originals_saved"] = False
                        result["warnings"].append(
                            "NDVI individual foi processado, mas nao foi possivel preservar "
                            "as fotos originais do WebODM: " + str(exc))
                return self.json_response(201 if result["processed"] else 422, result)
            if size <= 0 or size > MAX_UPLOAD:
                return self.json_response(413, {"error": "Requisicao vazia ou acima de 60 MiB"})
            fields, files = parse_multipart(self.headers.get("Content-Type", ""), self.rfile.read(size))
            flight = safe_id(fields.get("flight_id", "voo_teste"), "flight_id")
            capture_id = safe_id(fields.get("capture_id", uuid.uuid4().hex[:16]), "capture_id")
            if get_capture(capture_id):
                return self.json_response(409, {"error": "capture_id ja cadastrado"})
            add_capture(capture_id, flight, fields)
            inbox = ROOT / "entrada" / flight / capture_id
            inbox.mkdir(parents=True, exist_ok=False)
            for name, (extension, data) in files.items():
                (inbox / (name + extension)).write_bytes(data)
            summary = process_capture(capture_id)
            return self.json_response(201, {"status": "processed", **summary})
        except sqlite3.IntegrityError:
            return self.json_response(409, {"error": "capture_id ja cadastrado"})
        except (ValueError, OSError, zipfile.BadZipFile) as exc:
            return self.json_response(422, {"error": str(exc)})
        except Exception as exc:
            print("Falha no processamento:", exc, flush=True)
            return self.json_response(500, {"error": "Falha interna durante o processamento"})

def main():
    parser = argparse.ArgumentParser(description="Receptor NDVI com painel web AgroDT")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if not API_KEY:
        parser.error("Defina AGRODT_API_KEY antes de iniciar o receptor")
    init_db()
    resume_orthomosaic_jobs(ROOT)
    threading.Thread(target=watch_folder, daemon=True).start()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"AgroDT NDVI: http://{args.host}:{args.port}  |  armazenamento: {ROOT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
