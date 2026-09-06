#!/usr/bin/env python3
"""Diagnostic n°5 — LECTURE SEULE. Les deux ecarts de VWAP d'entree.

USOIL et NAS100 : le prix d'entree differe entre notre base et Edgewonk. Deux
causes possibles, opposees :
  (a) l'appariement s'est trompe de trade         -> la cle est a revoir
  (b) les deux systemes segmentent differemment    -> comme pour les sorties
On regarde les lignes BRUTES du releve et le trade Edgewonk complet.
"""

import csv
import glob
import io as _io
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base                                       # noqa: E402
from edgewonk.api import Client                             # noqa: E402
from edgewonk.appariement import apparier                   # noqa: E402

DONNEES = os.path.normpath(os.path.join(RACINE, "..", "donnees"))
TRADES = os.path.join(DONNEES, "trades.csv")
CIBLES = ("20260814-110700-USOIL-V", "20260814-170626-NAS100-V")


def titre(t):
    print("\n" + t)
    print("-" * len(t))


def main():
    nos = base.charger(TRADES)
    client = Client().authentifier()
    tous = client.tous_les_trades("100001")
    couples, _, _, _ = apparier(nos, tous)
    par_cle = {c: (j, t) for c, j, t in couples}

    # ⚠️ LE DERNIER EXPORT DU DOSSIER N'EST PAS FORCEMENT UN RELEVE cTRADER.
    # Depuis l'arrivee des futures, `donnees/brut/` melange les deux
    # plateformes, et le tri alphabetique tombait sur un export Tradovate —
    # dont les colonnes n'ont rien a voir. Le module plantait alors sur
    # « KeyError: 'Symbol' », un message qui ne dit pas quel fichier il lisait.
    # Mesure du 28/08/2026, premier audit global.
    #
    # On cherche donc le dernier fichier qui PORTE les colonnes attendues,
    # plutot que le dernier fichier tout court.
    COLONNES = ("Symbol", "Opening time (UTC+2)", "Order ID")
    brut = None
    for chemin in sorted(glob.glob(os.path.join(DONNEES, "brut", "*.csv")),
                         reverse=True):
        with _io.open(chemin, encoding="utf-8-sig", newline="") as f:
            tetes = next(csv.reader(f), [])
        if all(c in tetes for c in COLONNES):
            brut = chemin
            break
    if brut is None:
        print("\n  aucun releve cTrader dans donnees/brut/ — ce diagnostic")
        print("  compare le RELEVE BRUT a la base, il lui en faut un.\n")
        return 1
    print("  releve lu : %s" % os.path.basename(brut))
    with _io.open(brut, encoding="utf-8-sig", newline="") as f:
        lignes = [r for r in csv.DictReader(f) if (r.get("Order ID") or "").strip()]

    for prefixe in CIBLES:
        titre("=== %s ===" % prefixe)

        print("  LIGNES BRUTES DU RELEVE (toutes celles de ce symbole ce jour-la)")
        sym = prefixe.split("-")[2]
        jour = "%s/%s/%s" % (prefixe[6:8], prefixe[4:6], prefixe[0:4])
        for r in lignes:
            if r["Symbol"].startswith(sym) and r["Opening time (UTC+2)"].startswith(jour):
                print("    OID %-12s ouv %s  clo %s  entree %-12s sortie %-12s qte %-10s net %s"
                      % (r["Order ID"], r["Opening time (UTC+2)"][11:23],
                         r["Closing time (UTC+2)"][11:23], r["Entry price"],
                         r["Closing price"], r["Closing Quantity"], r["Net $"]))

        print()
        print("  NOS JAMBES")
        for c in sorted(x for x in nos if x.startswith(prefixe)):
            x = nos[c]
            print("    %-36s entree %-12s sortie %-12s lots %-6s net %s"
                  % (c, x["entree"], x["sortie"], x["volume_lots"], x["net"]))

        print()
        print("  LE TRADE EDGEWONK APPARIE")
        for c in sorted(x for x in nos if x.startswith(prefixe)):
            if c not in par_cle:
                print("    %s : non apparie" % c)
                continue
            _, t = par_cle[c]
            print("    %s  ->  id %s" % (c, t.get("id")))
            print("       entryDate %s   exitDate %s" % (t.get("entryDate"), t.get("exitDate")))
            print("       quantity %s   gain %s   direction %s"
                  % (t.get("quantity"), t.get("gain"), t.get("direction")))
            print("       scalings :")
            for sc in sorted(t.get("scalings") or [], key=lambda x: x.get("id") or 0):
                print("         %-13s px %-12s delta %-8s %s"
                      % (sc.get("type"), sc.get("scalingPrice"), sc.get("scalingDelta"),
                         sc.get("timestamp")))
            print("       fineScalings :")
            for sc in sorted(t.get("fineScalings") or [], key=lambda x: x.get("order") or 0):
                print("         %-13s px %-12s delta %-8s %s  profit %s"
                      % (sc.get("type"), sc.get("scalingPrice"), sc.get("scalingDelta"),
                         sc.get("timestamp"), sc.get("profit")))

        print()
        print("  TOUS LES TRADES EDGEWONK DE CE SYMBOLE CE JOUR-LA")
        for t in sorted(tous, key=lambda x: x.get("exitDate") or ""):
            nom = (t.get("instrument") or {}).get("name") or ""
            if nom.startswith(sym) and (t.get("entryDate") or "")[:10] == \
                    "%s-%s-%s" % (prefixe[0:4], prefixe[4:6], prefixe[6:8]):
                print("    id %-10s %s -> %s  qte %-8s gain %-10s"
                      % (t.get("id"), t.get("entryDate"), t.get("exitDate"),
                         t.get("quantity"), t.get("gain")))

    titre("Rien n'a ete ecrit")


if __name__ == "__main__":
    main()
