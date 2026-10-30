# COMO RODAR — AgroDT / Módulo NDVI

Guia para **Ubuntu 24.04**, usando o repositório [giovanapiazza/AgroDT](https://github.com/giovanapiazza/AgroDT), pasta `ndvi/`.

O módulo recebe pares de imagens **RED e NIR** por HTTP (ou pela pasta de entrada), calcula NDVI, identifica regiões de atenção, salva os resultados em **SQLite** e apresenta uma **interface web**. **Não** envia missões para o Husky nesta versão.

> **Importante:** este módulo é diferente do projeto standalone `agrodt-ndvi-deteccao-areas`. Os arquivos e testes de versões antigas **não são importados automaticamente**. O módulo integrado ao GitHub usa `ndvi/app.py` e abre a interface na porta **8765**.

## 1. Atualizar o repositório no notebook

Abra um terminal:

```bash
cd ~/AgroDT
git status
```

### Se aparecer `working tree clean` e NÃO houver divergência

```bash
git pull --ff-only origin main
```

### Se o Git disser que as branches divergem

No seu caso, o Git já informou `Diverging branches can't be fast-forwarded` e o `git status` mostrou arquivos **excluídos em `Site/venv/`**, além de pastas não monitoradas. Faça com cuidado:

```bash
cd ~/AgroDT

# Guarde as exclusões/modificações monitoradas apenas de Site/venv:
git stash push -m "Backup Site/venv antes do NDVI" -- Site/venv

# Confira as alterações restantes:
git status --short
```

**Só continue se não restarem arquivos monitorados marcados como modificados/excluídos** (`M`, `D`, etc.). Arquivos **não monitorados** indicados por `??`, como `agrobot-simulation/`, devem permanecer intactos. Se houver outras alterações monitoradas, resolva ou faça backup antes de seguir.

```bash
# Crie um marcador de backup da branch local:
git branch "backup-main-antes-ndvi-$(date +%Y%m%d-%H%M%S)"

# Busque e integre a atualização, preservando o histórico local:
git fetch origin main
git merge --no-ff origin/main
```

Se abrir um editor para a mensagem de merge, aceite a mensagem padrão. Se aparecer `CONFLICT`, **não use `reset --hard` ou `clean -fd`**; verifique `git status` e resolva os conflitos antes de continuar. **Não execute `git stash pop` para `Site/venv`**, pois isso pode reaplicar as exclusões que você acabou de guardar.

Verifique se o módulo apareceu:

```bash
ls ~/AgroDT/ndvi
```

Deverão aparecer `app.py`, `send_capture.py`, `gerar_demo.py`, `templates/`, `requirements.txt` e `README.md`.

## 2. Primeira instalação (uma única vez)

```bash
cd ~/AgroDT/ndvi
sudo apt update
sudo apt install -y python3 python3-venv python3-numpy python3-pil
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python3 -c 'import numpy, PIL; print("Bibliotecas instaladas")'
```

> Use **aspas simples por fora** no comando `python3 -c`, pois o Bash pode interpretar `!` dentro de aspas duplas como expansão do histórico.

## 3. Terminal 1 — iniciar receptor e interface

```bash
cd ~/AgroDT/ndvi
source .venv/bin/activate
export AGRODT_API_KEY='chave-local-teste-2026'
python3 app.py --host 127.0.0.1 --port 8765
```

Mantenha esse terminal aberto. No navegador, acesse:

**http://127.0.0.1:8765**

O painel lista as capturas, mostra as imagens RED e NIR, o mapa NDVI, as regiões de atenção e os números calculados. Ele se atualiza aproximadamente a cada cinco segundos.

Para verificar se o receptor está funcionando em outro terminal:

```bash
curl http://127.0.0.1:8765/health
```

## 4. Terminal 2 — primeiro teste (imagens de demonstração)

Abra **outro terminal**:

```bash
cd ~/AgroDT/ndvi
source .venv/bin/activate
export AGRODT_API_KEY='chave-local-teste-2026'

# Criar um par sintético RED/NIR para verificar o funcionamento:
python3 gerar_demo.py

# Enviar as duas bandas ao receptor:
python3 send_capture.py \
  --red data/demo/red.png \
  --nir data/demo/nir.png \
  --capture-id foto_001 \
  --flight-id voo_demo_01
```

O resultado esperado é um JSON com `"http_status": 201` e `"status": "processed"`. Volte à interface para ver a captura. Esse teste é **sintético**, adequado para validar o fluxo de software; não é evidência de uma condição real na plantação.

## 5. Fazer um segundo teste

As capturas são identificadas por `capture_id`, que precisa ser **único em todo o banco**. Por exemplo:

```bash
python3 send_capture.py \
  --red data/demo/red.png \
  --nir data/demo/nir.png \
  --capture-id foto_002 \
  --flight-id voo_demo_02
```

**Atenção:** esse comando reenvia as mesmas imagens sintéticas, apenas com outro identificador. Para avaliar imagens diferentes, use arquivos RED/NIR diferentes, como indicado na próxima seção.

## 6. Testar imagens reais RED e NIR

O módulo **não baixa imagens reais automaticamente**. Se você já tiver dois arquivos RED e NIR monocromáticos alinhados, execute:

```bash
python3 send_capture.py \
  --red /caminho/para/RED.tif \
  --nir /caminho/para/NIR.tif \
  --flight-id voo_real_01 \
  --capture-id captura_real_001
```

Requisitos: as bandas precisam ser da **mesma cena**, ter as **mesmas dimensões**, estar **alinhadas** e usar intensidades radiometricamente comparáveis. Uma foto RGB comum não basta para calcular NDVI convencional. Um GeoTIFF multibanda precisa ter as bandas separadas antes de usar este comando. Os dados de satélite Sentinel-2 e os exemplos MicaSense são fontes possíveis, mas **não estão integrados como download automático nesta versão GitHub**.

## 7. Onde ficam as imagens?

Todo o armazenamento fica em `~/AgroDT/ndvi/armazenamento/`:

```text
ndvi/
├── data/
│   └── demo/
│       ├── red.png
│       └── nir.png
└── armazenamento/
    ├── entrada/                   # arquivos aguardando processamento
    ├── processadas/
    │   └── voo_demo_01/
    │       └── foto_001/
    │           ├── originais/
    │           │   ├── red.png
    │           │   └── nir.png
    │           ├── ndvi_mapa.png
    │           ├── ndvi_valores.npy
    │           ├── mapa_areas_atencao.png
    │           ├── mascara_atencao.png
    │           ├── areas_atencao.json
    │           └── resumo.json
    ├── erros/                     # pares que falharam
    └── dados/
        └── capturas.sqlite3       # banco de dados SQLite
```

Abra a pasta com todas as capturas processadas:

```bash
xdg-open ~/AgroDT/ndvi/armazenamento/processadas
```

Abra apenas os resultados do primeiro voo:

```bash
xdg-open ~/AgroDT/ndvi/armazenamento/processadas/voo_demo_01
```

Abra o mapa NDVI e o mapa de atenção da captura:

```bash
xdg-open ~/AgroDT/ndvi/armazenamento/processadas/voo_demo_01/foto_001/ndvi_mapa.png
xdg-open ~/AgroDT/ndvi/armazenamento/processadas/voo_demo_01/foto_001/mapa_areas_atencao.png
```

Após um processamento bem-sucedido, a pasta `entrada` fica vazia porque as imagens são **movidas automaticamente** para `processadas/`, junto dos resultados. Se falhar, os arquivos ficam em `erros/`.

## 8. Opção alternativa: copiar imagens manualmente para a entrada

Com o **Terminal 1** em execução:

```bash
cd ~/AgroDT/ndvi
mkdir -p armazenamento/entrada/voo_manual_01/captura_manual_001
cp data/demo/red.png armazenamento/entrada/voo_manual_01/captura_manual_001/red.png
cp data/demo/nir.png armazenamento/entrada/voo_manual_01/captura_manual_001/nir.png
```

O monitor detectará automaticamente o par após alguns segundos, processará os arquivos e os moverá para `processadas/voo_manual_01/captura_manual_001/`.

## 9. Próximas vezes que abrir o notebook

Não é necessário reinstalar bibliotecas nem recriar a `.venv`.

**Terminal 1:**

```bash
cd ~/AgroDT/ndvi
source .venv/bin/activate
export AGRODT_API_KEY='chave-local-teste-2026'
python3 app.py --host 127.0.0.1 --port 8765
```

**Terminal 2:**

```bash
cd ~/AgroDT/ndvi
source .venv/bin/activate
export AGRODT_API_KEY='chave-local-teste-2026'
# Envie o próximo par RED/NIR com um capture_id novo.
```

## 10. Testes de código

Com o ambiente virtual ativado:

```bash
cd ~/AgroDT/ndvi
python3 -m unittest discover -s tests -v
```

## 11. Problemas comuns

| Mensagem | O que verificar |
|---|---|
| `Diverging branches can't be fast-forwarded` | Sua `main` local tem commits diferentes; veja a seção 1 para fazer merge preservando histórico. |
| `CONFLICT` no merge | Pare e veja `git status`. Não apague os arquivos sem avaliar o conflito. |
| `Address already in use` | Outro receptor está usando a porta 8765; encerre-o ou escolha outra porta e atualize `--pi`. |
| `401` | A variável `AGRODT_API_KEY` precisa estar igual no receptor e no envio. |
| `409` | O `capture_id` já existe; use outro identificador. |
| `422` | Verifique as dimensões, formato monocromático e integridade das bandas. |
| Interface vazia | Confirme se o envio retornou HTTP 201 e se você abriu `http://127.0.0.1:8765`. |
| `ModuleNotFoundError` | Confirme `source .venv/bin/activate` e a instalação das bibliotecas. |

## 12. Limitações importantes

- Valores baixos de NDVI indicam **possíveis regiões de atenção**; não confirmam falta de nutrientes, doença ou necessidade de pulverização.
- As regiões detectadas usam coordenadas em **pixels**, ainda não coordenadas geográficas para o Husky A300.
- O painel e as rotas de leitura **não têm autenticação** nesta versão. Use `127.0.0.1` para testes locais; não exponha o serviço diretamente à internet.
- A execução em Raspberry Pi física ainda precisa ser validada no equipamento.

---

**Arquivos do módulo:** [repositório GitHub / ndvi](https://github.com/giovanapiazza/AgroDT/tree/main/ndvi).