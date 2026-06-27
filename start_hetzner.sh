#!/usr/bin/env bash
# === CEXO Hetzner-Zelle ("Botschafter") ===
# Herz = cexo_orca 1.5B (geometrischer Kern)
# Kein Mund — der Botschafter spricht durch sein Herz.
# Schwere Anfragen eskaliert er an den Dell (Herz-Zelle).

export CEXO_OLLAMA_HOST="http://127.0.0.1:11434"
export CEXO_OLLAMA_MODEL="cexo_orca"
export CEXO_ARMS=""
export CEXO_CELL="botschafter"
export CEXO_INSTANCE="hetzner"
export CEXO_INSTANCES=3
export CEXO_HOST="0.0.0.0"
export CEXO_PORT=8000
export CEXO_BREATH=1
export CEXO_SELFMOD=1
export CEXO_DEEPSLEEP_EVERY=27
# Peer-Adresse des Dell (wenn erreichbar):
# export CEXO_PEER_HERZ="http://DELL_IP:8000"

exec python3 cexo_voice.py serve
