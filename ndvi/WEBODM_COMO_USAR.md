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


## NOVO: gerar ortomosaico direto pela interface AgroDT

Na versao atual, **nao e preciso digitar comandos de envio, status ou download** para novos voos.

1. Inicie WebODM e confirme que ele possui um no de processamento ativo.
2. **Antes de iniciar `app.py`**, configure os dados de conexao no terminal:

```bash
cd ~/AgroDT/ndvi
source .venv/bin/activate
pip install -r requirements-webodm.txt

export WEBODM_URL='http://127.0.0.1:8000'
read -rp "Usuario WebODM: " WEBODM_USER
read -rsp "Senha WebODM: " WEBODM_PASSWORD
echo
export WEBODM_USER WEBODM_PASSWORD

export AGRODT_API_KEY='agrodt-teste-123'
python app.py
```

3. Abra http://127.0.0.1:8765 e localize **Ortomosaicos dos voos (WebODM)**.
4. Informe a chave `AGRODT_API_KEY` (nao a senha do WebODM).
5. Para fotos que ja estao em `ndvi/data/<voo>/`, selecione o voo e clique **Gerar ortomosaico do voo**.
6. Alternativamente, coloque fotos **originais** de um unico voo num ZIP, indique identificador e clique **Enviar ZIP e gerar ortomosaico**.

A interface atualiza as tarefas automaticamente a cada 10 segundos. O backend cria um projeto/tarefa no WebODM, acompanha o status, faz download de `orthophoto.tif` quando estiver concluido e tenta gerar `preview.png` para exibicao no mesmo painel. Se a sessao do app.py for reiniciada apos o WebODM aceitar uma tarefa e salvar os IDs, o monitoramento dela e retomado automaticamente.

**Limites:** ZIP ate 600 MiB, maximo de 600 fotografias, um mesmo nome de arquivo por voo, e ate 1,4 GiB descompactados. Os originais ficam em `armazenamento/voos_originais/<voo>/` e nao sao modificados. Fotos originais de um voo devem ter sobreposicao; um conjunto de pares RED/NIR sem sobreposicao suficiente pode falhar no WebODM. Se o servidor reiniciar *durante* o upload inicial ao WebODM e ainda nao tiver IDs remotos, confirme no WebODM antes de reenviar para evitar uma tarefa duplicada.

O status e gravado em `armazenamento/ortomosaicos/<voo>/processamento.json`, sem salvar credenciais do WebODM. O backend utiliza credenciais definidas no ambiente; o navegador nunca recebe a senha do WebODM. Para operacao em rede, proteja a interface AgroDT e utilize conexao HTTPS conforme a infraestrutura.

O processamento do NDVI sobre o mosaico multibanda continua sendo uma etapa separada, dependente de identificacao das bandas e calibracao. Esta integracao **nao** gera automaticamente um NDVI georreferenciado de todo o voo.

### Endpoints do painel

- `GET /api/v1/orthomosaics/sources` — lista voos locais com fotografias originais.
- `GET /api/v1/orthomosaics` — lista mosaicos e estados de processamento.
- `POST /api/v1/orthomosaics/upload` — recebe ZIP original (header `X-Flight-ID`; exige `X-API-Key`).
- `POST /api/v1/orthomosaics/start` — inicia trabalho (JSON `{"flight_id":"voo_01","source":"data"}`; exige `X-API-Key`).
- `GET /orthomosaics/<voo>/preview.png` — exibe a previa PNG.

### Testes de desenvolvimento

```bash
python -m unittest discover -s tests -v
```

Os testes automatizados para WebODM usam API simulada e nao substituem o teste com suas credenciais e WebODM real no Ubuntu.
