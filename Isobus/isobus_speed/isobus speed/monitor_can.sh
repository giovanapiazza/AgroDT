#!/usr/bin/env bash
set -euo pipefail

CAN_INTERFACE="${1:-${ISOBUS_CAN_INTERFACE:-can0}}"

if ! command -v candump >/dev/null 2>&1; then
    echo "Erro: candump nao encontrado. Instale o pacote can-utils." >&2
    exit 1
fi

echo "Monitorando ${CAN_INTERFACE}. O PGN 0xF022 aparece normalmente como CAN ID 0x0CF022xx."
echo "Pressione Ctrl+C para encerrar."
candump -tz "${CAN_INTERFACE}"
