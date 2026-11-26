# AgroDT — NDVI e ortomosaicos WebODM

Este é o módulo NDVI **atual** do repositório AgroDT. O servidor `app.py` mantém a recepção automática de pares RED/NIR, imagens reais, simulação do drone, cálculo de NDVI por captura e ortomosaicos multiespectrais processados pelo WebODM.

## Organização

| Arquivo/pasta | Responsabilidade |
|---|---|
| `app.py` | Servidor HTTP (porta 8765), API, banco SQLite, NDVI por captura, pasta monitorada |
| `image_importer.py` | Reconhecimento e associação de bandas de sensores diferentes |
| `simular_drone.py` / `send_capture.py` | Envio automático e manual de capturas por HTTP |
| `webodm_ortomosaico.py` | Cliente da API WebODM e comandos pelo terminal |
| `orthomosaic_dashboard.py` | Orquestra tarefas WebODM pelo site e retoma acompanhamento |
| `orthomosaic_catalog.py` | Lista mosaicos e cria prévias PNG |
| `orthomosaic_ndvi.py` | NDVI GeoTIFF georreferenciado por blocos, com NoData |
| `preparar_2_voos_zenodo.py` | Obtém duas missões reais do Zenodo sem sintetizar fotos |
| `gerar_demo.py` | Gera dados artificiais somente para teste unitário/manual |
| `limpar_historico.py` | Arquiva o armazenamento anterior, sem apagar arquivos |
| `templates/index.html` | Painel de capturas, upload e ortomosaicos |
| `tests/` | Testes unitários e de integração simulada |
| `requirements*.txt` | Dependências Python; a variante WebODM inclui Rasterio e requests |
| `armazenamento/` e `data/` | Imagens/dados locais, ignorados pelo Git |

## Instalação Ubuntu 24.04

O WebODM deve estar funcionando separadamente em http://127.0.0.1:8000, com nó de processamento ativo.

```bash
cd ~/AgroDT/ndvi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-webodm.txt
python -m unittest discover -s tests -v
```

Em um terminal, configure as credenciais reais do WebODM e a chave local da API **antes de iniciar o servidor**:

```bash
cd ~/AgroDT/ndvi
source .venv/bin/activate
export WEBODM_URL='http://127.0.0.1:8000'
read -rp 'Usuário WebODM: ' WEBODM_USER
read -rsp 'Senha WebODM: ' WEBODM_PASSWORD
echo
export WEBODM_USER WEBODM_PASSWORD
export AGRODT_API_KEY='agrodt-teste-123'
python app.py
```

Acesse http://127.0.0.1:8765 (Ctrl+Shift+R). A senha do WebODM permanece no backend; a interface pede somente a chave local da API AgroDT.

## Sessão sempre vazia ao iniciar

Toda vez que você executa `python app.py`, o AgroDT inicia **sem capturas, sem resultados e sem ortomosaicos anteriores no painel**. Antes disso, o diretório `armazenamento/` da sessão anterior é movido automaticamente para `armazenamento_backup_<data>_<id>/`. O banco SQLite, as imagens originais enviadas e os mapas anteriores ficam nesse backup. Os arquivos em `ndvi/data/` não são removidos.

Esta limpeza acontece **somente na inicialização do processo**, não ao atualizar a página no navegador. Se existir um segundo `app.py` ativo na mesma porta, a nova instância não deve mover os dados da primeira. O servidor WebODM e as tarefas remotas existentes não são apagados: apenas deixam de aparecer na nova sessão AgroDT. Backups ocupam espaço em disco e devem ser gerenciados manualmente.

## Como testar

- **Recepção do drone:** em outro terminal `export AGRODT_API_KEY='agrodt-teste-123'` e execute `python simular_drone.py --quantidade 20 --intervalo 1 --flight-id teste_01`. Esses dados são sintéticos.
- **Imagens reais separadas:** abra **Adicionar imagens** no HTML e selecione ZIP multiespectral ou par RED/NIR.
- **Ortomosaico:** coloque fotos *originais* de um voo em `ndvi/data/voo_01/` ou envie um ZIP na área **Ortomosaicos dos voos (WebODM)**. Clique em gerar. Aguarde a tarefa, o download e a prévia.
- **NDVI do ortomosaico:** é calculado automaticamente quando RED e NIR podem ser identificados com segurança no GeoTIFF. Caso contrário, selecione manualmente os índices confirmados pelos metadados do sensor.
- **Dois voos reais do Zenodo:** veja `ZENODO_2_VOOS.md` e `preparar_2_voos_zenodo.py`.

## Dados gerados (não são código Git)

```text
armazenamento/
├── entrada/<voo>/<captura>/
├── analisadas/<voo>/<captura>/
├── ortomosaicos/<voo>/
│   ├── orthophoto.tif
│   ├── preview.png
│   ├── ndvi_ortomosaico.tif
│   ├── ndvi_ortomosaico.png
│   └── processamento.json
├── voos_originais/<voo>/
└── dados/capturas.sqlite3
```

**Atenção:** o GeoTIFF NDVI preserva georreferenciamento do mosaico, mas o módulo não calibra automaticamente reflectância nem valida deslocamentos entre bandas. NDVI bruto não comprova estresse nutricional.

## Manuais

- [Guia de uso](COMO_USAR.md)
- [Atualizar e rodar no Ubuntu](COMO_RODAR.md)
- [Importador multiespectral](IMPORTADOR_GENERICO.md)
- [WebODM](WEBODM_COMO_USAR.md)
- [NDVI de ortomosaico](NDVI_ORTOMOSAICO.md)
- [Dois datasets Zenodo](ZENODO_2_VOOS.md)

Não exponha o servidor Python diretamente à internet: as rotas GET de resultados são públicas na rede em que estiver acessível. Para uso local, mantenha o host em `127.0.0.1`.
