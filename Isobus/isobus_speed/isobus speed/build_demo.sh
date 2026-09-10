#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${BUILD_DIR:-${ROOT_DIR}/build}"

cmake_args=(-S "${ROOT_DIR}" -B "${BUILD_DIR}")
if [[ -n "${AGISOSTACK_DIR:-}" ]]; then
    cmake_args+=("-DAGISOSTACK_DIR=${AGISOSTACK_DIR}")
fi

cmake "${cmake_args[@]}"
cmake --build "${BUILD_DIR}" -j"$(nproc)"

echo
echo "Compilacao concluida."
echo "Executaveis:"
echo "  ${BUILD_DIR}/tractor_sim"
echo "  ${BUILD_DIR}/sprayer_sim"
