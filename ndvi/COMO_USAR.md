# Como usar — AgroDT NDVI (importacao multiespectral e WebODM)

## Funcionalidades atuais (branch main)

- Receptor de capturas RED/NIR por HTTP e pela pasta `armazenamento/entrada/`.
- Simulacao de envio automatico pelo drone (`simular_drone.py`).
- Importacao de pares, ZIPs genericos e GeoTIFF/JP2 multibanda na interface.
- Calculo NDVI, mapa de calor e areas de atencao por captura.
- **Ortomosaicos WebODM integrados ao site**: escolha um voo de fotos originais da pasta `data/<voo>/` ou envie ZIP de fotos, clique em gerar, acompanhe status e visualize a previa quando concluida.
- Processamento WebODM em segundo plano com historico de tarefa; fotos originais e GeoTIFF ficam preservados.

Veja o procedimento detalhado em [WEBODM_COMO_USAR.md](WEBODM_COMO_USAR.md). O WebODM precisa estar instalado e configurado no computador que executa a API AgroDT. O processamento de NDVI **sobre o ortomosaico completo** nao e automatico ainda.

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


## Importar imagens reais da Parrot Sequoia pelo HTML (novo)

1. Inicie o servidor normalmente:

```bash
cd ~/AgroDT/ndvi
source .venv/bin/activate
export AGRODT_API_KEY='agrodt-teste-123'
python app.py
```

2. Abra http://127.0.0.1:8765.
3. Em **Adicionar imagens reais**, preencha a mesma chave API do servidor.
4. Escolha o ZIP `imagens_sequoia.zip` e clique em **Importar e analisar ZIP**.

O ZIP de exemplo possui seis pares `*_RED.TIF` e `*_NIR.TIF`, além de GRE/REG/RGB. O importador usa RED e NIR sem exigir renomear os arquivos. Os arquivos ZIP originais não são modificados. **Não envie** GRE, REG ou RGB no lugar de NIR. A API existente de capturas individuais também permanece.

Há uma segunda opção no painel: **Adicionar um par RED/NIR**. Selecione um arquivo TIFF/PNG por banda, informe a mesma chave API e clique para analisar. A API de upload de pares permanece `POST /api/v1/captures`.

O servidor mantém o monitor da pasta `armazenamento/entrada/<voo>/<captura>/red.tif` e `nir.tif`, o envio via `send_capture.py` e o simulador `simular_drone.py`.

Cada nova captura processada cria `ndvi_mapa.png`, `heatmap_ndvi.png`, `red_preview.png`, `nir_preview.png`, `mapa_areas_atencao.png`, `areas_atencao.json` e `resumo.json`, dentro de `armazenamento/analisadas/<voo>/<captura>/`. Os TIFFs são preservados em `originais/`.

### Importar ZIP via linha de comando

```bash
curl -X POST http://127.0.0.1:8765/api/v1/import-zip \
  -H "X-API-Key: $AGRODT_API_KEY" \
  -H "X-Flight-ID: sequoia_teste_01" \
  -H "Content-Type: application/zip" \
  --data-binary @"/caminho/para/imagens_sequoia.zip"
```

### Limitações científicas

Os TIFFs Sequoia são bandas brutas de sensor, sem calibração radiométrica nem registro espacial aplicado pelo pipeline atual. O mapa de calor criado é uma visualização do **NDVI bruto**, útil para conferir a integração, mas **não** é um diagnóstico confiável de estresse vegetal. A correspondência de dimensões entre RED e NIR não garante alinhamento geométrico. Para aplicações agronômicas, é preciso calibrar as bandas para reflectância, ajustar o alinhamento e tratar NoData/valores inválidos.

### Testes

```bash
python -m unittest discover -s tests -v
```


## Interface de importacao recolhida e painel vazio

A secao **Adicionar imagens** inicia fechada. Clique nela para abrir e escolha uma das opcoes:
- **Imagens reais (ZIP Sequoia)**: upload de arquivo ZIP com pares `*_RED.TIF` / `*_NIR.TIF`.
- **Par RED/NIR**: upload de duas bandas individuais em PNG ou TIFF.

A chave API usada pelo servidor e requerida para ambos os envios.

Para limpar o painel e **arquivar** o historico anterior sem apagar os arquivos, pare o servidor e os simuladores e execute:

```bash
cd ~/AgroDT/ndvi
source .venv/bin/activate
python limpar_historico.py
export AGRODT_API_KEY='agrodt-teste-123'
python app.py
```

O comando renomeia a pasta atual `armazenamento/` para um backup com data e hora. No proximo inicio, o servidor cria um novo SQLite vazio e as pastas de trabalho. O script respeita `AGRODT_NDVI_DATA`, caso o armazenamento esteja configurado em outro local.

**Atenção:** nunca execute `limpar_historico.py` com `app.py` ou o simulador em funcionamento. O `git pull` sozinho nao altera o banco SQLite local e nao zera o painel.
