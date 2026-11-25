"""Reconhecimento conservador de bandas RED/NIR em ZIPs e imagens multiespectrais.

Nao adivinha bandas por sua posicao: arquivos ambiguos exigem selecao manual.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
import re
import zipfile

import numpy as np
from PIL import Image

VALID_SUFFIXES = {".tif", ".tiff", ".png", ".jp2", ".j2k"}
TOKEN_RED = {"RED", "VERMELHO", "B04", "B4"}
TOKEN_NIR = {"NIR", "NEARINFRARED", "INFRARED", "B08", "B8"}
TOKEN_OTHER = {"GRE", "GREEN", "REG", "RE", "REDEDGE", "RGB", "BLUE", "B02", "B03", "B05", "B06", "B07", "B8A"}
SUPPORTED_PROFILES = {"auto", "sequoia", "sentinel2", "micasense_rededge", "manual"}
MAX_MEMBERS = 1200
MAX_UNPACKED = 350 * 1024 * 1024
MAX_MEMBER = 60 * 1024 * 1024
MAX_PAIRS = 100


@dataclass
class Pair:
    capture: str
    red_name: str
    nir_name: str


def _tokens(name):
    return [x for x in re.split(r"[^A-Z0-9]+", name.upper()) if x]


def _metadata_band(payload):
    """Usa metadados declarativos; nao interpreta pixels como evidencias de banda."""
    try:
        with Image.open(BytesIO(payload)) as im:
            info = []
            for value in list(im.info.values()):
                if isinstance(value, str):
                    info.append(value)
            if hasattr(im, "tag_v2"):
                for code in (270, 285, 65000):
                    value = im.tag_v2.get(code)
                    if isinstance(value, str):
                        info.append(value)
            text = " ".join(info).upper()
            if re.search(r"(?:BAND.?NAME|BAND.?DESCRIPTION)\s*[:=]\s*(?:NIR|NEAR.?INFRARED)", text):
                return "nir"
            if re.search(r"(?:BAND.?NAME|BAND.?DESCRIPTION)\s*[:=]\s*RED\b", text):
                return "red"
    except (OSError, ValueError):
        pass
    return None


def classify(name, profile="auto", payload=None):
    """Retorna (banda, chave de captura) ou (None, None)."""
    if profile not in SUPPORTED_PROFILES:
        raise ValueError("Perfil de sensor desconhecido")
    path = PurePosixPath(name.replace("\\", "/"))
    if path.suffix.lower() not in VALID_SUFFIXES:
        return None, None
    stem = path.stem
    tokens = _tokens(stem)
    # Nao aceitar RGB ou RED_EDGE como RED por substring.
    if any(t in TOKEN_OTHER for t in tokens) and not any(t in TOKEN_RED | TOKEN_NIR for t in tokens):
        return None, None
    band = _metadata_band(payload) if payload else None
    chosen = [t for t in tokens if t in TOKEN_RED | TOKEN_NIR]
    if not band and len(chosen) == 1:
        t = chosen[0]
        if (t.startswith("B0") or t in {"B4", "B8"}) and profile not in {"auto", "sentinel2", "manual"}:
            return None, None
        band = "red" if t in TOKEN_RED else "nir"
        tokens.remove(t)
    elif band:
        if len(chosen) == 1:
            tokens.remove(chosen[0])
    if not band and profile == "micasense_rededge":
        # Indice numerico *somente* quando o perfil da camera for explicitamente informado.
        # RedEdge-M: 3=RED, 5=NIR; outros modelos podem usar mapeamentos diferentes.
        if tokens and tokens[-1] in {"3", "5"}:
            band = "red" if tokens[-1] == "3" else "nir"
            tokens.pop()
    if not band:
        folder_tokens = _tokens(path.parent.name)
        exact = [t for t in folder_tokens if t in TOKEN_RED | TOKEN_NIR]
        if len(exact) == 1:
            band = "red" if exact[0] in TOKEN_RED else "nir"
    if not band:
        return None, None
    # Nomes iguais em pastas de voos diferentes nao devem ser combinados.
    parent_parts = [p for p in path.parent.parts if p not in (".", "/", "")]
    parent_parts = [p for p in parent_parts if p.upper() not in TOKEN_RED | TOKEN_NIR]
    key = "/".join(parent_parts + ["_".join(tokens)]) or "capture"
    return band, key.lower()


def find_pairs(files, profile="auto"):
    """files: dict[nome_zip] = bytes; devolve (pares, avisos)."""
    buckets = defaultdict(lambda: {"red": [], "nir": []})
    unknown = []
    for name, payload in files.items():
        band, key = classify(name, profile, payload)
        if band:
            buckets[key][band].append(name)
        else:
            unknown.append(name)
    pairs, warnings = [], []
    for key, grouped in sorted(buckets.items()):
        if len(grouped["red"]) == len(grouped["nir"]) == 1:
            pairs.append(Pair(key, grouped["red"][0], grouped["nir"][0]))
        else:
            warnings.append(f"{key}: par RED/NIR incompleto ou ambiguo")
    if not pairs:
        warnings.append("Nenhum par seguro encontrado. Verifique nomes, metadados ou use selecao manual.")
    if unknown:
        warnings.append(f"{len(unknown)} arquivos nao identificados ou de outras bandas foram ignorados")
    return pairs, warnings


def read_zip(payload):
    """Le ZIP validando quantidade, nomes e descompactacao; sem gravar paths de usuario."""
    found = {}
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        members = [i for i in archive.infolist() if not i.is_dir()]
        if len(members) > MAX_MEMBERS or sum(i.file_size for i in members) > MAX_UNPACKED:
            raise ValueError("ZIP excede limites de seguranca")
        for item in members:
            path = PurePosixPath(item.filename)
            if path.is_absolute() or ".." in path.parts or item.file_size > MAX_MEMBER:
                raise ValueError("Arquivo invalido ou muito grande no ZIP")
            if path.suffix.lower() not in VALID_SUFFIXES:
                continue
            if item.filename in found:
                raise ValueError("ZIP contem caminhos duplicados")
            found[item.filename] = archive.read(item)
    return found


def extract_single_band(payload, ext, band_index=1, force_raster=False):
    """Le banda única com Pillow; opcionalmente Rasterio para JP2 e multibanda."""
    if not 1 <= band_index <= 64:
        raise ValueError("Indice de banda deve estar entre 1 e 64")
    if force_raster or ext.lower() in (".jp2", ".j2k") or band_index > 1:
        try:
            import rasterio
            from rasterio.io import MemoryFile
        except ImportError as exc:
            raise ValueError("Instale rasterio (requirements-geo.txt) para JP2/multibanda") from exc
        with MemoryFile(payload) as mem:
            with mem.open() as src:
                if band_index > src.count:
                    raise ValueError("Banda nao existe no arquivo")
                if src.width * src.height > 8_000_000:
                    raise ValueError("Imagem acima de 8 milhoes de pixels")
                data = src.read(band_index, masked=True).astype(np.float32)
                return np.ma.filled(data, np.nan)
    with Image.open(BytesIO(payload)) as im:
        if len(im.getbands()) != 1:
            raise ValueError("Arquivo multibanda requer selecao das bandas com Rasterio")
        values = np.asarray(im)
        if values.ndim != 2 or values.size > 8_000_000:
            raise ValueError("Dimensoes invalidas")
        return values.astype(np.float32)


def make_tiff(data):
    buf = BytesIO()
    Image.fromarray(np.asarray(data, dtype=np.float32)).save(buf, format="TIFF")
    return buf.getvalue()
