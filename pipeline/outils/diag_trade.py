#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UN trade, tout ce qu'on sait de lui. Lecture seule, aucune ecriture.

POURQUOI CE MODULE EXISTE

Le controle croise du TP-first ne trouve aucun desaccord — 152 jambes, trois
sources concordantes — alors que l'utilisateur voit des valeurs fausses dans son
journal. Quand un instrument dit « tout va bien » et que l'oeil dit le
contraire, c'est l'instrument qu'il faut mettre en doute : mes controles
partagent tous la meme donnee en amont, **les niveaux SL et TP saisis a la
main**. Si un niveau est faux, tout ce qui en decoule est faux de facon
COHERENTE, et aucun croisement ne peut le voir.

Ce module ne croise rien. Il DEBALLE un trade :

    ce que porte notre base · ce que porte Edgewonk · et ce que les bougies
    disent, minute par minute, autour des deux niveaux.

C'est fait pour etre lance sur un trade dont l'utilisateur doute, et pour que la
reponse tienne en un coup d'oeil : si le niveau saisi ne correspond a rien de ce
que le prix a fait, ca se verra.

Usage — n'importe quel fragment suffit :
    python3 outils/diag_trade.py 20260807-134318
    python3 outils/diag_trade.py XAUUSD
    python3 outils/diag_trade.py 2025-11-04
"""

import datetime as dt
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base, plateformes as pf                      # noqa: E402
from ctrader.bougies import recuperer                         # noqa: E402

G, J, R, N, GRAS, B = ("\033[32m", "\033[33m", "\033[31m", "\033[0m",
                       "\033[1m", "\033[34m")

DONNEES = os.path.normpath(os.path.join(RACINE, "..", "donnees"))
TRADES = os.path.join(DONNEES, "trades.csv")
# ⚠️ UNE SEULE BASE DEPUIS LE 28/08/2026 — le drapeau `--retroactif` a donc
# disparu. Le chantier avait sa base ; elle est fusionnee (241 jambes) et le
# projet archive. Un drapeau qui ne peut plus rien selectionner est pire qu'un
# drapeau absent : il se tape encore, et il ne fait plus rien.


def _f(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _utc(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    plateforme = pf.TRADOVATE if "--tradovate" in sys.argv else pf.CTRADER
    if not args:
        print(__doc__)
        return 1
    motif = args[0].lower()
    jours = int(sys.argv[sys.argv.index("--jours") + 1]) if "--jours" in sys.argv else 10

    trades = pf.filtrer(base.charger(TRADES), plateforme)

    trouves = {c: t for c, t in trades.items()
               if motif in c.lower()
               or motif in (t.get("symbole_broker") or "").lower()
               or motif in (t.get("ouverture") or "").lower()}
    if not trouves:
        print("\n  aucune jambe ne correspond a %r dans %s"
              % (motif, pf.nom(plateforme)))
        return 1
    if len(trouves) > 1:
        print("\n  %d jambes correspondent — precise :" % len(trouves))
        for c in sorted(trouves)[:25]:
            t = trouves[c]
            # ⚠️ La sortie porte sa DATE des qu'elle tombe un autre jour.
            # N'afficher que l'heure faisait lire « 18:22 -> 17:04 » sur un
            # trade tenu une nuit : le meme piege que les titres de graphiques,
            # corrige le 26/08 pour la meme raison (24 positions sur 131 sont a
            # cheval sur plusieurs jours).
            memejour = t["ouverture"][:10] == t["cloture"][:10]
            fin = t["cloture"][11:19] if memejour else t["cloture"][:16].replace("T", " ")
            duree = ""
            try:
                import datetime as _dt
                d = (_dt.datetime.fromisoformat(t["cloture"])
                     - _dt.datetime.fromisoformat(t["ouverture"]))
                h = d.total_seconds() / 3600.0
                duree = ("%.0f min" % (h * 60) if h < 1 else
                         "%.1f h" % h if h < 48 else "%.0f j" % (h / 24))
            except Exception:                                # noqa: BLE001
                pass
            print("     %-36s %-5s %-11s %s -> %-16s %-7s net %s"
                  % (c, t["sens"], t["symbole_broker"],
                     t["ouverture"][:16].replace("T", " "), fin, duree, t["net"]))
        if len(trouves) > 25:
            print("     … et %d autres" % (len(trouves) - 25))
        return 0

    cle = list(trouves)[0]
    t = trouves[cle]
    e, sl, tp = _f(t["entree"]), _f(t.get("sl")), _f(t.get("tp"))
    sortie = _f(t["sortie"])
    achat = t["sens"] == "Achat"

    print()
    print(GRAS + "  " + cle + N)
    print("  " + "=" * 70)
    print("  %s %s · %s contrat(s)/lots · net %s"
          % (t["sens"], t["symbole_broker"], t["volume_lots"], t["net"]))
    print("  entree  %s  a %s" % (t["entree"], t["ouverture"][:19]))
    print("  sortie  %s  a %s" % (t["sortie"], t["cloture"][:19]))
    print()
    print("  " + GRAS + "CE QUE TU AS SAISI" + N)
    if sl is None or tp is None:
        print("  SL %s · TP %s — la question du TP-first ne se pose pas sans les deux."
              % (t.get("sl") or "(vide)", t.get("tp") or "(vide)"))
    else:
        risque = abs(e - sl)
        print("  SL %-12s a %+.1f R de l'entree" % (t["sl"], (sl - e) / risque))
        print("  TP %-12s a %+.1f R de l'entree" % (t["tp"], (tp - e) / risque))
        print("  sortie          a %+.1f R de l'entree"
              % ((sortie - e) / risque * (1 if achat else -1)))
        cote_sl = (sl < e) if achat else (sl > e)
        cote_tp = (tp > e) if achat else (tp < e)
        if not cote_sl or not cote_tp:
            print("  " + R + "⚠ UN NIVEAU EST DU MAUVAIS COTE DE L'ENTREE." + N)

    print()
    print("  " + GRAS + "CE QUE LA BASE PORTE" + N)
    for champ in ("prix_plus_haut", "prix_plus_bas", "prix_max_favorable",
                  "tp_touche_en_premier", "management", "id_edgewonk",
                  "chemin_graphiques", "screenshots"):
        print("     %-22s %s" % (champ, t.get(champ) or "(vide)"))

    # --- Edgewonk
    print()
    print("  " + GRAS + "CE QU'EDGEWONK PORTE" + N)
    try:
        from edgewonk.api import Client
        from edgewonk.appariement import apparier, rattraper
        client_ew = Client().authentifier()
        try:
            _, _journal = base.options_ligne(sys.argv)
        except ValueError:
            _journal = None
        journal = _journal or pf.base_edgewonk(plateforme)
        tous = client_ew.tous_les_trades(journal)
        couples, sans, _, _ = apparier({cle: t}, tous)
        rattraper({cle: t}, tous, couples, sans)
        if couples:
            d = couples[0][2]
            for champ in ("id", "entryDate", "exitDate", "quantity", "gain",
                          "slPrice", "tpPrice", "highestPrice", "lowestPrice",
                          "originalTpHit", "rMultiple", "ignoreForWinrate"):
                print("     %-22s %s" % (champ, d.get(champ)))
        else:
            print("     " + J + "aucun trade apparie dans le journal %s" % journal + N)
    except Exception as ex:                                   # noqa: BLE001
        print("     " + J + "Edgewonk illisible (%s)" % str(ex).splitlines()[0] + N)

    if sl is None or tp is None:
        print()
        return 0

    # --- les bougies, minute par minute autour des deux niveaux
    print()
    print("  " + GRAS + "CE QUE LES BOUGIES DISENT" + N)
    print("  " + "-" * 70)
    if plateforme == pf.TRADOVATE:
        from databento import client as databento
        client = databento.Client(cache=os.path.join(DONNEES, "bougies")).ouvrir()
    else:
        from ctrader.mcp import Client as ClientMCP
        client = ClientMCP().ouvrir()

    depart = _utc(t["ouverture"])
    fin_trade = _utc(t["cloture"])
    m_tp = m_sl = None
    extreme_haut = extreme_bas = None
    for jour in range(jours):
        d = depart + dt.timedelta(days=jour)
        bougies = recuperer(client, t["symbole_broker"], d.isoformat(),
                            (d + dt.timedelta(days=1)).isoformat())
        for b in bougies:
            ts = _utc(b["timestamp"])
            if ts < depart:
                continue
            haut, bas = float(b["high"]), float(b["low"])
            extreme_haut = haut if extreme_haut is None else max(extreme_haut, haut)
            extreme_bas = bas if extreme_bas is None else min(extreme_bas, bas)
            if m_tp is None and (haut >= tp if achat else bas <= tp):
                m_tp = ts
            if m_sl is None and (bas <= sl if achat else haut >= sl):
                m_sl = ts
        if m_tp is not None and m_sl is not None:
            break

    def _quand(m):
        if m is None:
            return "JAMAIS touche en %d jours" % jours
        dedans = " (pendant le trade)" if m <= fin_trade else " (APRES ta sortie)"
        return m.strftime("%Y-%m-%d %H:%M UTC") + dedans

    print("  TP %-12s %s" % (t["tp"], _quand(m_tp)))
    print("  SL %-12s %s" % (t["sl"], _quand(m_sl)))
    print("  plus haut atteint depuis l'entree : %s" % extreme_haut)
    print("  plus bas  atteint depuis l'entree : %s" % extreme_bas)
    print()
    if m_tp is None and m_sl is None:
        verdict = "indetermine — aucun des deux touche"
    elif m_sl is None or (m_tp is not None and m_tp < m_sl):
        verdict = "TP FIRST"
    elif m_tp is None or m_sl < m_tp:
        verdict = "SL FIRST"
    else:
        verdict = "indecidable — les deux dans la meme bougie M1"
    print("  " + GRAS + "VERDICT DES BOUGIES : %s" % verdict + N)
    print()
    print("  Si ce verdict te parait faux, c'est que le SL ou le TP saisi n'est")
    print("  pas celui que tu avais reellement. Les bougies, elles, ne se")
    print("  trompent pas sur ce que le prix a fait.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
