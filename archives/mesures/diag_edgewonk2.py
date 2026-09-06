#!/usr/bin/env python3
"""Diagnostic Edgewonk n°2 — LECTURE SEULE. Aucun modify, aucun PUT.

La recherche n'est pas triee par date : le premier diag n'a vu que des trades
de nov. 2025 a juil. 2026. On parcourt donc TOUTE la base pour retrouver la
periode du releve, puis on confronte a notre base, jambe par jambe.
"""

import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base                                       # noqa: E402
from edgewonk.api import Client, ErreurEdgewonk             # noqa: E402

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
    print("authentifie")

    def avance(n):
        sys.stdout.write("\r  %d trades lus" % n)
        sys.stdout.flush()

    tous = client.tous_les_trades(BASE_COURANTE, progression=avance)
    sys.stdout.write("\r  %d trades au total dans la base %s\n" % (len(tous), BASE_COURANTE))

    nos = base.charger(TRADES)
    debut = min(t["ouverture"][:10] for t in nos.values())
    fin = max(t["cloture"][:10] for t in nos.values())

    titre("1. Couverture")
    dates = sorted((t.get("exitDate") or "")[:10] for t in tous if t.get("exitDate"))
    print("  Edgewonk : %s -> %s" % (dates[0], dates[-1]))
    print("  notre base : %s -> %s" % (debut, fin))
    periode = [t for t in tous if debut <= (t.get("exitDate") or "")[:10] <= fin]
    print("  trades Edgewonk sur notre periode : %d   (notre base : %d jambes)"
          % (len(periode), len(nos)))

    titre("2. Precision des horodatages, sur NOTRE periode")
    sec_entree = {(t.get("entryDate") or "")[17:19] for t in periode}
    sec_sortie = {(t.get("exitDate") or "")[17:19] for t in periode}
    print("  secondes distinctes vues sur entryDate : %d %s"
          % (len(sec_entree), sorted(sec_entree)[:8]))
    print("  secondes distinctes vues sur exitDate  : %d %s"
          % (len(sec_sortie), sorted(sec_sortie)[:8]))
    print("  -> entryDate %s"
          % ("ARRONDI A LA MINUTE" if sec_entree <= {"00"} else "porte les secondes"))
    print("  -> exitDate  %s"
          % ("ARRONDI A LA MINUTE" if sec_sortie <= {"00"} else "PORTE LES SECONDES"))

    titre("3. Les 4 sorties du 07/08 13:43")
    cands = [t for t in periode if (t.get("entryDate") or "").startswith("2026-08-07T13:43")]
    print("  cote Edgewonk : %d trade(s)" % len(cands))
    for t in sorted(cands, key=lambda x: x.get("exitDate") or ""):
        print("    id %-10s entree %s  sortie %s  qte %-6s gain %-9s px %s -> %s  SL %s TP %s"
              % (t.get("id"), t.get("entryDate"), t.get("exitDate"), t.get("quantity"),
                 t.get("gain"), vwap(t, "START_ENTRY"), vwap(t, "CLOSE_ENTRY"),
                 t.get("slPrice"), t.get("tpPrice")))
    print("  cote notre base :")
    for c in sorted(x for x in nos if x.startswith("20260807-134318")):
        x = nos[c]
        print("    %-34s sortie %s  lots %-6s net %-9s px %s -> %s"
              % (c, x["cloture"][:19], x["volume_lots"], x["net"], x["entree"], x["sortie"]))

    titre("4. Champs deja remplis dans Edgewonk sur notre periode")
    for champ in ("slPrice", "tpPrice", "highestPrice", "lowestPrice", "originalTpHit"):
        remplis = sum(1 for t in periode if t.get(champ) not in (None, ""))
        print("  %-16s : %d / %d deja renseigne(s)" % (champ, remplis, len(periode)))

    titre("5. Appariement a blanc — cle (instrument, sens, entree a la MINUTE, sortie)")
    index = {}
    for t in periode:
        cle = ((t.get("instrument") or {}).get("name"),
               t.get("direction"),
               (t.get("entryDate") or "")[:16],
               (t.get("exitDate") or "")[:19])
        index.setdefault(cle, []).append(t)
    trouves, manques, ambigus = 0, [], 0
    for c, x in sorted(nos.items()):
        cle = (x["symbole_broker"],
               "BUY" if x["sens"] == "Achat" else "SELL",
               x["ouverture"][:16],
               x["cloture"][:19])
        lot = index.get(cle, [])
        if len(lot) == 1:
            trouves += 1
        elif len(lot) > 1:
            ambigus += 1
        else:
            manques.append(c)
    print("  apparies sans ambiguite : %d / %d" % (trouves, len(nos)))
    print("  ambigus (>1 candidat)   : %d" % ambigus)
    print("  non trouves             : %d" % len(manques))
    for c in manques[:12]:
        print("     %s" % c)
    if len(manques) > 12:
        print("     … et %d autres" % (len(manques) - 12))

    titre("Rien n'a ete ecrit")


if __name__ == "__main__":
    main()
