# Duas missões reais de teste — Zenodo → WebODM → NDVI

## Fontes e separação entre os voos

O script `preparar_2_voos_zenodo.py` utiliza dois registros **independentes** do Zenodo:

| Voo | Registro | Arquivos requeridos |
|---|---|---|
| `ADM3` | https://zenodo.org/records/4070013 | `RED.zip`, `NIR.zip`, `GRE.zip`, `REG.zip` |
| `UFRGS` | https://zenodo.org/records/4076075 | `RED.zip`, `NIR.zip`, `GRE.zip`, `REG.zip` |

Ambas as fontes anunciam as bandas espectrais necessárias. O script verifica se os arquivos TIFF correspondentes possuem o mesmo identificador de captura, mantém os bytes originais e registra o nome do arquivo fonte e o ID Zenodo em `ORIGEM_ZENODO.json`. Não mistura capturas de registros diferentes nem inventa imagens.

**Atenção:** 30 *capturas* multiespectrais com quatro bandas significam **120 TIFFs por voo**, não apenas 30 arquivos. Isso permite enviar todas as bandas disponíveis ao WebODM. Se desejar exatamente 30 arquivos TIFF por voo, use `--capturas 7` (28 arquivos) ou ajuste o fluxo para apenas duas bandas (15 pares), mas a fotogrametria pode não ter sobreposição suficiente.

## Opção A — exatamente 30 imagens por missão (15 pares RED/NIR)

Este comando gera dois ZIPs com **30 TIFFs cada**: 15 capturas, duas bandas por captura.

```bash
cd ~/AgroDT/ndvi
source .venv/bin/activate
python -m pip install requests remotezip

python preparar_2_voos_zenodo.py \
  --capturas 15 --bandas RED,NIR \
  --saida ~/Downloads/pacotes_zenodo_webodm
```

Os resultados serão `webodm_ADM3_15_capturas_2bandas.zip` e `webodm_UFRGS_15_capturas_2bandas.zip`.

**Atenção:** 15 posições de câmera podem não ser suficientes para reconstruir um ortomosaico com boa sobreposição. Por isso, para testar a fotogrametria do WebODM, prefira a opção B abaixo.

## Opção B — 30 capturas com quatro bandas por missão (120 TIFFs/ZIP)



No Ubuntu, com rede:

```bash
cd ~/AgroDT
git fetch origin main
git pull --ff-only origin main
cd ndvi
source .venv/bin/activate
python -m pip install requests remotezip

python preparar_2_voos_zenodo.py --capturas 30 --saida ~/Downloads/pacotes_zenodo_webodm
```

Em caso de sucesso, serão gerados:

```text
~/Downloads/pacotes_zenodo_webodm/
├── webodm_ADM3_30_capturas_4bandas.zip
└── webodm_UFRGS_30_capturas_4bandas.zip
```

**O download remoto usa HTTP Range.** Alguns servidores ou redirecionamentos do Zenodo podem recusar essa operação. Nesse caso, o script falha com uma mensagem clara e **não** cria dados artificiais.

## Alternativa com ZIPs já baixados

Crie duas pastas com as quatro bandas, cada uma obtida do registro correto:

```text
~/Downloads/zenodo_ADM3/RED.zip
~/Downloads/zenodo_ADM3/NIR.zip
~/Downloads/zenodo_ADM3/GRE.zip
~/Downloads/zenodo_ADM3/REG.zip

~/Downloads/zenodo_UFRGS/RED.zip
~/Downloads/zenodo_UFRGS/NIR.zip
~/Downloads/zenodo_UFRGS/GRE.zip
~/Downloads/zenodo_UFRGS/REG.zip
```

Execute:

```bash
python preparar_2_voos_zenodo.py --capturas 30 \
  --adm3-local ~/Downloads/zenodo_ADM3 \
  --ufrgs-local ~/Downloads/zenodo_UFRGS \
  --saida ~/Downloads/pacotes_zenodo_webodm
```

## Enviar as missões ao site

Com WebODM ativo em http://127.0.0.1:8000 e AgroDT em http://127.0.0.1:8765:

1. Abra **Ortomosaicos dos voos (WebODM)** no AgroDT.
2. Informe a chave API local `AGRODT_API_KEY`.
3. Escolha `webodm_ADM3_30_capturas.zip`, identificador `zenodo_adm3_01`, e clique em **Enviar ZIP e gerar ortomosaico**.
4. Acompanhe o status. Confirme a geração de `orthophoto.tif` e `preview.png`.
5. Repita com `webodm_UFRGS_30_capturas.zip`, identificador `zenodo_ufrgs_01`.
6. Confirme se o GeoTIFF contém bandas RED e NIR e se o NDVI do ortomosaico é gerado. Se as bandas não forem identificadas, use a seleção manual baseada nos metadados do sensor.

### Limitações importantes

- O script só garante que as bandas de cada **identificador de captura** foram agrupadas corretamente. Não verifica se as 30 posições selecionadas cobrem uma área contínua ou possuem sobreposição fotogramétrica suficiente.
- **Não garante** que o WebODM produzirá um ortomosaico correto sem GPS/EXIF, calibração, sobreposição e parâmetros adequados.
- Os TIFFs podem conter dados brutos; NDVI agronomicamente confiável exige calibração radiométrica e alinhamento.
- Não envie o ZIP do processo NDVI individual ao WebODM quando ele contiver mapas gerados em vez das fotos originais.
