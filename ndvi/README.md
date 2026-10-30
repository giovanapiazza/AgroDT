# NDVI no AgroDT — receptor e interface web

Este módulo é independente do simulador Husky/Drone/ISOBUS. Recebe pares de bandas **RED e NIR** PNG/TIFF monocromáticas, calcula NDVI, detecta regiões de atenção (heurística), salva em SQLite e mostra os resultados pelo navegador.

## Ubuntu 24.04: instalação (primeira vez)

Na raiz do repositório AgroDT:

```bash
cd ndvi
sudo apt update
sudo apt install -y python3-venv python3-numpy python3-pil
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
export AGRODT_API_KEY='chave-local-teste-2026'
python3 app.py --host 127.0.0.1 --port 8765
```

Abra **http://127.0.0.1:8765**. Deixe o receptor aberto e use outro terminal:

```bash
cd ndvi
source .venv/bin/activate
export AGRODT_API_KEY='chave-local-teste-2026'
python3 gerar_demo.py
python3 send_capture.py --red data/demo/red.png --nir data/demo/nir.png --capture-id foto_001 --flight-id voo_demo_01
```

Para novos testes, altere `--capture-id` (IDs são únicos). O painel é atualizado a cada 5 segundos.

### Imagens reais

```bash
python3 send_capture.py --red /caminho/RED.tif --nir /caminho/NIR.tif --flight-id voo_real_01 --capture-id real_001
```

As bandas devem ser da mesma cena, alinhadas, na mesma escala radiométrica; RGB comum não equivale a RED+NIR. GeoTIFF multibanda deve ser separado antes. O endpoint `POST /api/v1/captures` é compatível com o script de envio da versão NDVI standalone.

### Pastas geradas automaticamente

```text
ndvi/armazenamento/
  entrada/<voo>/<captura>/       # pares aguardando processamento
  processadas/<voo>/<captura>/
     originais/red.png            # ou TIFF
     originais/nir.png
     ndvi_mapa.png
     ndvi_valores.npy
     mapa_areas_atencao.png
     mascara_atencao.png
     areas_atencao.json
     resumo.json
  erros/<voo>/<captura>/
  dados/capturas.sqlite3
```

Também pode copiar manualmente `red.png` e `nir.png` para uma pasta `entrada/<voo>/<captura>/`: o monitor local detecta pares completos após alguns segundos.

### Rotas

- `GET /` — painel web
- `GET /health` — saúde do receptor
- `POST /api/v1/captures` — upload autenticado, multipart com `red`, `nir`, `capture_id`, `flight_id`; metadados opcionais `latitude`, `longitude`, `captured_at`
- `GET /api/v1/captures` — capturas recentes
- `GET /api/v1/captures/<id>` — dados e regiões
- `GET /media/<id>/<arquivo>` — imagens de captura processada

### Limites e próximos passos

Limiar exploratório `AGRODT_NDVI_LIMIAR=0.40` e tamanho mínimo `AGRODT_NDVI_MIN_PIXELS=40`; vegetação aparente = NDVI > 0.20. O sistema não executa co-registro, calibração nem georreferenciamento. NDVI baixo **não comprova deficiência nutricional**; regiões são coordenadas em pixels, não missões do Husky A300.

O painel e as rotas GET estão sem autenticação: usar `--host 0.0.0.0` apenas em rede local confiável; nunca expor diretamente à internet. Na Raspberry real, a execução deve ser validada em hardware.

Dependências: NumPy e Pillow; SQLite e servidor HTTP nativos do Python. Não usa Flask nesta versão; interface em HTML/CSS/JavaScript.

### Testes

```bash
python3 -m unittest discover -s tests -v
```

### Atualizar código no notebook

```bash
git status
git pull --ff-only origin main
cd ndvi
```

Se houver mudanças locais, salve-as antes do pull.
