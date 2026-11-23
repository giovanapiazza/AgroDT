# WebODM no AgroDT — gerar e exibir ortomosaico

Esta integracao **nao substitui** o envio de capturas RED/NIR nem o calculo de NDVI existente. Ela envia **fotografias originais sobrepostas do mesmo voo** a um WebODM instalado, acompanha o processamento e apresenta uma previsualizacao no site AgroDT.

## 1. Preparar o WebODM

Instale e execute WebODM em um computador com recursos adequados, seguindo:
https://docs.opendronemap.org/installation/
https://docs.webodm.org/

O WebODM normalmente atende em http://127.0.0.1:8000. E preciso ter um no de processamento configurado. Certifique-se de que o servidor WebODM esteja acessivel antes do envio.

## 2. Instalar dependencias no AgroDT

```bash
cd ~/AgroDT
git pull origin main
cd ndvi
source .venv/bin/activate
pip install -r requirements-webodm.txt
```

## 3. Enviar fotografias originais do voo

As fotos devem estar em uma pasta, por exemplo `~/Downloads/voo_campo`, e conter fotos originais JPG/TIFF/PNG com sobreposicao. As bandas multiespectrais podem ser enviadas quando compativeis com o ODM e bem identificadas nos metadados.

```bash
export WEBODM_URL="http://127.0.0.1:8000"
export WEBODM_USER="seu_usuario"
export WEBODM_PASSWORD="sua_senha"

python webodm_ortomosaico.py submit \
  --imagens ~/Downloads/voo_campo \
  --nome voo_campo_01
```

Anote os `project_id` e `task_id` que o comando imprimir. O WebODM executa a reconstrucao separadamente.

## 4. Consultar estado da tarefa

```bash
python webodm_ortomosaico.py status --projeto-id 1 --tarefa-id 2
```

Substitua pelos IDs reais da tarefa. Quando a tarefa estiver **concluida**, baixe o ortomosaico:

```bash
python webodm_ortomosaico.py download \
  --projeto-id 1 --tarefa-id 2 --nome voo_campo_01
```

O resultado e salvo em:
`armazenamento/ortomosaicos/voo_campo_01/orthophoto.tif`

A previsualizacao para o site e gerada em:
`armazenamento/ortomosaicos/voo_campo_01/preview.png`

O arquivo `ortomosaico_info.json` registra dimensoes, contagem de bandas e CRS (quando presente). A previsualizacao usa apenas as tres primeiras bandas como RGB aproximado: **nao e NDVI**.

## 5. Ver ortomosaico no site AgroDT

Em outro terminal, execute:

```bash
export AGRODT_API_KEY='agrodt-teste-123'
python app.py
```

Abra http://127.0.0.1:8765, localize **Ortomosaicos dos voos (WebODM)**, selecione o voo e clique **Atualizar ortomosaicos**. A lista tambem atualiza a cada 10 segundos.

A integracao publica apenas a imagem pequena `preview.png` para visualizacao e metadados nao sensiveis. O GeoTIFF original permanece salvo no disco, sem download publico pelo endpoint do site.

## 6. NDVI do ortomosaico

Para NDVI do voo completo e necessario identificar corretamente a posicao das bandas RED e NIR no GeoTIFF, validar alinhamento e dados radiometricos. A simples previsualizacao RGB do ortomosaico **nao e mapa de calor NDVI**. O AgroDT ja possui importacao multibanda para calculo exploratorio, mas esse processamento nao e disparado automaticamente pela galeria de ortomosaicos.

Nao confunda fotos de levantamentos distintos: sem sobreposicao suficiente e metadados de captura, o WebODM pode falhar.

## Testar arquivos e rotas

```bash
python -m unittest discover -s tests -v
curl http://127.0.0.1:8765/api/v1/orthomosaics
```

Se a lista vier vazia, confira o caminho de armazenamento em `AGRODT_NDVI_DATA` e verifique se foi executado o comando `download` da tarefa concluida.
