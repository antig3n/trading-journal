#!/usr/bin/env python3
"""Diagnostic ciblé — NE MODIFIE RIEN.

Question posée : sur la position du 07/08 13:43, le plus haut mesuré est
1.15685 alors que la sortie est à 1.15470. Deux explications possibles, qui
appellent des corrections opposées :

  (a) le prix est monté à 1.15685 PENDANT le trade
      -> alors le TP saisi (1.15470) n'était pas le TP initial : il coïncide
         avec le prix de sortie, donc probablement recopié depuis la sortie.
         `tp_touche_en_premier = oui` serait un faux positif.

  (b) le 1.15685 est atteint APRÈS la sortie, dans la bougie de bord
      -> alors c'est notre fenêtre qui déborde, et il faut la resserrer.
         C'est le problème M5 documenté au §7 bis, en version M1.

On ne devine pas : on regarde à quelle minute le maximum tombe.
"""

import datetime as dt
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base                                  # noqa: E402
from ctrader import bougies                            # noqa: E402
from ctrader.mcp import Client, ErreurMCP              # noqa: E402

TRADES = os.path.normpath(os.path.join(RACINE, "..", "donnees", "trades.csv"))
CIBLE = "20260807-134318-EURUSD-A"


def main():
    trades = base.charger(TRADES)
    positions = base.grouper_en_positions(trades)
    p = positions.get(CIBLE)
    if not p:
        sys.exit("position %s absente de la base" % CIBLE)

    # ⚠️ CE MODULE SONDE LE MCP cTRADER. Depuis la fusion des bases, la cible
    # pourrait etre une position futures — et le serveur repondrait « Symbol
    # not available » en texte. On refuse clairement plutot que d'echouer plus
    # loin sur un message qui ne dit pas pourquoi.
    if (trades[p["jambes"][0]].get("plateforme") or "ctrader") != "ctrader":
        sys.exit("%s est une position futures — ce diagnostic interroge le MCP "
                 "cTrader.\n  Les bougies futures viennent de Databento." % CIBLE)
    jambes = sorted((trades[c] for c in p["jambes"]), key=lambda t: t["cloture"])
    derniere = jambes[-1]

    client = Client().ouvrir()
    brut = bougies.recuperer(client, derniere["symbole_broker"],
                             derniere["ouverture"], derniere["cloture"])
    print("bougies M1 recuperees : %d" % len(brut))

    sortie = bougies._utc(derniere["cloture"])
    entree = bougies._utc(derniere["ouverture"])
    print("entree  (UTC) : %s" % entree.strftime("%H:%M:%S"))
    print("sortie  (UTC) : %s   prix %s" % (sortie.strftime("%H:%M:%S"), derniere["sortie"]))
    print("SL / TP saisis : %s / %s" % (derniere["sl"], derniere["tp"]))
    print()

    # ⚠️ `_borne` N'EXISTE PLUS. Elle a été remplacée par `_decouper`, qui rend
    # DEUX listes au lieu d'une : les bougies intérieures (entièrement dans le
    # trade, donc dont l'extrême lui appartient à coup sûr) et les bougies de
    # BORD (qui chevauchent l'entrée ou la sortie, donc dont l'extrême peut
    # être hors du trade). C'est précisément la distinction que ce module
    # existe pour examiner — il ne pouvait pas continuer à ignorer.
    #
    # Le renommage remonte à plusieurs jours ; ce module était cassé depuis, et
    # personne ne l'avait vu parce qu'il n'était jamais lancé. Trouvé le
    # 29/08/2026 par le premier audit qui lance TOUT. *Un outil qu'on ne lance
    # pas ne vieillit pas, il pourrit.*
    interieures, bords = bougies._decouper(brut, derniere["ouverture"],
                                           derniere["cloture"])
    fenetre = interieures + bords
    fenetre.sort(key=bougies._horodatage_bougie)
    print("bougies retenues : %d interieures + %d de bord = %d"
          % (len(interieures), len(bords), len(fenetre)))
    if not fenetre:
        sys.exit("aucune bougie")

    sommet = max(fenetre, key=lambda b: float(b["high"]))
    t_sommet = dt.datetime.fromisoformat(sommet["timestamp"].replace("Z", "+00:00"))
    print()
    print("PLUS HAUT      : %s  a la bougie %s" % (sommet["high"], sommet["timestamp"]))
    print("               : %s la sortie"
          % ("APRES" if t_sommet >= sortie.replace(second=0, microsecond=0) else "avant"))
    ecart = (t_sommet - sortie).total_seconds() / 60.0
    print("               : %+.0f minutes par rapport a la sortie" % ecart)
    print()

    tp = float(derniere["tp"])
    premiere_au_dessus = None
    for b in fenetre:
        if float(b["high"]) >= tp:
            premiere_au_dessus = b
            break
    if premiere_au_dessus:
        t = dt.datetime.fromisoformat(premiere_au_dessus["timestamp"].replace("Z", "+00:00"))
        print("TP %s franchi pour la 1re fois a %s (%+.0f min / sortie)"
              % (tp, premiere_au_dessus["timestamp"], (t - sortie).total_seconds() / 60.0))
    print()

    print("--- les 10 dernieres bougies de la fenetre ---")
    print("  %-22s %-9s %-9s %-9s %-9s" % ("timestamp", "open", "high", "low", "close"))
    for b in fenetre[-10:]:
        t = dt.datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
        marque = "  <== bougie de la sortie" if t.strftime("%H:%M") == sortie.strftime("%H:%M") else ""
        print("  %-22s %-9s %-9s %-9s %-9s%s"
              % (b["timestamp"], b["open"], b["high"], b["low"], b["close"], marque))
    print()
    print("--- les 5 bougies de plus haut high, avec leur heure ---")
    for b in sorted(fenetre, key=lambda b: -float(b["high"]))[:5]:
        t = dt.datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
        print("  %s  high %s   %+.0f min / sortie"
              % (b["timestamp"], b["high"], (t - sortie).total_seconds() / 60.0))
    print("\n(rien n'a ete ecrit)")


if __name__ == "__main__":
    main()
