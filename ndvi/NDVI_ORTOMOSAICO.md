# NDVI automático do ortomosaico WebODM

## O que faz

O AgroDT preserva `orthophoto.tif` baixado do WebODM e tenta calcular automaticamente um NDVI georreferenciado assim que o WebODM concluir a tarefa. Não altera o cálculo NDVI por captura, a simulação do drone nem os importadores existentes.

### Requisitos

- WebODM com nó de processamento ativo.
- Fotografias originais do mesmo voo, em quantidade e sobreposição suficientes para ortomosaico.
- WebODM configurado para produzir um ortomosaico com **as bandas RED e NIR**, não apenas RGB.
- `pip install -r requirements-webodm.txt` no ambiente NDVI (inclui rasterio).

A documentação oficial do WebODM explica que ortomosaicos multiespectrais podem incluir as bandas dos diferentes sensores e um canal alpha. **Não assuma que RED e NIR estão sempre nos mesmos índices.** A configuração radiométrica do ODM/WebODM deve ser verificada; o AgroDT não faz calibração radiométrica automaticamente.

## Fluxo pela interface

1. Inicie WebODM no Ubuntu.
2. Configure `WEBODM_URL`, `WEBODM_USER`, `WEBODM_PASSWORD` e `AGRODT_API_KEY` **antes** de iniciar `python app.py`.
3. Em `http://127.0.0.1:8765`, abra **Ortomosaicos dos voos (WebODM)**.
4. Escolha um voo em `ndvi/data/<voo>/` ou envie um ZIP de fotografias originais. Clique em **Gerar ortomosaico**.
5. Quando o WebODM terminar, o AgroDT baixa `orthophoto.tif` e tenta identificar as bandas RED e NIR:
   - Se os nomes das bandas forem inequívocos nos metadados, o **NDVI é calculado automaticamente**.
   - Se o GeoTIFF não identificar as bandas, a interface exibe seletores para você confirmar o índice de RED e de NIR. O cálculo é feito sem reenviar as fotografias e sem refazer o ortomosaico.
   - Se a saída tiver apenas RGB, não é possível calcular NDVI verdadeiro. É necessário reprocessar o voo como multiespectral no WebODM.

## Resultados gerados

```text
ndvi/armazenamento/ortomosaicos/<voo>/
├── orthophoto.tif          # Ortomosaico original, mantido
├── preview.png             # Prévia RGB (quando disponível)
├── ndvi_ortomosaico.tif    # NDVI float32 georreferenciado, nodata -9999
├── ndvi_ortomosaico.png    # Mapa de calor para o navegador
├── ndvi_ortomosaico.json   # NDVI médio, min/max, bandas utilizadas
├── processamento.json      # Estado do fluxo WebODM/NDVI
└── ortomosaico_info.json   # Metadados geoespaciais
```

O NDVI é calculado por janelas de 512 pixels, evitando carregar o GeoTIFF inteiro em memória. O arquivo resultante mantém o CRS e a transformada espacial do mosaico. Pixels NoData não entram nas estatísticas. O PNG é apenas uma prévia colorida redimensionada, não substitui o GeoTIFF.

## API

- `GET /api/v1/orthomosaics` lista voos e informa `has_ndvi`, `ndvi_status` e, quando pronto, estatísticas.
- `GET /api/v1/orthomosaics/bands/<voo>` lista índices e nomes das bandas contidas no GeoTIFF.
- `POST /api/v1/orthomosaics/ndvi` aceita JSON com `flight_id`, `red_band`, `nir_band` e requer `X-API-Key`.
- `GET /orthomosaics/<voo>/ndvi_ortomosaico.png` apresenta a prévia do mapa de calor.

Exemplo de cálculo manual:

```bash
curl -X POST http://127.0.0.1:8765/api/v1/orthomosaics/ndvi \
  -H "X-API-Key: $AGRODT_API_KEY" -H "Content-Type: application/json" \
  -d '{"flight_id":"voo_campo_01","red_band":2,"nir_band":4}'
```

Os índices 2 e 4 acima são **exemplos**. Confira os índices reais no GeoTIFF/na tela, não copie sem verificar.

## Testar no Ubuntu

```bash
cd ~/AgroDT/ndvi
source .venv/bin/activate
pip install -r requirements-webodm.txt
python -m unittest discover -s tests -v
```

Também pode testar o cálculo local, quando já possuir um ortomosaico multibanda:

```bash
python orthomosaic_ndvi.py armazenamento/ortomosaicos/voo_campo_01/orthophoto.tif
# Se não houver metadados de banda suficientes:
python orthomosaic_ndvi.py armazenamento/ortomosaicos/voo_campo_01/orthophoto.tif --red 2 --nir 4
```

## Limitações

A identificação das bandas não substitui a calibração para reflectância, o alinhamento geométrico, as correções radiométricas ou a avaliação da qualidade fotogramétrica. A análise só deve ser interpretada agronomicamente depois dessas verificações. O usuário deve confirmar se RED e NIR representam efetivamente essas faixas espectrais.
