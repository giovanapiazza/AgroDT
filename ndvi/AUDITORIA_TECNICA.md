# Auditoria técnica do módulo NDVI — 25/11/2026

Escopo: diretório `ndvi/` da branch `main` do AgroDT. Esta auditoria registra funções, dependências e testes para evitar voltar a versões legadas por acidente.

## Inventário de código

| Arquivo | É necessário? | Papel / decisão |
|---|---|---|
| `app.py` | Sim | API HTTP, painel, monitoramento de entrada, persistência de capturas e NDVI individual. Manter. |
| `image_importer.py` | Sim | Importação multissensor, identificação RED/NIR e extração de bandas. Manter. |
| `simular_drone.py` | Sim | Envio de imagens reais organizadas ou sintéticas, via API. Manter. |
| `send_capture.py` | Sim | Cliente de upload de par individual e ensaios de recepção. Manter. |
| `webodm_ortomosaico.py` | Sim | Cliente CLI WebODM; também fornece API para o orquestrador. Manter. |
| `orthomosaic_dashboard.py` | Sim | Upload dos voos, criação e acompanhamento de tarefas WebODM, download. Manter. |
| `orthomosaic_catalog.py` | Sim | Metadados e prévia leve para o navegador. Manter. |
| `orthomosaic_ndvi.py` | Sim | NDVI do GeoTIFF multibanda e preservação de CRS/NoData. Corrigida sintaxe na CLI. |
| `preparar_2_voos_zenodo.py` | Sim, teste | Utilitário opcional para obter capturas originais de dois registros Zenodo independentes. |
| `gerar_demo.py` | Sim, teste | Gerador de dados sintéticos apenas para validação. Não é versão antiga do NDVI. |
| `limpar_historico.py` | Sim, manutenção | Arquiva dados locais antes de iniciar banco vazio. Usar com servidor parado. |
| `templates/index.html` | Sim | Capturas, upload, ortomosaico e NDVI do mosaico. Manter. |

## Dependências

- `requirements.txt`: NumPy e Pillow, necessários para capturas individuais.
- `requirements-geo.txt`: adiciona Rasterio, necessário para GeoTIFF/JP2.
- `requirements-webodm.txt`: adiciona Requests, necessário para integração com WebODM.
- `.gitignore`: protege `.venv/`, `data/`, `armazenamento/`, backups e produtos temporários.

Os três arquivos de dependências não são duplicatas: a versão WebODM herda GeoTIFF, que herda o núcleo.

## Documentação

- `README.md`: visão geral e instruções **atualizadas**.
- `COMO_RODAR.md`: atualização da máquina, instalação e ensaio ponta a ponta **atualizados**.
- `COMO_USAR.md`: uso do pipeline de capturas e upload.
- `IMPORTADOR_GENERICO.md`: formatos e sensores.
- `WEBODM_COMO_USAR.md`: processamento fotogramétrico.
- `NDVI_ORTOMOSAICO.md`: GeoTIFF e índices espectrais.
- `ZENODO_2_VOOS.md`: montagem dos dois lotes reais de missões diferentes.

## Testes

Os arquivos `tests/test_ndvi.py`, `test_simular_drone.py`, `test_upload_sequoia.py`, `test_image_importer.py`, `test_orthomosaic_catalog.py`, `test_orthomosaic_dashboard.py`, `test_orthomosaic_ndvi.py` e `test_preparar_2_voos_zenodo.py` cobrem os diferentes módulos. Executar:

```bash
cd ~/AgroDT/ndvi
source .venv/bin/activate
pip install -r requirements-webodm.txt
python -m compileall -q .
python -m unittest discover -s tests -v
```

O workflow `.github/workflows/ndvi-tests.yml` executa compilation + testes Python + validação de sintaxe JavaScript no GitHub Actions.

## Problemas corrigidos nesta revisão

1. **Erro sintático** na construção da mensagem de exceção do CLI `orthomosaic_ndvi.py` impedia importar o módulo.
2. Documentos `README.md` e `COMO_RODAR.md` descreviam apenas o pipeline standalone antigo e foram reescritos para a versão com WebODM.
3. Atualizado `.gitignore` para evitar inclusão acidental de backups locais.
4. Inclusão de testes e preparador dos dois voos multiespectrais do Zenodo.

## Limitações ainda existentes / antes de produção

- O NDVI automático identifica bandas apenas quando os metadados são inequívocos; caso contrário exige seleção confirmada pelo usuário.
- Não há pipeline automático de calibração radiométrica/refletância ou validação de georreferenciamento; sem isso, resultados agronômicos são exploratórios.
- A foto RGB comum não permite NDVI verdadeiro.
- A API do AgroDT tem leitura pública na rede em que a porta for exposta; manter em localhost para os testes.
- O processamento de tarefas WebODM foi testado com dependências simuladas; validar envio, nó, processamento e ortomosaico **real** no Ubuntu.
- O script Zenodo depende de HTTP Range para leitura parcial dos grandes ZIPs; não há garantia de conectividade externa ou de sucesso de ortomosaico para um lote escolhido apenas por nomes.
- Não são incluídos `.venv`, bancos SQLite, imagens de captura e ortomosaicos reais no GitHub: são dados locais, não versões antigas do código.
