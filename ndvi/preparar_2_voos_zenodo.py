#!/usr/bin/env python3
"""Prepara dois voos reais e distintos do Zenodo para WebODM/AgroDT.

Exige 4 bandas Sequoia por captura e NAO sintetiza fotografias.
Pode ler ZIPs remotos via HTTP Range ou arquivos locais ja baixados.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import ExitStack
import json
from pathlib import Path, PurePosixPath
import re
from zipfile import ZipFile, ZIP_DEFLATED

DATASETS = {
    "ADM3": {"record": 4070013, "label": "ADM3_UAV"},
    "UFRGS": {"record": 4076075, "label": "UFRGS_UAV"},
}
BANDS = ("RED", "NIR", "GRE", "REG")
TIFF_SIGNATURES = (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+")
MAX_WEBODM_ZIP = 600 * 1024 * 1024


def matched_capture_key(filename, band):
    path = PurePosixPath(filename.replace("\\", "/"))
    if path.suffix.lower() not in (".tif", ".tiff"):
        return None
    # Datasheets geralmente usam IMG_..._RED.TIF ou diretórios RED/IMG_....
    stem = path.stem.upper()
    pattern = r"(^|[_ .-])" + re.escape(band) + r"(?=$|[_ .-])"
    key = re.sub(pattern, "_", stem)
    key = re.sub(r"[_ .-]+", "_", key).strip("_")
    return key or None


def index_band(archive, band):
    groups = defaultdict(list)
    for member in archive.infolist():
        if not member.is_dir():
            key = matched_capture_key(member.filename, band)
            if key:
                groups[key].append(member)
    # Duplicatas nao sao usadas: evita parear imagens de tomadas ambiguas.
    return {key: items[0] for key, items in groups.items() if len(items) == 1}


def select_captures(archives, start, quantity, bands=BANDS):
    indices = {band: index_band(archive, band) for band, archive in archives.items()}
    keys = sorted(set.intersection(*(set(indices[band]) for band in bands)))
    if len(keys) < start + quantity - 1:
        raise ValueError(
            f"Somente {len(keys)} capturas RED/NIR/GRE/REG pareadas; "
            f"impossivel selecionar posicoes {start} a {start + quantity - 1}"
        )
    return [(key, {band: indices[band][key] for band in bands})
            for key in keys[start - 1: start - 1 + quantity]]


def create_archive(archives, dataset, start, quantity, output, bands=BANDS):
    captures = select_captures(archives, start, quantity, bands)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_suffix(".part")
    manifest = {
        "dataset": dataset, "zenodo_record": DATASETS[dataset]["record"],
        "source_url": f"https://zenodo.org/records/{DATASETS[dataset]['record']}",
        "capture_count": quantity, "file_count": quantity * len(bands),
        "capture_start": start, "bands": list(bands),
        "scientific_note": "Imagens originais. NDVI exige calibracao e registro das bandas.",
        "captures": [],
    }
    try:
        with ZipFile(temp, "w", compression=ZIP_DEFLATED, compresslevel=1, allowZip64=True) as target:
            for offset, (capture_key, members) in enumerate(captures):
                output_number = offset + 1
                record = {"capture_number": output_number, "source_capture_key": capture_key,
                          "source_files": {}}
                for band in bands:
                    member = members[band]
                    contents = archives[band].read(member)
                    if len(contents) != member.file_size or contents[:4] not in TIFF_SIGNATURES:
                        raise ValueError(f"TIFF ausente/incompleto: {member.filename}")
                    destination = f"IMG_{dataset}_{output_number:04d}_{band}.TIF"
                    target.writestr(destination, contents)
                    record["source_files"][band] = member.filename
                manifest["captures"].append(record)
                print(f"{dataset}: captura {output_number}/{quantity} ({capture_key})", flush=True)
            target.writestr("ORIGEM_ZENODO.json", json.dumps(manifest, indent=2, ensure_ascii=False))
        if temp.stat().st_size > MAX_WEBODM_ZIP:
            raise ValueError("ZIP acima do limite WebODM/AgroDT de 600 MiB; reduza --capturas")
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)
    return output


def read_zenodo_files(record_id, bands=BANDS):
    import requests
    response = requests.get(f"https://zenodo.org/api/records/{record_id}", timeout=45)
    response.raise_for_status()
    data = response.json()
    lookup = {}
    for item in data.get("files", []):
        filename = Path(item.get("key", "")).name.upper()
        url = item.get("links", {}).get("content")
        if url and filename:
            lookup[filename] = url
    missing = [f"{band}.ZIP" for band in bands if f"{band}.ZIP" not in lookup]
    if missing:
        raise ValueError(f"Registro {record_id} sem arquivos obrigatorios: {missing}")
    return {band: lookup[f"{band}.ZIP"] for band in bands}


def open_sources(stack, dataset, local_dir, bands=BANDS):
    if local_dir:
        folder = Path(local_dir).expanduser()
        files = {band: folder / (band + ".zip") for band in bands}
        missing = [str(path) for path in files.values() if not path.is_file()]
        if missing:
            raise ValueError("Faltam ZIPs locais: " + ", ".join(missing))
        return {band: stack.enter_context(ZipFile(path)) for band, path in files.items()}
    from remotezip import RemoteZip
    urls = read_zenodo_files(DATASETS[dataset]["record"], bands)
    return {band: stack.enter_context(RemoteZip(urls[band])) for band in bands}


def main():
    parser = argparse.ArgumentParser(description="Baixar 30 capturas de dois voos distintos do Zenodo")
    parser.add_argument("--bandas", default="RED,NIR,GRE,REG",
                        help="Bandas por captura: RED,NIR ou RED,NIR,GRE,REG")
    parser.add_argument("--capturas", type=int, default=30,
                        help="Posicoes de captura por missao (30 capturas * 4 bandas = 120 TIFFs)")
    parser.add_argument("--inicio-adm3", type=int, default=1)
    parser.add_argument("--inicio-ufrgs", type=int, default=1)
    parser.add_argument("--saida", type=Path, default=Path("pacotes_zenodo_webodm"))
    parser.add_argument("--adm3-local", type=Path, help="Pasta local com RED.zip, NIR.zip, GRE.zip e REG.zip do ADM3")
    parser.add_argument("--ufrgs-local", type=Path, help="Pasta local com quatro ZIPs do UFRGS")
    args = parser.parse_args()
    bands = tuple(b.strip().upper() for b in args.bandas.split(",") if b.strip())
    if bands not in (("RED", "NIR"), ("RED", "NIR", "GRE", "REG")):
        parser.error("Use --bandas RED,NIR ou --bandas RED,NIR,GRE,REG")
    if not 1 <= args.capturas <= 100 or args.inicio_adm3 < 1 or args.inicio_ufrgs < 1:
        parser.error("Use 1..100 capturas e posicoes iniciais >= 1")
    if not args.adm3_local or not args.ufrgs_local:
        try:
            import requests
            import remotezip
        except ImportError:
            parser.error("Instale requests e remotezip: pip install requests remotezip")
    try:
        args.saida.mkdir(parents=True, exist_ok=True)
        results = []
        for dataset, start, local in (
            ("ADM3", args.inicio_adm3, args.adm3_local),
            ("UFRGS", args.inicio_ufrgs, args.ufrgs_local),
        ):
            with ExitStack() as stack:
                archives = open_sources(stack, dataset, local, bands)
                dest = args.saida / f"webodm_{dataset}_{args.capturas}_capturas_{len(bands)}bandas.zip"
                results.append(str(create_archive(archives, dataset, start, args.capturas, dest, bands)))
        print("\nArquivos gerados:")
        for path in results:
            print(path)
        print("Use cada ZIP como um voo diferente em Ortomosaicos do AgroDT.")
    except Exception as exc:
        parser.exit(1, f"Falha ao extrair fotografias reais do Zenodo: {exc}\n"
                       "Se HTTP Range nao for aceito, use --adm3-local/--ufrgs-local.\n")


if __name__ == "__main__":
    main()
