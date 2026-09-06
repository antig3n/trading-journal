#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LES NIVEAUX QU'EDGEWONK PORTE ET QUE NOUS N'AVONS PAS — revue, puis reprise.

⚠️ LARGEMENT DEPASSE POUR LES FUTURES DEPUIS LE 28/08/2026, ET C'EST TANT MIEUX.
Ce module a ete ecrit le matin, quand on croyait que l'export ne portait pas les
niveaux de ces 18 positions. Il les portait — sous `Text = Chart` — et
`tradovate/protections.protections_par_fenetre` les lit desormais. Le chemin
normal (`jt.py importer --tradovate`) pre-remplit 31 positions sur 35, depuis TES
ordres et non depuis leur import.

Ce qui reste utile ici, et n'est pas dans le chemin normal : le JUGEMENT.
`juger()` confronte des niveaux au prix reellement constate et rend un verdict en
trois etats. C'est ce qui a permis de mesurer que la lecture par fenetre bat
celle d'Edgewonk sur les 3 cas ou elles divergent. Garder le module pour ca, et
pour les positions residuelles sans ordre lisible dans l'export.

LE PROBLEME, TEL QU'IL S'EST PRESENTE

`diag_coherence` a compte 18 trades ou Edgewonk affiche un SL et un TP alors
que notre base n'en a aucun. Consequence directe : le champ TP/SL first reste
vide dans le journal, puisque le pipeline ne calcule cette reponse que sur des
niveaux qu'il possede. De l'exterieur ca ressemble a un bug ; c'est un trou de
donnees, et il vient d'en haut — ce sont des entrees posees au graphique avant
le passage aux brackets ATM du 18/08, sans ordre stop lisible dans l'export.

DEUX ISSUES, ET UNE SEULE EST HONNETE

  * recopier leurs niveaux chez nous — non. Ils viennent de LEUR import et ils
    ne se valent pas entre eux : la mesure du 28/08/2026 en trouve dont le SL
    vaut 0.0, d'autres du mauvais cote de l'entree, d'autres que le prix a
    traverses alors que la position a continue. « Un stop devine est pire
    qu'un stop absent » vaut aussi pour un stop devine par quelqu'un d'autre.

  * les SOUMETTRE a l'utilisateur avec, a cote, ce que le prix a reellement fait —
    oui. C'est ce que fait ce module. Il ne decide rien : il instruit.

CE QU'IL PRODUIT

  1. un rapport lisible, un bloc par position, verdict en trois etats
  2. un fichier de saisie ordinaire (meme colonnes que `jt.py saisie`), pret
     pour `jt.py controler` puis `jt.py integrer`, augmente de colonnes de
     preuve que le controle ignore et qu'un tableur affiche

Par defaut les cases `sl` et `tp` restent VIDES : c'est l'utilisateur qui remplit.
`--proposer` les pre-remplit avec les niveaux d'Edgewonk, mais UNIQUEMENT pour
les positions jugees plausibles — jamais pour une douteuse, jamais pour une
impossible. Meme dans ce mode, rien n'est ecrit dans la base : le fichier reste
a relire, et c'est `jt.py integrer` qui ecrit, apres ses propres controles.

Usage :
    python3 outils/reprise_niveaux.py
    python3 outils/reprise_niveaux.py --proposer
    python3 outils/reprise_niveaux.py --journal 100004 --sortie /tmp/revue.csv
"""

import csv
import io
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base, plateformes as pf                      # noqa: E402
from core.saisie import COLONNES_SAISIE                       # noqa: E402
from edgewonk.api import Client, ErreurEdgewonk               # noqa: E402
from edgewonk.appariement import apparier, rattraper          # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from diag_id import juger, extremes_position, _f, _p              # noqa: E402

G, J, R, N, GRAS = "\033[32m", "\033[33m", "\033[31m", "\033[0m", "\033[1m"

DONNEES = os.path.normpath(os.path.join(RACINE, "..", "donnees"))
TRADES = os.path.join(DONNEES, "trades.csv")
RETRO = os.path.normpath(os.path.join(RACINE, "..", "retroactif", "donnees",
                                      "trades.csv"))
SORTIE = os.path.join(DONNEES, "reprise-niveaux.csv")

# Colonnes de PREUVE. `saisie.lire` passe par un DictReader : tout ce qui
# depasse COLONNES_SAISIE est lu puis ignore par le controle. Elles peuvent
# donc rester dans le fichier que l'utilisateur remet a `jt.py integrer`, ce qui
# evite qu'il ait a jongler avec deux fichiers.
COLONNES_PREUVE = ["verdict", "sl_edgewonk", "tp_edgewonk", "rr",
                   "plus_haut", "plus_bas", "id_edgewonk", "remarque"]


def main():
    proposer = "--proposer" in sys.argv
    journal = (sys.argv[sys.argv.index("--journal") + 1]
               if "--journal" in sys.argv else pf.base_edgewonk(pf.CTRADER))
    sortie = (sys.argv[sys.argv.index("--sortie") + 1]
              if "--sortie" in sys.argv else SORTIE)

    print()
    print(GRAS + "  REPRISE DES NIVEAUX — journal %s" % journal + N)
    print("  " + "=" * 74)

    try:
        client = Client().authentifier()
    except ErreurEdgewonk as e:
        print("\n  " + R + str(e).replace("\n", "\n  ") + N)
        return 1
    tous = client.tous_les_trades(journal)

    production = base.charger(TRADES)
    nos = dict(production)
    if os.path.exists(RETRO):
        for c, t in base.charger(RETRO).items():
            nos.setdefault(c, t)
    couples, sans, _, _ = apparier(nos, tous)
    rattraper(nos, tous, couples, sans)
    par_id = {str(t.get("id")): (cle, j) for cle, j, t in couples}
    print("  %d trades Edgewonk · %d jambes chez nous · %d appariees"
          % (len(tous), len(nos), len(par_id)))

    # --- selection : eux ont les deux niveaux, nous n'en avons aucun
    cas, hors_base, orphelins = {}, [], []
    for t in tous:
        l_sl, l_tp = _f(t.get("slPrice")), _f(t.get("tpPrice"))
        if l_sl is None or l_tp is None:
            continue
        r = par_id.get(str(t.get("id")))
        if r is None:
            orphelins.append(t)
            continue
        cle, j = r
        if _f(j.get("sl")) is not None or _f(j.get("tp")) is not None:
            continue                      # nous avons deja un niveau : rien a reprendre
        if cle not in production:
            hors_base.append((cle, j, t))  # chantier retroactif, autre fichier
            continue
        cp = j.get("cle_position") or cle
        cas.setdefault(cp, {"jambe": j, "trades": []})["trades"].append(t)

    if not cas and not hors_base:
        print("\n  " + G + "aucune position concernee — rien a reprendre." + N + "\n")
        return 0

    # --- instruction, position par position
    print()
    print(GRAS + "  %d POSITION(S) A ARBITRER" % len(cas) + N)
    print("  " + "-" * 74)
    decisions, compte = {}, {"plausible": 0, "douteux": 0, "impossible": 0,
                             "incomplet": 0}
    for cp in sorted(cas):
        j = cas[cp]["jambe"]
        ts = cas[cp]["trades"]
        # Plusieurs jambes d'une meme position peuvent porter des niveaux
        # DIFFERENTS chez eux — leur import segmente autrement. On ne choisit
        # pas a la place de l'utilisateur : on montre tout et on refuse de trancher.
        niveaux = sorted({(_f(t.get("slPrice")), _f(t.get("tpPrice"))) for t in ts})
        haut, bas = extremes_position(nos, j)
        entree, sortie_prix = _f(j.get("entree")), _f(j.get("sortie"))

        print()
        print("  " + GRAS + cp + N)
        print("     %s %s · %s · entree %s · sortie %s · net %s"
              % (j.get("sens"), j.get("symbole_broker"), j.get("ouverture")[:16],
                 j.get("entree"), j.get("sortie"), j.get("net")))
        if len(niveaux) > 1:
            print("     " + J + "%d jeux de niveaux differents chez eux sur cette "
                  "position — a trancher a la main." % len(niveaux) + N)
        pire = None
        for l_sl, l_tp in niveaux:
            verdict, lignes = juger(j.get("sens"), entree, l_sl, l_tp, haut, bas,
                                    sortie_prix)
            couleur = {"plausible": G, "douteux": J}.get(verdict, R)
            # ⚠️ `_p` et pas la valeur brute : leur API rend des flottants
            # bruites (29481.449999999997 pour un niveau pose a 29481.45).
            # Le bruit se recopiait tel quel dans le fichier de saisie.
            print("     SL %-12s TP %-12s  -> %s%s%s"
                  % (_p(l_sl), _p(l_tp), couleur + GRAS, verdict.upper(), N))
            for ligne in lignes:
                print("        " + ligne)
            rang = ["plausible", "douteux", "incomplet", "impossible"]
            if pire is None or rang.index(verdict) > rang.index(pire[0]):
                pire = (verdict, l_sl, l_tp, lignes)
        compte[pire[0]] = compte.get(pire[0], 0) + 1
        risque = abs(entree - pire[1]) if entree is not None and pire[1] else 0
        decisions[cp] = {
            "verdict": pire[0] if len(niveaux) == 1 else pire[0] + " (%d jeux)" % len(niveaux),
            "sl_edgewonk": _p(pire[1]) if len(niveaux) == 1 else "",
            "tp_edgewonk": _p(pire[2]) if len(niveaux) == 1 else "",
            "rr": "%.1f" % (abs(pire[2] - entree) / risque) if risque else "",
            "plus_haut": _p(haut) if haut is not None else "",
            "plus_bas": _p(bas) if bas is not None else "",
            "id_edgewonk": " ".join(str(t.get("id")) for t in ts),
            "remarque": " · ".join(l for l in pire[3] if "⚠" in l).replace(R, "")
                        .replace(N, "").replace("⚠ ", ""),
        }

    if hors_base:
        print()
        print("  " + J + "%d jambe(s) du chantier retroactif, hors du fichier de "
              "production :" % len(hors_base) + N)
        for cle, j, t in hors_base[:10]:
            print("     %-40s SL %s TP %s" % (cle, t.get("slPrice"), t.get("tpPrice")))
        print("     Elles se corrigent dans retroactif/, pas ici.")

    # --- le fichier
    cles_cas = {c for c, t in production.items()
                if (t.get("cle_position") or c) in decisions}
    sources = {production[c].get("source_brut") for c in cles_cas
               if production[c].get("source_brut")}
    # ⚠️ On ecrit TOUTES les positions des releves concernes, pas seulement les
    # 18. `jt.py controler` borne son controle d'exhaustivite au releve : un
    # fichier partiel ferait signaler comme « sans ligne de saisie » toutes les
    # positions du meme import. Les lignes deja renseignees sont pre-remplies
    # depuis la base, donc les rendre ne change rien.
    cles = {c for c, t in production.items() if t.get("source_brut") in sources}
    positions = base.grouper_en_positions(production, cles)

    dossier = os.path.dirname(sortie)
    if dossier and not os.path.isdir(dossier):
        os.makedirs(dossier)
    with io.open(sortie, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES_SAISIE + COLONNES_PREUVE)
        w.writeheader()
        for cp in sorted(positions, key=lambda c: positions[c].get("ouverture", "")):
            p = positions[cp]
            d = decisions.get(cp, {})
            ouv = p.get("ouverture", "")
            sl, tp = p.get("sl", "") or "", p.get("tp", "") or ""
            if proposer and not sl and not tp and d.get("verdict") == "plausible":
                sl, tp = d.get("sl_edgewonk", ""), d.get("tp_edgewonk", "")
            ligne = {
                "cle_position": cp,
                "date": "%s/%s/%s" % (ouv[8:10], ouv[5:7], ouv[0:4]) if len(ouv) >= 10 else "",
                "heure": ouv[11:19],
                "symbole": p.get("symbole_broker", ""),
                "sens": p.get("sens", ""),
                "entree": p.get("entree", ""),
                "lots": "%.2f" % p.get("lots", 0),
                "jambes": len(p.get("jambes", [])),
                "net": "%.2f" % p.get("net", 0),
                "sl": sl, "tp": tp,
                "management": p.get("management", ""),
            }
            ligne.update({c: d.get(c, "") for c in COLONNES_PREUVE})
            w.writerow(ligne)

    print()
    print(GRAS + "  RESUME" + N)
    print("  " + "-" * 74)
    for etat in ("plausible", "douteux", "impossible", "incomplet"):
        if compte.get(etat):
            couleur = {"plausible": G, "douteux": J}.get(etat, R)
            print("  %-12s : %s%d%s" % (etat, couleur, compte[etat], N))
    print("  fichier      : %s" % os.path.relpath(sortie, os.path.join(RACINE, "..")))
    print("  %d ligne(s) au total, dont %d a arbitrer" % (len(positions), len(decisions)))
    print()
    if not proposer:
        print("  Les colonnes sl et tp sont VIDES : c'est toi qui remplis, en")
        print("  t'appuyant sur les colonnes de preuve a droite. Pour pre-remplir")
        print("  les seules positions plausibles avec leurs niveaux :")
        print("    python3 outils/reprise_niveaux.py --proposer")
    else:
        print("  " + J + "Les positions PLAUSIBLES sont pre-remplies avec les niveaux"
              " d'Edgewonk." + N)
        print("  Ce ne sont pas des mesures : relis-les avant d'integrer.")
    print()
    print("  Puis, quand le fichier te convient :")
    print("    python3 jt.py controler %s" % os.path.relpath(sortie, RACINE))
    print("    python3 jt.py integrer  %s" % os.path.relpath(sortie, RACINE))
    print("    python3 jt.py bougies && python3 jt.py graphiques && python3 jt.py pousser")
    print()
    print("  Rien n'a ete ecrit dans la base.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
