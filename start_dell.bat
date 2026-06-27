@echo off
REM === CEXO Dell-Zelle ("Herz") ===
REM Herz = cexo_orca 1.5B (geometrischer Kern, Denken)
REM Mund = das installierte 7B-Modell (Sprechen)
REM Keine 5 Spezialisten — nur Herz + Mund.

set CEXO_OLLAMA_HOST=http://127.0.0.1:11434
set CEXO_OLLAMA_MODEL=cexo_orca
set CEXO_ARMS=mund=glm-4.7-flash
set CEXO_CELL=herz
set CEXO_INSTANCE=dell
set CEXO_INSTANCES=3
set CEXO_HOST=0.0.0.0
set CEXO_PORT=8000
set CEXO_BREATH=1
set CEXO_SELFMOD=1
set CEXO_DEEPSLEEP_EVERY=27

REM Mund = glm-4.7-flash (bereits installiert auf dem Dell)

python orca.py serve
