#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UN id Edgewonk -> tout ce qu'on sait de ce trade. Lecture seule.

POURQUOI CE MODULE EXISTE

L'utilisateur ouvre son journal, voit un trade dont le TP/SL first est vide (ou
faux), et donne l'id. `diag_trade.py` sait deballer une jambe a partir de NOTRE
cle ; il ne sait rien faire d'un id Edgewonk, qui est pourtant la seule
reference visible depuis l'interface. Chaque question coutait donc un
aller-retour pour retrouver la cle a la main.

Ce module part de l'autre bout : l'id, l'appariement inverse, puis les trois
sources cote a cote.

⚠️ LE BLOC « AVEC LEURS NIVEAUX » N'EST PAS UNE PROPOSITION D'ECRITURE.

Quand notre base n'a ni SL ni TP et qu'Edgewonk en affiche, la tentation est de
recopier. On ne le fait pas — « un stop devine est pire qu'un stop absent ».
Ces niveaux viennent de LEUR import, pas de nous, et la mesure du 28/08/2026
montre qu'ils ne se valent pas entre eux (17926433 porte un SL a 0.0). Le bloc
sert a JUGER un niveau, pas a l'adopter : il le confronte a ce que le prix a
reellement fait pendant le trade.

Usage :
    python3 outils/diag_id.py 17926446
    python3 outils/diag_id.py 17926446 --journal 100004
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
TRADES = os.path.join(DONNEES, "trades.csv")
# ⚠️ UNE SEULE BASE DEPUIS LE 28/08/2026. Le chantier retroactif avait la
# sienne ; elle a ete fusionnee dans la production (241 jambes) et le projet
# archive. Tout ce qui lisait « les deux bases » ne lit plus qu'un fichier.

CHAMPS_EW = ("id", "instrument", "entryDate", "exitDate", "quantity", "gain",
             "slPrice", "tpPrice", "highestPrice", "lowestPrice",
             "originalTpHit", "rMultiple", "ignoreForWinrate", "inReview")

CHAMPS_NOUS = ("cle_position", "sens", "symbole_broker", "ouverture", "cloture",
               "entree", "sortie", "volume_lots", "net", "sl", "tp",
               "prix_plus_haut", "prix_plus_bas", "tp_touche_en_premier",
               "prix_max_favorable", "management", "source_brut")


def _p(v):
    """Un prix, sans perdre de decimale. `%.5g` affichait 29404.5 en « 29404 » —
    une troncature invisible sur un indice a cinq chiffres, et le lecteur
    concluait que le niveau n'avait pas ete atteint."""
    if v is None:
        return "-"
    t = "%.8f" % float(v)
    return t.rstrip("0").rstrip(".") or "0"


def _f(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def charger_nos():
    """Toute la base, sans filtre de plateforme : un id Edgewonk peut tomber
    aussi bien sur une jambe cTrader que sur une jambe Tradovate."""
    return dict(base.charger(TRADES))


def extremes_position(nos, jambe):
    """Plus haut / plus bas sur TOUTE la position, pas sur la seule jambe.

    Une position sortie en trois fois porte trois jambes ; chacune ne connait
    que sa propre fenetre. Juger un niveau sur une fenetre partielle ferait
    conclure « jamais touche » sur un stop touche pendant une autre jambe.
    """
    cp = jambe.get("cle_position")
    hauts, bas = [], []
    for t in nos.values():
        if t.get("cle_position") != cp:
            continue
        h, b = _f(t.get("prix_plus_haut")), _f(t.get("prix_plus_bas"))
        if h is not None:
            hauts.append(h)
        if b is not None:
            bas.append(b)
    return (max(hauts) if hauts else None), (min(bas) if bas else None)


def juger(sens, entree, sl, tp, haut, bas, sortie=None):
    """(verdict, lignes) — ce que valent DES niveaux face au prix constate.

    Rend un verdict en trois etats, jamais un booleen : `impossible` (le niveau
    ne peut pas avoir existe), `douteux` (il peut, mais quelque chose cloche),
    `plausible` (rien a redire). Le troisieme ne veut pas dire « vrai ».
    """
    achat = sens == "Achat"
    lignes, defauts = [], []

    if sl is None or tp is None or entree is None:
        return "incomplet", ["niveaux incomplets"]
    if sl == 0 or tp == 0:
        defauts.append("un niveau vaut 0 — valeur d'import, pas un ordre")
    cote_sl = (sl < entree) if achat else (sl > entree)
    cote_tp = (tp > entree) if achat else (tp < entree)
    if not cote_sl:
        defauts.append("le SL est du MAUVAIS cote de l'entree")
    if not cote_tp:
        defauts.append("le TP est du MAUVAIS cote de l'entree")

    risque = abs(entree - sl)
    if risque > 0:
        rr = abs(tp - entree) / risque
        lignes.append("risque = %s  ·  R:R = %.1f" % (_p(risque), rr))
        if rr < 0.3 or rr > 20:
            defauts.append("R:R de %.1f hors de tout plan credible" % rr)

    if haut is not None and bas is not None:
        lignes.append("plus haut pendant le trade %s" % _p(haut))
        lignes.append("plus bas  pendant le trade %s" % _p(bas))

        # ⚠️ ON NE RACONTE RIEN D'UN NIVEAU DEJA DECLARE IMPOSSIBLE.
        # Mesure du 28/08/2026 : un SL a 0.0 sur un achat produisait
        # « le SL n'a jamais ete approche : il restait 29564 (1.0 R) », et un
        # niveau du mauvais cote produisait « c'est lui qui a ferme la
        # position ». Deux phrases exactes, mesurees, et absurdes — elles
        # habillaient une valeur d'import en protection reelle. Un niveau du
        # mauvais cote ou nul n'a pas de distance qui veuille dire quelque
        # chose : on le dit faux, et on se tait.
        if cote_sl and sl and risque > 0:
            touche_sl = (bas <= sl) if achat else (haut >= sl)
            # Un stop TOUCHE n'est pas un stop DOUTEUX quand c'est lui qui a
            # ferme la position — sinon tout trade sorti au stop, le cas
            # normal, serait signale. Le defaut n'existe que si le prix a
            # traverse le niveau et que la sortie s'est faite MIEUX que lui :
            # la position a alors survecu a sa propre protection.
            sorti_au_stop = sortie is not None and (
                (sortie <= sl + risque * 0.05) if achat
                else (sortie >= sl - risque * 0.05))
            if touche_sl and not sorti_au_stop:
                defauts.append("le prix a TRAVERSE ce SL et le trade a continue "
                               "(sortie a %s, du bon cote du stop)" % _p(sortie))
            elif touche_sl:
                lignes.append("le SL a ete touche — et c'est lui qui a ferme "
                              "la position")
            else:
                marge = (bas - sl) if achat else (sl - haut)
                lignes.append("le SL n'a jamais ete approche : il restait %s (%.1f R)"
                              % (_p(abs(marge)), abs(marge) / risque))
        if cote_tp and tp and risque > 0:
            if (haut >= tp) if achat else (bas <= tp):
                lignes.append("le TP a ete atteint pendant le trade")
            else:
                ecart = (tp - haut) if achat else (bas - tp)
                lignes.append("le TP n'a jamais ete approche : il restait %s (%.1f R)"
                              % (_p(abs(ecart)), abs(ecart) / risque))
    else:
        lignes.append(J + "pas d'extremes en base — jugement limite" + N)

    verdict = ("impossible" if any("MAUVAIS cote" in d or "vaut 0" in d for d in defauts)
               else "douteux" if defauts else "plausible")
    return verdict, lignes + [R + "⚠ " + d + N for d in defauts]


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args or not args[0].isdigit():
        print(__doc__)
        return 1
    ident = args[0]
    try:
        _, _journal = base.options_ligne(sys.argv)
    except ValueError as e:
        print("\n  " + str(e) + "\n")
        return 1
    journal = _journal or pf.base_edgewonk(pf.CTRADER)

    try:
        client = Client().authentifier()
    except ErreurEdgewonk as e:
        print("\n  " + R + str(e).replace("\n", "\n  ") + N)
        return 1
    tous = client.tous_les_trades(journal)
    leur = next((t for t in tous if str(t.get("id")) == ident), None)
    if leur is None:
        print("\n  aucun trade %s dans le journal %s (%d lus)"
              % (ident, journal, len(tous)))
        return 1

    print()
    print(GRAS + "  TRADE EDGEWONK %s" % ident + N + "   journal %s" % journal)
    print("  " + "=" * 72)
    for c in CHAMPS_EW:
        v = leur.get(c)
        if c == "instrument":
            v = (v or {}).get("name")
        if c == "originalTpHit":
            v = "(vide)" if v is None else ("oui — TP first" if v else "non — SL first")
        print("     %-20s %s" % (c, v if v not in (None, "") else "(vide)"))

    nos = charger_nos()
    couples, sans, _, _ = apparier(nos, tous)
    rattraper(nos, tous, couples, sans)
    notre = next(((cle, j) for cle, j, t in couples if str(t.get("id")) == ident), None)

    print()
    print(GRAS + "  NOTRE JAMBE" + N)
    print("  " + "-" * 72)
    if notre is None:
        print("  " + J + "aucune jambe appariee — ce trade n'a pas d'equivalent "
              "chez nous." + N)
        print("  Rien a corriger cote pipeline : il vient de leur import.")
        print()
        return 0
    cle, j = notre
    print("  " + GRAS + cle + N)
    for c in CHAMPS_NOUS:
        print("     %-20s %s" % (c, j.get(c) or "(vide)"))

    n_sl, n_tp = _f(j.get("sl")), _f(j.get("tp"))
    l_sl, l_tp = _f(leur.get("slPrice")), _f(leur.get("tpPrice"))
    entree = _f(j.get("entree"))
    haut, bas = extremes_position(nos, j)

    print()
    print(GRAS + "  POURQUOI LE TP/SL FIRST EST CE QU'IL EST" + N)
    print("  " + "-" * 72)
    if n_sl is not None and n_tp is not None:
        print("  Notre base porte les deux niveaux : la reponse a ete calculee")
        print("  sur bougies M1. Pour la deballer minute par minute :")
        print("    python3 outils/diag_trade.py %s%s"
              % (cle.split("#")[0], " --tradovate" if j.get("plateforme") == "tradovate" else ""))
    else:
        print("  Notre base n'a %s — et le pipeline ne calcule le TP-first"
              % ("ni SL ni TP" if n_sl is None and n_tp is None
                 else "pas de SL" if n_sl is None else "pas de TP"))
        print("  QUE si la jambe porte les deux. Le champ est vide parce qu'il")
        print("  n'y a rien a comparer, pas parce qu'un calcul a echoue.")
        if l_sl is not None or l_tp is not None:
            print()
            print("  Les niveaux affiches dans Edgewonk (SL %s · TP %s) viennent de"
                  % (leur.get("slPrice"), leur.get("tpPrice")))
            print("  LEUR import, pas de nous. Ce qu'ils valent :")
            print()
            verdict, lignes = juger(j.get("sens"), entree, l_sl, l_tp, haut, bas,
                                    _f(j.get("sortie")))
            couleur = {"plausible": G, "douteux": J}.get(verdict, R)
            for ligne in lignes:
                print("     " + ligne)
            print()
            print("     verdict : " + couleur + GRAS + verdict.upper() + N)
    print()
    print("  Rien n'a ete ecrit.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
