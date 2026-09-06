#!/usr/bin/env python3
"""Combien de temps prend get_trendbars, par timeframe ? LECTURE SEULE.

Les graphiques ont expiré sur m5/m15/h1 alors que le m1 passe depuis ce matin.
Hypothèse : cTrader doit télécharger l'historique d'un timeframe qu'il n'a pas
encore chargé. On mesure au lieu de gonfler le délai à l'aveugle.
"""

import os
import sys
import time

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from ctrader.mcp import Client, ErreurMCP                    # noqa: E402

SYMBOLE = "EURUSD.raw"
FENETRES = [
    ("m1",  "2026-08-07T11:00:00Z", "2026-08-07T13:00:00Z"),
    ("m5",  "2026-08-07T09:00:00Z", "2026-08-07T15:00:00Z"),
    ("m15", "2026-08-06T11:00:00Z", "2026-08-08T13:00:00Z"),
    ("h1",  "2026-08-05T11:00:00Z", "2026-08-09T13:00:00Z"),
    ("h4",  "2026-07-20T00:00:00Z", "2026-08-10T00:00:00Z"),
]


def main():
    client = Client().ouvrir()
    print("session ouverte · symbole %s\n" % SYMBOLE)
    print("  %-5s %-10s %-8s %s" % ("tf", "duree", "barres", "2e appel (cache ?)"))
    for tf, debut, fin in FENETRES:
        for passe in (1, 2):
            t0 = time.time()
            try:
                r = client.appeler("get_trendbars", {
                    "symbolName": SYMBOLE, "timeframe": tf,
                    "from": debut, "to": fin, "limit": 1000})
                n = len((r or {}).get("bars") or [])
                ecoule = time.time() - t0
                if passe == 1:
                    print("  %-5s %7.1f s  %6d" % (tf, ecoule, n), end="")
                else:
                    print("   %7.1f s" % ecoule)
            except ErreurMCP as e:
                ecoule = time.time() - t0
                msg = str(e).splitlines()[0]
                if passe == 1:
                    print("  %-5s %7.1f s  ECHEC : %s" % (tf, ecoule, msg[:60]), end="")
                else:
                    print("   %7.1f s ECHEC" % ecoule)
    print("\n(rien n'a ete ecrit)")


if __name__ == "__main__":
    main()
