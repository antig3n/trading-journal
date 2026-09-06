"""Lecture de l'export « Orders » de Tradovate -> des JAMBES.

UN SEUL FICHIER SUFFIT — mesure du 26/08/2026, et c'est un renversement.

`docs/tradovate.md` §5 bis et §8 tenaient l'export « Position History » pour la piece
maitresse : lui seul porterait l'appariement FIFO des executions, donc la
segmentation d'Edgewonk. **C'est faux.** L'export « Orders » porte, pour chaque
ordre rempli, son heure, sa quantite, son prix moyen et sa valeur notionnelle.
De quoi refaire l'appariement FIFO soi-meme — et le refaire EXACTEMENT.

Verifie contre les trades reels du journal 100004, cinq sur cinq, au centime :

    NQ  SELL 13:03->13:15  q2  +1780.00     = trade 17860742
    NQ  SELL 13:25->13:25  q2   +250.00     = trade 17860743
    MNQ SELL 13:26->13:29  q2    -53.00     = trade 17860744
    MNQ SELL 13:30->13:35  q1     +0.50     = trade 17860745
    MNQ BUY  11:43->14:07  q2     -9.00     = trade 17860746

Segmentation, horodatages, quantites et P/L : identiques. Le second export
n'apporterait rien qu'on ne sache deja, et il faisait dependre la chaine d'un
fichier de plus a exporter, a nommer et a ne pas confondre.

──────────────────────────────────────────────────────────────────────────────
LE GRAIN — un trade Edgewonk = UN PASSAGE A PLAT

    Tout ce qui se passe sur un contrat entre deux moments ou le compte est
    plat forme UN trade Edgewonk, et UNE position — donc une ligne de saisie,
    donc une protection.

⚠️ RENVERSE le 26/08/2026, sur un contre-exemple trouve dans les donnees.

Le §5 bis de `docs/tradovate.md` avait etabli une regle plus savante : un trade
Edgewonk serait une **composante connexe du graphe d'appariement**, un groupe
d'appariements relies par un fill commun. Elle expliquait les deux cas mesures
le 25/08 :

    position `…044`  deux appariements sans fill commun  -> DEUX trades
    position `…180`  deux appariements partageant un fill -> UN SEUL

Mais elle est FAUSSE, et le passage a plat explique les memes deux cas :
`…044` repasse a plat entre ses deux appariements, `…180` non.

Le contre-exemple qui tranche — position MGCV6 du 17/08 14:10 :

    14:10:50  vente 2 @ 4416.0        composante A+B : les deux rachats de
    14:12:20  vente 4 @ 4416.6                         14:17 et 14:18 partagent
    14:17:38  achat 1 @ 4416.8                         le fill de 14:10
    14:18:54  achat 1 @ 4417.0        composante C   : le rachat de 15:07
    15:07:06  achat 4 @ 4407.0                         consomme le fill de 14:12

La regle des composantes predit DEUX trades (-18.00 et +384.00). Edgewonk n'en
a fait **qu'un**, entree au VWAP **4416.4**, gain **366.00** — soit exactement
la position entiere. Le passage a plat, lui, le predit juste.

Et le compte tombe : **34 positions flat-to-flat ouvertes avant le 22/08, 34
trades dans le journal 100004.** L'ancienne regle en donnait 35.

*La regle des composantes n'etait pas absurde : elle collait aux deux seuls cas
alors disponibles. C'est le §8, regle 6, mot pour mot — un echantillon de deux
ne fait pas une regle. Elle a survecu une journee.*

⚠️ Une position ENCORE OUVERTE ne produit aucune jambe. Un trade Edgewonk naît
du retour a plat ; une sortie partielle n'en est pas un. Le cas est signale et
la position entrera au cycle suivant, complete. Meme principe que la simulation
des paliers non resolue : on n'ecrit rien plutot qu'une moitie de fait.

──────────────────────────────────────────────────────────────────────────────
LE MULTIPLICATEUR EST MESURE, PAS TABULE

Le P/L en dollars demande la taille du contrat. La coder en dur — NQ 20, MNQ 2,
GC 100, 6E 125 000 — serait une table a maintenir, et une table fausse produit
des montants plausibles. L'export porte `Notional Value`, donc :

    multiplicateur = notionnel / (prix * quantite)

Mesure : NQU6 -> 20, MNQU6 -> 2, GCZ6 -> 100, MGC* -> 10, MCLU6 -> 100,
6EU6 -> 125 000. Le notionnel etant arrondi au cent, la division rend parfois
9.999924 : on arrondit a l'entier et on SIGNALE si l'ecart depasse le bruit
d'arrondi, au lieu de l'absorber en silence.

⚠️ L'export ne porte NI commission NI frais. `brut` et `net` valent donc le
meme P/L, et les colonnes de frais restent VIDES — pas a zero, qui aurait l'air
d'un fait mesure. Edgewonk affiche le meme montant (`gain` = `gainGross`).
"""

import collections
import csv
import datetime as dt
import io
import os
import re

from core.modele import (SENS_ACHAT, SENS_VENTE, construire_cle_jambe,
                         construire_cle_position, trade_vide)
from core.plateformes import TRADOVATE

# ⚠️ FUSEAU DE L'EXPORT — MESURE le 26/08/2026, pas suppose.
#
# `outils/diag_fuseau_tradovate.py` : pour dix ordres remplis, sur cinq
# contrats et a des heures allant de 01:55 a 19:19, on a cherche quels
# decalages font tomber le prix d'execution DANS la bougie M1 du marche.
# Resultat : **UTC+2 colle sur 10/10**, le suivant sur 3/10. Confirme
# independamment par Edgewonk, qui stocke en UTC : notre 19:19:07 devient
# 17:19:07 chez eux, soit exactement deux heures.
#
# ⚠️ CE QUI N'EST PAS TRANCHE : l'export ne couvre qu'aout, donc que l'heure
# d'ete. Un decalage FIXE de +2 et l'heure locale de Paris sont indiscernables
# sur ces donnees. On retient « paris », qui suit le changement d'heure tout
# seul, plutot qu'un +2 fige qui deriverait d'une heure en novembre — en
# silence, et sur des extremes qui resteraient plausibles.
#   -> Relancer le diagnostic sur un export couvrant novembre ou janvier
#      tranchera de lui-meme. La sortie est deja groupee par mois pour ca.
FUSEAU = "paris"

# Les colonnes dont ce module a besoin. Une absence doit SE VOIR, avec
# l'en-tete reelle sous les yeux — pas degrader en trades manquants.
COLONNES_ATTENDUES = ("Order ID", "B/S", "Contract", "Product", "Status",
                      "Fill Time", "Filled Qty", "Avg Fill Price",
                      "Notional Value")

# Bruit d'arrondi tolere sur le multiplicateur deduit. `Notional Value` est
# arrondi au cent : sur un MGC a 4400, l'erreur relative depasse a peine 1e-5.
TOLERANCE_MULTIPLICATEUR = 1e-3

STATUT_REMPLI = "Filled"

try:
    from zoneinfo import ZoneInfo
    _PARIS = ZoneInfo("Europe/Paris")
except Exception:                                            # noqa: BLE001
    _PARIS = None


class ErreurExport(Exception):
    pass


# ------------------------------------------------------------------ lecture

def _nombre(txt):
    if txt is None:
        return None
    t = str(txt).strip().replace("\xa0", "").replace(" ", "").replace(",", "")
    if t.startswith("(") and t.endswith(")"):        # (53.00) = -53.00
        t = "-" + t[1:-1]
    t = t.replace("$", "")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _decalage(naif):
    """Le decalage a appliquer a CET horodatage, selon FUSEAU."""
    if FUSEAU == "paris":
        if _PARIS is None:
            return "+00:00"
        delta = naif.replace(tzinfo=_PARIS).utcoffset()
        signe = "+" if delta >= dt.timedelta(0) else "-"
        mn = abs(int(delta.total_seconds())) // 60
        return "%s%02d:%02d" % (signe, mn // 60, mn % 60)
    heures = float(FUSEAU)
    signe = "+" if heures >= 0 else "-"
    mn = int(abs(heures) * 60)
    return "%s%02d:%02d" % (signe, mn // 60, mn % 60)


def _naif(txt):
    """« 08/06/2026 15:03:00 » -> datetime naif.

    ⚠️ Le format Tradovate est MM/JJ/AAAA — americain, contrairement a cTrader
    qui ecrit JJ/MM/AAAA. Confondre les deux passerait inapercu onze jours par
    mois et casserait les vingt autres.
    """
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})[ T]+(\d{1,2}):(\d{2})(?::(\d{2}))?",
                 (txt or "").strip())
    if not m:
        raise ErreurExport("horodatage illisible : %r" % txt)
    mo, j, a, h, mi, s = m.groups()
    return dt.datetime(int(a), int(mo), int(j), int(h), int(mi), int(s or 0))


def _iso(naif):
    return "%s.000%s" % (naif.strftime("%Y-%m-%dT%H:%M:%S"), _decalage(naif))


def _exiger(entetes, chemin):
    manquantes = [c for c in COLONNES_ATTENDUES if c not in entetes]
    if manquantes:
        raise ErreurExport(
            "colonnes absentes de %s : %s\n"
            "  en-tete reelle : %s\n"
            "  Est-ce bien l'export « Orders » de Tradovate ?"
            % (os.path.basename(chemin), ", ".join(manquantes),
               ", ".join(e for e in entetes if e)))


def multiplicateurs(fills):
    """{contrat: taille du contrat} — DEDUITE de l'export, jamais tabulee.

    Retourne (multiplicateurs, notes). Une deduction instable est signalee, pas
    moyennee en silence : un multiplicateur faux produit des montants
    plausibles, donc invisibles a la relecture.
    """
    brut = collections.defaultdict(list)
    for x in fills:
        if x["notionnel"] and x["prix"] and x["quantite"]:
            brut[x["contrat"]].append(x["notionnel"] / (x["prix"] * x["quantite"]))
    tailles, notes = {}, []
    for contrat, valeurs in brut.items():
        entier = round(sum(valeurs) / len(valeurs))
        if not entier:
            notes.append("%s : multiplicateur deduit nul — montants non calcules" % contrat)
            continue
        ecart = max(abs(v - entier) / entier for v in valeurs)
        if ecart > TOLERANCE_MULTIPLICATEUR:
            notes.append(
                "%s : multiplicateur instable (%.6g a %.6g, retenu %d) — les "
                "montants de ce contrat sont a verifier"
                % (contrat, min(valeurs), max(valeurs), entier))
        tailles[contrat] = float(entier)
    return tailles, notes


def lire_fills(chemin):
    """Les ordres REMPLIS, tries chronologiquement. Aucune interpretation."""
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f)
        _exiger(lecteur.fieldnames or [], chemin)
        lignes = [{k: (v or "").strip() for k, v in r.items() if k} for r in lecteur]

    fills, anomalies = [], []
    for r in lignes:
        if r.get("Status") != STATUT_REMPLI or not r.get("Fill Time"):
            continue
        quantite = _nombre(r.get("Filled Qty"))
        prix = _nombre(r.get("Avg Fill Price"))
        if not quantite or prix is None:
            anomalies.append("ordre %s rempli mais sans quantite ou prix lisible"
                             % r.get("Order ID"))
            continue
        try:
            moment = _naif(r["Fill Time"])
        except ErreurExport as e:
            anomalies.append("ordre %s : %s" % (r.get("Order ID"), e))
            continue
        fills.append({
            "id": r.get("Order ID", ""),
            "contrat": r.get("Contract", ""),
            "produit": r.get("Product", ""),
            "achat": (r.get("B/S", "")).strip().lower().startswith("buy"),
            "quantite": quantite,
            "prix": prix,
            "notionnel": _nombre(r.get("Notional Value")),
            "moment": moment,
            "compte": r.get("Account", ""),
        })
    # Tri par heure PUIS par identifiant : deux fills a la meme seconde doivent
    # etre consommes dans l'ordre ou le broker les a crees, sinon le FIFO
    # dependrait de l'ordre des lignes du fichier — qu'un tableur peut changer.
    fills.sort(key=lambda x: (x["moment"], int(x["id"]) if x["id"].isdigit() else 0))
    return fills, anomalies


# ------------------------------------------------------- appariement FIFO

def positions_a_plat(fills):
    """(positions, anomalies) pour UN contrat.

    Une position = tout ce qui se passe entre deux passages a plat. On suit la
    quantite nette : elle repasse a zero, la position est close, et la suivante
    commence. C'est mecanique, ca ne suppose rien, et ca reproduit exactement ce
    qu'Edgewonk fabrique (34 positions closes avant le 22/08, 34 trades chez
    eux).

    Chaque position : {"fills": [...], "close": bool}.
    """
    positions, courante, nette = [], [], 0.0
    for x in fills:
        courante.append(x)
        nette += x["quantite"] if x["achat"] else -x["quantite"]
        if abs(nette) < 1e-9:
            positions.append({"fills": courante, "close": True})
            courante, nette = [], 0.0
    anomalies = []
    if courante:
        positions.append({"fills": courante, "close": False})
        anomalies.append(
            "%s : position encore ouverte a la fin de l'export (%.10g contrat(s) "
            "nets) — aucune jambe produite, elle entrera complete au prochain "
            "cycle" % (fills[0]["contrat"], abs(nette)))
    return positions, anomalies


def _decrire(position, tailles):
    """Une position close -> les faits d'UNE jambe. None si indecidable.

    Le sens est celui du PREMIER fill : c'est lui qui ouvre. Entree et sortie
    sont les VWAP de chaque cote — mesure sur la position MGCV6 du 17/08, le
    VWAP d'entree 4416.4 est exactement celui qu'affiche Edgewonk.
    """
    fills = position["fills"]
    achat = fills[0]["achat"]
    entrees = [x for x in fills if x["achat"] == achat]
    sorties = [x for x in fills if x["achat"] != achat]
    if not entrees or not sorties:
        return None
    qe = sum(x["quantite"] for x in entrees)
    qs = sum(x["quantite"] for x in sorties)
    if not qe or not qs:
        return None
    entree = sum(x["prix"] * x["quantite"] for x in entrees) / qe
    sortie = sum(x["prix"] * x["quantite"] for x in sorties) / qs
    taille = tailles.get(fills[0]["contrat"], 1.0)
    signe = 1.0 if achat else -1.0
    return {
        "achat": achat,
        "contrat": fills[0]["contrat"],
        "produit": fills[0]["produit"],
        "quantite": min(qe, qs),
        "entree": entree,
        "sortie": sortie,
        "ouverture": min(x["moment"] for x in entrees),
        "cloture": max(x["moment"] for x in sorties),
        "net": signe * (sortie - entree) * min(qe, qs) * taille,
    }


# ------------------------------------------------------------------- lecture

def lire(chemin):
    """(trades, anomalies). Un trade = UNE position a plat = UN trade Edgewonk."""
    fills, anomalies = lire_fills(chemin)
    if not fills:
        return [], anomalies + ["aucun ordre rempli dans %s"
                                % os.path.basename(chemin)]

    tailles, notes = multiplicateurs(fills)
    anomalies += notes

    par_contrat = collections.OrderedDict()
    for x in fills:
        par_contrat.setdefault(x["contrat"], []).append(x)

    decrites = []
    for contrat, lot in par_contrat.items():
        positions, anos = positions_a_plat(lot)
        anomalies += anos
        for position in positions:
            if not position["close"]:
                continue
            d = _decrire(position, tailles)
            if d is None:
                anomalies.append("%s : position indecidable, ignoree" % contrat)
                continue
            decrites.append(d)

    # Ordre chronologique global : le fichier de saisie se lit dans l'ordre ou
    # les trades ont ete pris, pas contrat par contrat.
    decrites.sort(key=lambda d: d["ouverture"])

    source = os.path.basename(chemin)
    compte = fills[0].get("compte", "")
    trades, vues = [], {}

    for d in decrites:
        sens = SENS_ACHAT if d["achat"] else SENS_VENTE
        ouverture = _iso(d["ouverture"])
        cloture = _iso(d["cloture"])

        cle_pos = construire_cle_position(ouverture, d["contrat"], sens)
        n = vues.get(cle_pos, 0) + 1
        vues[cle_pos] = n
        if n > 1:
            cle_pos = "%s-%d" % (cle_pos, n)
            anomalies.append("deux positions a la meme seconde : %s" % cle_pos)

        t = trade_vide()
        t.update({
            "cle": construire_cle_jambe(cle_pos, cloture),
            "cle_position": cle_pos,
            "compte": compte,
            "symbole": d["produit"] or d["contrat"],
            "symbole_broker": d["contrat"],
            "sens": sens,
            "ouverture": ouverture,
            "cloture": cloture,
            "entree": "%.10g" % d["entree"],
            "sortie": "%.10g" % d["sortie"],
            "volume_lots": "%.2f" % d["quantite"],     # des CONTRATS, pas des lots
            "nb_jambes": "1",                          # une position = un trade
            # L'export ne porte ni commission ni swap : on laisse VIDE plutot
            # qu'un zero, qui aurait l'air d'un fait mesure.
            "swaps": "",
            "commission": "",
            "brut": "%.2f" % d["net"],
            "net": "%.2f" % d["net"],
            "source_brut": source,
            "plateforme": TRADOVATE,
        })
        trades.append(t)
    return trades, anomalies


# ---------------------------------------------------------------------------
# Les SL/TP : des SUGGESTIONS, jamais des ecritures.
# ---------------------------------------------------------------------------

def _sans_fuseau(iso):
    """ISO horodate -> datetime naif dans le fuseau de l'export.

    Les deux cotes parlent la meme horloge (`FUSEAU`, mesure contre le MARCHE
    et non contre Edgewonk, cf. l'en-tete de ce module) : retirer le fuseau
    d'un cote suffit a les comparer. Comparer un naif a un aware leverait une
    TypeError ; comparer deux naifs de fuseaux differents ne leverait rien du
    tout, et c'est pour ca que cette fonction existe plutot qu'un `.replace`
    en ligne.
    """
    import datetime as dt
    return dt.datetime.fromisoformat(iso).replace(tzinfo=None)


def suggestions_sltp(trades, chemin_orders):
    """{cle_position: {"sl", "tp"}} — a PRE-REMPLIR dans le fichier de saisie.

    ⚠️ POURQUOI DES SUGGESTIONS ET PAS UNE ECRITURE EN BASE.

    La tentation est evidente : l'export porte le SL et le TP, autant les poser
    dans la base et sauter la saisie. C'est un piege, et il vient de la regle de
    fusion (`core/base.fusionner`) : une valeur non vide en REMPLACE une autre.
    Le jour ou l'utilisateur corrige a la main un stop mal lu, le re-import du meme
    export ECRASERAIT sa correction — sans bruit, les deux valeurs etant
    plausibles.

    On passe donc par le fichier de saisie, ou la valeur est PROPOSEE, relue,
    controlee par `core/saisie.controler`, puis ecrite comme n'importe quelle
    saisie manuelle. La base ne connait qu'une seule autorite, et c'est lui.

    L'appariement se fait sur (contrat, sens, seconde d'entree) : l'ordre ATM
    d'entree est rempli a la seconde ou la position s'ouvre, par construction.
    """
    from tradovate import protections as mod_protections

    brutes, notes = mod_protections.protections(chemin_orders)
    index = {}
    for (contrat, sens_brut, heure), p in brutes.items():
        sens = SENS_ACHAT if (sens_brut or "").strip().lower().startswith("buy") else SENS_VENTE
        try:
            iso = _iso(_naif(heure))
        except ErreurExport:
            continue
        index[(contrat, sens, iso[:19])] = p

    positions = collections.OrderedDict()
    for t in trades:
        positions.setdefault(t["cle_position"], t)

    suggestions, apparies = {}, set()
    for cp, t in positions.items():
        cle = (t["symbole_broker"], t["sens"], t["ouverture"][:19])
        p = index.get(cle)
        if p is None:
            continue
        apparies.add(cle)
        valeurs = {}
        if p["sl"] is not None and not p.get("sl_douteux"):
            valeurs["sl"] = "%.10g" % p["sl"]
        if p["tp"] is not None:
            valeurs["tp"] = "%.10g" % p["tp"]
        if valeurs:
            suggestions[cp] = valeurs
        if p["signalement"]:
            notes.append("%s : %s" % (cp, p["signalement"]))

        # Controle d'integrite gratuit : le prix d'execution de l'ordre ATM doit
        # etre celui de l'entree de la position. S'ils divergent, ce n'est pas le
        # bon ordre qu'on vient d'apparier, et le SL propose appartient a un
        # autre trade.
        entree = _nombre(t.get("entree"))
        if p["entree"] is not None and entree is not None:
            if abs(p["entree"] - entree) > max(abs(entree) * 1e-6, 1e-9):
                notes.append(
                    "%s : l'ordre ATM apparie est rempli a %.10g alors que la "
                    "position entre a %.10g — appariement douteux, SL/TP a "
                    "verifier a la main" % (cp, p["entree"], entree))

    # ------------------------------------------------------------------ Chart
    # ⚠️ EN REPLI, JAMAIS EN CONCURRENCE. Le chemin ATM lit un groupe d'ids
    # consecutifs : c'est la lecture la plus contrainte des deux, et elle reste
    # prioritaire partout ou elle repond. La lecture par fenetre ne sert que
    # les positions qu'elle laisse vides — les entrees posees au graphique.
    # Mesure du 28/08/2026 : sur les 6 positions ATM deja en base, les deux
    # lectures rendent la meme chose, donc ce repli ne peut rien deplacer.
    par_contrat = collections.OrderedDict()
    for cp, t in positions.items():
        jambes = [j for j in trades if j["cle_position"] == cp]
        fin = max(j["cloture"] for j in jambes)
        par_contrat[cp] = {
            "cle_position": cp,
            "symbole_broker": t["symbole_broker"],
            "sens": t["sens"],
            "sens_broker": "Buy" if t["sens"] == SENS_ACHAT else "Sell",
            "entree": _nombre(t.get("entree")),
            "ouverture": _sans_fuseau(t["ouverture"]),
            "cloture": _sans_fuseau(fin),
        }
    a_completer = [v for cp, v in par_contrat.items() if cp not in suggestions]
    if a_completer:
        ordres = mod_protections.lire(chemin_orders)
        fenetres = mod_protections.protections_par_fenetre(ordres, a_completer)
        for cp, p2 in fenetres.items():
            valeurs = {}
            if p2["sl"] is not None and not p2["sl_douteux"]:
                valeurs["sl"] = "%.10g" % p2["sl"]
            if p2["tp"] is not None:
                valeurs["tp"] = "%.10g" % p2["tp"]
            if valeurs:
                suggestions[cp] = valeurs
            if p2["signalement"]:
                notes.append("%s : %s" % (cp, p2["signalement"]))
            # Le stop a-t-il bouge pendant le trade ? On ne touche pas au champ
            # `management` — il est a l'utilisateur — mais se taire serait pire : il
            # le remplit de memoire, et l'export, lui, se souvient.
            m = p2.get("management")
            if m:
                notes.append(
                    "%s : stop %s de %.10g a %.10g, %.0f minutes apres l'entree "
                    "— l'export dit que la position a ete GEREE ; si tu saisis "
                    "management = OK, l'un des deux se trompe"
                    % (cp, m["vers"], m["de"], m["a"], m["minutes"]))

    sans = len(positions) - len(suggestions)
    if sans > 0:
        notes.append(
            "%d position(s) sur %d sans SL/TP dans l'export — a saisir a la "
            "main, ou a laisser vide" % (sans, len(positions)))

    # ⚠️ Les brackets qui ne s'accrochent a AUCUNE ouverture de position. Deux
    # causes, et il faut les distinguer a l'oeil :
    #   - un ordre de PROTECTION que sa forme fait ressembler a une entree
    #     (cas mesure le 24/08 : un stop remplace, declenche sur 2 contrats
    #     sur 4). C'est le cas normal, et le silence est le bon comportement ;
    #   - un vrai renforcement de position, qui poserait un SECOND bracket sur
    #     une position deja ouverte. Celui-la, la suggestion ne le voit pas, et
    #     il faut le savoir avant de valider un SL.
    orphelines = [c for c in index if c not in apparies]
    if orphelines:
        notes.append(
            "%d bracket(s) de l'export ne s'accrochent a aucune ouverture de "
            "position — soit des ordres de protection que leur forme fait "
            "ressembler a une entree (le cas courant), soit un second bracket "
            "pose sur une position deja ouverte : %s"
            % (len(orphelines),
               ", ".join("%s %s %s" % o for o in sorted(orphelines)[:4])
               + (" …" if len(orphelines) > 4 else "")))
    return suggestions, notes
