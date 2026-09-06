"""Lecture de l'export CSV du relevé cTrader.

Faits mesurés sur un export réel du 25/08/2026 (46 lignes, compte 1234567) :

  * la colonne « Order ID » est l'ordre de CLOTURE, pas la position ;
  * une position sortie en plusieurs fois produit UNE LIGNE PAR SORTIE ;
  * le prix d'entrée est déjà le VWAP de la position, identique sur toutes ses
    sorties partielles ;
  * l'en-tête porte son propre fuseau : « Opening time (UTC+2) ». On le LIT,
    on ne le suppose pas : il passera à UTC+1 en hiver.

⚠️ RENVERSEMENT DU 25/08/2026 — on n'agrège plus.

Ce module agrégeait les lignes en positions (46 -> 38). C'était une erreur :
mesuré dans Edgewonk, une sortie partielle y est un TRADE À PART ENTIÈRE.
Les 4 sorties de la position du 07/08 13:43 sont 4 trades Edgewonk, nets
12.00 / 1.50 / 1.50 / 302.00, concordants à l'unité avec le relevé. Agréger
produisait 38 lignes face à 46 trades : 8 n'auraient jamais trouvé leur
correspondance.

La position n'est pas perdue pour autant : elle devient `cle_position`, et
c'est elle qui porte la saisie SL/TP. On garde le regroupement, on ne le
laisse plus écraser les lignes.

(L'ancienne conclusion venait de `docs/edgewonk-api.md` §8 bis, mesuré sur des
trades FUTURES Tradovate puis généralisé à cTrader sans revérification.)
"""

import csv
import datetime as dt
import io
import os
import re

from core.modele import (COLONNES, SENS_ACHAT, SENS_VENTE, construire_cle_jambe,
                         construire_cle_position, symbole_nu, trade_vide)

_ESPACES = u"\xa0   "


def _nombre(txt):
    """« 22 941.39 » -> 22941.39 ; « » -> None. Les séparateurs de milliers
    de cet export sont des espaces, parfois insécables."""
    if txt is None:
        return None
    t = txt.strip()
    for e in _ESPACES:
        t = t.replace(e, "")
    if not t:
        return None
    return float(t)


def _lots(txt):
    """« 3.17 Lots » -> 3.17"""
    if not txt:
        return None
    return _nombre(re.sub(r"[^0-9.,\s -]", "", txt).replace(",", "."))


def _decalage(entetes):
    """Extrait « +02:00 » de « Opening time (UTC+2) »."""
    for e in entetes:
        m = re.search(r"\(UTC([+-])(\d{1,2})(?::?(\d{2}))?\)", e or "")
        if m:
            signe, h, mi = m.group(1), int(m.group(2)), int(m.group(3) or 0)
            return "%s%02d:%02d" % (signe, h, mi)
    raise ValueError("aucun fuseau trouve dans l'en-tete du relevé")


def _colonne(entetes, prefixe):
    for e in entetes:
        if e and e.startswith(prefixe):
            return e
    raise ValueError("colonne absente du relevé : %s" % prefixe)


try:
    from zoneinfo import ZoneInfo
    _PARIS = ZoneInfo("Europe/Paris")
except Exception:                                            # noqa: BLE001
    _PARIS = None


def _offset_paris(date_iso):
    """« +02:00 » — le decalage d'Europe/Paris ce jour-la. None sans zoneinfo."""
    if _PARIS is None:
        return None
    naif = dt.datetime.fromisoformat(date_iso[:10] + "T12:00:00")
    delta = naif.replace(tzinfo=_PARIS).utcoffset()
    signe = "+" if delta >= dt.timedelta(0) else "-"
    mn = abs(int(delta.total_seconds())) // 60
    return "%s%02d:%02d" % (signe, mn // 60, mn % 60)


def _date_export(chemin):
    """cT_1234567_2026-08-26_00-42.csv -> « 2026-08-26 ». None si illisible."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", os.path.basename(chemin))
    return "-".join(m.groups()) if m else None


def regime_horaire(chemin, decalage_entete):
    """La plateforme suit-elle l'heure de Paris, ou un decalage fixe ?

    MESURE DU 26/08/2026, sur un export de dix mois. cTrader ecrit l'heure
    MURALE locale et l'en-tete annonce le decalage EN VIGUEUR LE JOUR DE
    L'EXPORT. Applique tel quel a toutes les lignes, il decale d'une heure
    toutes celles ecrites dans l'autre regime : 82 jambes sur 157, et
    l'appariement Edgewonk echouait sur 86 des 203 trades.

    Mais on ne corrige PAS a l'aveugle — remarque de l'utilisateur, et elle est
    juste : selon le reglage de sa plateforme, l'export peut deja etre dans le
    bon fuseau. Ajouter une heure d'office casserait ce cas-la.

    Le discriminant est gratuit et deterministe : **le decalage annonce
    correspond-il a celui de Paris LE JOUR DE L'EXPORT ?**

      - OUI  -> la plateforme est a l'heure de Paris. Les lignes d'un autre
                regime ont donc ete ecrites avec un autre decalage : on resout
                par DATE.
      - NON  -> la plateforme est sur un decalage FIXE (ou un autre fuseau).
                L'en-tete est litteral pour toutes les lignes : on ne touche a
                rien.

    Retourne (suit_paris, date_export, offset_paris_ce_jour_la).
    Dans le doute — pas de zoneinfo, pas de date lisible — on ne touche a rien.
    """
    date = _date_export(chemin)
    if date is None or _PARIS is None:
        return False, date, None
    attendu = _offset_paris(date)
    return (attendu == decalage_entete), date, attendu


def _decalage_de_la_ligne(txt, decalage_entete, suit_paris):
    """Le decalage a appliquer a CETTE ligne.

    `suit_paris` faux -> l'en-tete, litteralement, pour tout le monde.
    `suit_paris` vrai  -> celui de Paris a la date ecrite sur la ligne.
    """
    if not suit_paris:
        return decalage_entete
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", txt.strip())
    if not m:
        return decalage_entete
    j, mo, a = m.groups()
    return _offset_paris("%s-%s-%s" % (a, mo, j)) or decalage_entete


def _horodatage(txt, decalage):
    """« 07/08/2026 13:43:18.644 » -> « 2026-08-07T13:43:18.644+02:00 »"""
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?", txt.strip())
    if not m:
        raise ValueError("horodatage illisible : %r" % txt)
    j, mo, a, h, mi, s, ms = m.groups()
    return "%s-%s-%sT%s:%s:%s.%s%s" % (a, mo, j, h, mi, s, (ms or "0").ljust(3, "0")[:3], decalage)


def _compte(chemin):
    """cT_1234567_20260825_1316.csv -> 1234567"""
    m = re.search(r"cT[_-](\d+)", os.path.basename(chemin))
    return m.group(1) if m else ""


def lire(chemin):
    """Retourne (trades, anomalies). Un trade = UNE JAMBE = une ligne du relevé.

    Ne calcule aucune statistique : uniquement des faits présents dans l'export.
    Le seul travail dérivé est le regroupement en positions, qui alimente
    `cle_position` et `nb_jambes` — il ne fusionne plus aucune ligne.
    """
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f)
        entetes = lecteur.fieldnames or []
        decalage = _decalage(entetes)
        suit_paris, date_export, offset_attendu = regime_horaire(chemin, decalage)
        c_ouv = _colonne(entetes, "Opening time")
        c_clo = _colonne(entetes, "Closing time")
        lignes = [r for r in lecteur if (r.get("Order ID") or "").strip()]

    compte = _compte(chemin)
    source = os.path.basename(chemin)
    anomalies = []
    recales = 0
    groupes = {}
    ordre = []

    # --- passe 1 : regrouper en positions, sans rien fusionner
    for r in lignes:
        sens_brut = (r["Opening direction"] or "").strip().lower()
        if sens_brut.startswith("buy"):
            sens = SENS_ACHAT
        elif sens_brut.startswith("sell"):
            sens = SENS_VENTE
        else:
            anomalies.append("sens inconnu (%s) sur %s" % (r["Opening direction"], r["Order ID"]))
            continue

        dec_ouv = _decalage_de_la_ligne(r[c_ouv], decalage, suit_paris)
        dec_clo = _decalage_de_la_ligne(r[c_clo], decalage, suit_paris)
        if dec_ouv != decalage or dec_clo != decalage:
            recales += 1
        ouverture = _horodatage(r[c_ouv], dec_ouv)
        cle_groupe = (r["Symbol"], sens, ouverture, (r["Entry price"] or "").strip())
        if cle_groupe not in groupes:
            groupes[cle_groupe] = []
            ordre.append(cle_groupe)
        groupes[cle_groupe].append((r, sens, ouverture, _horodatage(r[c_clo], dec_clo)))

    # --- passe 2 : une ligne de base par JAMBE
    trades = []
    positions_vues = {}
    for cle_groupe in ordre:
        symbole_broker, sens, ouverture, entree_txt = cle_groupe
        parts = sorted(groupes[cle_groupe], key=lambda p: p[3])      # par heure de sortie

        cle_pos = construire_cle_position(ouverture, symbole_broker, sens)
        n = positions_vues.get(cle_pos, 0) + 1
        positions_vues[cle_pos] = n
        if n > 1:            # même seconde, même symbole, même sens, entrée différente
            cle_pos = "%s-%d" % (cle_pos, n)
            anomalies.append("deux positions distinctes a la meme seconde : %s" % cle_pos)

        jambes_vues = {}
        for r, sens_r, ouv_r, cloture in parts:
            cle = construire_cle_jambe(cle_pos, cloture)
            m = jambes_vues.get(cle, 0) + 1
            jambes_vues[cle] = m
            if m > 1:        # deux sorties dans la MEME seconde : jamais vu, mais prévu
                cle = "%s-%d" % (cle, m)
                anomalies.append("deux sorties dans la meme seconde : %s" % cle)

            quantite = _lots(r["Closing Quantity"])
            prix_sortie = _nombre(r["Closing price"])
            if quantite is None or prix_sortie is None:
                anomalies.append("quantite ou prix de sortie illisible sur %s" % r["Order ID"])
                continue

            t = trade_vide()
            t.update({
                "cle": cle,
                "cle_position": cle_pos,
                "compte": compte,
                "symbole": symbole_nu(symbole_broker),
                "symbole_broker": symbole_broker,
                "sens": sens_r,
                "ouverture": ouv_r,
                "cloture": cloture,
                "entree": entree_txt,
                "sortie": (r["Closing price"] or "").strip(),
                "volume_lots": "%.2f" % quantite,
                "nb_jambes": str(len(parts)),
                "swaps": "%.2f" % (_nombre(r["Swaps"]) or 0),
                "commission": "%.2f" % (_nombre(r["Broker commission"]) or 0),
                "brut": "%.2f" % (_nombre(r["Gross $"]) or 0),
                "net": "%.2f" % (_nombre(r["Net $"]) or 0),
                "source_brut": source,
            })
            trades.append(t)

    # Jamais silencieux : si des lignes ont ete recalees, ou si on s'est
    # abstenu alors que l'en-tete ne colle pas a Paris, ca doit se voir.
    if recales:
        anomalies.append(
            "fuseau : %d ligne(s) ecrites dans un autre regime horaire que "
            "l'export du %s (en-tete %s) — decalage resolu par date"
            % (recales, date_export, decalage))
    elif date_export and offset_attendu and not suit_paris:
        anomalies.append(
            "fuseau : l'en-tete annonce %s alors que Paris etait a %s le %s — "
            "la plateforme n'est pas a l'heure de Paris, les horodatages sont "
            "pris tels quels. Verifier avec outils/diag_fuseau.py"
            % (decalage, offset_attendu, date_export))
    return trades, anomalies
