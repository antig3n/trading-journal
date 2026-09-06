#!/usr/bin/env python3
"""Diagnostic n°13 — LECTURE SEULE. Les doublons d'Edgewonk.

NE SUPPRIME RIEN. NE MODIFIE RIEN. L'utilisateur supprime a la main dans
l'interface ; ce script lui dit QUOI supprimer, et sert ensuite de controle.

    python3 outils/diag_doublons.py            analyse et produit la liste
    python3 outils/diag_doublons.py --controle verifie qu'il n'en reste plus

ORIGINE — 25/08/2026. Un reimport du releve a duplique des trades : le releve
cTrader compte 34 jambes en mars 2026 quand Edgewonk en affiche 64, 23 en avril
contre 46, 11 en mai contre 22. Les copies ne sont pas identiques : certaines
portent la saisie manuelle de l'utilisateur, les autres sont vierges.

LA REGLE DE DECISION, et pourquoi elle est prudente :

  On ne declare une copie supprimable que si son contenu est un SOUS-ENSEMBLE
  STRICT d'une autre copie du meme groupe — c'est-a-dire : tout ce qu'elle porte,
  l'autre le porte aussi, et l'autre porte quelque chose en plus.

  On ne devine PAS quels champs comptent. On compare les copies champ par champ,
  sur tous les champs non derives. Un champ rempli d'un cote et vide de l'autre
  suffit a decider ; deux copies qui portent chacune quelque chose que l'autre
  n'a pas ne sont JAMAIS proposees a la suppression — elles sont signalees pour
  jugement humain.
"""

import csv
import io
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from core import base as _base                              # noqa: E402
from edgewonk.api import Client                              # noqa: E402

# ⚠️ LE JOURNAL SE CHOISIT, IL N'EST PLUS EN DUR.
# Depuis que l'utilisateur a un bac à sable (29/08/2026), chercher des doublons
# dans le mauvais journal donnerait une réponse juste sur les mauvaises
# données — la forme d'erreur la plus difficile à voir. La résolution se fait
# ici, au chargement du module, parce que ce module n'a pas de `main()` : ses
# deux entrées (`analyser`, `controle`) partagent la constante.
BASE = "100001"
try:
    _, _journal = _base.options_ligne(sys.argv)
    if _journal:
        BASE = _journal
except ValueError as _e:
    sys.exit("\n  %s\n" % _e)
SORTIE = os.path.normpath(os.path.join(RACINE, "..", "donnees", "controles",
                                       "doublons-a-supprimer.csv"))

# Champs calcules par le serveur ou purement techniques : leur presence ne
# temoigne d'aucun travail de l'utilisateur, donc ils ne comptent pas dans la
# comparaison. Tout le reste compte, y compris ce qu'on ne connait pas.
DERIVES = {
    "id", "rMultiple", "rrrPlanned", "rrrRealized", "outcome", "updraw",
    "drawDown", "createdAt", "updatedAt", "modifiedAt", "importId",
    "importedAt", "accountBalance", "balance", "equity", "profitPercent",
    "riskPercent", "positionSize", "duration",
}


def _f(v):
    try:
        return round(float(str(v).replace(",", ".")), 4)
    except (TypeError, ValueError):
        return None


def cle(t):
    """Clé d'identité d'un trade Edgewonk.

    ⚠️ La clé d'appariement du pipeline (symbole, sens, entrée, sortie à la
    MINUTE) ne suffit PAS ici. Mesuré le 26/08/2026 : elle produisait 4 faux
    positifs — de vraies sorties partielles fermées dans la même minute, par
    exemple le 07/08 à 13:44:34 (3,00 lots, +12,00) et 13:44:43 (0,50 lot,
    +1,50). Ce sont deux trades légitimes, pas un doublon.

    On ajoute donc la QUANTITÉ et le GAIN, qui sont exactement les deux
    critères par lesquels `appariement._depart` départage ce cas. Deux vraies
    copies partagent tout ; deux sorties partielles diffèrent sur l'un des deux.
    """
    return ((t.get("instrument") or {}).get("name"),
            t.get("direction"),
            (t.get("entryDate") or "")[:16],
            (t.get("exitDate") or "")[:16],
            _f(t.get("quantity")),
            _f(t.get("gain")))


def rempli(v):
    if v is None or v is False:
        return False
    if isinstance(v, str):
        return v.strip() != ""
    if isinstance(v, (list, dict)):
        return len(v) > 0
    if isinstance(v, (int, float)):
        return v != 0
    return True


def contenu(t):
    """L'ensemble des champs porteurs de quelque chose, hors derives."""
    return {k for k, v in t.items() if k not in DERIVES and rempli(v)}


def libelle(t):
    k = cle(t)
    return "%s %-4s %s -> %s  %s lots  net %s" % (
        k[0], k[1], k[2], (k[3] or "")[11:], k[4], k[5])


def charger():
    c = Client()
    c.authentifier()
    print("  authentifie")
    trades = c.tous_les_trades(BASE)
    print("  %d trades lus sur la base %s\n" % (len(trades), BASE))
    return c, trades


def grouper(trades):
    g = {}
    for t in trades:
        g.setdefault(cle(t), []).append(t)
    return {k: v for k, v in g.items() if len(v) > 1}


def analyser():
    _, trades = charger()
    doublons = grouper(trades)
    if not doublons:
        print("  Aucun doublon. Rien a faire.")
        return

    a_supprimer, a_juger = [], []
    for k, copies in sorted(doublons.items(), key=lambda x: x[0][2] or ""):
        contenus = [(t, contenu(t)) for t in copies]
        # La copie la plus riche sert de reference.
        contenus.sort(key=lambda x: len(x[1]), reverse=True)
        garde, riche = contenus[0]
        for t, c in contenus[1:]:
            manque = c - riche          # ce que CETTE copie a et que l'autre n'a pas
            if manque:
                a_juger.append((k, garde, t, sorted(manque)))
            else:
                a_supprimer.append((k, garde, t, sorted(riche - c)))

    print("=" * 78)
    print(" %d groupe(s) de doublons — %d trade(s) en trop"
          % (len(doublons), sum(len(v) - 1 for v in doublons.values())))
    print("=" * 78)
    print()

    if a_supprimer:
        print("  A SUPPRIMER — %d trade(s). Copie vierge, contenu strictement" % len(a_supprimer))
        print("  inclus dans celle qu'on garde. Suppression sans perte.\n")
        mois = None
        for k, garde, mort, plus in a_supprimer:
            m = (k[2] or "")[:7]
            if m != mois:
                mois = m
                print("  --- %s ---" % mois)
            print("     %s" % libelle(mort))
            print("        supprimer id %-10s | garder id %-10s (porte en plus : %s)"
                  % (mort.get("id"), garde.get("id"),
                     ", ".join(plus[:6]) + ("…" if len(plus) > 6 else "") or "rien"))
        print()

    if a_juger:
        print("  ⚠ A JUGER TOI-MEME — %d cas. Chaque copie porte quelque chose" % len(a_juger))
        print("  que l'autre n'a pas : AUCUNE n'est supprimable sans perte.\n")
        for k, autre, t, manque in a_juger:
            print("     %s" % libelle(t))
            print("        id %-10s porte en propre : %s"
                  % (t.get("id"), ", ".join(manque)))
            print("        id %-10s est l'autre copie" % autre.get("id"))
        print()

    dossier = os.path.dirname(SORTIE)
    if dossier and not os.path.isdir(dossier):
        os.makedirs(dossier)
    with io.open(SORTIE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["verdict", "id_a_supprimer", "id_a_garder", "symbole",
                    "sens", "entree", "sortie", "ce_que_garde_porte_en_plus"])
        for k, garde, mort, plus in a_supprimer:
            w.writerow(["SUPPRIMER", mort.get("id"), garde.get("id"),
                        k[0], k[1], k[2], k[3], " ".join(plus)])
        for k, autre, t, manque in a_juger:
            w.writerow(["A_JUGER", t.get("id"), autre.get("id"),
                        k[0], k[1], k[2], k[3], "porte en propre: " + " ".join(manque)])
    print("  Liste ecrite : %s" % SORTIE)
    print()
    print("  Ouvre-la a cote d'Edgewonk et supprime a la main les lignes")
    print("  SUPPRIMER. Ensuite :  python3 outils/diag_doublons.py --controle")
    print()
    print("  CE SCRIPT N'A RIEN MODIFIE.")


def controle():
    _, trades = charger()
    doublons = grouper(trades)
    print("=" * 78)
    if not doublons:
        print("  ✓ PLUS AUCUN DOUBLON sur la base %s" % BASE)
        print("=" * 78)
    else:
        reste = sum(len(v) - 1 for v in doublons.values())
        print("  %d groupe(s) restants — %d trade(s) en trop" % (len(doublons), reste))
        print("=" * 78)
        for k, copies in sorted(doublons.items(), key=lambda x: x[0][2] or ""):
            print("     %s  -> ids %s" % (libelle(copies[0]),
                                          [t.get("id") for t in copies]))
    print()
    reconcilier(trades)


def _jambes_locales():
    """Toutes les jambes connues localement.

    ⚠️ Il y avait deux bases jusqu'au 28/08/2026 — production et chantier
    retroactif — et cette fonction les concatenait. Elles sont fusionnees ;
    un seul fichier suffit.
    """
    from core import base as _base
    chemin = os.path.normpath(os.path.join(RACINE, "..", "donnees", "trades.csv"))
    return list(_base.charger(chemin).values()) if os.path.exists(chemin) else []


def reconcilier(trades):
    """Compare Edgewonk aux releves, trade par trade. C'est le vrai controle :
    un compte mensuel identique peut cacher un manquant et un intrus."""
    from edgewonk.appariement import cle_jambe, cle_trade

    jambes = _jambes_locales()
    if not jambes:
        print("  (aucune base locale — reconciliation impossible)")
        return

    locales, distants = {}, {}
    for j in jambes:
        locales.setdefault(cle_jambe(j), []).append(j)
    for t in trades:
        nom = (t.get("instrument") or {}).get("name") or ""
        if ".raw" not in nom.lower():
            continue                                    # futures : hors perimetre
        distants.setdefault(cle_trade(t), []).append(t)

    print("=" * 78)
    print(" RECONCILIATION  releve(s) <-> Edgewonk")
    print("=" * 78)
    mois = sorted({(k[2] or "")[:7] for k in locales} |
                  {(k[2] or "")[:7] for k in distants})
    print("  %-9s %8s %10s %8s" % ("mois", "releve", "Edgewonk", "ecart"))
    tl = td = 0
    for m in mois:
        nl = sum(len(v) for k, v in locales.items() if (k[2] or "")[:7] == m)
        nd = sum(len(v) for k, v in distants.items() if (k[2] or "")[:7] == m)
        tl += nl
        td += nd
        print("  %-9s %8d %10d %8s%s" % (m, nl, nd, "%+d" % (nd - nl),
                                         "" if nl == nd else "   <<<"))
    print("  " + "-" * 40)
    print("  %-9s %8d %10d %8s" % ("TOTAL", tl, td, "%+d" % (td - tl)))
    print()

    intrus = [t for k, v in distants.items() if k not in locales for t in v]
    manquants = [j for k, v in locales.items() if k not in distants for j in v]

    if intrus:
        print("  DANS EDGEWONK MAIS PAS DANS LE RELEVE — %d :" % len(intrus))
        for t in sorted(intrus, key=lambda x: x.get("entryDate") or "")[:20]:
            print("     id %-10s %s" % (t.get("id"), libelle(t)))
        print("     -> doublon residuel, saisie manuelle, ou trade d'un autre compte")
        print()
    if manquants:
        print("  DANS LE RELEVE MAIS PAS DANS EDGEWONK — %d :" % len(manquants))
        for j in sorted(manquants, key=lambda x: x.get("ouverture") or "")[:20]:
            print("     %s  %s  %s lots  net %s"
                  % (j.get("cle"), j.get("symbole"), j.get("volume_lots"), j.get("net")))
        print("     -> jamais importe dans Edgewonk (normal avant le chantier)")
        print()
    if not intrus and not manquants:
        print("  ✓ CONCORDANCE PARFAITE, trade par trade.")
        print()


if __name__ == "__main__":
    if "--controle" in sys.argv:
        controle()
    else:
        analyser()
