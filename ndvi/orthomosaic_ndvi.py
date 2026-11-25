"""Calcula NDVI georreferenciado de um ortomosaico WebODM multiespectral.

Nao adivinha indices das bandas. Requer nomes reconhecidos no GeoTIFF ou
indices RED e NIR explicitamente confirmados. Processa por janelas.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import uuid

import numpy as np
from PIL import Image

NODATA = -9999.0
MAX_PREVIEW = 1400


class BandSelectionRequired(ValueError):
    """GeoTIFF nao identifica as bandas RED e NIR com seguranca."""


def _band_kind(value):
    tokens = set(re.findall(r"[a-z0-9]+", str(value).lower()))
    if {"red", "edge"} <= tokens or "rededge" in tokens or "re" in tokens:
        return None
    if "nir" in tokens or "nearinfrared" in tokens or {"near", "infrared"} <= tokens:
        return "nir"
    if "red" in tokens or "b04" in tokens:
        return "red"
    if "b08" in tokens:
        return "nir"
    return None


def inspect_bands(source):
    try:
        import rasterio
    except ImportError as exc:
        raise RuntimeError("Instale rasterio: pip install -r requirements-webodm.txt") from exc
    with rasterio.open(source) as ds:
        return [{"index": i, "description": ds.descriptions[i - 1] or "",
                 "tags": {key: str(val) for key, val in ds.tags(i).items()
                          if key.lower() in ("band_name", "name", "description", "wavelength")}}
                for i in range(1, ds.count + 1)]


def choose_bands(source, red_index=None, nir_index=None):
    bands = inspect_bands(source)
    if red_index is not None or nir_index is not None:
        if red_index is None or nir_index is None:
            raise ValueError("Informe os dois indices RED e NIR juntos")
        try:
            red_index, nir_index = int(red_index), int(nir_index)
        except (TypeError, ValueError) as exc:
            raise ValueError("Indices RED/NIR devem ser inteiros") from exc
        if not (1 <= red_index <= len(bands) and 1 <= nir_index <= len(bands)) or red_index == nir_index:
            raise ValueError("Indices de banda invalidos ou iguais")
        return red_index, nir_index, "manual"
    found = {"red": [], "nir": []}
    for item in bands:
        labels = [item["description"]]
        for key in ("band_name", "name", "description"):
            labels.extend(val for k, val in item["tags"].items() if k.lower() == key)
        kinds = {_band_kind(label) for label in labels} - {None}
        if len(kinds) == 1:
            found[next(iter(kinds))].append(item["index"])
    if len(found["red"]) != 1 or len(found["nir"]) != 1 or found["red"][0] == found["nir"][0]:
        labels = ", ".join(f'{band["index"]}:{band["description"] or "sem nome"}' for band in bands)
        raise BandSelectionRequired("Bandas RED/NIR nao identificadas de forma unica. "
                                    f"Selecione os indices no site. Bandas: {labels}")
    return found["red"][0], found["nir"][0], "metadata"


def _heatmap(values, valid):
    stops = np.array([-1, 0, .2, .4, .6, .8, 1], dtype=np.float32)
    colors = np.array([[115, 35, 65], [220, 60, 50], [244, 114, 50],
                       [246, 205, 62], [130, 200, 70], [28, 145, 78],
                       [8, 96, 70]], dtype=np.float32)
    values = np.nan_to_num(values, nan=-1, posinf=-1, neginf=-1)
    out = np.stack([np.interp(values, stops, colors[:, channel])
                    for channel in range(3)], axis=-1).astype(np.uint8)
    out[~valid] = [68, 73, 83]
    return Image.fromarray(out, "RGB")


def calculate_orthomosaic_ndvi(source, output_dir, red_index=None, nir_index=None):
    """Grava NDVI float GeoTIFF, PNG de visualizacao e resumo JSON."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.windows import Window

    source, output_dir = Path(source), Path(output_dir)
    if not source.is_file():
        raise ValueError("orthophoto.tif nao encontrado para este voo")
    red_index, nir_index, method = choose_bands(source, red_index, nir_index)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / "ndvi_ortomosaico.tif"
    temporary = output_dir / (".ndvi_" + uuid.uuid4().hex + ".tif")
    count = 0
    sum_value = 0.0
    min_value, max_value = 1.0, -1.0
    try:
        with rasterio.open(source) as ds:
            input_width, input_height = ds.width, ds.height
            profile = {"driver": "GTiff", "width": ds.width, "height": ds.height,
                       "count": 1, "dtype": "float32", "nodata": NODATA,
                       "transform": ds.transform, "crs": ds.crs,
                       "compress": "deflate", "predictor": 3, "BIGTIFF": "IF_SAFER"}
            with rasterio.open(temporary, "w", **profile) as dest:
                dest.set_band_description(1, "NDVI")
                dest.update_tags(1, red_source_band=str(red_index), nir_source_band=str(nir_index))
                for row in range(0, ds.height, 512):
                    for col in range(0, ds.width, 512):
                        window = Window(col, row, min(512, ds.width - col),
                                        min(512, ds.height - row))
                        red = ds.read(red_index, window=window, masked=True).astype(np.float32)
                        nir = ds.read(nir_index, window=window, masked=True).astype(np.float32)
                        a, b = np.ma.getdata(red), np.ma.getdata(nir)
                        valid = (~np.ma.getmaskarray(red) & ~np.ma.getmaskarray(nir)
                                 & np.isfinite(a) & np.isfinite(b) & (a >= 0) & (b >= 0)
                                 & (a + b > 0))
                        ndvi = np.full(a.shape, NODATA, dtype=np.float32)
                        np.divide(b - a, b + a, out=ndvi, where=valid)
                        dest.write(ndvi, 1, window=window)
                        if np.any(valid):
                            pixels = ndvi[valid]
                            count += int(pixels.size)
                            sum_value += float(np.sum(pixels, dtype=np.float64))
                            min_value = min(min_value, float(pixels.min()))
                            max_value = max(max_value, float(pixels.max()))
        if count == 0:
            raise ValueError("Ortomosaico nao possui pixels RED/NIR validos")
        with rasterio.open(temporary) as ds:
            scale = min(1.0, MAX_PREVIEW / max(ds.width, ds.height))
            height = max(1, round(ds.height * scale))
            width = max(1, round(ds.width * scale))
            preview = ds.read(1, masked=True, out_shape=(height, width),
                              resampling=Resampling.average)
            values = np.ma.filled(preview, np.nan)
            image = _heatmap(values, np.isfinite(values) & (values != NODATA))
        preview_tmp = output_dir / (".preview_" + uuid.uuid4().hex + ".png")
        image.save(preview_tmp)
        report = {"status": "ready", "red_band": red_index, "nir_band": nir_index,
                  "selection_method": method, "valid_pixels": count,
                  "mean_ndvi": round(sum_value / count, 6),
                  "min_ndvi": round(min_value, 6), "max_ndvi": round(max_value, 6),
                  "width": input_width, "height": input_height,
                  "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "note": "NDVI calculado sobre os valores do ortomosaico; confirme calibracao radiometrica, correspondencia das bandas e georreferenciamento."}
        report_tmp = output_dir / (".resumo_" + uuid.uuid4().hex + ".json")
        report_tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(target)
        preview_tmp.replace(output_dir / "ndvi_ortomosaico.png")
        report_tmp.replace(output_dir / "ndvi_ortomosaico.json")
        return report
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Calcular NDVI do ortomosaico WebODM")
    parser.add_argument("arquivo", type=Path, help="orthophoto.tif")
    parser.add_argument("--red", type=int, help="indice RED (a partir de 1)")
    parser.add_argument("--nir", type=int, help="indice NIR (a partir de 1)")
    args = parser.parse_args()
    try:
        print(json.dumps(calculate_orthomosaic_ndvi(args.arquivo, args.arquivo.parent,
                   args.red, args.nir), indent=2, ensure_ascii=False))
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"Erro: {exc}\\n")


if __name__ == "__main__":
    main()
