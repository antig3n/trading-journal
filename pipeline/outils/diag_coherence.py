#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AUDIT DE COHERENCE DU JOURNAL EDGEWONK — lecture seule, aucune ecriture.

LES TROIS SYMPTOMES, releves par l'utilisateur en relisant son journal :

    1. « SL first » affiche alors qu'AUCUN stop n'est renseigne
    2. « TP first » affiche alors qu'AUCUNE cible n'est renseignee
    3. un stop ET une cible renseignes, et AUCUNE reponse TP/SL first

Les trois sont des incoherences INTERNES au journal : elles se voient sans
bougies, sans simulation, sans rien recalculer. Il suffit de croiser trois
champs — `slPrice`, `tpPrice`, `originalTpHit` — sur chacun des trades.

⚠️ POURQUOI CE MODULE NE REGARDE PAS QUE CHEZ NOUS.

`originalTpHit` sans `slPrice` est impossible a produire par notre pipeline :
il ne calcule le TP-first QUE si la jambe porte un SL **et** un TP
(`bougies.analyser` rend "" des que l'un manque). Donc soit la valeur vient
d'ailleurs — de leur import, ou d'un clic — soit elle vient de nous et le
NIVEAU a disparu depuis. Le seul moyen de trancher est de regarder les deux
cotes en meme temps, et c'est ce que fait ce module :

    ce que porte Edgewonk  ×  ce que porte notre base

Un trade incoherent chez eux ET vide chez nous ne vient pas du pipeline.
Un trade incoherent chez eux et RENSEIGNE chez nous est un defaut de poussee.

Usage :
    python3 outils/diag_coherence.py               # journal 100001
    python3 outils/diag_coherence.py 100004        # un autre journal
"""

import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base, plateformes as pf                      # noqa: E402
from edgewonk.api import Client, ErreurEdgewonk               # noqa: E402
from edgewonk.appariement import apparier, rattraper          # noqa: E402

G, J, R, N, GRAS = "\033[32m", "\033[33m", "\033[31m", "\033[0m", "\033[1m"

DONNEES = os.path.normpath(os.path.join(RACINE, "..", "donnees"))
# ⚠️ UNE SEULE BASE DEPUIS LE 28/08/2026. Le chantier retroactif avait la
# sienne ; elle a ete fusionnee dans la production (241 jambes) et le projet
# archive. Tout ce qui lisait « les deux bases » ne lit plus qu'un fichier.


def _f(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def main():
    # --periode / --journal, lus par le lecteur commun (`core/base`). Un outil
    # d'audit doit accepter les mêmes bornes que le moteur, sinon auditer une
    # journée lirait toute la base — et le résultat serait juste, mais sur
    # autre chose que ce qui a été demandé.
    try:
        (_debut, _fin), _journal = base.options_ligne(sys.argv)
    except ValueError as e:
        print("\n  " + str(e) + "\n")
        return 1
    journal = _journal or (sys.argv[1] if len(sys.argv) > 1
                           and sys.argv[1].isdigit()
                           else pf.base_edgewonk(pf.CTRADER))
    print()
    print(GRAS + "  AUDIT DE COHERENCE — journal %s" % journal + N)
    print("  " + "=" * 72)
    try:
        client = Client().authentifier()
    except ErreurEdgewonk as e:
        print("\n  " + R + str(e).replace("\n", "\n  ") + N)
        return 1
    tous = client.tous_les_trades(journal)
    print("  %d trades lus" % len(tous))

    # --- toutes nos jambes, les trois sources confondues
    nos = {}
    nos.update(base.filtrer_periode(
        base.charger(os.path.join(DONNEES, "trades.csv")), _debut, _fin))
    couples, sans, _, _ = apparier(nos, tous)
    rattraper(nos, tous, couples, sans)
    par_id = {t.get("id"): j for _, j, t in couples}
    print("  %d apparies avec nos %d jambes" % (len(par_id), len(nos)))

    cas1, cas2, cas3, sains = [], [], [], 0
    for t in tous:
        sl, tp = _f(t.get("slPrice")), _f(t.get("tpPrice"))
        rep = t.get("originalTpHit")
        notre = par_id.get(t.get("id"))
        n_sl = _f(notre.get("sl")) if notre else None
        n_tp = _f(notre.get("tp")) if notre else None
        n_rep = (notre.get("tp_touche_en_premier") or "").strip() if notre else ""
        ligne = (t.get("id"), (t.get("instrument") or {}).get("name"),
                 (t.get("entryDate") or "")[:16], sl, tp, rep,
                 n_sl, n_tp, n_rep or "-")
        if rep is not None and sl is None:
            cas1.append(ligne)
        elif rep is not None and tp is None:
            cas2.append(ligne)
        elif sl is not None and tp is not None and rep is None:
            cas3.append(ligne)
        else:
            sains += 1

    def bloc(titre, cas, explication):
        print()
        print("  " + GRAS + titre + N + "  —  %s%d%s trade(s)"
              % (R if cas else G, len(cas), N))
        print("  " + "-" * 72)
        if not cas:
            print("  aucun.")
            return
        print("  %-10s %-11s %-17s %-10s %-10s %-8s | %-9s %-9s %s"
              % ("id", "instrument", "entree", "leur SL", "leur TP", "leur rep",
                 "notre SL", "notre TP", "nous"))
        for x in cas[:20]:
            print("  %-10s %-11s %-17s %-10s %-10s %-8s | %-9s %-9s %s"
                  % (x[0], x[1], x[2], x[3] if x[3] is not None else "-",
                     x[4] if x[4] is not None else "-",
                     # ⚠️ `None` n'est pas `False`. Afficher « non » pour une
                     # valeur ABSENTE etait un mensonge d'affichage : le cas 3
                     # est precisement celui ou la reponse manque, et la colonne
                     # disait « non ». Trois etats, trois libelles.
                     ("(vide)" if x[5] is None else ("oui" if x[5] else "non")),
                     x[6] if x[6] is not None else "-",
                     x[7] if x[7] is not None else "-", x[8]))
        if len(cas) > 20:
            print("  … et %d autres" % (len(cas) - 20))
        # d'ou ca vient : de nous, ou d'ailleurs ?
        du_pipeline = sum(1 for x in cas if x[8] in ("oui", "non"))
        print()
        print("  %s" % explication)
        print("  dont %d que NOTRE base explique (elle porte une reponse) et"
              % du_pipeline)
        print("  %d qu'elle n'explique pas — ceux-la ne viennent pas du pipeline."
              % (len(cas) - du_pipeline))

    bloc("1. UNE REPONSE, MAIS AUCUN STOP CHEZ EUX", cas1,
         "Le pipeline ne calcule le TP-first QUE si la jambe a un SL et un TP.")
    bloc("2. UNE REPONSE, MAIS AUCUNE CIBLE CHEZ EUX", cas2,
         "Meme raison : sans cible, `analyser` rend une chaine vide.")
    bloc("3. UN STOP ET UNE CIBLE, MAIS AUCUNE REPONSE", cas3,
         "Soit la simulation n'a pas resolu, soit le trade n'a jamais ete pousse.")

    print()
    print("  " + GRAS + "RESUME" + N)
    print("  " + "-" * 72)
    print("  coherents            : %d" % sains)
    print("  reponse sans stop    : %d" % len(cas1))
    print("  reponse sans cible   : %d" % len(cas2))
    print("  niveaux sans reponse : %d" % len(cas3))
    print()
    print("  Rien n'a ete ecrit.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
