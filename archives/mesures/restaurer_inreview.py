#!/usr/bin/env python3
"""Repare les `inReview` poses a tort le 25/08/2026.

Cause : le controle comparait (entree - sortie) x quantite x `multiplier` au
gainGross. Or `multiplier` vaut 1.0 chez Edgewonk, y compris sur EURUSD — ce
n'est PAS la taille du contrat. Le controle obtenait 0.00027 face a 27.00 et
concluait a l'incoherence sur 40 trades sains.

Ce script relit l'instantane pris AVANT l'ecriture, recalcule qui merite
reellement le marqueur (par comparaison de PRIX a PRIX), et remet les autres
dans leur etat d'origine. Relecture apres chaque ecriture.
"""

import glob
import io
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base                                       # noqa: E402
from edgewonk.api import Client                             # noqa: E402
from edgewonk.appariement import apparier                   # noqa: E402
from edgewonk.ecriture import prix_divergents               # noqa: E402

DONNEES = os.path.normpath(os.path.join(RACINE, "..", "donnees"))
BASE_EDGEWONK = "100001"


def main():
    fichiers = sorted(glob.glob(os.path.join(DONNEES, "instantanes",
                                             "edgewonk-%s-*.json" % BASE_EDGEWONK)))
    if not fichiers:
        sys.exit("aucun instantane Edgewonk trouve")
    avant = json.load(io.open(fichiers[-1], encoding="utf-8"))
    print("instantane de reference : %s (%d trades)"
          % (os.path.basename(fichiers[-1]), len(avant)))

    nos = base.charger(os.path.join(DONNEES, "trades.csv"))
    client = Client().authentifier()
    distants = client.tous_les_trades(BASE_EDGEWONK)
    couples, _, _, _ = apparier(nos, distants)

    # qui merite REELLEMENT le marqueur ?
    legitimes = set()
    for cle, jambe, trade in couples:
        divergent, detail = prix_divergents(jambe, trade)
        if divergent:
            legitimes.add(str(trade.get("id")))
            print("  legitime : id %s — %s" % (trade.get("id"), detail))

    a_defaire = []
    for tid, etat in avant.items():
        if etat.get("inReview"):
            continue                       # il l'etait deja avant : on n'y touche pas
        if tid in legitimes:
            continue                       # marqueur justifie : on le garde
        a_defaire.append(tid)

    print()
    print("  marques a tort, a remettre a false : %d" % len(a_defaire))
    print("  marqueurs legitimes conserves      : %d" % len(legitimes))
    if not a_defaire:
        print("  rien a reparer.")
        return

    print("\n  Tape ENVOYER pour corriger.")
    try:
        if input("  > ").strip().upper() != "ENVOYER":
            sys.exit("\nRien n'a ete modifie.")
    except (EOFError, KeyboardInterrupt):
        sys.exit("\nRien n'a ete modifie.")

    remis, echecs = 0, []
    for i, tid in enumerate(a_defaire, 1):
        try:
            client.modifier(BASE_EDGEWONK, int(tid), {"inReview": False})
            relu = client.trade(BASE_EDGEWONK, int(tid))
            if relu.get("inReview"):
                echecs.append("id %s : toujours inReview apres ecriture" % tid)
            else:
                remis += 1
        except Exception as e:                                # noqa: BLE001
            echecs.append("id %s : %s" % (tid, e))
        sys.stdout.write("\r  %d/%d" % (i, len(a_defaire)))
        sys.stdout.flush()
    print()
    print("  remis a false et CONFIRMES PAR RELECTURE : %d" % remis)
    for e in echecs:
        print("  ECHEC " + e)


if __name__ == "__main__":
    main()
