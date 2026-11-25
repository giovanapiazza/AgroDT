# Como atualizar e rodar — NDVI + WebODM (Ubuntu 24.04)

> Este documento substitui instrucoes das primeiras versoes. A interface atual inclui capturas individuais, importacao de bandas, ortomosaicos WebODM e NDVI do ortomosaico.

## 1. Encerrar o que estiver rodando

Encerre com Ctrl+C qualquer `python app.py`, simulador ou script NDVI. O WebODM em Docker pode continuar funcionando.

## 2. Atualizar o GitHub no notebook (sobrescrever arquivos monitorados)

**Antes de atualizar, confira**:

```bash
cd ~/AgroDT
git status --short
git fetch origin main
```

Para atualizar **todo o repositório**, descartando modificações locais *em arquivos monitorados*:

```bash
git branch "backup-local-$(date +%Y%m%d_%H%M%S)"
git reset --hard origin/main
```

Isso **não** exclui automaticamente arquivos não monitorados, o ambiente `.venv` ou dados ignorados por `.gitignore`. Não execute `git clean -fdx`: ele apagaria também arquivos de dados e ambientes virtuais.

Se quiser substituir **apenas a pasta NDVI** e preservar outros projetos:

```bash
git fetch origin main
git restore --source=origin/main --staged --worktree ndvi/
```

Para inspecionar arquivos não rastreados antes de excluí-los:

```bash
git clean -nd ndvi/
```

Só use `git clean -fd ndvi/` depois de ler a prévia e salvar seus arquivos pessoais. Arquivos ignorados permanecem, mas a exclusão de arquivos não rastreados é irreversível sem backup.

## 3. Instalar dependências atuais

```bash
cd ~/AgroDT/ndvi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-webodm.txt
```

Se o ambiente virtual já existe, basta ativá-lo e executar o comando `pip install -r`.

## 4. Testar código e arquivos

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
git -C ~/AgroDT rev-parse --short HEAD
```

O NDVI também tem testes GitHub Actions em `.github/workflows/ndvi-tests.yml`.

## 5. Verificar WebODM

```bash
cd ~/WebODM
./webodm.sh start
```

Em outro terminal:

```bash
docker ps
curl -I http://127.0.0.1:8000
```

A interface WebODM deverá abrir em http://127.0.0.1:8000, com um nó de processamento configurado.

## 6. Iniciar AgroDT com WebODM integrado

```bash
cd ~/AgroDT/ndvi
source .venv/bin/activate

export WEBODM_URL="http://127.0.0.1:8000"
read -rp "Usuário WebODM: " WEBODM_USER
read -rsp "Senha WebODM: " WEBODM_PASSWORD
echo
export WEBODM_USER WEBODM_PASSWORD

export AGRODT_API_KEY="agrodt-teste-123"
python app.py
```

Abra http://127.0.0.1:8765 (Ctrl+Shift+R). Os resultados antigos não reaparecem se você já arquivou `armazenamento/` usando `limpar_historico.py`.

## 7. Teste da simulação de drone

Em outro terminal:

```bash
cd ~/AgroDT/ndvi
source .venv/bin/activate
export AGRODT_API_KEY="agrodt-teste-123"
python simular_drone.py --quantidade 10 --intervalo 1 --flight-id teste_simulado_01
```

O painel deve apresentar 10 análises. Esses dados são sintéticos.

## 8. Teste de ortomosaico com duas missões reais

Consulte [ZENODO_2_VOOS.md](ZENODO_2_VOOS.md) para tentar obter dois ZIPs reais de voos independentes. Na seção **Ortomosaicos dos voos** do AgroDT, envie um ZIP, indique um ID único para o voo, informe a chave `AGRODT_API_KEY` e clique em **Enviar ZIP e gerar ortomosaico**.

Depois de o WebODM concluir, confira na seção do voo:
- ortomosaico `preview.png` e `orthophoto.tif`;
- mapa `ndvi_ortomosaico.png` se as bandas RED e NIR forem detectadas;
- ou mensagem para escolher as bandas manualmente, quando necessário.

Se a tarefa WebODM falhar, veja o log no WebODM e os estados em `armazenamento/ortomosaicos/<voo>/processamento.json`.

## 9. Arquivos locais e backups

Pastas `armazenamento/`, `data/`, `.venv/` e `armazenamento_backup_*/` são conteúdo local e não fazem parte do código versionado. Não exclua essas pastas ao atualizar. O comando `python limpar_historico.py`, com servidor parado, arquiva dados existentes e inicia um painel vazio na próxima execução.
