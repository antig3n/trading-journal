#!/usr/bin/env python3
"""DIAGNOSTIC EN LECTURE SEULE — a quoi ressemble un trade FUTURES chez Edgewonk ?

N'ecrit rien, nulle part. Que des GET sur le journal Tradovate.

LA QUESTION

La cle d'appariement cote cTrader est mesuree et validee : instrument, sens,
minute d'entree, minute de sortie, en UTC, puis montant et quantite pour
departager (`edgewonk/appariement.py`). Elle repose sur trois faits qui n'ont
ete verifies QUE sur l'importateur cTrader :

  1. `instrument.name` vaut exactement notre `symbole_broker` — cote cTrader,
     « XAUUSD.raw ». Cote futures, est-ce « MNQU6 », « MNQ », « MNQU2026 » ?
     **Personne ne le sait.** Un nom different fait echouer 100 % des
     appariements, bruyamment — c'est le cas le moins dangereux.
  2. les horodatages sont stockes en UTC. `docs/tradovate.md` §5 bis observe le
     meme ecart de 2 h, mais c'est une OBSERVATION sur deux trades.
  3. ils sont tronques a la minute.

⚠️ Le §6 du README dit ce qu'a coute une generalisation non reverifiee : la
regle de segmentation, mesuree sur des trades FUTURES puis appliquee a cTrader,
a desaligne huit trades. On ne refait pas l'erreur dans l'autre sens.

CE QU'IL AFFICHE : la forme brute de quelques trades du journal futures —
instrument, sens, dates, quantite, gain — puis, si la base porte deja des
jambes Tradovate, ce que la cle actuelle donnerait sur elles.

Usage :
    python3 outils/diag_edgewonk_tradovate.py [id_du_journal]
"""

import collections
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base, plateformes as pf                     # noqa: E402
from edgewonk.api import Client, ErreurEdgewonk              # noqa: E402
from edgewonk.appariement import apparier, cle_jambe, cle_trade   # noqa: E402

TRADES = os.path.normpath(os.path.join(RACINE, "..", "donnees", "trades.csv"))

G, J, R, N, GRAS = "\033[32m", "\033[33m", "\033[31m", "\033[0m", "\033[1m"


def titre(t):
    print("\n  " + GRAS + t.upper() + N)
    print("  " + "-" * 66)


def main():
    journal = sys.argv[1] if len(sys.argv) > 1 else pf.base_edgewonk(pf.TRADOVATE)
    print()
    print(GRAS + "  DIAGNOSTIC — LES TRADES FUTURES CHEZ EDGEWONK" + N)
    print("  " + "=" * 66)
    print("  journal vise : %s (lecture seule)" % journal)

    try:
        client = Client().authentifier()
    except ErreurEdgewonk as e:
        print("\n  " + R + str(e).replace("\n", "\n  ") + N)
        return 1
    tous = client.tous_les_trades(journal)
    print("  %d trades lus" % len(tous))
    if not tous:
        print("  " + J + "journal vide — mauvais identifiant ?" + N)
        return 1

    # --- 1. les noms d'instrument. C'est LE point qui decide de la cle.
    titre("1. les noms d'instrument, tels qu'Edgewonk les stocke")
    noms = collections.Counter((t.get("instrument") or {}).get("name")
                               for t in tous)
    for nom, n in noms.most_common(20):
        print("  %-20s %d trade(s)" % (nom, n))
    print()
    print("  MESURE le 26/08/2026 : ce sont des PRODUITS — MGC, MNQ, 6E, NQ, GC,")
    print("  MCL — et jamais des contrats « MNQU6 ». La cle d'appariement compare")
    print("  donc la colonne `symbole` cote Tradovate, la ou elle compare")
    print("  `symbole_broker` cote cTrader (core/plateformes.colonne_instrument).")
    print("  Si cette liste changeait de forme, c'est LA qu'il faudrait corriger.")

    # --- 2. la forme d'un trade
    titre("2. la forme brute d'un trade")
    exemple = tous[0]
    interessants = ("id", "direction", "entryDate", "exitDate", "quantity",
                    "gain", "gainGross", "multiplier", "slPrice", "tpPrice",
                    "highestPrice", "lowestPrice", "rMultiple", "gainPercent")
    for c in interessants:
        print("  %-16s %s" % (c, json.dumps(exemple.get(c), ensure_ascii=False)))
    print("  %-16s %s" % ("instrument", json.dumps(exemple.get("instrument"),
                                                   ensure_ascii=False)[:120]))

    # --- 3. les horodatages sont-ils tronques a la minute ?
    titre("3. les horodatages sont-ils tronques a la minute ?")
    non_ronds = [t for t in tous
                 if (t.get("entryDate") or "")[17:19] not in ("", "00")]
    print("  entryDate avec des secondes non nulles : %d / %d" % (len(non_ronds), len(tous)))
    if non_ronds:
        print("  " + J + "PAS tronques ici — la cle cTrader compare des minutes," + N)
        print("  " + J + "ce qui reste correct, mais le fait merite d'etre note." + N)
        for t in non_ronds[:3]:
            print("     %s -> %s" % (t.get("id"), t.get("entryDate")))
    else:
        print("  " + G + "tronques, comme cote cTrader." + N)
    for t in tous[:5]:
        print("     %-10s %-22s %-22s q=%-6s gain=%s"
              % (t.get("id"), t.get("entryDate"), t.get("exitDate"),
                 t.get("quantity"), t.get("gain")))

    # --- 4. les SL/TP deja poses, et leur credibilite
    titre("4. les SL/TP deja presents — ils sont FAUX, on mesure l'ampleur")
    aberrants = 0
    for t in tous:
        sl = t.get("slPrice")
        entree = None
        for s in sorted(t.get("scalings") or [], key=lambda x: x.get("id") or 0):
            if s.get("type") == "START_ENTRY":
                entree = s.get("scalingPrice")
                break
        if sl and entree:
            try:
                if abs(float(sl) - float(entree)) / max(abs(float(entree)), 1e-9) > 0.005:
                    aberrants += 1
            except (TypeError, ValueError):
                pass
    avec_sl = sum(1 for t in tous if t.get("slPrice"))
    print("  trades avec un slPrice : %d / %d" % (avec_sl, len(tous)))
    print("  dont le stop est a plus de 0,5 %% de l'entree : %d" % aberrants)
    print()
    print("  Rappel du §5 de tradovate.md : ces valeurs viennent de l'import")
    print("  Edgewonk, qui ne distingue pas un ordre de protection d'un ordre")
    print("  d'entree. Elles sont a RECALCULER, pas a completer.")

    # --- 5. la cle actuelle marcherait-elle ?
    titre("5. la cle actuelle appareille-t-elle nos jambes ?")
    nos = pf.filtrer(base.charger(TRADES), pf.TRADOVATE)
    if not nos:
        print("  " + J + "aucune jambe Tradovate dans la base locale." + N)
        print("  Importer d'abord :")
        print("    python3 jt.py importer --tradovate <position_history.csv> <orders.csv>")
        return 0
    couples, sans, ambigus, controles = apparier(nos, tous)
    print("  apparies    : %d / %d" % (len(couples), len(nos)))
    print("  non trouves : %d" % len(sans))
    print("  ambigus     : %d" % len(ambigus))
    for x in controles[:8]:
        print("  " + J + "controle : " + x + N)
    if sans:
        print()
        print("  Les cles qui n'ont rien trouve, et ce qu'on cherchait :")
        for cle in sans[:6]:
            print("     %-36s %s" % (cle, cle_jambe(nos[cle])))
        print()
        print("  Les cles disponibles cote Edgewonk, pour comparaison :")
        for t in tous[:6]:
            print("     %s" % (cle_trade(t),))
    print()
    print("  " + "=" * 66)
    print("  Rien n'a ete ecrit.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
