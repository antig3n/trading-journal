# -*- coding: utf-8 -*-
"""Étape 4 : produire les QUATRE graphiques de chaque position.

CE FICHIER DÉCIDE DE CE QU'ON MONTRE. L'apparence vit dans `gabarit.py`, et
nulle part ailleurs.

────────────────────────────────────────────────────────────────────────────
RÉVISION DU 25/08/2026 (soir) — tranché par l'utilisateur sur rendus comparés.

1. **Quatre images par position : M5, M15, H1, H4.** Plus de timeframe choisi
   par la durée, plus de couple LTF/HTF. Les quatre sont produites à chaque
   fois, parce que les quatre servent : M5 le trade, M15 la session, H1 le
   swing, H4 la tendance. Edgewonk a six emplacements — les quatre premiers
   sont pris, deux restent libres pour ses propres captures.

   ⚠️ **Le M1 est hors de l'échelle.** l'utilisateur ne lit jamais en dessous du M5.
   Le M1 ne sert qu'au calcul des extrêmes (`ctrader/bougies.py`), où il n'est
   jamais affiché.

2. **La marge de contexte est en BOUGIES, pas en pourcentage.** Un pourcentage
   donne trois heures de marge sur un trade de trois heures et six minutes sur
   un trade de six minutes : la quantité de contexte à l'écran change tout le
   temps. Un nombre de bougies donne toujours la même chose à lire.
   60 avant / 30 après — asymétrique, parce que la structure qui justifie
   l'entrée est DERRIÈRE ; ce qui suit la sortie n'a qu'à confirmer.
   Remplace `LTF_PART_DU_TRADE` et `LTF_MIN_BOUGIES`, supprimées.

3. **Le graphique montre la jambe RÉELLEMENT TENUE** — voir `jambe_reelle`.

4. **Seule cette jambe reçoit les images.** *(Tranché le 25/08 au soir.)* Les jambes
   d'allègement sont des trades Edgewonk à part entière, mais elles ne représentent
   aucune décision : leur coller les captures de la vraie position encombrerait le
   journal sans rien apprendre. Elles restent sans graphique, et c'est exact.
   → `chemin_graphiques` n'est renseigné que sur la jambe réellement tenue. La
     sélection du travail à faire passe donc par `position_a_rendre`, qui interroge
     CETTE jambe : filtrer sur « les jambes sans graphique » relancerait indéfiniment
     le rendu des positions multiples, dont les allègements n'en auront jamais.
────────────────────────────────────────────────────────────────────────────

DEUX POINTS QUI SE RATENT FACILEMENT

* **Le fuseau.** Le MCP renvoie des horodatages en UTC. Les afficher tels quels
  montrerait 11:44 là où l'utilisateur a tradé à 13:44. On reconvertit vers l'offset
  porté par le relevé — jamais vers un fuseau supposé.

* **Une position, une série de bougies PAR TIMEFRAME.** Toutes les jambes
  partagent leur entrée et reçoivent les mêmes images : on tire quatre séries
  par position, pas quatre par jambe.
"""

import datetime as dt
import os

from ctrader import bougies as mod_bougies
# ⚠️ NI `pandas` NI `gabarit` NE SONT IMPORTES ICI, ET C'EST DELIBERE.
# Les deux vivent dans .venv/ (Homebrew refuse les installations systeme,
# PEP 668). Ce module porte
# aussi les regles de DECISION — `jambes_de_position`, `jambe_reelle` — dont un
# diagnostic en lecture seule a besoin sans rien dessiner. L'import global les
# rendait inaccessibles hors du venv, et la seule issue etait de recopier la
# regle ailleurs : deux sources de verite pour « quelle jambe est la vraie »,
# c'est-a-dire la garantie qu'elles divergent un jour.
# L'import descend donc dans la seule fonction qui dessine. Mesure du
# 28/08/2026, en ecrivant `outils/diag_images.py`.

# (code MCP, minutes par bougie, nom affiché, format de date de l'axe)
TIMEFRAMES = [
    ("m5",  5,   "M5",  "%H:%M"),
    ("m15", 15,  "M15", "%d/%m %H:%M"),
    ("h1",  60,  "H1",  "%d/%m %H:%M"),
    ("h4",  240, "H4",  "%d/%m"),
]

BOUGIES_AVANT = 60      # contexte avant l'entrée
BOUGIES_APRES = 30      # contexte après la sortie

# Le projet se localise depuis `__file__`, comme partout ailleurs : aucun
# chemin absolu n'est écrit nulle part.
_DONNEES = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                         "..", "..", "donnees"))


def images_presentes(dossier):
    """Combien des quatre PNG attendus existent RÉELLEMENT dans ce dossier.

    ⚠️ On compte les fichiers, jamais les positions × 4. Mesuré le 26/08/2026 :
    le premier cycle Tradovate a annoncé « 7 positions, 28 images » alors que
    23 seulement étaient sur le disque — cinq timeframes avaient échoué et le
    total était un PRODUIT, pas un décompte. C'est la définition d'un
    vérificateur qui ment, et le projet en a déjà corrigé quatre.
    """
    if not dossier or not os.path.isdir(dossier):
        return 0
    return sum(1 for _, _, nom, _ in TIMEFRAMES
               if os.path.exists(os.path.join(dossier, "%s.png" % nom)))


def _decalage(iso):
    """L'offset porté par la donnée, jamais un fuseau supposé."""
    return dt.datetime.fromisoformat(iso).utcoffset() or dt.timedelta(0)


def _local(ts_utc, decalage):
    """« 2026-08-07T11:44:00Z » -> datetime naïf en heure locale du relevé."""
    m = dt.datetime.fromisoformat(ts_utc.replace("Z", "+00:00"))
    return (m + decalage).replace(tzinfo=None)


def _naif(iso):
    """« 2026-08-07T13:43:18.644+02:00 » -> datetime naïf, heure locale."""
    return dt.datetime.fromisoformat(iso).replace(tzinfo=None)


def _f(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _dataframe(liste, decalage):
    import pandas as pd                        # cf. l'en-tete : import local
    if not liste:
        return None
    index, o, h, b, c = [], [], [], [], []
    for x in liste:
        index.append(_local(x["timestamp"], decalage))
        o.append(float(x["open"]))
        h.append(float(x["high"]))
        b.append(float(x["low"]))
        c.append(float(x["close"]))
    return pd.DataFrame({"Open": o, "High": h, "Low": b, "Close": c},
                        index=pd.DatetimeIndex(index))


def jambes_de_position(trades, cle_position):
    """Toutes les jambes de la position, triées par heure de sortie.

    ⚠️ On relit `trades` au lieu d'utiliser `position["jambes"]` : l'appelant
    passe souvent une vue RESTREINTE (les jambes qui n'ont pas encore leurs
    graphiques), et la dernière jambe de ce sous-ensemble n'est pas forcément
    la dernière jambe de la position. Se tromper là revient à dessiner un
    allègement à la place du trade.
    """
    return sorted((t for t in trades.values()
                   if t.get("cle_position") == cle_position),
                  key=lambda t: t.get("cloture", ""))


def jambe_reelle(jambes):
    """LA position telle que l'utilisateur l'a tenue : la DERNIÈRE sortie.

    Fait établi par lui le 25/08/2026 : il ne prend pas de partiels. Une
    position sortie en plusieurs fois, c'est un ALLÈGEMENT après ajustement du
    SL, puis le reste qu'il tient. Toutes les jambes partageant la même entrée,
    la dernière sortie est par construction celle qui a été tenue le plus
    longtemps.

    Mesuré sur ses 4 positions à sorties multiples : le critère est juste 4 fois
    sur 4. Le critère concurrent — « la plus grosse jambe » — se trompe 2 fois
    sur 4, et se trompe précisément sur le trade qui compte : sur la position du
    07/08 13:43 il aurait retenu les 3 lots soldés en 76 secondes à +12,00 au
    lieu des 2 lots tenus 47 minutes jusqu'au TP, à +302,00.
    """
    return jambes[-1]


SIGNATURE = "rendu.txt"


def signature_rendu(jambes, reelle):
    """Ce qui, dans les DONNÉES, change le dessin. Une ligne, comparable.

    ⚠️ POURQUOI CE FICHIER EXISTE *(29/08/2026, et ça a coûté cinq graphiques
    faux)*. Le rendu était idempotent sur l'EXISTENCE des PNG : quatre fichiers
    sur le disque, la position était réputée faite. Or le dessin dépend aussi
    du SL et du TP — les deux bandes en pointillés et les deux rectangles du
    Position Tool. Une position rendue AVANT que ses niveaux soient saisis
    gardait donc, pour toujours, un graphique sans niveaux : ni bandes, ni
    rectangles, juste les deux points et la diagonale. Rien ne le signalait,
    et aucun cycle ne le résorbait — même forme que le verrou des captures.

    Mesuré : les 5 positions du 28/08, rendues à 01:47 alors que la saisie des
    niveaux est arrivée à 02:40. Les 206 autres sont saines, vérifiées une à
    une contre l'horodatage de la saisie qui a porté leurs niveaux.

    La signature ne porte QUE des données. Un changement de gabarit ne s'y voit
    pas et continue de se demander à la main (`graphiques --refaire`) : c'est
    une décision, pas un fait.
    """
    return "|".join(str(x) for x in (
        jambes[0].get("ouverture"), reelle.get("cloture"),
        jambes[0].get("entree"), reelle.get("sortie"), reelle.get("sens"),
        reelle.get("sl") or "", reelle.get("tp") or "",
        ",".join(nom for _, _, nom, _ in TIMEFRAMES)))


def signature_lue(dossier):
    """La signature inscrite lors du dernier rendu complet, ou None."""
    try:
        with open(os.path.join(dossier, SIGNATURE), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def position_a_rendre(trades, cle_position, refaire=False):
    """La position attend-elle ses graphiques ?

    La question se pose sur la JAMBE RÉELLEMENT TENUE, seule porteuse de
    `chemin_graphiques`. Poser la question sur « une jambe sans graphique »
    répondrait toujours oui pour une position sortie en plusieurs fois.
    """
    jambes = jambes_de_position(trades, cle_position)
    if not jambes:
        return False
    reelle = jambe_reelle(jambes)
    if not (reelle.get("prix_plus_haut") or "").strip():
        return False                      # étape 3 pas encore passée sur cette jambe
    if bool(refaire):
        return True
    chemin = (reelle.get("chemin_graphiques") or "").strip()
    if not chemin:
        return True

    # ⚠️ ON INTERROGE LE DISQUE, PAS LA COLONNE. Ajouté le 26/08/2026, sur un
    # cas réel : trois positions Tradovate ont été enregistrées comme rendues
    # avec 2 ou 3 images sur 4 — le H4 tombait sur la journée en cours, que
    # Databento refusait. La colonne remplie les figeait : sans `--refaire`
    # elles n'auraient JAMAIS été recomplétées, et `--refaire` aurait tout
    # regénéré, y compris les quatre positions saines.
    #
    # C'est exactement le bug attrapé le 25/08 sur l'envoi des captures — une
    # image échoue, les trois autres sont confirmées, le trade est inscrit
    # « fait ». Même forme, autre étape. Le PNG est un artefact LOCAL : le
    # disque en est la référence, et le consulter coûte un `os.path.exists`.
    dossier = os.path.join(_DONNEES, chemin)
    if images_presentes(dossier) < len(TIMEFRAMES):
        return True

    # ⚠️ ET LE DISQUE NE SUFFIT PAS NON PLUS : quatre PNG peuvent être là et
    # PÉRIMÉS. Voir `signature_rendu`. Une signature absente vaut « inconnu »,
    # donc on rend — c'est le défaut sûr, et il se paie une fois.
    return signature_lue(dossier) != signature_rendu(jambes, reelle)


def fenetre(entree, sortie, minutes, avant=BOUGIES_AVANT, apres=BOUGIES_APRES):
    return (entree - dt.timedelta(minutes=avant * minutes),
            sortie + dt.timedelta(minutes=apres * minutes))


def graphiques_de_position(client, position, trades, dossier_racine):
    """Rend les quatre PNG d'une position.

    Retourne ({cle_jambe: chemin_dossier}, notes) — UNE SEULE entrée, celle de
    la jambe réellement tenue. Les jambes d'allègement ne reçoivent pas d'image
    (voir le point 4 de l'en-tête).
    """
    cle_pos = position["cle_position"]
    jambes = jambes_de_position(trades, cle_pos)
    if not jambes:
        return {}, []

    reelle = jambe_reelle(jambes)
    entree_dt = _naif(jambes[0]["ouverture"])
    sortie_dt = _naif(reelle["cloture"])
    decalage = _decalage(jambes[0]["ouverture"])
    decalage_iso = jambes[0]["ouverture"][-6:]
    symbole = jambes[0]["symbole_broker"]

    trade = {
        "entry_price": _f(jambes[0]["entree"]),
        "exit_price": _f(reelle["sortie"]),
        "entry_time": entree_dt,
        "exit_time": sortie_dt,
        "direction": "BUY" if reelle["sens"] == "Achat" else "SELL",
        "sl": _f(reelle.get("sl")),
        "tp": _f(reelle.get("tp")),
    }
    if trade["entry_price"] is None or trade["exit_price"] is None:
        return {}, ["%s : prix d'entree ou de sortie illisible" % cle_pos]

    def iso(moment):
        return moment.strftime("%Y-%m-%dT%H:%M:%S") + decalage_iso

    dossier = os.path.join(dossier_racine, cle_pos)
    if not os.path.isdir(dossier):
        os.makedirs(dossier)

    sens = "Long" if trade["direction"] == "BUY" else "Short"
    notes, rendus = [], 0

    for code, minutes, nom, format_date in TIMEFRAMES:
        debut, fin = fenetre(entree_dt, sortie_dt, minutes)
        try:
            brutes = mod_bougies.recuperer(client, symbole, iso(debut), iso(fin), code)
        except Exception as e:                                # noqa: BLE001
            notes.append("%s %s : bougies indisponibles (%s)" % (cle_pos, nom, e))
            continue
        df = _dataframe(brutes, decalage)
        if df is None or len(df) < 3:
            notes.append("%s %s : pas assez de bougies retournees" % (cle_pos, nom))
            continue
        # Le titre ne montrait que l'HEURE de sortie. Sur une position qui
        # franchit minuit, « 27/10/2025 13:45 -> 14:30 » se lit comme 45 minutes
        # alors qu'il s'agit de 4 jours. Mesure du 26/08/2026 : 24 positions sur
        # 131 sont a cheval sur plusieurs jours, et la production en a aussi.
        # On ne date la sortie QUE si elle tombe un autre jour : le cas courant
        # reste court et lisible.
        if sortie_dt.date() != entree_dt.date():
            fin_txt = sortie_dt.strftime("%d/%m/%Y %H:%M")
            # Et l'axe doit porter la date, sinon les heures se repetent sans
            # qu'on sache de quel jour elles viennent.
            if "%d" not in format_date:
                format_date = "%d/%m %H:%M"
        else:
            fin_txt = sortie_dt.strftime("%H:%M")
        titre = "%s · %s · %s · %s → %s" % (
            jambes[0]["symbole"], sens, nom,
            entree_dt.strftime("%d/%m/%Y %H:%M"), fin_txt)
        from graphiques import gabarit          # cf. l'en-tete : import local
        gabarit.rendre(df, trade, titre, os.path.join(dossier, "%s.png" % nom),
                       format_date)
        rendus += 1

    if not rendus:
        return {}, notes
    if rendus < len(TIMEFRAMES):
        notes.append("%s : %d/%d timeframes rendus seulement"
                     % (cle_pos, rendus, len(TIMEFRAMES)))
    else:
        # La signature n'est posée QUE sur un rendu complet — un rendu partiel
        # doit repasser, exactement comme il repassait déjà par le compte de PNG.
        try:
            with open(os.path.join(dossier, SIGNATURE), "w", encoding="utf-8") as f:
                f.write(signature_rendu(jambes, reelle) + "\n")
        except OSError as e:                                  # noqa: BLE001
            notes.append("%s : signature de rendu non ecrite (%s)" % (cle_pos, e))

    return {reelle["cle"]: dossier}, notes
