#!/usr/bin/env python3
"""DIAGNOSTIC — dans quel fuseau l'export Tradovate ecrit-il ses heures ?

⚠️ CELUI-CI DEPENSE. De l'ordre de 0,10 $ au premier passage (quelques
journees de M1 a 0,0050 $ l'unite), **zero ensuite** : tout passe par le cache
disque de `databento/client.py`. Il n'ecrit rien, ni en local ni chez Edgewonk.

LA QUESTION, ET POURQUOI ELLE N'EST PAS SECONDAIRE

L'export Tradovate n'annonce pas son fuseau. cTrader, lui, le porte dans son
en-tete (« Opening time (UTC+2) ») et `ctrader/statement.py` le LIT. Ici il n'y
a rien a lire — et `docs/tradovate.md` §5 bis n'a qu'une observation : « decalage
constant de 2 h entre l'horodatage du CSV et celui d'Edgewonk ». Observe sur
quelques trades, jamais mesure.

Or ce decalage decide de TOUT ce qui suit : la fenetre de bougies d'un trade,
donc ses extremes, ses paliers et ses quatre graphiques ; et la cle
d'appariement avec Edgewonk. Une heure d'erreur ne plante pas — elle produit
des MAE, des MFE et des R plausibles et faux. Exactement ce que le §9 du README
appelle « casser en silence ».

LA METHODE — ON MESURE CONTRE LE MARCHE, PAS CONTRE EDGEWONK

Un ordre rempli porte trois faits que personne ne peut contester : un contrat,
un prix d'execution, et une heure locale. Le marche, lui, a un plus haut et un
plus bas par minute UTC. Donc :

    pour chaque decalage candidat, l'heure locale moins ce decalage
    tombe-t-elle sur une bougie M1 dont l'intervalle CONTIENT le prix ?

Un decalage faux fait tomber le prix hors de la bougie, sauf coincidence. Dix
ordres pris a des heures et sur des produits differents ne coincident pas dix
fois. C'est le meme raisonnement qui a tranche le fuseau d'Edgewonk le 25/08 :
partir d'un pivot que le fuseau ne peut pas decaler — la, le montant net ; ici,
le prix — et lire l'ecart plutot que le supposer.

⚠️ CE QUE CE DIAGNOSTIC NE PEUT PAS DIRE tout seul : si le decalage est FIXE ou
s'il suit l'heure d'ete. Un export d'aout ne contient que de l'ete. La sortie
groupe donc les resultats PAR MOIS : le jour ou un export couvrira novembre ou
janvier, la reponse apparaitra d'elle-meme — +1 en hiver signifie heure locale
de Paris, +2 partout signifie decalage fixe.

Usage :
    python3 outils/diag_fuseau_tradovate.py [export_orders.csv] [nb_ordres]
"""

import collections
import csv
import datetime as dt
import glob
import io
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from databento import client as db                            # noqa: E402

DONNEES = os.path.normpath(os.path.join(RACINE, "..", "donnees"))
CACHE = os.path.join(DONNEES, "bougies")

G, J, R, N, GRAS = "\033[32m", "\033[33m", "\033[31m", "\033[0m", "\033[1m"

# Decalages plausibles. On balaie large expres : borner a « +1 ou +2 » serait
# supposer la reponse. Chicago est a -5/-6, New York a -4/-5, Londres a 0/+1.
CANDIDATS = list(range(-8, 9))

ECHANTILLON = 10


def _trouver_export(argument):
    if argument:
        return argument
    motifs = [os.path.join(DONNEES, "brut", "*Orders*.csv"),
              os.path.join(RACINE, "..", "IMPORT", "*Orders*.csv")]
    for m in motifs:
        trouves = sorted(glob.glob(m))
        if trouves:
            return trouves[-1]
    return None


def _lire(chemin):
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f))
    remplis = []
    for r in lignes:
        r = {k: (v or "").strip() for k, v in r.items() if k}
        if r.get("Status") != "Filled" or not r.get("Fill Time"):
            continue
        try:
            moment = dt.datetime.strptime(r["Fill Time"], "%m/%d/%Y %H:%M:%S")
            prix = float(r["Avg Fill Price"].replace(",", ""))
        except (ValueError, KeyError):
            continue
        remplis.append({"contrat": r["Contract"], "moment": moment,
                        "prix": prix, "sens": r.get("B/S", ""),
                        "id": r.get("Order ID", "")})
    return remplis


def _echantillonner(remplis, combien):
    """Etale l'echantillon sur les jours ET les produits.

    Dix ordres de la meme demi-heure sur le meme contrat ne prouveraient rien :
    ils partagent la meme fourchette de prix, donc les memes faux positifs.
    """
    par_groupe = collections.OrderedDict()
    for f in remplis:
        par_groupe.setdefault((f["moment"].date(), f["contrat"]), []).append(f)
    choisis, groupes = [], list(par_groupe.values())
    i = 0
    while len(choisis) < combien and groupes:
        g = groupes[i % len(groupes)]
        if g:
            choisis.append(g.pop(0))
        else:
            groupes.remove(g)
            continue
        i += 1
    return choisis


def main():
    argument = sys.argv[1] if len(sys.argv) > 1 else None
    combien = int(sys.argv[2]) if len(sys.argv) > 2 else ECHANTILLON

    chemin = _trouver_export(argument)
    if not chemin or not os.path.exists(chemin):
        print("\n  export « Orders » introuvable.")
        print("  Le deposer dans donnees/brut/ ou IMPORT/, ou le passer en argument.")
        return 1

    print()
    print(GRAS + "  DIAGNOSTIC — FUSEAU DE L'EXPORT TRADOVATE" + N)
    print("  " + "=" * 66)
    print("  export : %s" % os.path.basename(chemin))

    remplis = _lire(chemin)
    if not remplis:
        print("  " + R + "aucun ordre rempli lisible dans ce fichier." + N)
        return 1
    echantillon = _echantillonner(remplis, combien)
    print("  %d ordres remplis, %d testes" % (len(remplis), len(echantillon)))

    try:
        c = db.Client(cache=CACHE).ouvrir()
    except db.ErreurDatabento as e:
        print("\n  " + R + str(e).replace("\n", "\n  ") + N)
        return 1

    print()
    print("  %-8s %-20s %-11s  %s" % ("contrat", "heure de l'export", "prix", "decalages qui collent"))
    print("  " + "-" * 66)

    compte = collections.Counter()
    par_mois = collections.defaultdict(collections.Counter)
    testes = 0

    for f in echantillon:
        colles = []
        for h in CANDIDATS:
            vise = (f["moment"] - dt.timedelta(hours=h)).replace(tzinfo=dt.timezone.utc)
            minute = vise.replace(second=0, microsecond=0)
            try:
                reponse = c.appeler("get_trendbars", {
                    "symbolName": f["contrat"], "timeframe": "m1",
                    "from": minute.isoformat(),
                    "to": (minute + dt.timedelta(minutes=1)).isoformat(),
                })
            except db.ErreurDatabento as e:
                print("  " + R + "%s : %s" % (f["contrat"], e) + N)
                return 1
            barres = reponse.get("bars") or []
            if barres and barres[0]["low"] <= f["prix"] <= barres[0]["high"]:
                colles.append(h)
        testes += 1
        for h in colles:
            compte[h] += 1
            par_mois["%04d-%02d" % (f["moment"].year, f["moment"].month)][h] += 1
        texte = ", ".join("UTC%+d" % h for h in colles) or (J + "aucun" + N)
        print("  %-8s %-20s %-11.5g  %s"
              % (f["contrat"], f["moment"].strftime("%d/%m/%Y %H:%M:%S"), f["prix"], texte))

    print()
    print("  " + GRAS + "VERDICT" + N)
    print("  " + "-" * 66)
    if not compte:
        print("  " + R + "aucun decalage ne colle sur aucun ordre." + N)
        print("  Deux causes possibles, et elles ne se confondent pas :")
        print("    - l'echelle des prix du client Databento est fausse")
        print("      -> lancer d'abord outils/diag_tirage.py ;")
        print("    - le decalage n'est pas un nombre entier d'heures.")
        return 1

    unanimes = [h for h, n in compte.items() if n == testes]
    for h, n in compte.most_common():
        marque = G + "  <-- sur TOUS les ordres testes" + N if n == testes else ""
        print("  UTC%+d : %d/%d ordres%s" % (h, n, testes, marque))

    print()
    if len(unanimes) == 1:
        print("  " + G + "L'export Tradovate ecrit ses heures en UTC%+d."
              % unanimes[0] + N)
        print("  Un seul decalage colle sur les %d ordres testes." % testes)
    elif unanimes:
        print("  " + J + "%d decalages collent partout : %s."
              % (len(unanimes), ", ".join("UTC%+d" % h for h in unanimes)) + N)
        print("  Relancer avec un echantillon plus large :")
        print("    python3 outils/diag_fuseau_tradovate.py %s 25" % os.path.basename(chemin))
    else:
        print("  " + J + "aucun decalage ne colle sur TOUS les ordres." + N)
        print("  Soit l'export melange deux regimes horaires (heure d'ete),")
        print("  soit un ordre a ete rempli hors bougie. Lire le detail par mois.")

    if len(par_mois) > 1:
        print()
        print("  " + GRAS + "PAR MOIS — c'est ici que se voit l'heure d'ete" + N)
        print("  " + "-" * 66)
        for mois in sorted(par_mois):
            detail = ", ".join("UTC%+d (%d)" % (h, n)
                               for h, n in par_mois[mois].most_common(3))
            print("  %s : %s" % (mois, detail))
        print()
        print("  Un decalage qui BAISSE d'une heure en hiver = heure locale de")
        print("  Paris, a resoudre par date. Un decalage constant = offset fixe.")
    else:
        print()
        print("  " + J + "Un seul mois dans cet export : l'heure d'ete n'est pas" + N)
        print("  " + J + "testee. Relancer sur un export couvrant novembre ou janvier." + N)

    print()
    print("  " + c.resume())
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
