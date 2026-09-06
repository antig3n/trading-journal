#!/usr/bin/env python3
"""Diagnostic n°12 — LECTURE SEULE. Le chantier rétroactif est-il faisable ?

Trois inconnues décident de tout, et une seule est une question d'opinion.
Ce script mesure les deux autres.

  1. JUSQU'OÙ REMONTENT LES BOUGIES, par timeframe.
     Les brokers purgent le M1 bien plus vite que le H1. Si c'est le cas ici,
     la réponse n'est pas « tout ou rien » : les GRAPHIQUES (M5/M15/H1/H4)
     pourraient couvrir tout l'historique pendant que les EXTRÊMES et les
     PALIERS (M1) ne couvrent que le récent.

  2. LES SL/TP DES VIEUX TRADES SONT-ILS DÉJÀ DANS EDGEWONK ?
     L'utilisateur les a saisis à la main pendant des mois. S'ils y sont, on les
     LIT au lieu de les redemander — et le chantier perd sa partie pénible.

Ce que le script ne peut pas savoir : si les relevés des anciens comptes sont
encore exportables. Ça, c'est pour l'utilisateur.

    cd pipeline && python3 outils/diag_retroactif.py            # tout
    cd pipeline && python3 outils/diag_retroactif.py --bougies  # sans Edgewonk
"""

import datetime as dt
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from ctrader import bougies                                  # noqa: E402
from ctrader.mcp import Client, ErreurMCP                    # noqa: E402

SYMBOLES = ["EURUSD.raw", "XAUUSD.raw"]
TIMEFRAMES = ["m1", "m5", "m15", "h1", "h4"]

# Un mercredi de chaque mois : jamais un week-end, rarement un férié.
def mercredis(depuis_annee=2025, depuis_mois=9):
    out, a, m = [], depuis_annee, depuis_mois
    auj = dt.datetime.now(dt.timezone.utc)
    while (a, m) <= (auj.year, auj.month):
        d = dt.datetime(a, m, 1, 12, 0, tzinfo=dt.timezone.utc)
        while d.weekday() != 2:                              # 2 = mercredi
            d += dt.timedelta(days=1)
        if d < auj - dt.timedelta(days=1):
            out.append(d)
        m += 1
        if m > 12:
            a, m = a + 1, 1
    return out


def sonder(client, symbole, tf, quand):
    """True si le broker a des bougies ce jour-là. None si l'appel échoue."""
    try:
        b = bougies.recuperer(client, symbole, quand.isoformat(),
                              (quand + dt.timedelta(hours=3)).isoformat(),
                              timeframe=tf)
        return len(b) > 0
    except ErreurMCP:
        return None
    except Exception:                                        # noqa: BLE001
        return None


def partie_bougies():
    print("=" * 74)
    print(" 1. PROFONDEUR DE L'HISTORIQUE DE BOUGIES")
    print("=" * 74)
    print(" cTrader doit être ouvert, serveur MCP activé.\n")

    dates = mercredis()
    client = Client()
    try:
        client.ouvrir()
    except Exception as e:                                   # noqa: BLE001
        print("  IMPOSSIBLE de joindre le MCP : %s" % e)
        print("  -> cTrader ouvert ? Paramètres > Serveur MCP > Enable coché ?")
        return

    for symbole in SYMBOLES:
        print("  %s" % symbole)
        print("    %-10s %s" % ("mois", "  ".join("%-4s" % t for t in TIMEFRAMES)))
        plus_vieux = {}
        for quand in dates:
            cases = []
            for tf in TIMEFRAMES:
                r = sonder(client, symbole, tf, quand)
                cases.append("OUI " if r else ("--  " if r is False else "?   "))
                if r:
                    plus_vieux.setdefault(tf, quand)
            print("    %-10s %s" % (quand.strftime("%Y-%m"), "  ".join(cases)))
        print()
        print("    -> plus ancienne bougie trouvée, par timeframe :")
        for tf in TIMEFRAMES:
            q = plus_vieux.get(tf)
            print("       %-4s %s" % (tf, q.strftime("%Y-%m-%d") if q else "AUCUNE"))
        print()


def partie_edgewonk():
    print("=" * 74)
    print(" 2. CE QU'EDGEWONK DÉTIENT DÉJÀ")
    print("=" * 74)
    try:
        from edgewonk.api import Client as EW
    except Exception as e:                                   # noqa: BLE001
        print("  module indisponible : %s" % e)
        return

    BASE = "100001"
    c = EW()
    try:
        c.authentifier()
    except Exception as e:                                   # noqa: BLE001
        print("  authentification impossible : %s" % e)
        return
    print("  authentifié")

    trades = c.tous_les_trades(BASE)
    print("  %d trades lus sur la base %s\n" % (len(trades), BASE))

    def vide(t):
        s = (t.get("symbol") or t.get("instrument") or "")
        if isinstance(s, dict):
            s = s.get("name") or s.get("symbol") or ""
        return str(s)

    def compter(sous_ensemble):
        par_mois = {}
        for t in sous_ensemble:
            d = (t.get("entryDate") or "")[:7] or "?"
            s = par_mois.setdefault(d, {"n": 0, "sl": 0, "tp": 0, "haut": 0, "img": 0})
            s["n"] += 1
            s["sl"] += 1 if t.get("slPrice") else 0
            s["tp"] += 1 if t.get("tpPrice") else 0
            s["haut"] += 1 if t.get("highestPrice") else 0
            s["img"] += 1 if t.get("screenshot1Exists") else 0
        return par_mois

    def tableau(titre, par_mois):
        print("  %s" % titre)
        print("  %-9s %6s %8s %8s %10s %8s"
              % ("mois", "trades", "avec SL", "avec TP", "extremes", "images"))
        tot = {"n": 0, "sl": 0, "tp": 0, "haut": 0, "img": 0}
        for mois in sorted(par_mois):
            s = par_mois[mois]
            for k in tot:
                tot[k] += s[k]
            print("  %-9s %6d %8d %8d %10d %8d"
                  % (mois, s["n"], s["sl"], s["tp"], s["haut"], s["img"]))
        print("  " + "-" * 52)
        print("  %-9s %6d %8d %8d %10d %8d"
              % ("TOTAL", tot["n"], tot["sl"], tot["tp"], tot["haut"], tot["img"]))
        print()
        return tot

    symboles = {}
    for t in trades:
        symboles[vide(t)] = symboles.get(vide(t), 0) + 1
    print("  symboles présents :")
    for sym, n in sorted(symboles.items(), key=lambda x: -x[1]):
        print("     %-16s %4d" % (sym or "(vide)", n))
    print()

    # cTrader = suffixe .raw (mesure du projet). Le reste = futures / autre.
    ct = [t for t in trades if ".raw" in vide(t).lower()]
    autres = [t for t in trades if ".raw" not in vide(t).lower()]

    tableau("--- cTrader (.raw) ---", compter(ct))
    if autres:
        tableau("--- hors cTrader (futures Tradovate, etc.) ---", compter(autres))

    print("  Lecture : « avec SL » élevé sur un mois = les SL/TP y sont déjà,")
    print("  donc PAS de ressaisie — on les lit et on calcule le reste.")
    print()

    # ------------------------------------------------------------ doublons
    # Soupçon du 25/08/2026 : le relevé cTrader du compte 1234567 compte 34
    # jambes en mars 2026 quand Edgewonk en affiche 64, 23 en avril contre 46,
    # 11 en mai contre 22. Exactement le DOUBLE sur avril et mai — ce n'est pas
    # un hasard. On vérifie avec la clé d'appariement réelle du pipeline.
    print("=" * 74)
    print(" 3. DOUBLONS DANS EDGEWONK")
    print("=" * 74)

    def cle(t):
        return ((t.get("instrument") or {}).get("name"),
                t.get("direction"),
                (t.get("entryDate") or "")[:16],
                (t.get("exitDate") or "")[:16])

    groupes = {}
    for t in trades:
        groupes.setdefault(cle(t), []).append(t)
    doublons = {k: v for k, v in groupes.items() if len(v) > 1}

    if not doublons:
        print("  Aucun doublon. L'écart vient d'ailleurs (autre compte ?).\n")
        return

    par_mois = {}
    for k, v in doublons.items():
        par_mois.setdefault((k[2] or "")[:7], []).append((k, v))

    total_exces = sum(len(v) - 1 for v in doublons.values())
    print("  %d groupe(s) de doublons, soit %d trade(s) EN TROP.\n"
          % (len(doublons), total_exces))
    print("  %-9s %10s %10s" % ("mois", "groupes", "en trop"))
    for mois in sorted(par_mois):
        g = par_mois[mois]
        print("  %-9s %10d %10d" % (mois, len(g), sum(len(v) - 1 for _, v in g)))
    print()

    mois0 = sorted(par_mois)[0]
    print("  Exemples (%s) :" % mois0)
    for k, v in par_mois[mois0][:3]:
        print("     %s %s  entree %s  sortie %s  -> %d exemplaires, ids %s"
              % (k[0], k[1], k[2], k[3], len(v), [t.get("id") for t in v]))
    print()
    print("  IMPORTANT : des doublons faussent DEJA tes statistiques actuelles,")
    print("  et rendraient l'appariement du chantier retroactif ambigu.")
    print("  A regler AVANT toute poussee. Ce script n'a rien modifie.")
    print()


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--edgewonk" not in args:
        partie_bougies()
    if "--bougies" not in args:
        partie_edgewonk()
