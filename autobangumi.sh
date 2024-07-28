#!/bin/bash
# used in linuxserver/qbittorrent container

set -e

DIR=$(dirname "$0")
LOG="/tmp/autobangumi.log"

VENV="${DIR}/.venv"
PIP="${VENV}/bin/pip"
PYTHON="${VENV}/bin/python"
MAIN="${DIR}/autobangumi.py"
CONFIG="${DIR}/config.json"

if [ ! -d "${VENV}" ]; then
    echo "Creating virtual environment"
    python3 -m venv ${VENV}
    echo "Installing requirements"
    ${PIP} install -r ${DIR}/requirements.txt
fi

if [ ! -f "${MAIN}" ]; then
    echo "Error: ${MAIN} not found"
    exit 1
fi

if [ ! -f "${CONFIG}" ]; then
    echo "Warning: ${CONFIG} not found, creating from template"
    cp "${CONFIG}.template" "${CONFIG}"
fi

"${PYTHON}" \
  "${MAIN}" \
    --config ${CONFIG} \
    "$@" \
  | tee "${LOG}"
