#!/usr/bin/env python3
"""Diagnostic n°3 — LECTURE SEULE. Trouve le decalage horaire par la MESURE.

L'appariement par horodatage a rendu 0/46. Plutot que de deviner le fuseau, on
apparie d'abord sur un pivot qui n'en depend PAS — le montant net, au centime —
puis on LIT le decalage sur les couples ainsi obtenus.

`docs/tradovate.md` §5 bis avait deja releve 2 h d'ecart entre l'export et Edgewonk,
en notant que « le traitement du fuseau semble differer d'un importateur a
l'autre ». On verifie si cTrader est logé a la meme enseigne.
"""

import collections
import datetime as dt
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base                                       # noqa: E402
from edgewonk.api import Client                             # noqa: E402

TRADES = os.path.normpath(os.path.join(RACINE, "..", "donnees", "trades.csv"))
BASE_COURANTE = "100001"


def titre(t):
    print("\n" + t)
    print("-" * len(t))


def vwap(t, type_jambe):
    for s in sorted(t.get("scalings") or [], key=lambda x: x.get("id") or 0):
        if s.get("type") == type_jambe:
            return s.get("scalingPrice")
    return None


def main():
    client = Client().authentifier()
    tous = client.tous_les_trades(BASE_COURANTE)
    print("%d trades lus" % len(tous))
    nos = base.charger(TRADES)

    titre("1. Appariement par MONTANT + instrument + sens (sans aucune heure)")
    par_montant = collections.defaultdict(list)
    for t in tous:
        g = t.get("gain")
        if g is None:
            continue
        par_montant[((t.get("instrument") or {}).get("name"),
                     t.get("direction"), round(float(g), 2))].append(t)

    couples, sans, multiples = [], [], []
    for c, x in sorted(nos.items()):
        cle = (x["symbole_broker"], "BUY" if x["sens"] == "Achat" else "SELL",
               round(float(x["net"]), 2))
        lot = par_montant.get(cle, [])
        if len(lot) == 1:
            couples.append((c, x, lot[0]))
        elif len(lot) > 1:
            multiples.append((c, x, lot))
        else:
            sans.append(c)
    print("  uniques   : %d / %d" % (len(couples), len(nos)))
    print("  multiples : %d" % len(multiples))
    print("  aucun     : %d" % len(sans))

    titre("2. Le decalage horaire, LU sur les couples uniques")
    ecarts = collections.Counter()
    for c, x, t in couples:
        try:
            n = dt.datetime.fromisoformat(x["cloture"][:19])
            e = dt.datetime.fromisoformat(t["exitDate"][:19])
        except (ValueError, TypeError):
            continue
        ecarts[round((n - e).total_seconds() / 60.0)] += 1
    for minutes, n in ecarts.most_common(8):
        print("  notre heure - Edgewonk = %+5d min  (%+.1f h)  ->  %d trade(s)"
              % (minutes, minutes / 60.0, n))
    if ecarts:
        dominant = ecarts.most_common(1)[0]
        print()
        print("  DECALAGE DOMINANT : %+d min sur %d/%d couples"
              % (dominant[0], dominant[1], len(couples)))

    titre("3. Verification sur la position du 07/08 13:43")
    for c, x, t in couples:
        if not c.startswith("20260807-134318"):
            continue
        print("  %s" % c)
        print("      nous     : entree %s  sortie %s  net %s  lots %s"
              % (x["ouverture"][:19], x["cloture"][:19], x["net"], x["volume_lots"]))
        print("      Edgewonk : entree %s  sortie %s  gain %s  qte %s   id %s"
              % (t.get("entryDate"), t.get("exitDate"), t.get("gain"),
                 t.get("quantity"), t.get("id")))
        print("      prix     : nous %s -> %s   |   Edgewonk %s -> %s"
              % (x["entree"], x["sortie"], vwap(t, "START_ENTRY"), vwap(t, "CLOSE_ENTRY")))

    titre("4. Les cas non apparies par le montant")
    for c in sans[:10]:
        x = nos[c]
        print("  %-34s %s %s net %s" % (c, x["sens"], x["symbole_broker"], x["net"]))
    if len(sans) > 10:
        print("  … et %d autres" % (len(sans) - 10))
    for c, x, lot in multiples[:5]:
        print("  AMBIGU %-30s net %s -> %d candidats (sorties %s)"
              % (c, x["net"], len(lot), [t.get("exitDate") for t in lot]))

    titre("5. Le prix d'entree concorde-t-il ?")
    ecarts_px = 0
    for c, x, t in couples:
        p = vwap(t, "START_ENTRY")
        if p is not None and abs(float(p) - float(x["entree"])) > 1e-9:
            ecarts_px += 1
    print("  couples dont le VWAP d'entree differe : %d / %d" % (ecarts_px, len(couples)))

    titre("Rien n'a ete ecrit")


if __name__ == "__main__":
    main()
