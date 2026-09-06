"""Apparier une JAMBE de notre base avec SON trade Edgewonk.

Il n'existe aucun identifiant commun. La clé est dérivée, et chaque élément
vient d'une mesure, pas d'une hypothèse.

CE QUI A ÉTÉ MESURÉ LE 25/08/2026, sur 302 trades réels de la base 100001

* **Edgewonk stocke en UTC, pas en heure de Paris.** Mesuré à l'envers pour ne
  pas deviner : on a d'abord apparié sur le montant net — un pivot qu'aucun
  fuseau ne décale — puis LU l'écart sur les couples obtenus. Résultat net :
  2 h 00 pile en août, c'est-à-dire UTC.
  ⚠️ `docs/edgewonk-api.md` §9 affirme le contraire (« tout normaliser en heure de
  Paris »). C'est faux pour l'importateur cTrader. `docs/tradovate.md` §5 bis avait
  déjà relevé les mêmes 2 h en notant que le traitement du fuseau « semble
  différer d'un importateur à l'autre » — il différait bien.
  On convertit donc via l'offset porté par le relevé, jamais en soustrayant
  2 h en dur : l'heure d'hiver passerait à UTC+1 et un décalage figé casserait
  en silence.

* **Edgewonk TRONQUE les horodatages à la minute** sur ces trades :
  13:43:18 -> 11:43:00, 13:44:34 -> 11:44:00, 14:30:01 -> 12:30:00.
  La clé compare donc des minutes, pas des secondes.

* **Conséquence : deux jambes sorties dans la même minute deviennent
  indiscernables par l'heure seule.** Le cas existe déjà : #134434 (13:44:34)
  et #134443 (13:44:43) tombent toutes deux sur 11:44. Le montant net et la
  quantité les séparent (12.00 / 3 lots contre 1.50 / 0.5 lot). La clé porte
  donc les quatre : instrument, sens, minute d'entrée, minute de sortie —
  puis montant et quantité départagent.

* **Le VWAP d'entrée concorde** entre les deux systèmes (mesuré) : il sert de
  contrôle d'intégrité, pas de clé.

CE QUI A ÉTÉ MESURÉ LE 26/08/2026, sur les 34 trades futures de la base 100004

* **Edgewonk ne stocke pas le même nom d'instrument selon l'importateur.** Côté
  cTrader c'est le symbole du broker, suffixe compris. Côté Tradovate c'est le
  **PRODUIT** — `MGC`, `MNQ`, `6E`, `NQ`, `GC`, `MCL` — et jamais le contrat
  `MNQU6`. Chercher `MNQU6` n'aurait rien trouvé, sur 100 % des jambes.
  → La colonne à comparer est déclarée par plateforme
    (`core/plateformes.colonne_instrument`), et mesurée des deux côtés. C'est
    le seul élément de la clé qui diffère.

* **Les horodatages ne sont PAS toujours tronqués à la minute côté futures :**
  24 trades sur 34 portent des secondes non nulles (`2026-08-11T17:19:07`),
  les autres non. Deux régimes coexistent dans le même journal. La clé compare
  des MINUTES, ce qui reste juste dans les deux cas — mais il fallait le savoir
  avant de resserrer sur la seconde, ce qui aurait paru plus précis et aurait
  cassé 10 trades sur 34.

* **Edgewonk stocke bien en UTC côté Tradovate aussi**, et c'est mesuré à
  l'envers : notre `19:19:07` (UTC+2, lui-même mesuré contre les bougies du
  marché) devient `17:19:07` chez eux. Deux heures pile, comme côté cTrader.
"""

import datetime as dt

from core import plateformes as pf


def _utc_minute(iso):
    """« 2026-08-07T13:43:18.644+02:00 » -> « 2026-08-07T11:43 ».

    Passe par l'offset réel porté par la donnée. En hiver le relevé sortira en
    UTC+1 et la conversion suivra toute seule.
    """
    moment = dt.datetime.fromisoformat(iso).astimezone(dt.timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M")


def _f(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


def cle_jambe(jambe):
    """⚠️ Le nom d'instrument dépend de la PLATEFORME, et il est mesuré des deux
    côtés : `symbole_broker` pour cTrader (« XAUUSD.raw »), `symbole` pour
    Tradovate (« MNQ », pas « MNQU6 »). Voir l'en-tête de ce module."""
    colonne = pf.colonne_instrument(jambe.get("plateforme"))
    return (jambe.get(colonne),
            "BUY" if jambe.get("sens") == "Achat" else "SELL",
            _utc_minute(jambe["ouverture"]),
            _utc_minute(jambe["cloture"]))


def cle_trade(trade):
    return ((trade.get("instrument") or {}).get("name"),
            trade.get("direction"),
            (trade.get("entryDate") or "")[:16],
            (trade.get("exitDate") or "")[:16])


def _depart(candidats, jambe):
    """Départage plusieurs trades sur la même minute : montant, puis quantité."""
    net = _f(jambe.get("net"))
    lots = _f(jambe.get("volume_lots"))
    for critere in (
        lambda t: net is not None and _f(t.get("gain")) is not None
                  and abs(_f(t.get("gain")) - net) < 0.005,
        lambda t: lots is not None and _f(t.get("quantity")) is not None
                  and abs(_f(t.get("quantity")) - lots) < 1e-6,
    ):
        restants = [t for t in candidats if critere(t)]
        if len(restants) == 1:
            return restants[0], ""
        candidats = restants or candidats
    return None, "%d candidats indiscernables (meme minute, meme montant, meme quantite)" % len(candidats)


def _marge_arrondi(leur):
    """Demi-unite de la derniere decimale de `leur`. Voir `ecriture`."""
    if leur is None:
        return 0.0
    texte = repr(float(leur))
    if "." not in texte or "e" in texte or "E" in texte:
        return 0.0
    return 0.5 * (10.0 ** -len(texte.split(".")[1])) * 1.000001


def apparier(jambes, trades_edgewonk):
    """Retourne (couples, sans_correspondance, ambigus, controles).

    `couples`  : [(cle_jambe, jambe, trade)]
    `controles`: anomalies de vérification — un couple formé dont le VWAP
                 d'entrée ne concorde pas. Jamais silencieux.
    """
    index = {}
    for t in trades_edgewonk:
        index.setdefault(cle_trade(t), []).append(t)

    couples, sans, ambigus, controles = [], [], [], []
    for cle, jambe in sorted(jambes.items()):
        candidats = index.get(cle_jambe(jambe), [])
        if not candidats:
            sans.append(cle)
            continue
        if len(candidats) == 1:
            trade = candidats[0]
        else:
            trade, raison = _depart(candidats, jambe)
            if trade is None:
                ambigus.append("%s : %s" % (cle, raison))
                continue

        # contrôle d'intégrité : le VWAP d'entrée doit concorder
        px = None
        for s in sorted(trade.get("scalings") or [], key=lambda x: x.get("id") or 0):
            if s.get("type") == "START_ENTRY":
                px = _f(s.get("scalingPrice"))
                break
        nx = _f(jambe.get("entree"))
        # Tolerance RELATIVE : Edgewonk stocke 1.15972197 la ou nous avons
        # 1.1597219714 — c'est le meme prix a la 10e decimale pres, pas un
        # ecart. Un seuil absolu de 1e-9 criait au loup sur un arrondi.
        #
        # ⚠️ 1e-6 relatif ne suffit pas. Mesure du 26/08/2026 sur 153 trades :
        # 4 faux positifs, dont 1.16966 chez eux contre 1.1696554545 chez nous —
        # 4 milliemes de pip, soit 3.9e-6 en relatif. Edgewonk stocke un nombre
        # FIXE de decimales ; notre VWAP en porte autant que la moyenne
        # ponderee en produit. On prend donc le plus large des deux seuils :
        # le relatif habituel, et la demi-unite de LEUR derniere decimale —
        # le pire ecart qu'un arrondi puisse creer. Meme regle que
        # `ecriture._marge_arrondi`, et pour la meme raison.
        seuil = max(1e-6 * max(abs(px or 0.0), 1.0), _marge_arrondi(px))
        if px is not None and nx is not None and abs(px - nx) > seuil:
            controles.append("%s : VWAP d'entree %s cote Edgewonk, %s chez nous"
                             % (cle, px, nx))

        net, gain = _f(jambe.get("net")), _f(trade.get("gain"))
        if net is not None and gain is not None and abs(net - gain) > 0.005:
            controles.append("%s : net %s chez nous, gain %s cote Edgewonk"
                             % (cle, net, gain))

        couples.append((cle, jambe, trade))
    return couples, sans, ambigus, controles


def rattraper(trades, distants, couples, sans):
    """Repeche les jambes que `apparier` laisse de cote — le changement d'heure.

    ⚠️ DEPLACEE ICI le 28/08/2026, depuis `retroactif/retro.py`. Elle y etait
    nee sous le nom « ecart E5 », comme si c'etait une particularite du chantier
    d'historique. C'en est une regle d'APPARIEMENT : le changement d'heure
    revient deux fois par an, et la production traversera celui du 25/10/2026
    exactement comme le chantier a traverse celui du 29/03.

    Le cout de l'avoir laissee la-bas s'est vu tout de suite :
    `diag_appariement`, qui ne la connaissait pas, a compte 5 « orphelins » qui
    etaient parfaitement apparies — dont le trade a +606,00 du 31/03, present
    dans la base sous la cle 20260331-181419-EURUSD-A#234805.
    Un diagnostic qui ignore une regle que la production applique ne mesure pas
    la production.

    Mesure du 26/08/2026 : 4 jambes du 30/03 au 01/04 restaient orphelines.
    Diagnostic (`retro.py orphelins`) : leur entree concorde A LA MINUTE, leur
    quantite et leur gain au centime, et seule la SORTIE differe — d'une heure
    pile, cote Edgewonk. Leur import a mal resolu le changement d'heure du
    29/03 sur l'horodatage de sortie ; notre releve, lui, est coherent.

    La cle de secours n'est PAS plus laxiste, elle est plus DISCRIMINANTE :
    (instrument, sens, entree a la minute, quantite, gain au centime). Deux
    trades distincts partagent rarement les cinq. Trois verrous en plus :
      - on ne repeche que ce que l'appariement a deja renonce a apparier ;
      - le candidat doit etre UNIQUE, sinon on s'abstient ;
      - il ne doit pas etre deja apparie a une autre jambe.
    """
    if not sans:
        return []

    pris = {t.get("id") for _, _, t in couples}

    def _f(v):
        try:
            return float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return None

    rattrapes = []
    for cle in list(sans):
        j = trades[cle]
        k = cle_jambe(j)
        lots, net = _f(j.get("volume_lots")), _f(j.get("net"))
        if lots is None or net is None:
            continue
        candidats = []
        for t in distants:
            if t.get("id") in pris:
                continue
            if ((t.get("instrument") or {}).get("name") or "") != k[0]:
                continue
            if t.get("direction") != k[1]:
                continue
            if (t.get("entryDate") or "")[:16] != k[2]:
                continue
            q, g = _f(t.get("quantity")), _f(t.get("gain"))
            if q is None or g is None:
                continue
            if abs(q - lots) > 1e-6 or abs(g - net) > 0.005:
                continue
            candidats.append(t)
        if len(candidats) != 1:
            continue
        t = candidats[0]
        couples.append((cle, j, t))
        pris.add(t.get("id"))
        sans.remove(cle)
        rattrapes.append("%s -> id %s (%s lots, gain %s)"
                         % (cle, t.get("id"), t.get("quantity"), t.get("gain")))
    return rattrapes
