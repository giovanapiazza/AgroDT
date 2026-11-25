"""Catalogo e previsualizacao de ortomosaicos WebODM para o painel NDVI."""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
from PIL import Image

MAX_SIDE = 1400


def build_preview(tiff_path, png_path=None):
    """Gera PNG RGB de tamanho controlado a partir de GeoTIFF (nao e NDVI)."""
    source = Path(tiff_path)
    output = Path(png_path) if png_path else source.with_name("preview.png")
    try:
        import rasterio
        from rasterio.enums import Resampling
    except ImportError as exc:
        raise RuntimeError("Instale rasterio: pip install -r requirements-geo.txt") from exc
    with rasterio.open(source) as ds:
        if not ds.count:
            raise ValueError("GeoTIFF sem bandas")
        scale = min(1.0, MAX_SIDE / max(ds.width, ds.height))
        width = max(1, round(ds.width * scale))
        height = max(1, round(ds.height * scale))
        if ds.count >= 3:
            channels = [1, 2, 3]
        else:
            channels = [1, 1, 1]
        arrays = []
        for index in channels:
            band = ds.read(index, out_shape=(height, width),
                           resampling=Resampling.bilinear, masked=True)
            data = np.asarray(band, dtype=np.float32)
            valid = np.isfinite(data) & ~np.ma.getmaskarray(band)
            if not valid.any():
                arrays.append(np.zeros((height, width), dtype=np.uint8))
                continue
            low, high = np.percentile(data[valid], [2, 98])
            if high <= low:
                high = low + 1.0
            normalized = np.clip((data - low) / (high - low), 0, 1)
            arrays.append(np.where(valid, normalized * 255, 0).astype(np.uint8))
        img = Image.fromarray(np.stack(arrays, axis=-1), mode="RGB")
        output.parent.mkdir(parents=True, exist_ok=True)
        img.save(output)
        info = {"width": ds.width, "height": ds.height, "bands": ds.count,
                "crs": str(ds.crs) if ds.crs else None,
                "resolution": list(ds.res) if ds.crs else None,
                "preview_note": "Visualizacao RGB aproximada; cores nao sao NDVI e podem ser falsas se a ordem das bandas for diferente."}
    output.with_name("ortomosaico_info.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def list_mosaics(root):
    """Retorna apenas subpastas com nomes controlados, sem expor caminhos locais."""
    base = Path(root) / "ortomosaicos"
    if not base.is_dir():
        return []
    import re
    safe = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
    results = []
    for folder in sorted(base.iterdir(), reverse=True):
        if not folder.is_dir() or not safe.fullmatch(folder.name):
            continue
        orthophoto = folder / "orthophoto.tif"
        metadata = folder / "webodm_tarefa.json"
        info_path = folder / "ortomosaico_info.json"
        result = {"flight_id": folder.name, "has_orthophoto": orthophoto.is_file(),
                  "has_preview": (folder / "preview.png").is_file(),
                  "has_ndvi": (folder / "ndvi_ortomosaico.png").is_file()}
        for p, fields in ((metadata, ("project_id", "task_id", "images_count")),
                          (info_path, ("width", "height", "bands", "crs", "preview_note"))):
            if p.is_file():
                try:
                    record = json.loads(p.read_text(encoding="utf-8"))
                    result.update({field: record[field] for field in fields if field in record})
                except (ValueError, OSError, TypeError):
                    pass
        ndvi_report = folder / "ndvi_ortomosaico.json"
        if ndvi_report.is_file():
            try:
                ndvi = json.loads(ndvi_report.read_text(encoding="utf-8"))
                if isinstance(ndvi, dict):
                    result["ndvi"] = {key: ndvi[key] for key in (
                        "mean_ndvi", "min_ndvi", "max_ndvi", "red_band", "nir_band",
                        "valid_pixels", "selection_method") if key in ndvi}
            except (ValueError, OSError, TypeError):
                pass
        results.append(result)
    return results
