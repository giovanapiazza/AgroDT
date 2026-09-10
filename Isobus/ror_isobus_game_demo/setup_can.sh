#!/usr/bin/env bash
set -euo pipefail
sudo modprobe vcan
if ! ip link show can0 >/dev/null 2>&1; then
    sudo ip link add dev can0 type vcan
fi
sudo ip link set can0 up
echo "can0 pronta."
