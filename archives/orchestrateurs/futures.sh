#!/bin/bash
# Le cycle futures complet, d'un bloc. Ecrit le 28/08/2026.
#
# Pourquoi un script et pas six commandes : le fichier de saisie est nomme avec
# l'horodatage de l'import, donc son nom n'existe pas avant de l'avoir lance.
# Le retrouver a la main a chaque fois est le genre de friction qui fait sauter
# une etape — et l'etape sautee ici, c'est `integrer`.
#
#   ./futures.sh                 le dernier export deja archive
#   ./futures.sh mon-export.csv  un nouvel export
#
# Rien n'est force : `pousser` demande toujours ENVOYER avant d'ecrire chez
# Edgewonk, et chaque ecriture en base pose son instantane.

set -e
cd "$(dirname "$0")"

# ⚠️ LE VENV, ET PAS `python3`. Mesure du 28/08/2026, sur le premier passage
# reel : les quatre premieres etapes passent avec le python systeme, la
# cinquieme meurt sur « No module named 'pandas' » — matplotlib et mplfinance
# vivent dans .venv/ (Homebrew refuse les installations systeme, PEP 668).
# Faire mourir un enchainement a l'avant-derniere etape est la pire facon de
# rater : tout est ecrit, rien n'est visible. Meme regle que `journal-sync.sh`,
# on prend le venv s'il existe et on retombe sur python3 sinon.
PY_BIN="../.venv/bin/python3"
[ -x "$PY_BIN" ] || PY_BIN="python3"

EXPORT="${1:-$(ls -t ../donnees/brut/*tradovate*.csv | head -1)}"
[ -f "$EXPORT" ] || { echo "export introuvable : $EXPORT"; exit 1; }

echo
echo "════════ 1/5  IMPORT ════════"
echo "export : $EXPORT"
"$PY_BIN" jt.py importer --tradovate "$EXPORT"

SAISIE=$(ls -t ../donnees/saisies/sltp_*.csv | head -1)
echo
echo "════════ 2/5  CONTROLE ════════"
echo "saisie : $SAISIE"
"$PY_BIN" jt.py controler --tradovate "$SAISIE"

echo
echo "════════ 3/5  INTEGRATION ════════"
# On RETIENT si des niveaux ont ete ecrits — l'etape 4 en depend. Passage par
# un fichier et non `tee /dev/tty` : le script doit aussi tourner sans terminal
# (cron, `journal-sync.sh`), et /dev/tty n'existe pas la-bas.
JOURNAL=$(mktemp)
trap 'rm -f "$JOURNAL"' EXIT
"$PY_BIN" jt.py integrer --tradovate "$SAISIE" 2>&1 | tee "$JOURNAL"
INTEGRE=$(grep -Eo '^ +[0-9]+ valeurs' "$JOURNAL" | grep -Eo '[0-9]+' | head -1 || true)
INTEGRE="${INTEGRE:-0}"

echo
echo "════════ 4/5  BOUGIES + GRAPHIQUES ════════"
"$PY_BIN" jt.py bougies --tradovate

# ⚠️ UN SL QUI ARRIVE REND LES GRAPHIQUES PERIMES, ET EN SILENCE.
# Mesure du 28/08/2026, sur le premier passage reel : le gabarit trace le SL et
# le TP en pointilles (`graphiques/gabarit.py`), or `graphiques` saute toute
# position dont les PNG sont deja sur le disque. Les 24 positions qui venaient
# de gagner leurs niveaux gardaient donc des images SANS ces lignes — des
# images justes le mois dernier, fausses aujourd'hui, et rien ne le disait.
# Des que l'integration a ecrit quelque chose, on redessine.
if [ "$INTEGRE" -gt 0 ]; then
  echo "  ($INTEGRE valeur(s) integree(s) — les niveaux ont change, on redessine)"
  "$PY_BIN" jt.py graphiques --tradovate --refaire
else
  "$PY_BIN" jt.py graphiques --tradovate
fi

echo
echo "════════ 5/5  POUSSEE EDGEWONK ════════"
"$PY_BIN" jt.py pousser --tradovate

echo
echo "termine. saisie utilisee : $SAISIE"
echo "python     : $PY_BIN"
