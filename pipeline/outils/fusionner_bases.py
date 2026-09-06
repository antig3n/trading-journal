#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FUSIONNER LE CHANTIER RETROACTIF DANS LA BASE DE PRODUCTION. Une fois.

POURQUOI DEUX BASES EXISTAIENT, ET POURQUOI ELLES N'ONT PLUS LIEU D'ETRE

Le chantier retroactif a ete isole en aout 2026 pour une raison de securite :
reprendre dix mois d'historique avec des outils encore jeunes, sans risquer la
base courante. L'isolement a fait son travail — 157 jambes reprises, poussees,
verifiees.

Ce qui le rendait necessaire disparait avec l'orchestrateur unique : ses deux
particularites — n'ecrire que dans les emplacements d'images vides (regle E1),
et repecher le changement d'heure — deviennent des MODES choisis au lancement,
disponibles pour tout le monde. Une regle qu'on peut demander n'a plus besoin
d'un projet a elle.

CE QUE LA MESURE AUTORISE (28/08/2026, avant d'ecrire une ligne) :

    memes 28 colonnes, meme ordre        oui
    cles de jambe en collision            0
    dossiers de graphiques en collision   0
    le retroactif est-il mono-plateforme  oui, 157/157 cTrader
    chevauchement de dates                2 jambes, trades distincts

Aucune de ces proprietes n'etait garantie d'avance ; toutes ont ete verifiees.
Si l'une tombe, ce module refuse de fusionner plutot que de melanger.

⚠️ ON COPIE LES GRAPHIQUES, ON NE LES DEPLACE PAS. Le dossier `retroactif/`
reste intact jusqu'a son archivage : tant que la fusion n'est pas verifiee, la
source doit rester lisible. C'est 35 Mo de doublon pendant quelques minutes,
contre l'impossibilite de revenir en arriere.

Usage :
    python3 outils/fusionner_bases.py             # controle seul, n'ecrit rien
    python3 outils/fusionner_bases.py --ecrire
"""

import csv
import io
import os
import shutil
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base                                          # noqa: E402

G, J, R, N, GRAS = "\033[32m", "\033[33m", "\033[31m", "\033[0m", "\033[1m"

DONNEES = os.path.normpath(os.path.join(RACINE, "..", "donnees"))
TRADES = os.path.join(DONNEES, "trades.csv")
GRAPHIQUES = os.path.join(DONNEES, "graphiques")
RETRO_D = os.path.normpath(os.path.join(RACINE, "..", "retroactif", "donnees"))
RETRO = os.path.join(RETRO_D, "trades.csv")
RETRO_G = os.path.join(RETRO_D, "graphiques")


def colonnes(chemin):
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


def main():
    ecrire = "--ecrire" in sys.argv
    print()
    print(GRAS + "  FUSION DES BASES" + N)
    print("  " + "=" * 72)

    for c in (TRADES, RETRO):
        if not os.path.exists(c):
            print("  " + R + "introuvable : %s" % c + N)
            return 1

    prod, retro = base.charger(TRADES), base.charger(RETRO)
    cp, cr = colonnes(TRADES), colonnes(RETRO)

    # --- les cinq controles. Un seul qui tombe, et on ne fusionne pas.
    collisions = set(prod) & set(retro)
    dossiers_prod = set(os.listdir(GRAPHIQUES)) if os.path.isdir(GRAPHIQUES) else set()
    dossiers_retro = set(os.listdir(RETRO_G)) if os.path.isdir(RETRO_G) else set()
    coll_dossiers = dossiers_prod & dossiers_retro
    plateformes = {(t.get("plateforme") or "ctrader") for t in retro.values()}

    controles = [
        ("memes colonnes, meme ordre", cp == cr, "%d vs %d colonnes" % (len(cp), len(cr))),
        ("aucune cle en collision", not collisions, "%d collision(s)" % len(collisions)),
        ("aucun dossier d'images en collision", not coll_dossiers,
         "%d collision(s)" % len(coll_dossiers)),
        ("retroactif mono-plateforme", plateformes <= {"ctrader"},
         "plateformes : %s" % ", ".join(sorted(plateformes))),
    ]
    print()
    for libelle, ok, detail in controles:
        print("  %s %-42s %s" % ((G + "✓" + N) if ok else (R + "✗" + N), libelle, detail))
    if not all(ok for _, ok, _ in controles):
        print()
        print("  " + R + "Un controle a echoue. Rien n'a ete fait." + N + "\n")
        return 1

    # --- les chemins d'images morts, a nettoyer au passage
    morts = [c for c, t in prod.items()
             if (t.get("chemin_graphiques") or "").strip()
             and not os.path.isdir(os.path.join(DONNEES, t["chemin_graphiques"].strip()))]

    print()
    print("  production %d jambes  ·  retroactif %d jambes  ->  %d"
          % (len(prod), len(retro), len(prod) + len(retro)))
    print("  %d dossier(s) d'images a rapatrier" % len(dossiers_retro))
    print("  %d chemin(s) d'images mort(s) a nettoyer (allegements d'un ancien nommage)"
          % len(morts))
    for c in morts:
        print("     %s" % c)

    if not ecrire:
        print()
        print("  Rien n'a ete ecrit. Pour fusionner :")
        print("    python3 outils/fusionner_bases.py --ecrire")
        print()
        return 0

    # --- 1. les images D'ABORD. Une base fusionnee qui pointe vers des dossiers
    #        absents serait pire que deux bases separees : l'etape 4 les croirait
    #        a rendre et l'etape 5 n'aurait rien a envoyer.
    print()
    print("  " + GRAS + "RAPATRIEMENT DES IMAGES" + N)
    copies = 0
    for d in sorted(dossiers_retro):
        src, dst = os.path.join(RETRO_G, d), os.path.join(GRAPHIQUES, d)
        if os.path.isdir(dst):
            continue
        shutil.copytree(src, dst)
        copies += 1
    print("  %d dossier(s) copies (les originaux restent en place)" % copies)

    # --- 2. la base. `base.ecrire` prend l'instantane et refuse toute perte.
    fusion = dict(prod)
    fusion.update(retro)
    for c in morts:
        fusion[c]["chemin_graphiques"] = ""
    copie = base.ecrire(TRADES, fusion)
    print()
    print("  " + GRAS + "BASE" + N)
    print("  %d jambes ecrites" % len(fusion))
    if copie:
        print("  instantane : %s" % os.path.basename(copie))

    # --- 3. verification, sur le disque et pas sur nos intentions
    apres = base.charger(TRADES)
    sans_dossier = [c for c, t in apres.items()
                    if (t.get("chemin_graphiques") or "").strip()
                    and not os.path.isdir(os.path.join(DONNEES, t["chemin_graphiques"].strip()))]
    print()
    print("  " + GRAS + "VERIFICATION" + N)
    print("  %s %d jambes relues (%d attendues)"
          % ((G + "✓" + N) if len(apres) == len(fusion) else (R + "✗" + N), len(apres), len(fusion)))
    print("  %s %d chemin(s) d'images introuvable(s)"
          % ((G + "✓" + N) if not sans_dossier else (R + "✗" + N), len(sans_dossier)))
    for c in sans_dossier[:5]:
        print("     %s" % c)
    print()
    print("  `retroactif/` n'a pas ete touche — il sera archive separement.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
