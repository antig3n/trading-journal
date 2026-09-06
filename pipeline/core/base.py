"""La base locale. Un fichier CSV, une ligne par JAMBE, la clé fait foi.

Principe directeur du projet : la base locale est la référence, Edgewonk n'en
est qu'un consommateur. Ce module ne connaît donc ni cTrader ni Edgewonk.

Règle de fusion : on ne remplace JAMAIS une valeur non vide par une valeur
vide. Un ré-import du même relevé est donc sans effet destructeur, et la saisie
manuelle survit à tous les ré-imports.

Depuis le 25/08/2026 la base est au grain de la JAMBE (voir core/modele.py).
`grouper_en_positions` fournit la vue « position », qui est celle où se fait la
saisie du SL/TP : une position n'a qu'une protection.
"""

import csv
import io
import os
import shutil
import time

from core.modele import COLONNES, trade_vide


def _lire_brut(chemin):
    if not os.path.exists(chemin):
        return []
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def charger(chemin):
    """Retourne un dictionnaire {cle: trade}, en préservant l'ordre du fichier."""
    trades = {}
    for r in _lire_brut(chemin):
        cle = (r.get("cle") or "").strip()
        if not cle:
            continue
        t = trade_vide()
        for c in COLONNES:
            t[c] = (r.get(c) or "").strip()
        # colonnes inconnues : conservées telles quelles, jamais perdues
        for k, v in r.items():
            if k and k not in t:
                t[k] = v
        trades[cle] = t
    return trades


def _sauvegarder_copie(chemin):
    if not os.path.exists(chemin):
        return None
    dossier = os.path.join(os.path.dirname(chemin), "instantanes")
    if not os.path.isdir(dossier):
        os.makedirs(dossier)
    cible = os.path.join(dossier, "trades-%s.csv" % time.strftime("%Y%m%d-%H%M%S"))
    shutil.copy2(chemin, cible)
    return cible


class BaseRetrecie(Exception):
    """Une écriture allait retirer des jambes. Presque toujours un bug."""


def ecrire(chemin, trades, suppression_attendue=False):
    """Écrit la base. Un instantané de l'état précédent est pris d'abord —
    règle non négociable du projet : instantané avant toute écriture.

    ⚠️ UNE ÉCRITURE QUI PERD DES LIGNES EST REFUSÉE PAR DÉFAUT.
    *(Ajouté le 26/08/2026, après que le cas se soit produit.)*

    `jt.py pousser --tradovate` avait reçu une vue FILTRÉE de la base — les
    35 jambes futures — dans la variable qu'il réécrit à la fin pour y poser la
    colonne `screenshots`. Les 46 jambes cTrader ont donc été effacées du
    fichier. L'instantané pris juste avant a permis de tout restaurer sans rien
    perdre, et c'est la première fois que la règle 3 du §8 servait pour de bon.

    Mais un filet qui rattrape n'est pas un garde-fou qui empêche. Retirer une
    jambe est une opération rare et TOUJOURS délibérée — on ne supprime pas un
    trade par accident. Le dire explicitement coûte un argument ; ne pas le dire
    coûte une base.

    `suppression_attendue=True` autorise l'écriture, et n'est à passer que
    lorsqu'on retire sciemment des lignes.
    """
    if not suppression_attendue:
        existantes = {(r.get("cle") or "").strip() for r in _lire_brut(chemin)}
        existantes.discard("")
        perdues = existantes - set(trades)
        if perdues:
            exemples = ", ".join(sorted(perdues)[:5])
            raise BaseRetrecie(
                "REFUS : cette écriture retirerait %d jambe(s) de la base "
                "(%d -> %d).\n"
                "  Exemples : %s%s\n"
                "  Écrit-on une VUE FILTRÉE au lieu de la base entière ?\n"
                "  Si la suppression est voulue : ecrire(..., "
                "suppression_attendue=True)."
                % (len(perdues), len(existantes), len(trades), exemples,
                   " …" if len(perdues) > 5 else ""))
    copie = _sauvegarder_copie(chemin)
    colonnes = list(COLONNES)
    for t in trades.values():
        for k in t:
            if k not in colonnes:
                colonnes.append(k)
    dossier = os.path.dirname(chemin)
    if dossier and not os.path.isdir(dossier):
        os.makedirs(dossier)
    provisoire = chemin + ".tmp"
    with io.open(provisoire, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colonnes, extrasaction="ignore")
        w.writeheader()
        for cle in sorted(trades, key=lambda c: (trades[c].get("ouverture", ""),
                                                 trades[c].get("cloture", ""), c)):
            w.writerow(trades[cle])
    os.replace(provisoire, chemin)      # remplacement atomique
    return copie


def fusionner(existants, nouveaux):
    """Insère ou complète. Ne remplace jamais du non-vide par du vide.

    Retourne (base, ajoutes, completes, inchanges).
    """
    ajoutes, completes, inchanges = [], [], []
    for t in nouveaux:
        cle = t["cle"]
        if cle not in existants:
            existants[cle] = dict(t)
            ajoutes.append(cle)
            continue
        courant = existants[cle]
        modifie = False
        for c, v in t.items():
            v = (v or "").strip()
            if c == "source_brut" and (courant.get(c) or "").strip():
                continue          # on garde le PREMIER relevé qui a fait naître le trade
            if v and (courant.get(c) or "").strip() != v:
                courant[c] = v
                modifie = True
        (completes if modifie else inchanges).append(cle)
    return existants, ajoutes, completes, inchanges


def grouper_en_positions(trades, cles=None):
    """Vue « position » de la base : {cle_position: {...}}.

    C'est le niveau où se fait la saisie du SL/TP — une position cTrader n'a
    qu'une protection, quel que soit le nombre de sorties partielles.

    `cles` restreint le regroupement à un sous-ensemble de jambes (typiquement
    celles du relevé qu'on vient d'importer).
    """
    positions = {}
    for cle, t in trades.items():
        if cles is not None and cle not in cles:
            continue
        cp = t.get("cle_position") or cle
        p = positions.get(cp)
        if p is None:
            p = positions[cp] = {
                "cle_position": cp,
                "ouverture": t.get("ouverture", ""),
                "symbole_broker": t.get("symbole_broker", ""),
                "sens": t.get("sens", ""),
                "entree": t.get("entree", ""),
                "lots": 0.0,
                "net": 0.0,
                # VWAP de sortie de la position, pondere par les lots. Sert au
                # controle du R realise a la saisie (`saisie.controler`) : sans
                # lui, on ne peut juger un SL que par le R:R, donc uniquement
                # quand un TP est renseigne. Mesure du 26/08/2026 : c'est
                # exactement le trou par lequel un stop a 0.45 point est passe.
                "sortie": "",
                "_sortie_ponderee": 0.0,
                "jambes": [],
                "sl": "",
                "tp": "",
                "management": "",
            }
        p["jambes"].append(cle)
        try:
            lots = float(t.get("volume_lots") or 0)
            p["lots"] += lots
            p["net"] += float(t.get("net") or 0)
            p["_sortie_ponderee"] += float(t.get("sortie") or 0) * lots
        except ValueError:
            pass
        # SL, TP et management sont portés par la POSITION — une position n'a
        # qu'une protection, et on ne la gère qu'une fois. La première valeur
        # non vide fait foi.
        for champ in ("sl", "tp", "management"):
            if not p[champ] and (t.get(champ) or "").strip():
                p[champ] = t[champ].strip()

    for p in positions.values():
        if p["lots"]:
            p["sortie"] = "%.10g" % (p.pop("_sortie_ponderee") / p["lots"])
        else:
            p.pop("_sortie_ponderee", None)
    return positions


# ─────────────────────────────────────────────────────────────────── PÉRIODE
#
# Travailler sur UNE journée plutôt que sur toute la base : demandé par
# L'utilisateur le 29/08/2026, et c'est le bon réflexe. Un diagnostic global sur
# 241 jambes noie le cas qu'on cherche ; un import global re-touche des trades
# qu'on ne voulait pas toucher. La borne réduit le bruit ET la surface d'erreur.

_MOTIFS_DATE = (
    # JJMMAAAA sous toutes ses ponctuations : 06082026, 06/08/2026, 06-08-2026
    (r"(\d{2})[/.\-]?(\d{2})[/.\-]?(\d{4})", ("j", "m", "a")),
    # AAAAMMJJ : 20260806, 2026-08-06
    (r"(\d{4})[/.\-]?(\d{2})[/.\-]?(\d{2})", ("a", "m", "j")),
)


def lire_periode(texte):
    """« 06082026 » ou « 06082026-12082026 » -> (début, fin) en AAAA-MM-JJ.

    Retourne (None, None) si le texte est vide, et lève ValueError s'il n'est
    pas lisible — on ne devine pas une date, sous peine de filtrer sur autre
    chose que ce qui a été demandé.

    ⚠️ ON NE COUPE PAS SUR LE TIRET, ON EXTRAIT LES DATES.
    « 2026-08-06 » contient deux tirets et n'est pourtant qu'une seule date :
    découper dessus donnerait trois morceaux illisibles. On cherche donc les
    MOTIFS de date dans le texte, et leur nombre dit ce qu'on a — une date, ou
    deux. C'est aussi ce qui rend le séparateur libre : tiret, espace, « au ».
    """
    import re
    texte = (texte or "").strip()
    if not texte:
        return None, None

    trouvees = []
    reste = texte
    for motif, ordre in _MOTIFS_DATE:
        for m in re.finditer(motif, reste):
            champs = dict(zip(ordre, m.groups()))
            a, mo, j = int(champs["a"]), int(champs["m"]), int(champs["j"])
            # Un contrôle de vraisemblance, pas un calendrier complet : il
            # attrape l'inversion jour/mois, qui est l'erreur de frappe réelle.
            if not (1 <= mo <= 12 and 1 <= j <= 31 and 2000 <= a <= 2100):
                continue
            trouvees.append("%04d-%02d-%02d" % (a, mo, j))
        if trouvees:
            break

    if not trouvees:
        raise ValueError(
            "période illisible : %r\n"
            "  attendu : JJMMAAAA pour un jour (06082026)\n"
            "            JJMMAAAA-JJMMAAAA pour une période (06082026-12082026)\n"
            "            les ponctuations sont libres (06/08/2026)" % texte)
    if len(trouvees) == 1:
        return trouvees[0], trouvees[0]
    debut, fin = sorted(trouvees[:2])       # l'ordre de saisie n'a pas à compter
    return debut, fin


def filtrer_periode(trades, debut, fin):
    """Les jambes dont l'OUVERTURE tombe dans [début, fin], bornes incluses.

    ⚠️ SUR L'OUVERTURE, ET PAS SUR LA CLÔTURE. Un trade ouvert le 6 et fermé le
    9 appartient au 6 : c'est la journée où la décision a été prise, et c'est
    celle que l'utilisateur a en tête quand il dit « la journée du 6 ». Filtrer sur
    la clôture ferait disparaître ce trade de sa propre journée.
    """
    if not debut and not fin:
        return trades
    return {c: t for c, t in trades.items()
            if debut <= (t.get("ouverture") or "")[:10] <= fin}


def libelle_periode(debut, fin):
    """« le 06/08/2026 » · « du 06/08/2026 au 12/08/2026 » · « (toute la base) »."""
    def fr(d):
        return "%s/%s/%s" % (d[8:10], d[5:7], d[0:4])
    if not debut:
        return "toute la base"
    if debut == fin:
        return "le %s" % fr(debut)
    return "du %s au %s" % (fr(debut), fr(fin))


def options_ligne(argv):
    """(periode, journal) lus dans une ligne de commande, sans les retirer.

    Un seul lecteur pour les huit outils plutôt qu'un par outil : c'est la même
    règle que `CHAMPS_ECRITS` pour les champs — une source, donc pas de dérive
    entre ce que le menu propose et ce que l'outil accepte.

        --periode 06082026            un jour
        --periode 06082026-12082026   une période
        --journal 100001              un autre journal Edgewonk

    `periode` vaut (None, None) si le drapeau est absent.
    """
    debut = fin = None
    journal = None
    if "--periode" in argv:
        i = argv.index("--periode")
        if i + 1 >= len(argv):
            raise ValueError("--periode attend une date : JJMMAAAA ou JJMMAAAA-JJMMAAAA")
        debut, fin = lire_periode(argv[i + 1])
    if "--journal" in argv:
        i = argv.index("--journal")
        if i + 1 >= len(argv) or not argv[i + 1].isdigit():
            raise ValueError("--journal attend un identifiant numerique (ex. 100001)")
        journal = argv[i + 1]
    return (debut, fin), journal
