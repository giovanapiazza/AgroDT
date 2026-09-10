#!/usr/bin/env bash
set -euo pipefail

CAN_INTERFACE="${1:-${ISOBUS_CAN_INTERFACE:-can0}}"

if [[ ! "${CAN_INTERFACE}" =~ ^[a-zA-Z0-9_.:-]+$ ]]; then
    echo "Nome de interface invalido: ${CAN_INTERFACE}" >&2
    exit 1
fi

if ! command -v ip >/dev/null 2>&1; then
    echo "Erro: o comando 'ip' nao foi encontrado. Instale o pacote iproute2." >&2
    exit 1
fi

SUDO=""
if [[ "${EUID}" -ne 0 ]]; then
    if ! command -v sudo >/dev/null 2>&1; then
        echo "Erro: execute como root ou instale/configure o sudo." >&2
        exit 1
    fi
    SUDO="sudo"
fi

if ! ip link show "${CAN_INTERFACE}" >/dev/null 2>&1; then
    ${SUDO} modprobe vcan
    ${SUDO} ip link add dev "${CAN_INTERFACE}" type vcan
    echo "Interface virtual ${CAN_INTERFACE} criada."
fi

${SUDO} ip link set "${CAN_INTERFACE}" up

echo "Interface ${CAN_INTERFACE} pronta:"
ip -details link show "${CAN_INTERFACE}"
echo
echo "Use nos simuladores:"
echo "  export ISOBUS_CAN_INTERFACE=${CAN_INTERFACE}"
