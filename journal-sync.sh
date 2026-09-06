#!/bin/bash
# @raycast.schemaVersion 1
# @raycast.title Journal de trading — sync
# @raycast.mode silent
# @raycast.icon 📓
# @raycast.packageName Trading
# @raycast.description Assistant guidé : relevé cTrader -> base locale -> Edgewonk

# --- Où est le projet ? -------------------------------------------------------
# Le script se localise TOUT SEUL, en remontant les liens symboliques jusqu'à son
# vrai emplacement. Conséquence : si tu installes le lanceur Raycast avec `ln -s`
# plutôt qu'avec `cp`, déplacer le dossier du projet ne casse plus rien ici — il
# n'y a qu'à refaire le lien.
#
#     ln -sf "<chemin du projet>/journal-sync.sh" ~/Documents/Automation/
#
# CHEMIN_DE_SECOURS ne sert que si le lanceur est une COPIE : dans ce cas la
# copie ignore où vit le projet, et c'est la seule ligne à corriger après un
# déplacement.
CHEMIN_DE_SECOURS="$HOME/Projects/trading-journal"

SOURCE="${BASH_SOURCE[0]}"
while [ -L "$SOURCE" ]; do
  DOSSIER="$(cd -P "$(dirname "$SOURCE")" && pwd)"
  SOURCE="$(readlink "$SOURCE")"
  [[ "$SOURCE" != /* ]] && SOURCE="$DOSSIER/$SOURCE"
done
PROJET="$(cd -P "$(dirname "$SOURCE")" && pwd)"

# Le marqueur, c'est `pipeline/journal.py` : sans lui on n'est pas dans le projet.
if [ ! -f "$PROJET/pipeline/journal.py" ]; then
  PROJET="$CHEMIN_DE_SECOURS"
fi

if [ ! -f "$PROJET/pipeline/journal.py" ]; then
  osascript -e 'display alert "Journal de trading — projet introuvable" message "Ni le lanceur ni le chemin de secours ne mènent au projet.\n\nSi tu as déplacé le dossier : refais le lien\n  ln -sf \"<nouveau chemin>/journal-sync.sh\" ~/Documents/Automation/\nou corrige CHEMIN_DE_SECOURS dans journal-sync.sh." as critical'
  exit 1
fi

# --- Quel python ? ------------------------------------------------------------
# Les étapes 1, 2, 3 et 5 sont en stdlib pure : elles tournent avec n'importe quel
# python3. Seule l'étape 4 (graphiques) a besoin de matplotlib et mplfinance, qui
# vivent dans .venv/ — Homebrew refuse les installations système (PEP 668).
# On prend donc le venv S'IL EXISTE, et on retombe sur python3 sinon : le projet
# reste utilisable même sans lui.
PY="$PROJET/.venv/bin/python3"
[ -x "$PY" ] || PY="python3"

osascript <<APPLESCRIPT
tell application "Terminal"
  activate
  do script "clear && cd '$PROJET/pipeline' && '$PY' journal.py"
end tell
APPLESCRIPT
