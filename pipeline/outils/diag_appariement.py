#!/usr/bin/env python3
"""Diagnostic n°4 — LECTURE SEULE. Le dernier avant toute ecriture.

Apparie nos jambes avec les trades Edgewonk, puis affiche ce qui serait ecrit.
Aucun modify, aucun PUT : que des GET.

⚠️ CORRIGE le 26/08/2026 — il sous-declarait, et il l'annoncait comme exhaustif.

Il n'inspectait que quatre champs (slPrice, tpPrice, highestPrice, lowestPrice)
plus originalTpHit, en promettant « exactement ce qui serait ecrit ». Les
`alternativeStrategies`, `ignoreForWinrate` et surtout `managementComments`
n'apparaissaient nulle part — or le management est, sur les futures, le seul
champ ecrit pour la majorite des trades. Un diagnostic qui montre le tiers du
plan et annonce le tout est un vérificateur qui ment, sixieme fois dans ce
projet.

Il appelle desormais `ecriture.preparer`, le MEME constructeur de plan que
`jt.py pousser`. Ce qu'il affiche est ce qui partirait, par construction et non
par ressemblance.
"""

import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base, plateformes as pf                    # noqa: E402
from edgewonk.api import Client                             # noqa: E402
from edgewonk.appariement import apparier, rattraper        # noqa: E402
from edgewonk import ecriture                               # noqa: E402

G, J, R, N = "\033[32m", "\033[33m", "\033[31m", "\033[0m"

TRADES = os.path.normpath(os.path.join(RACINE, "..", "donnees", "trades.csv"))

# La plateforme se declare, comme partout ailleurs :
#     python3 outils/diag_appariement.py --tradovate
# Sans drapeau, c'est cTrader. C'est le dernier controle avant `pousser`, et il
# doit viser le meme journal et le meme sous-ensemble de jambes que lui —
# sinon il rassurerait sur autre chose que ce qui sera ecrit.
PLATEFORME = pf.TRADOVATE if "--tradovate" in sys.argv else pf.CTRADER
BASE_COURANTE = pf.base_edgewonk(PLATEFORME)
for _a in sys.argv[1:]:
    if _a.isdigit():
        BASE_COURANTE = _a


def titre(t):
    print("\n" + t)
    print("-" * len(t))


def _nb(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def main():
    # --periode / --journal, par le lecteur commun de `core/base`.
    try:
        (_debut, _fin), _journal = base.options_ligne(sys.argv)
    except ValueError as e:
        print("\n  " + str(e) + "\n")
        return 1
    global BASE_COURANTE
    if _journal:
        BASE_COURANTE = _journal

    client = Client().authentifier()
    tous = client.tous_les_trades(BASE_COURANTE)
    nos = base.filtrer_periode(
        pf.filtrer(base.charger(TRADES), PLATEFORME), _debut, _fin)
    if _debut:
        print("  periode %s : %d jambe(s)"
              % (base.libelle_periode(_debut, _fin), len(nos)))
    print("plateforme %s · journal %s" % (pf.nom(PLATEFORME), BASE_COURANTE))
    print("%d trades Edgewonk · %d jambes locales" % (len(tous), len(nos)))

    couples, sans, ambigus, controles = apparier(nos, tous)
    # Le repechage du changement d'heure fait partie de l'appariement REEL :
    # `retro.py pousser` l'applique. Un diagnostic qui ne l'applique pas ne
    # mesure pas ce qui se passera.
    repeches = rattraper(nos, tous, couples, sans)
    for r in repeches:
        print("  repeche (changement d'heure) : %s" % r)

    titre("1. Resultat de l'appariement")
    print("  apparies    : %d / %d" % (len(couples), len(nos)))
    print("  non trouves : %d" % len(sans))
    print("  ambigus     : %d" % len(ambigus))
    print("  controles en echec : %d" % len(controles))

    if sans:
        titre("2. Non trouves — sont-ils seulement importes dans Edgewonk ?")
        fin_ew = max((t.get("exitDate") or "")[:10] for t in tous)
        print("  dernier trade Edgewonk : %s" % fin_ew)
        for c in sans:
            x = nos[c]
            apres = x["cloture"][:10] > fin_ew
            print("  %-34s sortie %s  net %-9s %s"
                  % (c, x["cloture"][:19], x["net"],
                     "<- posterieur au dernier import" if apres else "<- A EXPLIQUER"))

    # --- LE SENS INVERSE : leurs trades que PERSONNE chez nous ne produit.
    #
    # ⚠️ Angle mort corrige le 28/08/2026, sur une question de l'utilisateur — « c'est
    # normal que j'aie 243 trades ? ». Ce diagnostic ne regardait que dans un
    # sens : nos jambes qui ne trouvent pas leur trade. Un trade present chez EUX
    # et absent de chez nous etait invisible, alors que c'est le symptome d'un
    # doublon d'import, d'un releve jamais passe par le pipeline, ou d'une
    # segmentation qui diverge.
    #
    # ⚠️ ET LA PREMIERE VERSION DE CE BLOC MENTAIT, dans l'heure qui a suivi.
    # Elle comparait les 49 jambes de PRODUCTION cTrader aux 243 trades du
    # journal et annoncait « 194 orphelins ». Or ce journal porte trois sources :
    # le forex de production, les futures, et les 157 trades du chantier
    # une seule base depuis le 28/08 : 206 cTrader + 35 Tradovate = 241, le vrai
    # reste est 2.
    #
    # Un compte d'orphelins qui ignore deux des trois sources n'est pas un
    # controle, c'est du bruit — et du bruit qui ressemble a une alerte. On
    # confronte donc les restants a TOUTES nos bases avant de conclure.
    # ⚠️ UNE SEULE BASE DEPUIS LE 28/08/2026. Le chantier retroactif avait la
    # sienne ; elle a ete fusionnee dans la production (241 jambes) et le projet
    # archive. Tout ce qui lisait « les deux bases » ne lit plus qu'un fichier.
    autre = pf.TRADOVATE if PLATEFORME == pf.CTRADER else pf.CTRADER
    toutes = base.charger(TRADES)

    sources = [("%s, meme journal" % pf.nom(autre), pf.filtrer(toutes, autre))]


    apparies = {t.get("id") for _, _, t in couples}
    restants = [t for t in tous if t.get("id") not in apparies]
    detail = [("%s (la plateforme visee)" % pf.nom(PLATEFORME), len(couples))]

    for nom, jambes in sources:
        if not jambes or not restants:
            continue
        couples2, sans2, _, _ = apparier(jambes, restants)
        rattraper(jambes, restants, couples2, sans2)
        pris = {t.get("id") for _, _, t in couples2}
        if pris:
            detail.append((nom, len(pris)))
            restants = [t for t in restants if t.get("id") not in pris]

    titre("2 bis. D'ou viennent leurs %d trades" % len(tous))
    for nom, n in detail:
        print("  %-34s %4d" % (nom, n))
    print("  %-34s %4d" % ("SANS correspondance chez nous", len(restants)))

    if restants:
        print()
        print("  Ces %d-la ne sortent d'AUCUNE de nos bases :" % len(restants))
        for t in sorted(restants, key=lambda x: x.get("entryDate") or "")[:15]:
            print("     %-10s %-11s %-6s %-18s q=%-7s gain=%s"
                  % (t.get("id"), (t.get("instrument") or {}).get("name"),
                     t.get("direction"), (t.get("entryDate") or "")[:16],
                     t.get("quantity"), t.get("gain")))
        if len(restants) > 15:
            print("     … et %d autres" % (len(restants) - 15))
        # ⚠️ ON NE LAISSE PAS LE LECTEUR CHOISIR ENTRE TROIS CAUSES.
        #
        # Lister « trois causes possibles » etait confortable et paresseux : la
        # donnee permet de trancher. Un orphelin dont un trade DEJA APPARIE
        # porte le meme instrument, le meme sens, la meme minute d'entree, la
        # meme quantite et le meme gain au centime n'est pas un trade manquant —
        # c'est un DOUBLON cote Edgewonk. Les cinq champs ensemble ne coincident
        # pas par hasard.
        #
        # Ecrit le 28/08/2026, sur le cas du EURUSD a +606,00 du 31/03 : il
        # restait orphelin alors que les 157 jambes du chantier etaient toutes
        # appariees — donc quelqu'un d'autre portait deja sa signature.
        # Tous les trades qu'UNE de nos bases revendique, pas seulement la
        # plateforme visee : un doublon peut jumeler un trade du chantier.
        tous_apparies = [t for t in tous if t.get("id") not in
                         {x.get("id") for x in restants}]
        print()
        print("  Verdict, pour chacun :")
        for t in restants:
            sig = ((t.get("instrument") or {}).get("name"), t.get("direction"),
                   (t.get("entryDate") or "")[:16],
                   (t.get("exitDate") or "")[:16])
            # ⚠️ LA SORTIE FAIT PARTIE DE LA SIGNATURE — corrige le 28/08/2026,
            # apres que l'utilisateur ait supprime un trade sur ce verdict.
            #
            # La premiere version comparait instrument, sens, minute d'ENTREE,
            # quantite et gain. Or **deux jambes d'une meme position partagent
            # leur minute d'entree** : c'est la definition d'une position sortie
            # en plusieurs fois. Sans la sortie, deux trades legitimes d'une
            # meme position pouvaient se ressembler assez pour qu'on declare un
            # doublon.
            #
            # Un doublon, c'est le MEME trade deux fois : meme entree ET meme
            # sortie. Six champs, pas cinq.
            jumeaux = [u for u in tous_apparies
                       if ((u.get("instrument") or {}).get("name"), u.get("direction"),
                           (u.get("entryDate") or "")[:16],
                           (u.get("exitDate") or "")[:16]) == sig
                       and u.get("id") != t.get("id")
                       and abs((_nb(u.get("quantity")) or -1) - (_nb(t.get("quantity")) or -2)) < 1e-6
                       and abs((_nb(u.get("gain")) or -1) - (_nb(t.get("gain")) or -2)) < 0.005]
            if jumeaux:
                print("     %s : DOUBLON cote Edgewonk — meme instrument, sens,"
                      % t.get("id"))
                print("        minute d'entree, quantite et gain que le trade %s,"
                      % jumeaux[0].get("id"))
                print("        qui est deja apparie. A supprimer chez eux.")
            else:
                print("     %s : aucun jumeau apparie. Soit son releve n'est jamais"
                      % t.get("id"))
                print("        passe par le pipeline, soit notre segmentation")
                print("        diverge de la leur sur cette position.")
    else:
        print()
        print("  " + G + "Chaque trade du journal sort d'une de nos bases." + N)

    if ambigus:
        titre("3. Ambigus")
        for a in ambigus:
            print("  " + a)

    if controles:
        titre("4. Controles d'integrite en echec")
        for c in controles:
            print("  " + c)

    titre("5. Ce qui serait ECRIT (rien ne l'est)")

    # Le MEME plan que `jt.py pousser`, construit par le MEME code. Les deux
    # catalogues sont des lectures : ils ne coutent rien et ils sont
    # indispensables — sans eux, `preparer` ne resout ni les paliers ni les
    # options de management, et le plan affiche serait faux par omission.
    catalogues = {}
    for _, _, trade in couples:
        setup = trade.get("setup") or {}
        sid = setup.get("id") if isinstance(setup, dict) else setup
        if sid and sid not in catalogues:
            try:
                catalogues[sid] = client.strategies(BASE_COURANTE, sid)
            except Exception as e:                            # noqa: BLE001
                catalogues[sid] = []
                print("  strategies du setup %s illisibles (%s)" % (sid, e))
    try:
        commentaires = client.commentaires(BASE_COURANTE)
    except Exception as e:                                    # noqa: BLE001
        commentaires = None
        print("  catalogue des commentaires illisible (%s) — repli" % e)

    donnees = os.path.dirname(TRADES)
    plans, notes = ecriture.preparer(couples, donnees, catalogues, tous,
                                     commentaires=commentaires)
    if notes:
        print()
        for x in notes[:10]:
            print("  signalement : " + x)
        if len(notes) > 10:
            print("  … et %d autres" % (len(notes) - 10))

    print()
    champs = sum(len(p["modify"]) + len(p["put"]) for p in plans)
    images = sum(len(p["images"]) for p in plans)
    print("  %d trade(s) a modifier, %d champ(s), %d image(s)"
          % (len(plans), champs, images))
    print()
    for p in plans[:25]:
        detail = dict(p["modify"])
        detail.update(p["put"])
        # Les listes (paliers) sont longues : on les resume plutot que de
        # noyer la sortie.
        for k, v in list(detail.items()):
            if isinstance(v, list):
                detail[k] = "%d entree(s)" % len(v)
        print("  %-34s id %-10s %s%s"
              % (p["cle"], p["id"], detail,
                 "  +%d image(s)" % len(p["images"]) if p["images"] else ""))
    if len(plans) > 25:
        print("  … et %d autres" % (len(plans) - 25))

    # Ce que chaque champ represente, pour qu'un total ne cache pas un vide.
    par_champ = {}
    for p in plans:
        for k in list(p["modify"]) + list(p["put"]):
            par_champ[k] = par_champ.get(k, 0) + 1
    if par_champ:
        print()
        print("  Repartition par champ :")
        for k in sorted(par_champ, key=lambda x: -par_champ[x]):
            print("     %-24s %d trade(s)" % (k, par_champ[k]))

    titre("Rien n'a ete ecrit")
    print("  Aucun modify, aucun PUT.")


if __name__ == "__main__":
    main()
