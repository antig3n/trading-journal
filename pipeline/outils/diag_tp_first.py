#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CONTROLE CROISE DU TP-FIRST — lecture seule, et une SECONDE implementation.

N'ecrit rien chez Edgewonk. Produit un fichier CSV a relire.

POURQUOI CELUI-CI NE REUTILISE PAS `ctrader/bougies.analyser`

L'utilisateur releve, en relisant son journal, des trades marques « SL first » dont
le graphique montre le contraire. La question n'est donc pas « le pipeline
a-t-il tourne ? » mais « le pipeline a-t-il RAISON ? ».

Un controle qui appellerait `analyser` et `simuler_tp_first` confirmerait
mecaniquement leurs propres conclusions, erreurs comprises. Ce module refait
donc le calcul **a partir de zero**, avec une logique ecrite independamment :

    on balaie les bougies M1 depuis l'entree, et on note la PREMIERE minute ou
    le prix touche la cible, et la PREMIERE ou il touche le stop.
    Celle qui vient avant gagne. Meme minute -> indecidable.

Deux implementations qui divergent, c'est une information. Deux implementations
identiques par construction, c'est un vérificateur muet — le projet en a corrige
six.

CE QU'IL CROISE, POUR CHAQUE JAMBE AYANT UN SL ET UN TP

    mesure        ce que les bougies disent, recalcule ici
    base          ce que porte `tp_touche_en_premier` chez nous
    edgewonk      ce que porte `originalTpHit` chez eux

Et il affiche QUAND chaque niveau a ete touche, pour que le desaccord se
verifie a l'oeil sur le graphique.

⚠️ Le SL et le TP viennent de la SAISIE de l'utilisateur. Si un desaccord vient
d'un niveau mal saisi, ce diagnostic ne peut pas le savoir — il le rendra
visible en montrant les prix, et c'est a lui de trancher.

Usage :
    python3 outils/diag_tp_first.py                 # cTrader (MCP ouvert)
    python3 outils/diag_tp_first.py --tradovate     # futures (Databento)

    ... --jours 90                                  # horizon de recherche

⚠️ `--jours` n'est PAS un nombre de trades. TOUTES les jambes ayant un SL et un
TP sont controlees, sans exception. C'est la profondeur de recherche APRES
l'entree de chaque trade : jusqu'ou on avance dans les bougies pour voir lequel
des deux niveaux tombe en premier. Par defaut il vaut `JOURS_MAX`, le meme
horizon que le pipeline — sinon le controle declarerait « indetermine » des
trades que le pipeline, lui, a resolus, et le desaccord viendrait du controle.
    ... --corriger                                  # ECRIT la mesure dans la base

CORRECTION — `--corriger`

Sans ce drapeau, rien n'est ecrit : on regarde. Avec, la valeur MESUREE remplace
`tp_touche_en_premier` partout ou elle differe, instantane pris avant.

⚠️ IL N'ECRIT QUE DANS LA BASE LOCALE, jamais chez Edgewonk. C'est le principe
du projet — la base est la reference, Edgewonk n'en est qu'un consommateur — et
c'est aussi le chemin le plus sur : le `pousser` habituel verra ensuite que
notre valeur differe de la leur et corrigera `originalTpHit`, avec son
instantane, sa confirmation tapee et sa relecture. On ne double pas un chemin
d'ecriture externe deja eprouve.

    python3 outils/diag_tp_first.py --corriger
"""

import csv
import datetime as dt
import io
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base, plateformes as pf                      # noqa: E402
from ctrader.bougies import recuperer                         # noqa: E402

G, J, R, N, GRAS = "\033[32m", "\033[33m", "\033[31m", "\033[0m", "\033[1m"

DONNEES = os.path.normpath(os.path.join(RACINE, "..", "donnees"))
TRADES = os.path.join(DONNEES, "trades.csv")
# ⚠️ UNE SEULE BASE DEPUIS LE 28/08/2026 — le drapeau `--retroactif` a donc
# disparu. Le chantier avait sa base ; elle est fusionnee (241 jambes) et le
# projet archive. Un drapeau qui ne peut plus rien selectionner est pire qu'un
# drapeau absent : il se tape encore, et il ne fait plus rien.
from ctrader.bougies import JOURS_MAX                       # noqa: E402

JOURS = JOURS_MAX          # le meme horizon que le pipeline qu'on controle
VIDES_MAX = 4


def _f(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _utc(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def premiere_touche(client, symbole, sens, entree, sl, tp, ouverture, jours):
    """(moment_tp, moment_sl, note) — les PREMIERES minutes ou chaque niveau
    est touche, ou None si le niveau ne l'est pas dans l'horizon.

    Ecrit independamment de `ctrader/bougies.py` : on ne cherche pas « lequel
    en premier », on releve les DEUX dates et on laisse l'appelant comparer.
    C'est ce qui permet d'afficher la preuve au lieu d'une conclusion.
    """
    achat = sens == "Achat"
    depart = _utc(ouverture)
    moment_tp = moment_sl = None
    vides = 0
    for jour in range(jours):
        d = depart + dt.timedelta(days=jour)
        f = d + dt.timedelta(days=1)
        try:
            bougies = recuperer(client, symbole, d.isoformat(), f.isoformat())
        except Exception as e:                                # noqa: BLE001
            return moment_tp, moment_sl, "bougies indisponibles (%s)" % str(e).splitlines()[0]
        if not bougies:
            if f > dt.datetime.now(dt.timezone.utc):
                return moment_tp, moment_sl, "historique pas encore disponible"
            vides += 1
            if vides > VIDES_MAX:
                return moment_tp, moment_sl, "historique interrompu"
            continue
        vides = 0
        for b in bougies:
            t = _utc(b["timestamp"])
            if t < depart:
                continue
            haut, bas = float(b["high"]), float(b["low"])
            if moment_tp is None and (haut >= tp if achat else bas <= tp):
                moment_tp = t
            if moment_sl is None and (bas <= sl if achat else haut >= sl):
                moment_sl = t
            if moment_tp is not None and moment_sl is not None:
                return moment_tp, moment_sl, ""
    return moment_tp, moment_sl, ""


def verdict(moment_tp, moment_sl):
    """« oui » (TP d'abord) · « non » (SL d'abord) · « » (indecidable/inconnu)."""
    if moment_tp is None and moment_sl is None:
        return "", "aucun des deux touche"
    if moment_sl is None:
        return "oui", ""
    if moment_tp is None:
        return "non", ""
    if moment_tp == moment_sl:
        return "", "les deux dans la meme bougie M1"
    return ("oui", "") if moment_tp < moment_sl else ("non", "")


def main():
    args = sys.argv[1:]
    jours = JOURS
    if "--jours" in args:
        jours = int(args[args.index("--jours") + 1])

    plateforme = pf.TRADOVATE if "--tradovate" in args else pf.CTRADER
    chemin = TRADES

    try:
        (_debut, _fin), _journal = base.options_ligne(args)
    except ValueError as e:
        print("\n  " + str(e) + "\n")
        return 1
    trades = base.filtrer_periode(
        pf.filtrer(base.charger(chemin), plateforme), _debut, _fin)
    lot = {c: t for c, t in trades.items()
           if _f(t.get("sl")) is not None and _f(t.get("tp")) is not None}

    print()
    print(GRAS + "  CONTROLE CROISE DU TP-FIRST — lecture seule" + N)
    print("  " + "=" * 70)
    print("  source     : la base, %s, %s"
          % (pf.nom(plateforme), base.libelle_periode(_debut, _fin)))
    print("  jambes     : %d avec SL et TP, sur %d — TOUTES sont controlees"
          % (len(lot), len(trades)))
    sans = len(trades) - len(lot)
    if sans:
        print("               (%d sans SL ou sans TP : la question ne se pose pas)"
              % sans)
    print("  horizon    : %d jours APRES l'entree de chaque trade" % jours)
    if not lot:
        print("  rien a croiser.")
        return 0

    # --- ce que porte Edgewonk
    distants = {}
    try:
        from edgewonk.api import Client
        from edgewonk.appariement import apparier, rattraper
        client_ew = Client().authentifier()
        tous = client_ew.tous_les_trades(_journal or pf.base_edgewonk(plateforme))
        couples, sans, _, _ = apparier(lot, tous)
        rattraper(lot, tous, couples, sans)
        distants = {cle: t for cle, _, t in couples}
        print("  edgewonk   : %d / %d apparies" % (len(distants), len(lot)))
    except Exception as e:                                    # noqa: BLE001
        print("  " + J + "edgewonk illisible (%s) — on croisera sans eux"
              % str(e).splitlines()[0] + N)

    # --- la source de bougies
    if plateforme == pf.TRADOVATE:
        from databento import client as databento
        client = databento.Client(cache=os.path.join(DONNEES, "bougies")).ouvrir()
    else:
        from ctrader.mcp import Client as ClientMCP
        client = ClientMCP().ouvrir()
    print("  bougies    : %s" % pf.PLATEFORMES[plateforme]["bougies"])
    print()

    lignes, desaccords, indetermines = [], 0, 0
    for i, cle in enumerate(sorted(lot), 1):
        t = lot[cle]
        e, sl, tp = _f(t["entree"]), _f(t["sl"]), _f(t["tp"])
        m_tp, m_sl, note = premiere_touche(
            client, t["symbole_broker"], t["sens"], e, sl, tp, t["ouverture"], jours)
        mesure, raison = verdict(m_tp, m_sl)
        note = note or raison

        notre = (t.get("tp_touche_en_premier") or "").strip()
        trade = distants.get(cle)
        leur_brut = trade.get("originalTpHit") if trade else None
        leur = "" if leur_brut is None else ("oui" if leur_brut else "non")

        accord = "OK"
        if mesure and not notre:
            accord = "BASE VIDE"
        elif mesure and notre and mesure != notre:
            accord = "BASE FAUSSE"
        elif mesure and leur and mesure != leur:
            accord = "EDGEWONK FAUX"
        elif not mesure:
            accord = "indetermine"
            indetermines += 1
        if accord in ("BASE FAUSSE", "EDGEWONK FAUX", "BASE VIDE"):
            desaccords += 1

        lignes.append({
            "cle": cle, "symbole": t["symbole_broker"], "sens": t["sens"],
            "ouverture": t["ouverture"][:19], "entree": t["entree"],
            "sl": t["sl"], "tp": t["tp"],
            "tp_touche_le": m_tp.strftime("%Y-%m-%d %H:%M") if m_tp else "",
            "sl_touche_le": m_sl.strftime("%Y-%m-%d %H:%M") if m_sl else "",
            "mesure": mesure, "base": notre, "edgewonk": leur,
            "verdict": accord, "note": note,
            "id_edgewonk": trade.get("id") if trade else "",
        })
        sys.stdout.write("\r  %d/%d  %-34s" % (i, len(lot), cle))
        sys.stdout.flush()
    sys.stdout.write("\r" + " " * 60 + "\r")

    nom = "tp_first_%s_%s.csv" % (
        pf.normaliser(plateforme),
        dt.datetime.now().strftime("%Y%m%d-%H%M%S"))
    sortie = os.path.join(DONNEES, "controles", nom)
    if not os.path.isdir(os.path.dirname(sortie)):
        os.makedirs(os.path.dirname(sortie))
    with io.open(sortie, "w", encoding="utf-8-sig", newline="") as fic:
        w = csv.DictWriter(fic, fieldnames=list(lignes[0].keys()))
        w.writeheader()
        w.writerows(lignes)

    print("  " + GRAS + "RESULTAT" + N)
    print("  " + "-" * 70)
    print("  jambes croisees   : %d" % len(lignes))
    print("  desaccords        : %s%d%s" % (R if desaccords else G, desaccords, N))
    print("  indetermines      : %d" % indetermines)
    print()
    for l in lignes:
        if l["verdict"] in ("BASE FAUSSE", "EDGEWONK FAUX"):
            print("  %s%s%s  %s" % (R, l["verdict"], N, l["cle"]))
            print("     %s %s · entree %s · SL %s · TP %s"
                  % (l["sens"], l["symbole"], l["entree"], l["sl"], l["tp"]))
            print("     TP touche le %s · SL touche le %s"
                  % (l["tp_touche_le"] or "jamais", l["sl_touche_le"] or "jamais"))
            print("     mesure « %s » · base « %s » · edgewonk « %s »"
                  % (l["mesure"], l["base"] or "-", l["edgewonk"] or "-"))
    print()
    print("  fichier : %s" % sortie)

    a_corriger = [l for l in lignes if l["mesure"]
                  and l["mesure"] != l["base"]]
    if not a_corriger:
        print("  Rien a corriger : la base dit ce que les bougies disent.")
        print("  Rien n'a ete ecrit, ni en local ni chez Edgewonk.")
        print()
        return 0

    print()
    print("  %d jambe(s) ou la base differe de la mesure." % len(a_corriger))
    if "--corriger" not in args:
        print("  Relancer avec %s--corriger%s pour ecrire la mesure dans la base"
              % (GRAS, N))
        print("  locale. Rien n'a ete ecrit, ni en local ni chez Edgewonk.")
        print()
        return 0

    # --- ECRITURE, base locale uniquement.
    complet = base.charger(chemin)
    ecrits = 0
    for l in a_corriger:
        t = complet.get(l["cle"])
        if t is None:
            continue
        t["tp_touche_en_premier"] = l["mesure"]
        ecrits += 1
    copie = base.ecrire(chemin, complet)
    print()
    print("  " + G + "%d valeur(s) corrigee(s) dans la base locale." % ecrits + N)
    print("  instantane : %s" % os.path.basename(copie or ""))
    print()
    print("  Edgewonk n'a PAS ete touche. Pour y propager la correction :")
    print("     python3 jt.py pousser%s"
          % (" --tradovate" if plateforme == pf.TRADOVATE else ""))
    print("  Le plan te montrera les originalTpHit a retourner avant d'ecrire.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
