# Como usar — AgroDT NDVI: 100 capturas

Fluxo: **drone simulado → API HTTP → processamento NDVI (PC ou Raspberry Pi) → pasta `armazenamento/analisadas/` → painel HTML**.

## Instalar (primeira vez)

```bash
cd ndvi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Terminal 1 — iniciar o receptor e o HTML

```bash
cd ndvi
source .venv/bin/activate
export AGRODT_API_KEY='chave-local-de-teste'
python app.py
```

Acesse **http://127.0.0.1:8765**. A interface é servida pelo próprio `app.py` e atualiza a cada 5 segundos.

## Terminal 2 — simular 100 capturas

```bash
cd ndvi
source .venv/bin/activate
export AGRODT_API_KEY='chave-local-de-teste'
python simular_drone.py --quantidade 100 --intervalo 0.2
```

Cada captura contém **duas bandas**, RED e NIR. Portanto, são **100 capturas (200 imagens de banda)**. Por padrão são **imagens sintéticas variadas**, geradas automaticamente para testar o sistema, sem validade agronômica. Cada execução recebe identificadores únicos, então você pode repetir.

Após cada envio, o receptor processa a captura e grava os resultados em `armazenamento/analisadas/voo_simulado/<capture_id>/`. O banco SQLite indexa as capturas e o HTML consulta a API automaticamente. O servidor e o HTML permanecem no ar durante o envio.

## Usar pares RED/NIR reais

Prepare um diretório com 100 subpastas, cada qual contendo um par alinhado de bandas únicas:

```text
data/capturas/
  captura_001/red.tif
  captura_001/nir.tif
  captura_002/red.tif
  captura_002/nir.tif
  ...
  captura_100/red.tif
  captura_100/nir.tif
```

Execute:

```bash
python simular_drone.py --origem data/capturas --quantidade 100 --intervalo 0.2 --flight-id voo_real_teste
```

O simulador **não importa imagens automaticamente da internet**; usa imagens sintéticas ou pares reais previamente baixados. Imagens reais precisam de calibração radiométrica, compatibilidade RED/NIR, alinhamento e validação de NoData antes de qualquer interpretação agrícola.

## Executar o receptor numa Raspberry Pi real

Instale o projeto e as dependências na Raspberry Pi e execute:

```bash
export AGRODT_API_KEY='uma-chave-forte-e-privada'
python app.py --host 0.0.0.0 --port 8765
```

No PC que simula o drone:

```bash
export AGRODT_API_KEY='uma-chave-forte-e-privada'
python simular_drone.py --pi http://IP_DA_RASPBERRY:8765 --quantidade 100
```

Abra `http://IP_DA_RASPBERRY:8765` em um navegador na mesma rede. O endpoint usa HTTP sem criptografia, portanto não exponha diretamente à internet; proteja conexões fora da rede de testes com VPN ou HTTPS.

## Saídas

```text
armazenamento/
  analisadas/
    voo_simulado/
      sim_<sessao>_0001/
        originais/red.png
        originais/nir.png
        ndvi_mapa.png
        mapa_areas_atencao.png
        mascara_atencao.png
        ndvi_valores.npy
        areas_atencao.json
        resumo.json
  dados/capturas.sqlite3
```

Capturas antigas em `armazenamento/processadas/` permanecem legíveis no painel. Não envie `.venv/`, `armazenamento/` ou `data/` ao Git.

## Testes

```bash
python -m unittest discover -s tests -v
```


## Executar lotes diferentes sem apagar o histórico

Use uma semente (`--seed`) e um voo (`--flight-id`) diferentes em cada execução:

```bash
python simular_drone.py --quantidade 100 --flight-id voo_01 --seed 1 --intervalo 0.2
python simular_drone.py --quantidade 100 --flight-id voo_02 --seed 2 --intervalo 0.2
python simular_drone.py --quantidade 100 --flight-id voo_03 --seed 3 --intervalo 0.2
```

Cada execução utiliza novos IDs de captura; os resultados se acumulam em `armazenamento/analisadas/voo_01/`, `voo_02/` e `voo_03/`. A semente torna a geração reprodutível para um mesmo número de captura e permite variar os conjuntos sintéticos. Os dados sintéticos não substituem pares de imagens reais RED/NIR.
