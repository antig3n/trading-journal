#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LES QUATRE IMAGES DE CHAQUE TRADE — qui les a, qui ne les a plus.

LE CAS QUI L'A FAIT NAITRE (28/08/2026), ET CE QUI L'A PERIME (29/08/2026)

L'utilisateur a supprime a la main, chez Edgewonk, des captures qu'il avait prises
lui-meme — souvent les emplacements 1 et 2 — pour les remplacer par les
versions generees. Elles ne sont jamais revenues : `images_a_envoyer` rendait
`[]` des que notre colonne `screenshots` portait un horodatage, et ce verrou se
fermait AVANT que le mode d'ecriture soit consulte. Notre marqueur disait
« envoye », leur emplacement etait vide, personne ne comparait, et aucun cycle
ne resorbait le trou. `--reparer` etait la seule sortie.

⚠️ CE VERROU N'EXISTE PLUS. Les images sont devenues un champ comme les huit
autres : `filtrer_plan` decide, contre le trade LU dans le journal vise. Un
emplacement vide chez eux se remplit tout seul au prochain `pousser`, meme en
mode « ne remplir que le vide » — le trou stable n'existe plus, et il n'y a
plus de marqueur a reparer pour ca.

Ce module reste le SEUL a lire les deux cotes a la fois, et c'est toujours ce
qui le rend utile : verifier avant/apres une poussee, voir quels PNG manquent
sur le disque, reperer les trades qu'aucune jambe n'apparie. `--reparer`
survit pour un cas residuel — une colonne `screenshots` qui ment sur un envoi
qui n'a pas eu lieu — mais ce n'est plus le remede a quoi que ce soit de
structurel.

    emplacements 1 a 4  = M5, M15, H1, H4, les notres
    emplacements 5 et 6 = a l'utilisateur, jamais touches

⚠️ `--reparer` N'ENVOIE RIEN ET NE SUPPRIME RIEN. Il efface le marqueur
`screenshots` des jambes dont un emplacement manque, ce qui les rend eligibles
au prochain `pousser`. C'est la plus petite ecriture qui remette le systeme en
marche : reversible, sans effet chez Edgewonk, et le televersement passe par le
chemin normal, avec sa relecture de confirmation.

Usage :
    python3 outils/diag_images.py               # lecture seule
    python3 outils/diag_images.py --reparer     # efface les marqueurs concernes
    python3 outils/diag_images.py --journal 100004
"""

import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base, plateformes as pf                      # noqa: E402
from edgewonk.api import Client, ErreurEdgewonk               # noqa: E402
from edgewonk.appariement import apparier, rattraper          # noqa: E402
from edgewonk.ecriture import EMPLACEMENTS                    # noqa: E402
from graphiques.rendu import jambe_reelle, jambes_de_position  # noqa: E402

G, J, R, N, GRAS = "\033[32m", "\033[33m", "\033[31m", "\033[0m", "\033[1m"

DONNEES = os.path.normpath(os.path.join(RACINE, "..", "donnees"))
TRADES = os.path.join(DONNEES, "trades.csv")
# ⚠️ LA RACINE, PAS LE DOSSIER DES IMAGES. `chemin_graphiques` vaut deja
# « graphiques/<cle_position> » : joindre `donnees/graphiques` donnerait
# `donnees/graphiques/graphiques/...`. Mesure du 28/08/2026 — l'erreur ne leve
# rien, elle fait juste repondre « 0/4 PNG » sur TOUT, et le diagnostic conclut
# calmement qu'il n'y a rien a reparer. Un vérificateur muet est pire qu'absent.
GRAPHIQUES = DONNEES
# ⚠️ UNE SEULE BASE DEPUIS LE 28/08/2026. Le chantier retroactif avait la
# sienne ; elle a ete fusionnee dans la production (241 jambes) et le projet
# archive. Tout ce qui lisait « les deux bases » ne lit plus qu'un fichier.


def png_presents(jambe, racine):
    """Les timeframes dont le PNG est sur le disque, pour cette jambe."""
    dossier = (jambe.get("chemin_graphiques") or "").strip()
    if not dossier:
        return []
    d = os.path.join(racine, dossier)
    return [nom for nom, _ in EMPLACEMENTS
            if os.path.exists(os.path.join(d, "%s.png" % nom))]


def main():
    reparer = "--reparer" in sys.argv
    # --periode / --journal, lus par le lecteur commun (`core/base`). Un outil
    # d'audit doit accepter les mêmes bornes que le moteur, sinon auditer une
    # journée lirait toute la base — et le résultat serait juste, mais sur
    # autre chose que ce qui a été demandé.
    try:
        (_debut, _fin), _journal = base.options_ligne(sys.argv)
    except ValueError as e:
        print("\n  " + str(e) + "\n")
        return 1
    journal = _journal or pf.base_edgewonk(pf.CTRADER)

    print()
    print(GRAS + "  ETAT DES IMAGES — journal %s" % journal + N)
    print("  " + "=" * 76)
    try:
        client = Client().authentifier()
    except ErreurEdgewonk as e:
        print("\n  " + R + str(e).replace("\n", "\n  ") + N)
        return 1
    tous = client.tous_les_trades(journal)

    # Les deux bases restent SEPAREES : chacune a son fichier, ses graphiques et
    # sa poussee. Les fondre ici ferait ecrire le marqueur dans le mauvais.
    lots = [("la base", TRADES, GRAPHIQUES,
             base.filtrer_periode(base.charger(TRADES), _debut, _fin))]

    nos = {}
    for _, _, _, t in lots:
        for c, j in t.items():
            nos.setdefault(c, j)
    couples, sans, _, _ = apparier(nos, tous)
    rattraper(nos, tous, couples, sans)
    par_id = {str(t.get("id")): cle for cle, _, t in couples}
    print("  %d trades Edgewonk · %d jambes chez nous · %d appariees"
          % (len(tous), len(nos), len(par_id)))

    complets, a_reparer, a_rendre, allegements, sans_nous = [], [], [], [], []
    partiels = []
    for t in tous:
        manquants = [nom for nom, e in EMPLACEMENTS
                     if not t.get("screenshot%dExists" % e)]
        perso = [e for e in (5, 6) if t.get("screenshot%dExists" % e)]
        cle = par_id.get(str(t.get("id")))
        if cle is None:
            if manquants:
                sans_nous.append((t, manquants))
            continue
        lot = next(l for l in lots if cle in l[3])
        jambe = lot[3][cle]
        if not manquants:
            complets.append(cle)
            continue

        # ⚠️ UNE JAMBE D'ALLEGEMENT N'A PAS D'IMAGE, ET C'EST EXACT.
        # Decision du 25/08/2026 (`graphiques/rendu`, §4) : seule la jambe
        # REELLEMENT TENUE recoit les captures — un allegement est un trade
        # Edgewonk a part entiere, mais il ne represente aucune decision.
        # Premiere version de ce module : les 35 allegements tombaient dans
        # « a rendre d'abord », noyant l'unique vraie anomalie sous 34 fausses.
        # C'est la faute que ce projet documente le plus souvent, et je viens
        # de la refaire : un signalement qui se declenche sur du sain dresse a
        # ignorer les signalements.
        soeurs = jambes_de_position(lot[3], jambe.get("cle_position"))
        if soeurs and jambe.get("cle") != jambe_reelle(soeurs).get("cle"):
            allegements.append(cle)
            continue
        disponibles = png_presents(jambe, lot[2])
        ligne = (t, cle, jambe, lot, manquants, disponibles, perso)

        # ⚠️ « REPARABLE » N'EST PAS TOUT OU RIEN. Premiere version : un trade
        # etait reparable seulement si TOUS ses emplacements manquants avaient
        # leur PNG. Mesure du 28/08/2026 sur `20260817-091714-MGCQ6-A` : ses
        # quatre emplacements sont vides chez Edgewonk, deux PNG existent
        # (H1, H4), M5 et M15 ne seront jamais rendus faute de bougies sur un
        # contrat quasi mort. Il tombait donc dans « a rendre d'abord » — donc
        # personne ne renvoyait les deux images qu'on AVAIT, et le trade
        # restait sans aucune capture. Refuser une reparation partielle, c'est
        # preferer zero image a deux.
        recuperables = [n for n in manquants if n in disponibles]
        if not recuperables:
            a_rendre.append(ligne)
        elif len(recuperables) == len(manquants):
            a_reparer.append(ligne)
        else:
            partiels.append(ligne)

    def bloc(titre, lignes, couleur, explication):
        print()
        print("  " + GRAS + titre + N + "  —  %s%d%s" % (couleur, len(lignes), N))
        print("  " + "-" * 76)
        if not lignes:
            print("  aucun.")
            return
        print("  %-10s %-38s %-16s %-14s %s"
              % ("id", "notre jambe", "manque chez eux", "PNG dispo", "marqueur"))
        for t, cle, jambe, lot, manquants, dispo, perso in lignes[:60]:
            print("  %-10s %-38s %-16s %-14s %s"
                  % (t.get("id"), cle, "+".join(manquants),
                     "%d/4" % len(dispo),
                     (jambe.get("screenshots") or "(vide)")))
        if len(lignes) > 60:
            print("  … et %d autres" % (len(lignes) - 60))
        print()
        print("  %s" % explication)

    bloc("A REPARER — les PNG existent, seul le marqueur bloque", a_reparer, J,
         "Le marqueur `screenshots` dit « envoye », l'emplacement est vide chez "
         "eux.\n  C'est exactement le cas d'une image supprimee a la main.")
    print()
    print("  " + GRAS + "SANS IMAGE PAR CONCEPTION — jambes d'allegement" + N
          + "  —  %s%d%s" % (G, len(allegements), N))
    print("  " + "-" * 76)
    print("  Seule la jambe reellement tenue recoit les captures (decision du")
    print("  25/08). Ces jambes-la n'en auront jamais, et c'est exact.")

    bloc("REPARABLES EN PARTIE — certains PNG manquent, les autres peuvent partir",
         partiels, J,
         "Ces trades n'ont AUCUNE capture chez Edgewonk alors qu'on en a.\n"
         "  `--reparer` renvoie ce qu'on a ; les emplacements sans PNG restent vides\n"
         "  et le trade repassera ici tant qu'ils le seront.")

    bloc("A RENDRE D'ABORD — il manque des PNG sur le disque", a_rendre, R,
         "Rien a reparer tant que l'image n'existe pas. Rendre les graphiques :\n"
         "    python3 jt.py graphiques --refaire        (ou --tradovate)")
    # ⚠️ CES LIGNES N'ONT PAS LA MEME FORME QUE LES AUTRES, ET ELLES NE PEUVENT
    # PAS L'AVOIR : sans jambe appariee il n'y a ni cle, ni PNG, ni marqueur.
    # Les faire passer par `bloc` a plante en reel le 28/08/2026 — sept valeurs
    # attendues, deux fournies. Le test ne l'avait pas vu parce que le faux
    # journal etait fabrique DEPUIS nos jambes : il ne pouvait produire aucun
    # orphelin, donc la branche n'a jamais tourne. Un jeu d'essai derive des
    # donnees saines ne teste que les chemins sains.
    print()
    print("  " + GRAS + "CHEZ EUX, PAS CHEZ NOUS" + N + "  —  %s%d%s"
          % (J if sans_nous else G, len(sans_nous), N))
    print("  " + "-" * 76)
    if not sans_nous:
        print("  aucun.")
    else:
        print("  %-10s %-13s %-20s %-16s %s"
              % ("id", "instrument", "entree", "manque", "gain"))
        for t, manquants in sans_nous[:30]:
            print("  %-10s %-13s %-20s %-16s %s"
                  % (t.get("id"), (t.get("instrument") or {}).get("name"),
                     (t.get("entryDate") or "")[:16], "+".join(manquants),
                     t.get("gain")))
        if len(sans_nous) > 30:
            print("  … et %d autres" % (len(sans_nous) - 30))
        print()
        print("  Aucune jambe appariee : ces trades ne sortent pas de nos bases,")
        print("  le pipeline n'a donc aucune image a leur donner.")

    print()
    print("  " + GRAS + "RESUME" + N)
    print("  " + "-" * 76)
    print("  quatre images au complet : %s%d%s" % (G, len(complets), N))
    print("  reparables (marqueur)    : %s%d%s" % (J, len(a_reparer), N))
    print("  reparables en partie     : %s%d%s" % (J, len(partiels), N))
    print("  a rendre d'abord         : %s%d%s" % (R, len(a_rendre), N))
    print("  allegements (normal)     : %d" % len(allegements))
    print("  non apparies             : %d" % len(sans_nous))

    a_reparer = a_reparer + partiels
    if not a_reparer:
        print()
        print("  Rien a reparer. Rien n'a ete ecrit.")
        print()
        return 0

    if not reparer:
        print()
        print("  Pour rendre ces jambes eligibles au prochain televersement :")
        print("    python3 outils/diag_images.py --reparer")
        print()
        print("  Rien n'a ete ecrit.")
        print()
        return 0

    # --- la reparation, fichier par fichier
    print()
    print("  " + GRAS + "REPARATION" + N)
    print("  " + "-" * 76)
    for nom, chemin, _, trades in lots:
        touchees = [l for l in a_reparer if l[3][1] == chemin]
        if not touchees:
            continue
        for _, cle, _, _, _, _, _ in touchees:
            trades[cle]["screenshots"] = ""
        copie = base.ecrire(chemin, trades)
        print("  %-12s %d marqueur(s) efface(s)" % (nom, len(touchees)))
        if copie:
            print("               instantane : %s" % os.path.basename(copie))
    print()
    print("  Les images repartiront au prochain `pousser` — par le chemin")
    print("  normal, avec sa relecture de confirmation. Rien n'a ete envoye ici.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
