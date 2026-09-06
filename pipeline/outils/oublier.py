#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OUBLIER UN NIVEAU — et tout ce que le pipeline en a deduit.

POURQUOI CE N'EST PAS « effacer une case »

Un SL n'est pas une donnee isolee : c'est la racine d'un arbre. Effacer la
colonne `sl` en laissant le reste produit un etat pire que l'erreur d'origine —
des valeurs justes en apparence, calculees depuis un stop qui n'existe plus, et
qu'aucun cycle ne recalculera puisqu'elles sont remplies.

Ce qui descend d'un SL, mesure le 28/08/2026 :

    prix_max_favorable     la simulation des paliers part du stop
    tp_touche_en_premier   « le TP avant le stop » n'a pas de sens sans stop
    les PNG                le gabarit trace le SL en pointilles
    les captures poussees  ce sont ces PNG-la, deja chez Edgewonk

D'ou les cinq colonnes vidées d'un coup. Les deux dernieres ne sont pas des
donnees mais des MARQUEURS : `chemin_graphiques` vide fait repasser la position
a l'etape 4 (`rendu.position_a_rendre`), `screenshots` vide la fait repasser a
l'etape 5. Le cycle normal reconstruit le reste, sans niveau cette fois.

LE CAS QUI L'A FAIT NAITRE : `20260814-170626-NAS100-V`, vente a 30040,35 avec
un stop saisi a 30040,80 — 0,45 point de risque sur du NAS100, soit +181 R
realises. La saisie l'avait signale (R aberrant), le signalement a ete acquitte,
et la valeur est restee. Elle etait sur le point de partir chez Edgewonk.

⚠️ ON EFFACE, ON NE CORRIGE PAS. « Un stop devine est pire qu'un stop absent »
(§4) : absent, le trade sort des statistiques de R (regle R7) ; faux, il produit
du R ayant l'apparence du juste. Pour REMETTRE un niveau, le chemin reste le
fichier de saisie et `jt.py integrer` — une seule autorite.

Usage :
    python3 outils/oublier.py 20260814-170626-NAS100-V --sl
    python3 outils/oublier.py <cle_position> --sl --tp
    python3 outils/oublier.py <cle_position> --sl --ecrire      # ecrit vraiment
"""

import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base                                          # noqa: E402

G, J, R, N, GRAS = "\033[32m", "\033[33m", "\033[31m", "\033[0m", "\033[1m"

DONNEES = os.path.normpath(os.path.join(RACINE, "..", "donnees"))
TRADES = os.path.join(DONNEES, "trades.csv")
# ⚠️ UNE SEULE BASE DEPUIS LE 28/08/2026. Le chantier retroactif avait la
# sienne ; elle a ete fusionnee dans la production (241 jambes) et le projet
# archive. Tout ce qui lisait « les deux bases » ne lit plus qu'un fichier.

# Ce qui descend d'un niveau. `sl` et `tp` sont demandes par l'appelant ; le
# reste part avec, toujours, parce que c'en est deduit.
DERIVEES = ("prix_max_favorable", "tp_touche_en_premier",
            "chemin_graphiques", "screenshots")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args or not ("--sl" in sys.argv or "--tp" in sys.argv):
        print(__doc__)
        return 1
    cible = args[0]
    ecrire = "--ecrire" in sys.argv
    niveaux = [c for c in ("sl", "tp") if "--%s" % c in sys.argv]

    # ⚠️ La cle peut vivre dans l'une OU l'autre base, et on ne sait pas
    # laquelle avant de regarder. On parcourt les deux et on retient si on a
    # trouve : sans ce drapeau, une cle trouvee en production faisait quand
    # meme afficher « aucune jambe » a la fin, et sortir en code 1. Mesure du
    # 28/08/2026, premier appel du module.
    trouve = False

    for nom, chemin in (("la base", TRADES),):
        if not os.path.exists(chemin):
            continue
        trades = base.charger(chemin)
        touchees = {c: t for c, t in trades.items()
                    if t.get("cle_position") == cible or c == cible}
        if not touchees:
            continue
        trouve = True

        print()
        print(GRAS + "  %s  —  %s" % (cible, nom) + N)
        print("  " + "=" * 72)
        efface = 0
        for c in sorted(touchees):
            t = trades[c]
            avant = {ch: (t.get(ch) or "") for ch in niveaux + list(DERIVEES)}
            print("  %s" % c)
            for ch in niveaux + list(DERIVEES):
                v = avant[ch]
                if not v:
                    continue
                print("     %-22s %s%s%s  ->  (vide)" % (ch, R, v, N))
                efface += 1
                if ecrire:
                    t[ch] = ""
        if not efface:
            print("  " + G + "deja vide — rien a faire." + N)
            continue
        if not ecrire:
            print()
            print("  %d valeur(s) seraient effacees. Pour le faire :" % efface)
            print("    python3 outils/oublier.py %s %s --ecrire"
                  % (cible, " ".join("--" + c for c in niveaux)))
            continue

        copie = base.ecrire(chemin, trades)
        print()
        print("  " + GRAS + "%d valeur(s) effacees dans %s" % (efface, nom) + N)
        if copie:
            print("  instantane : %s" % os.path.basename(copie))
        print()
        print("  Le cycle normal reconstruit le reste, sans niveau cette fois :")
        print("    python3 jt.py bougies")
        print("    ../.venv/bin/python3 jt.py graphiques      # cette position seule")
        print("    ../.venv/bin/python3 jt.py pousser")
        print()
        print("  " + J + "⚠️ Edgewonk garde SON slPrice : un champ vide chez nous "
              "n'est jamais\n     pousse. A supprimer a la main dans leur interface "
              "si tu veux qu'il\n     disparaisse de leurs statistiques." + N)
        return 0

    if not trouve:
        print("\n  aucune jambe pour %r dans les deux bases.\n" % cible)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
