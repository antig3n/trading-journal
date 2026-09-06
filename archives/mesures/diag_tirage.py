#!/usr/bin/env python3
"""DIAGNOSTIC — la FORME de la reponse de `timeseries.get_range`.

⚠️ CELUI-CI DEPENSE. Une journee de M1 sur un contrat : **0,0050 $**, chiffre
par `metadata.get_cost` le 26/08/2026. Rien n'est ecrit nulle part.

POURQUOI IL EXISTE

Les six sondes de `diag_databento.py` sont des METADONNEES : elles disent que
l'API repond, jusqu'ou remonte l'historique, quels schemas existent et combien
ca coute. Aucune ne dit **quelle tete a un enregistrement OHLCV** — or c'est de
cette forme que `databento/client.py` tire ses prix. Trois hypotheses y sont
ecrites noir sur blanc, et une seule requete les tranche :

  1. la reponse est du JSON par lignes ;
  2. les prix sont des ENTIERS en virgule fixe, a diviser par 1e9 ;
  3. l'horodatage est en nanosecondes depuis l'epoque, dans `hd.ts_event`.

Une erreur d'echelle ne planterait pas : elle produirait des extremes 1e9 fois
trop grands, qui deviendraient des MAE et des R-multiples faux. Invisible a la
lecture — exactement la categorie d'erreur que ce projet elimine.

CE QU'IL AFFICHE : les trois premieres lignes BRUTES telles que Databento les
rend, puis les memes passees par `_barre`. Si les deux se ressemblent, le
client est bon. Sinon, corriger `_barre` — et lui seul.
"""

import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from databento import client as db                            # noqa: E402

G, J, R, N, GRAS = "\033[32m", "\033[33m", "\033[31m", "\033[0m", "\033[1m"

# Une journee ancienne et fermee, sur un contrat que la sonde 5 a resolu.
SYMBOLE = "MNQH6"
JOUR = "2026-03-02"


def main():
    print()
    print(GRAS + "  DIAGNOSTIC — FORME D'UNE REPONSE OHLCV" + N)
    print("  " + "=" * 62)
    print("  %s, %s, ohlcv-1m — cout annonce : 0,0050 $" % (SYMBOLE, JOUR))

    try:
        c = db.Client(cache=None).ouvrir()
    except db.ErreurDatabento as e:
        print("\n  " + R + str(e).replace("\n", "\n  ") + N)
        return 1

    print("\n  " + GRAS + "1. LA REPONSE BRUTE, TELLE QUELLE" + N)
    print("  " + "-" * 62)
    try:
        charge = c._get("timeseries.get_range", {
            "dataset": db.DATASET, "symbols": SYMBOLE, "schema": "ohlcv-1m",
            "stype_in": "raw_symbol",
            "start": "%sT14:30:00Z" % JOUR, "end": "%sT14:35:00Z" % JOUR,
            "encoding": "json", "pretty_px": "false", "pretty_ts": "false",
        })
    except db.ErreurDatabento as e:
        print("  " + R + str(e) + N)
        return 1

    lignes = [l for l in charge.splitlines() if l.strip()]
    print("  %d ligne(s) rendues" % len(lignes))
    for l in lignes[:3]:
        print("    " + l[:200])
    if not lignes:
        print("  " + J + "aucune ligne — fenetre hors seance, ou schema muet." + N)
        return 1

    print("\n  " + GRAS + "2. LES MEMES, PASSEES PAR _barre()" + N)
    print("  " + "-" * 62)
    try:
        barres = [db._barre(e) for e in db._lignes_json(charge)]
    except db.ErreurDatabento as e:
        print("  " + R + "LECTURE IMPOSSIBLE : " + str(e) + N)
        print("  -> corriger `_barre` dans databento/client.py, et rien d'autre.")
        return 1
    for b in barres[:3]:
        print("    %s  O %s  H %s  L %s  C %s  vol %s"
              % (b["timestamp"], b["open"], b["high"], b["low"], b["close"], b["volume"]))

    # Le controle qui compte : un MNQ de mars 2026 vaut quelques dizaines de
    # milliers de points. Une echelle fausse d'un facteur 1e9 saute aux yeux ici
    # et nulle part plus loin.
    print("\n  " + GRAS + "3. L'ORDRE DE GRANDEUR EST-IL CREDIBLE ?" + N)
    print("  " + "-" * 62)
    prix = barres[0]["close"]
    if 1000.0 < prix < 100000.0:
        print("  " + G + "OUI" + N + " — cloture a %.2f, un MNQ plausible." % prix)
        print("  -> l'echelle 1e9 est la bonne, `databento/client.py` est bon.")
    else:
        print("  " + R + "NON" + N + " — cloture a %r." % prix)
        print("  -> l'echelle est fausse. Corriger ECHELLE_PRIX / `_prix`.")
        return 1

    print("\n  " + "=" * 62)
    print("  Rien n'a ete ecrit. Une seule journee a ete facturee.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
