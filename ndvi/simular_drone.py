#!/usr/bin/env python3
"""Simula o drone enviando capturas RED/NIR para o servidor NDVI."""
import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import random
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

import numpy as np
from PIL import Image

EXT = (".png", ".tif", ".tiff")


def arquivo_banda(pasta, nome):
    return next((p for p in sorted(pasta.iterdir()) if p.is_file() and p.stem.lower() == nome and p.suffix.lower() in EXT), None)


def pares_reais(origem):
    if not origem.is_dir():
        raise ValueError(f"Pasta inexistente: {origem}")
    pastas = [origem] + sorted(p for p in origem.iterdir() if p.is_dir())
    pares = [(r, n) for p in pastas if (r := arquivo_banda(p, "red")) and (n := arquivo_banda(p, "nir"))]
    if not pares:
        raise ValueError("Nenhum par red/nir encontrado")
    return pares


def imagem_sintetica(numero, largura=160, altura=120):
    """Dados sintéticos para teste, não são imagens reais de drone."""
    rng = random.Random(numero)
    yy, xx = np.ogrid[:altura, :largura]
    red = np.full((altura, largura), 9000, dtype=np.uint16)
    nir = np.full((altura, largura), 51000, dtype=np.uint16)
    for _ in range(numero % 5):
        cx, cy = rng.randrange(15, largura - 15), rng.randrange(15, altura - 15)
        raio = rng.randrange(7, 19)
        regiao = (xx - cx)**2 + (yy - cy)**2 < raio**2
        red[regiao], nir[regiao] = 22000, 41000
    return [converter_png(red), converter_png(nir)]


def converter_png(matriz):
    buffer = BytesIO()
    Image.fromarray(matriz).save(buffer, format="PNG")
    return buffer.getvalue()


def enviar(url, chave, voo, identificador, red, nir, extensoes):
    boundary = "agrodt-" + uuid.uuid4().hex
    corpo = bytearray()
    for nome, valor in [("flight_id", voo), ("capture_id", identificador)]:
        corpo += (f'--{boundary}\r\nContent-Disposition: form-data; name="{nome}"\r\n\r\n{valor}\r\n').encode()
    for nome, dados, ext in zip(("red", "nir"), (red, nir), extensoes):
        corpo += (f'--{boundary}\r\nContent-Disposition: form-data; name="{nome}"; filename="{nome}{ext}"\r\nContent-Type: application/octet-stream\r\n\r\n').encode()
        corpo += dados + b"\r\n"
    corpo += (f"--{boundary}--\r\n").encode()
    request = Request(url.rstrip("/") + "/api/v1/captures", data=corpo, headers={
        "X-API-Key": chave, "Content-Type": "multipart/form-data; boundary=" + boundary}, method="POST")
    try:
        with urlopen(request, timeout=180) as resposta:
            return resposta.status, json.load(resposta)
    except HTTPError as erro:
        try:
            detalhe = json.load(erro)
        except (ValueError, OSError):
            detalhe = {"error": str(erro)}
        return erro.code, detalhe


def main():
    parser = argparse.ArgumentParser(description="Simula envios de capturas de drone para NDVI")
    parser.add_argument("--quantidade", type=int, default=100)
    parser.add_argument("--intervalo", type=float, default=0.1)
    parser.add_argument("--pi", default="http://127.0.0.1:8765")
    parser.add_argument("--api-key", default=os.getenv("AGRODT_API_KEY"))
    parser.add_argument("--flight-id", default="voo_simulado")
    parser.add_argument("--origem", type=Path, help="Pasta com pares red/nir reais")
    args = parser.parse_args()
    if not args.api_key:
        parser.error("Configure AGRODT_API_KEY ou informe --api-key")
    if args.quantidade < 1 or args.intervalo < 0:
        parser.error("--quantidade >= 1 e --intervalo >= 0 sao obrigatorios")
    try:
        pares = pares_reais(args.origem) if args.origem else None
    except ValueError as erro:
        parser.error(str(erro))
    if pares and args.quantidade > len(pares):
        parser.error(f"Existem apenas {len(pares)} pares distintos; reduza --quantidade")
    sessao = uuid.uuid4().hex[:8]
    sucesso = falhas = 0
    for i in range(args.quantidade):
        identificador = f"sim_{sessao}_{i+1:04d}"
        if pares:
            r, n = pares[i]
            red, nir = r.read_bytes(), n.read_bytes()
            extensoes = (r.suffix.lower(), n.suffix.lower())
        else:
            red, nir = imagem_sintetica(i + 1)
            extensoes = (".png", ".png")
        try:
            codigo, resposta = enviar(args.pi, args.api_key, args.flight_id, identificador, red, nir, extensoes)
            ok = codigo == 201 and resposta.get("status") == "processed"
            print(f'[{i+1}/{args.quantidade}] {identificador} | HTTP {codigo} | {"analisada" if ok else resposta.get("error", "falhou")}', flush=True)
            sucesso += int(ok)
            falhas += int(not ok)
        except (OSError, URLError, ValueError) as erro:
            falhas += 1
            print(f"[{i+1}/{args.quantidade}] {identificador} | falha: {erro}", flush=True)
        if i < args.quantidade - 1:
            time.sleep(args.intervalo)
    print(f"Concluido: {sucesso} analisadas, {falhas} falhas. Consulte {args.pi}")
    if falhas:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
