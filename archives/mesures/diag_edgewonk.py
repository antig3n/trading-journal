#!/usr/bin/env python3
"""Diagnostic Edgewonk — LECTURE SEULE. Aucune écriture, aucun modify, aucun PUT.

    cd pipeline && python3 outils/diag_edgewonk.py

Prérequis, une seule fois, dans un Terminal :
    security add-generic-password -s edgewonk -a <ton-email> -w
(sans mettre le mot de passe sur la ligne : `security` le demandera, il ne
restera donc pas dans l'historique du shell.)

Ce qu'on cherche à savoir, et qu'on ne veut pas supposer :
  1. la chaîne d'authentification fonctionne-t-elle ?
  2. quelle est la forme EXACTE de `entryDate` / `exitDate` — à la seconde ou
     à la minute ? dans quel fuseau ? C'est le pivot de l'appariement, et
     `docs/tradovate.md` §5 bis rappelle qu'un décalage silencieux de fuseau est
     exactement ce qui fait rater des rapprochements sans qu'on le voie.
  3. combien de trades Edgewonk couvrent la période de notre base ?
"""

import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base                                       # noqa: E402
from edgewonk.api import Client, ErreurEdgewonk             # noqa: E402

TRADES = os.path.normpath(os.path.join(RACINE, "..", "donnees", "trades.csv"))
BASE_COURANTE = "100001"          # Compte A


def titre(t):
    print("\n" + t)
    print("-" * len(t))


def vwap(trade, type_jambe):
    """Le prix agrégé de la jambe. L'ordre de `scalings` n'est pas stable d'un
    appel à l'autre : on trie par id avant de lire, sinon les comparaisons
    produisent des faux positifs."""
    for s in sorted(trade.get("scalings") or [], key=lambda x: x.get("id") or 0):
        if s.get("type") == type_jambe:
            return s.get("scalingPrice")
    return None


def main():
    try:
        client = Client().authentifier()
    except ErreurEdgewonk as e:
        sys.exit("\n%s\n" % e)
    print("authentifie — jeton valide jusqu'a %s" % client.valide_jusqu_a())

    titre("1. Bases disponibles")
    try:
        for b in client.bases() or []:
            marque = "  <== base courante" if str(b.get("id")) == BASE_COURANTE else ""
            print("  %-8s %s%s" % (b.get("id"), b.get("name"), marque))
    except ErreurEdgewonk as e:
        print("  %s" % e)

    titre("2. Trades de la base %s" % BASE_COURANTE)
    trades = client.trades(BASE_COURANTE, 0, 200)
    print("  %d trades retournes" % len(trades))
    if not trades:
        sys.exit("  aucun trade — mauvaise base ?")

    dates = sorted((t.get("exitDate") or "")[:10] for t in trades if t.get("exitDate"))
    print("  periode couverte : %s -> %s" % (dates[0], dates[-1]))

    titre("3. Forme EXACTE des champs d'appariement")
    print("  (3 trades bruts, pour lire la precision et le fuseau)")
    for t in trades[:3]:
        print()
        print("    id          : %s" % t.get("id"))
        print("    instrument  : %r" % (t.get("instrument"),))
        print("    direction   : %r" % t.get("direction"))
        print("    entryDate   : %r" % t.get("entryDate"))
        print("    exitDate    : %r" % t.get("exitDate"))
        print("    quantity    : %r" % t.get("quantity"))
        print("    gain        : %r" % t.get("gain"))
        print("    slPrice     : %r    tpPrice : %r" % (t.get("slPrice"), t.get("tpPrice")))
        print("    highestPrice: %r    lowestPrice : %r"
              % (t.get("highestPrice"), t.get("lowestPrice")))
        print("    originalTpHit : %r   ignoreForWinrate : %r"
              % (t.get("originalTpHit"), t.get("ignoreForWinrate")))
        print("    scalings    : %s"
              % [(s.get("type"), s.get("scalingPrice"), s.get("scalingDelta"),
                  s.get("timestamp"))
                 for s in sorted(t.get("scalings") or [], key=lambda x: x.get("id") or 0)])

    titre("4. Notre base, pour comparaison")
    nos = base.charger(TRADES)
    exemples = sorted(c for c in nos if c.startswith("20260807-134318"))
    for c in exemples:
        x = nos[c]
        print("    %-34s ouverture %s  cloture %s  entree %s  sortie %s"
              % (c, x["ouverture"][:19], x["cloture"][:19], x["entree"], x["sortie"]))

    titre("5. Les 4 sorties du 07/08 13:43, cote Edgewonk")
    candidats = [t for t in trades
                 if (t.get("entryDate") or "").startswith("2026-08-07T13:43")
                 or (t.get("entryDate") or "").startswith("2026-08-07T11:43")]
    print("  %d trade(s) trouve(s) avec cette heure d'entree" % len(candidats))
    for t in sorted(candidats, key=lambda x: x.get("exitDate") or ""):
        print("    id %-10s entree %s  sortie %s  qte %-6s gain %-9s entryPx %s exitPx %s"
              % (t.get("id"), t.get("entryDate"), t.get("exitDate"), t.get("quantity"),
                 t.get("gain"), vwap(t, "START_ENTRY"), vwap(t, "CLOSE_ENTRY")))

    titre("Rien n'a ete ecrit")
    print("  Aucun modify, aucun PUT. Lecture seule.")


if __name__ == "__main__":
    main()
