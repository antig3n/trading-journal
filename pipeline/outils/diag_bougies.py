#!/usr/bin/env python3
"""Diagnostic de l'étape 3 — NE MODIFIE RIEN. Lecture seule, base non touchée.

    cd pipeline && python3 outils/diag_bougies.py

Prérequis : cTrader ouvert et connecté au compte Prop Firm A,
Paramètres → Serveur MCP → « Enable MCP Server » coché.

Trois questions, dans l'ordre :
  1. le transport MCP répond-il, et sous quelle forme exacte ?
  2. les bougies M1 arrivent-elles sur la fenêtre d'un vrai trade ?
  3. les extrêmes et le TP-first calculés sont-ils cohérents avec la sortie ?
"""

import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base, plateformes as pf               # noqa: E402
from ctrader import bougies                            # noqa: E402
from ctrader.mcp import Client, ErreurMCP              # noqa: E402

TRADES = os.path.normpath(os.path.join(RACINE, "..", "donnees", "trades.csv"))


def titre(t):
    print("\n" + t)
    print("-" * len(t))


def main():
    trades = base.charger(TRADES)
    if not trades:
        sys.exit("base vide — importer un releve d'abord (python3 journal.py)")

    # ⚠️ CE MODULE SONDE LE MCP cTRADER : IL NE PEUT PARLER QUE DE cTRADER.
    # Depuis la fusion des bases (28/08/2026), `trades.csv` porte les DEUX
    # plateformes. Sans ce filtre, le module demandait « MNQU6 » au serveur
    # cTrader, qui repondait « Symbol not available » — en texte — et le
    # diagnostic tombait apres 120 jambes saines. Le bon reflexe n'est pas de
    # tolerer l'erreur, c'est de ne pas poser la question.
    #
    # Les bougies futures se verifient avec leur propre source : Databento,
    # via `archives/mesures/diag_databento.py` et `diag_tirage.py`.
    trades = pf.filtrer(trades, pf.CTRADER)
    # --periode / --journal, lus par le lecteur commun (`core/base`). Un outil
    # d'audit doit accepter les mêmes bornes que le moteur, sinon auditer une
    # journée lirait toute la base — et le résultat serait juste, mais sur
    # autre chose que ce qui a été demandé.
    try:
        (_debut, _fin), _journal = base.options_ligne(sys.argv)
    except ValueError as e:
        print("\n  " + str(e) + "\n")
        sys.exit(1)
    trades = base.filtrer_periode(trades, _debut, _fin)
    if _debut:
        print("période %s : %d jambe(s)"
              % (base.libelle_periode(_debut, _fin), len(trades)))
    if not trades:
        sys.exit("aucune jambe cTrader dans la base")
    positions = base.grouper_en_positions(trades)
    renseignees = {c: p for c, p in positions.items() if p["sl"] and p["tp"]}
    if not renseignees:
        sys.exit("aucune position avec SL et TP — remplir la saisie d'abord")

    try:
        client = Client().ouvrir()
    except ErreurMCP as e:
        sys.exit("\n%s\n" % e)
    print("session MCP ouverte")

    # --- 1. forme exacte de la reponse, sur la plus petite fenetre utile
    cible = sorted(renseignees)[1] if len(renseignees) > 1 else sorted(renseignees)[0]
    p = renseignees[cible]
    jambes = sorted((trades[c] for c in p["jambes"]), key=lambda t: t["cloture"])
    j = jambes[0]

    titre("1. get_trendbars — reponse brute")
    print("  symbole demande : %s" % j["symbole_broker"])
    print("  fenetre  : %s -> %s" % (j["ouverture"][:19], j["cloture"][:19]))
    import datetime as _dt
    _debut = bougies._utc(j["ouverture"]).replace(second=0, microsecond=0)
    _fin = bougies._utc(j["cloture"]).replace(second=0, microsecond=0) + _dt.timedelta(minutes=1)
    brut = client.appeler("get_trendbars", {
        "symbolName": j["symbole_broker"], "timeframe": "m1",
        "from": bougies._z(_debut), "to": bougies._z(_fin), "limit": 1000})
    if isinstance(brut, dict):
        print("  cles de la reponse : %s" % list(brut.keys()))
        barres = brut.get("bars") or []
        print("  nombre de barres   : %d" % len(barres))
        print("  truncated          : %s" % brut.get("truncated"))
        if barres:
            print("  premiere barre     : %s" % barres[0])
            print("  derniere barre     : %s" % barres[-1])
        else:
            print("  ⚠️  AUCUNE BARRE — le symbole est-il le bon sur ce compte ?")
    else:
        print("  reponse inattendue : %r" % str(brut)[:300])
        sys.exit(1)

    # --- 2 & 3. calcul sur toutes les positions renseignees
    titre("2. extremes et TP-first, sur tes positions renseignees")
    print("  %-34s %-9s %-10s %-10s %-9s %s" %
          ("jambe", "sortie", "plus_haut", "plus_bas", "SL/TP", "tp_first"))
    total_notes, total_bords = [], []
    for cp in sorted(renseignees):
        pos = renseignees[cp]
        try:
            maj, notes, bords = bougies.traiter_position(client, pos, trades)
            total_bords += bords
        except (ErreurMCP, bougies.ReponseIllisible) as e:
            # ⚠️ UN SYMBOLE QUI ECHOUE NE DOIT PAS ARRETER LE LOT.
            # `ReponseIllisible` manquait ici : une jambe futures demandee au
            # MCP cTrader (« Symbol not available: MNQU6 ») faisait tomber le
            # diagnostic entier apres 120 jambes saines. Trouve le 29/08/2026.
            print("  %s : %s" % (cp, str(e).splitlines()[0]))
            continue
        total_notes += notes
        for cle in sorted(maj):
            t, m = trades[cle], maj[cle]
            print("  %-34s %-9s %-10s %-10s %-9s %s" %
                  (cle, t["sortie"], m["prix_plus_haut"], m["prix_plus_bas"],
                   "%s/%s" % (t["sl"], t["tp"]), m["tp_touche_en_premier"] or "?"))

    if total_notes:
        titre("Signalements")
        for n in total_notes:
            print("  " + n)

    titre("Bougies de bord")
    total = sum(len(p["jambes"]) for p in renseignees.values())
    print("  %d jambe(s) sur %d ont un debordement de bord >= %.2f R."
          % (len(total_bords), total, bougies.R_ECART_BORD))
    print("  Sur celles-la, plus_haut/plus_bas est une BORNE, pas un maximum.")
    for c, e in sorted(total_bords, key=lambda x: -x[1]):
        print("    %-34s %+.2f R" % (c, e))

    titre("Controle de coherence")
    print("  Le plus_haut doit etre >= la sortie ET >= l'entree sur un achat,")
    print("  et une sortie AU niveau du TP doit donner tp_first = oui.")
    print("\n  (rien n'a ete ecrit dans la base)")


if __name__ == "__main__":
    main()
