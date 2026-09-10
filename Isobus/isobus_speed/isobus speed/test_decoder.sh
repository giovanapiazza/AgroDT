#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT="$("${ROOT_DIR}/decode_machine_selected_speed.py" AE 08 A0 86 01 00 C0 11)"

grep -q "2222 mm/s" <<<"${OUTPUT}"
grep -q "100000 mm" <<<"${OUTPUT}"
grep -q "Forward" <<<"${OUTPUT}"
grep -q "Simulated" <<<"${OUTPUT}"
grep -q "Not Limited" <<<"${OUTPUT}"
grep -q "corretos" <<<"${OUTPUT}"

echo "Teste do decodificador concluido com sucesso."
