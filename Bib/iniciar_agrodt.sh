#!/bin/bash
# Script para iniciar o sistema AgroDT

# Navega para a pasta do projeto
cd ~/AgroDT/Bib

# Ativa o ambiente
source .venv/bin/activate

echo "==============================="
echo "   SISTEMA AGRODT INICIADO     "
echo "==============================="
echo "1) Rodar Tradutor em Lote (Batch)"
echo "2) Rodar Interface Web (Streamlit)"
echo "3) Rodar Testes de Validação"
echo "4) Sair"
echo "==============================="

read -p "Escolha uma opção [1-4]: " opcao

case $opcao in
    1) python3 batch_translator.py ;;
    2) streamlit run app.py ;;
    3) pytest test_migration.py ;;
    4) exit ;;
    *) echo "Opção inválida" ;;
esac
