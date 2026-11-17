# Importador multiespectral generico — AgroDT NDVI

## Objetivo
Preserva o receptor da pasta `armazenamento/entrada/`, API de pares, simulador de drone, SQLite, mapas e HTML. Adiciona importacao multissensor por ZIP e arquivo multibanda.

## Formatos suportados

- **Par RED/NIR manual**: selecione os dois arquivos PNG/TIFF de banda unica na interface.
- **ZIP automatico**: arquivos com marcadores `RED`/`NIR`, `B04`/`B08` (Sentinel-2), pastas `RED/` e `NIR/`, ou perfis conhecidos. Arquivos GRE, REG, RGB e nomes ambiguos sao ignorados. Os pares sao associados pelo identificador restante e pelas pastas.
- **Parrot Sequoia**: `IMG_0001_RED.TIF` + `IMG_0001_NIR.TIF`, preservando a importacao anterior.
- **MicaSense RedEdge-M**: com o perfil selecionado explicitamente, indices `_3` (RED) e `_5` (NIR). Nao usar com outros modelos sem conferir a ordem das bandas.
- **GeoTIFF ou JP2 multibanda**: selecionar arquivo e os indices RED e NIR a partir de 1. Requer Rasterio.

O perfil automatico tenta ler nomes de banda presentes em metadados TIFF conhecidos e os nomes dos arquivos. Nao garante reconhecimento de todos os fabricantes ou todas as tags EXIF proprietarias. A correspondencia entre imagens deve ser conferida.

## Rodar

```bash
cd ~/AgroDT
git pull origin main
cd ndvi
source .venv/bin/activate
pip install -r requirements.txt
# Para JP2/GeoTIFF multibanda:
pip install -r requirements-geo.txt
export AGRODT_API_KEY='chave-local-de-teste'
python app.py
```

Abra http://127.0.0.1:8765 e clique em **Adicionar imagens**. O menu oferece:
1. ZIP multiespectral, com selecao do perfil.
2. Par RED/NIR manual.
3. GeoTIFF/JP2 multibanda com selecao de indices.

A chave deve corresponder a `AGRODT_API_KEY` usada para iniciar o receptor.

## API

ZIP:

```bash
curl -X POST http://127.0.0.1:8765/api/v1/import-zip \
-H "X-API-Key: $AGRODT_API_KEY" \
-H "X-Sensor-Profile: auto" \
-H "X-Flight-ID: teste_importador" \
-H "Content-Type: application/zip" \
--data-binary @"/caminho/dataset.zip"
```

Perfis: `auto`, `sequoia`, `sentinel2`, `micasense_rededge`. A resposta informa numero de capturas processadas, falhas e avisos sobre arquivos ignorados/ambiguos.

GeoTIFF multibanda:

```bash
curl -X POST http://127.0.0.1:8765/api/v1/import-multiband \
-H "X-API-Key: $AGRODT_API_KEY" \
-H "X-Flight-ID: teste_multibanda" \
-H "X-File-Extension: .tif" \
-H "X-Red-Band: 1" \
-H "X-Nir-Band: 4" \
-H "Content-Type: application/octet-stream" \
--data-binary @"/caminho/multibanda.tif"
```

**Os indices 1 e 4 sao ilustrativos**: consulte a documentacao e os metadados do produto antes de selecionar canais.

## Requisitos e limites
- ZIP ate 128 MiB compactados, 350 MiB descompactados e no maximo 100 pares reconhecidos; cada membro ate 60 MiB. Datasets grandes devem ser divididos em lotes.
- Para Sentinel-2, rasterio pode ser necessario para bandas JP2. Os produtos podem conter offsets e NoData que precisam de tratamento especifico.
- O sistema **nao realiza calibracao radiometrica, alinhamento geometrico, correcao atmosferica, composicao de mosaicos nem validacao de georreferenciamento**. O NDVI bruto/visualizacao e exploratorio. RGB isolado nao permite NDVI verdadeiro.
- Arquivos não identificados nao sao processados como se fossem bandas: revise os avisos e use a opcao manual.
- As capturas processadas continuam em `armazenamento/analisadas/` e sao exibidas no HTML. Para limpar o historico anterior utilize `python limpar_historico.py` com o servidor parado.

## Testes
```bash
python -m unittest discover -s tests -v
```
