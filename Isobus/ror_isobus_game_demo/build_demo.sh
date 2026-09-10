#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
echo
echo "Executaveis:"
echo "  build/ror_to_isobus"
echo "  build/sprayer_sim"
