"""Étape 3 : bougies M1 du broker -> extrêmes de prix et TP-first.

Source : `get_trendbars` du MCP local (mesuré « qualité production » le
25/08/2026). Jamais le feed d'Edgewonk : ses prix viennent d'un symbole
canonique qui n'est pas celui d'Prop Firm A, et mélanger deux sources de prix
dans un même trade est l'incohérence silencieuse que ce projet élimine.

FAITS MESURÉS QUI DICTENT CE MODULE

* **M1, pas M5.** Vérifié sur la position 284853317 : la bougie M5 contenant la
  sortie s'étend au-delà de la clôture et porte un extrême POSTÉRIEUR au trade.
  En M1 l'erreur de bord tombe à 59 secondes.
* **Le symbole est `symbole_broker`.** `get_symbols` sur le compte Alpha
  Capital répond « XAUUSD.raw ». Le « XAUUSD » nu du compte démo était un
  artefact du compte démo. Prendre les bougies sur le mauvais flux donnerait des
  extrêmes issus d'une autre source que les exécutions — invisible à la lecture.
* **La pagination est obligatoire, pas optionnelle.** Cap de 1000 barres par
  requête ; la plus longue position du relevé du 25/08 dure 16 h 51, soit
  **1011 barres M1**. Le cas limite est déjà dans les données réelles.
* **Une requête par POSITION, pas par jambe.** Toutes les jambes d'une position
  partent de la même entrée : on tire la fenêtre la plus large une fois, puis on
  découpe par jambe. 38 requêtes au lieu de 46, et une seule pour la position
  sortie en quatre fois.

* **Les bougies de bord débordent du trade, et pas qu'un peu.** Mesuré le
  25/08/2026 sur la jambe 20260807-134318-EURUSD-A#143001 : sortie au TP à
  12:30:01Z, et la bougie M1 de 12:30 porte un high à 1.15685 — **21,5 pips
  au-dessus du TP, atteints APRÈS la sortie** (publication macro US de 8h30 NY,
  41 pips d'amplitude dans la minute). Le high suivant le plus élevé de tout le
  trade est 1.15379, à 19 minutes de là. Le README affirmait que « en M1
  l'erreur de bord tombe à 59 secondes » et la traitait comme négligeable :
  faux sur une bougie de news, et faux en silence.

  → On ne retient que les bougies ENTIÈREMENT contenues dans [entrée, sortie],
    plus les deux prix qu'on connaît exactement : l'entrée et la sortie. Sur la
    jambe ci-dessus, le plus haut redevient 1.15470, c'est-à-dire le TP —
    exactement ce qui s'est passé.

CE QU'ON N'INVENTE PAS

Si une même bougie M1 touche le SL *et* le TP, l'ordre est indécidable à la
minute : `tp_touche_en_premier` reste VIDE et le cas est signalé. Descendre plus
bas demanderait des ticks, que le MCP n'expose pas.

Une jambe de moins d'une minute n'a AUCUNE bougie intérieure : ses extrêmes
valent alors max/min(entrée, sortie). Sans enjeu — l'utilisateur ne scalpe pas ; une
jambe si courte est une erreur de saisie ou une réduction de sizing immédiate,
pas une décision de trading dont le MAE/MFE porterait un sens.
"""

import datetime as dt

from core.modele import SENS_ACHAT


class ReponseIllisible(Exception):
    """La source de bougies a repondu autre chose que des donnees.

    ⚠️ DEFINIE ICI ET PAS IMPORTEE. Ce module est generique — il sert cTrader
    ET Databento (voir l'en-tete) — donc il ne peut pas dependre de l'exception
    de l'un des deux sans se lier a lui. Les deux appelants l'ajoutent a ce
    qu'ils rattrapent ; c'est le prix, faible, de l'independance.
    """

# Un débordement de bougie de bord ne compte QUE s'il change matériellement le
# MAE/MFE. Mesuré en R, jamais en pips : l'utilisateur empile des comptes de tailles
# et d'instruments différents, un seuil en devise serait incomparable — même
# raison que R_BREAK_EVEN. Calibré le 25/08/2026 sur 9 jambes réelles : à 0,
# 8 jambes sur 9 déclenchaient (un bord dépasse presque toujours de quelques
# dixièmes de pip, ce qui ne veut rien dire) ; à 0.10 R, seule la bougie de news
# de #143001 reste — elle dépassait de 2,99 R.
R_ECART_BORD = 0.10

# ---------------------------------------------------------------- paliers
# Les stratégies alternatives d'Edgewonk : « qu'aurais-je gagné en tenant
# jusqu'à 2R, 3R, 3,5R, 4R, 5R ? ».
#
# RÈGLE, tranchée par l'utilisateur le 25/08/2026 : pour chaque palier, c'est SOIT
# le palier, SOIT −1. Rien d'autre. On simule la tenue de la position avec le
# SL initial, et on regarde ce qui tombe en premier.
#
#   le prix monte à 4,5 R puis revient au stop  ->  4R = +4, 5R = −1
#   le prix touche le stop d'abord              ->  tous les paliers = −1
#
# **On ne mesure jamais au-dessus de 5R.** C'est le dernier palier : dès qu'il
# est atteint, la simulation s'arrête. Que le prix soit ensuite allé à 50 R
# n'intéresse personne — il n'y a pas de champ pour le recevoir.
# ⚠️ ÉTENDU le 26/08/2026 : l'utilisateur a ajoute 1R, 1.5R et 2.5R cote Edgewonk.
# Les trois nouveaux paliers sont TOUS sous 5R, donc `PALIER_MAX` ne bouge pas
# et la simulation est inchangee : ils se resolvent depuis le
# `prix_max_favorable` DEJA stocke, sans une seule requete de bougies. C'est
# exactement le benefice de « on stocke les faits, pas les statistiques ».
#
# Cette liste est le SEUL endroit ou les paliers sont enumeres. Le nom cote
# Edgewonk est parse (`ecriture.palier_du_nom`) et l'ecriture vise le
# `strategyId` : l'ordre d'affichage dans leur interface n'entre nulle part.
# Un palier absent d'ici est vu, signale, puis laisse intact.
PALIERS_R = (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0)
PALIER_MAX = max(PALIERS_R)

# ⚠️ LA SIMULATION CONTINUE APRÈS LA SORTIE RÉELLE. C'est toute la difficulté :
# les extrêmes du trade (`prix_plus_haut` / `prix_plus_bas`) s'arrêtent à la
# sortie de l'utilisateur, et s'en servir sous-estimerait systématiquement.
# Mesuré sur la position 20260807-134318-EURUSD-A : le plus haut PENDANT le
# trade vaut 2,17 R, ce qui donnerait −1 pour 3R, 3,5R, 4R et 5R. Or le prix
# monte à ~6,75 R dans l'heure qui suit : les cinq paliers étaient atteints.
#
# L'utilisateur : « dans tous les cas c'est soit le SL, soit le 5R, il y a toujours
# l'un des deux, même si ça arrive un an après ». Vrai — mais les bougies, elles,
# ne sont pas toujours disponibles : un trade de ce matin n'a pas encore de
# futur, et le broker purge l'ancien. D'où un plafond de JOURS, qui ne fabrique
# JAMAIS de valeur : au-delà, la simulation est déclarée NON RÉSOLUE et signalée.
# Le trade repassera au prochain cycle, quand les bougies existeront.
# ⚠️ RELEVE A 180 JOURS le 28/08/2026, et il n'y a qu'UN horizon.
#
# Ce plafond valait 10 jours. Il n'a JAMAIS ete une decision d'analyse : le
# commentaire d'origine le dit lui-meme — l'utilisateur soutient que « dans tous les
# cas c'est soit le SL, soit le 5R, il y a toujours l'un des deux, meme si ca
# arrive un an apres », et le plafond ne servait qu'a se proteger des bougies
# INDISPONIBLES (un trade du matin n'a pas encore de futur, le broker purge
# l'ancien).
#
# Cinq positions d'octobre-novembre 2025 repartaient donc « non resolues » a
# chaque passage, pour une raison purement technique.
#
# ⚠️ ET J'AVAIS PROPOSE DE NE LE MONTER QUE POUR LE TP-FIRST, en soutenant que
# « tenir une position forex trois semaines n'est pas une strategie alternative
# realiste ». C'etait faux, et c'etait une justification inventee :
#
#   - elle contredisait la position de l'utilisateur, ecrite au §9 du README ;
#   - et le raisonnement ne tient pas. La simulation s'arrete au PREMIER des
#     deux niveaux atteints. Tenir la position avec son stop initial, ce n'est
#     pas « tenir trois semaines » : c'est attendre que l'un des deux tombe. Si
#     aucun n'est tombe en dix jours, la position etait simplement encore
#     ouverte — on n'a pas repondu, on a coupe la question.
#
# Les deux champs posent la meme question — « et apres, avec le stop initial,
# que se passe-t-il ? » — donc ils partagent le meme horizon.
#
# 180 jours borne sans brider : au-dela, un contrat future a expire et
# `VIDES_MAX` arrete le parcours de lui-meme. Le plafond reste ce qu'il a
# toujours ete, un garde-fou, et il ne fabrique JAMAIS de valeur : au-dela, la
# simulation est declaree non resolue et le trade repasse.
JOURS_MAX = 180
TRANCHE_JOURS = 1

# ---------------------------------------------------- le SL est-il l'INITIAL ?
#
# Ajoute le 26/08/2026, sur un cas trouve dans les donnees reelles.
#
# LE RAISONNEMENT. `prix_plus_haut` / `prix_plus_bas` disent ce que le prix a
# fait PENDANT le trade. `prix_max_favorable` dit jusqu'ou il serait alle si la
# position avait ete tenue AVEC LE SL SAISI — la simulation avance dans le
# temps et s'arrete au premier des deux niveaux atteints.
#
# Si la simulation s'arrete NETTEMENT plus tot que le MFE reel, c'est que le
# prix a franchi le SL saisi AVANT d'aller chercher son extreme — et que le
# trade, lui, a continue. **Un trade ne survit pas a son propre stop.** Donc le
# SL saisi n'etait pas en place a ce moment-la : soit ce n'est pas le niveau
# initial, soit la position a ete geree.
#
# C'est le seul controle qui attrape un SL faux SANS avoir besoin d'un R:R
# aberrant ni d'un |R| realise aberrant. Le cas qui l'a fait ecrire :
#   20260820-140208-6EU6-A — entree 1.16935, SL saisi 1.16895 (4 pips).
#   Le plus bas du trade est 1.16820, soit 1,9 R SOUS le stop, et le trade a
#   continue trois heures avant de sortir exactement au stop. Le R:R de 12,5
#   avait bien signale quelque chose ; l'alerte a ete acquittee et le stop est
#   reste. Meme scenario que le NAS100 du 14/08 cote cTrader.
#
# ⚠️ SIGNALEMENT, JAMAIS REJET NI CORRECTION. On ne sait pas laquelle des deux
# causes s'applique, et ni l'une ni l'autre ne se devine.
#
# Seuil calibre sur les 83 jambes de la base au 26/08/2026 : DEUX declenchent,
# a 2,9 R et 202 R d'ecart, et les deux sont de vrais cas. La troisieme valeur
# la plus haute est a 0,05 R — du bruit de bord de bougie. 0,50 R laisse donc
# passer tout le bruit mesure et n'attrape que ce qui est structurel.
R_SIMULATION_INCOHERENTE = 0.50

# Une tranche VIDE n'est pas la fin de l'historique : le marche ferme le
# week-end. Mesure du 25/08/2026 — le NAS100 du vendredi 14/08 butait sur le
# samedi 15 et se declarait « non resolu, le trade repassera ». C'etait faux :
# la tranche du samedi est vide a chaque relance, donc il ne se resolvait
# JAMAIS. On distingue desormais marche ferme (on saute) de fin d'historique
# (on s'arrete). VIDES_MAX couvre un week-end long plus un ferie.
VIDES_MAX = 4

TIMEFRAME = "m1"
BARRES_MAX = 1000          # cap serveur mesuré
BARRES_PAR_TRANCHE = 900   # sous le cap, avec de la marge
MARGE = dt.timedelta(minutes=1)   # couvre la bougie qui contient l'entrée / la sortie

# Minutes par barre, par timeframe MCP. Sert à calculer la largeur d'une tranche
# de pagination : 900 barres de H4 couvrent 150 jours, 900 barres de M1 en
# couvrent 15 heures. Une tranche en minutes fixes paginerait 240 fois trop
# souvent en H4, et pas assez en M1.
MINUTES = {"m1": 1, "m5": 5, "m15": 15, "m30": 30,
           "h1": 60, "h4": 240, "h12": 720, "d1": 1440}


def _utc(iso):
    """« 2026-08-07T13:43:18.644+02:00 » -> datetime aware en UTC."""
    return dt.datetime.fromisoformat(iso).astimezone(dt.timezone.utc)


def _z(moment):
    """datetime UTC -> « 2026-08-07T11:43:00Z », la forme attendue par le MCP."""
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def recuperer(client, symbole_broker, debut_iso, fin_iso, timeframe=TIMEFRAME):
    """Bougies sur [debut, fin], paginées et dédoublonnées.

    Retourne une liste de dicts {timestamp, open, high, low, close, volume},
    triée par horodatage, ou lève ErreurMCP.

    ⚠️ Le `from` DOIT être arrondi à la minute inférieure : mesuré, un `from`
    portant des secondes fait sauter la bougie qui contient l'entrée — le
    serveur n'inclut pas une barre commencée avant la borne.
    """
    pas = MINUTES.get(timeframe, 1)
    debut = _utc(debut_iso).replace(second=0, microsecond=0) - MARGE
    fin = _utc(fin_iso).replace(second=0, microsecond=0) + MARGE
    largeur = dt.timedelta(minutes=BARRES_PAR_TRANCHE * pas)

    par_horodatage = {}
    curseur = debut
    while curseur <= fin:
        tranche_fin = min(curseur + largeur, fin)
        reponse = client.appeler("get_trendbars", {
            "symbolName": symbole_broker,
            "timeframe": timeframe,
            "from": _z(curseur),
            "to": _z(tranche_fin),
            "limit": BARRES_MAX,
        })
        # ⚠️ UNE REPONSE QUI N'EST PAS UN OBJET EST UN MESSAGE D'ERREUR.
        # `mcp.appeler` rend le texte brut quand la charge utile n'est pas du
        # JSON — c'est-a-dire quand le serveur repond en prose plutot qu'en
        # donnees. Ce texte traversait ici sans controle et plantait 300 lignes
        # plus loin sur « 'str' object has no attribute 'get' », un message qui
        # ne dit ni quel symbole, ni quelle fenetre, ni ce que le serveur a
        # repondu. Mesure du 28/08/2026, en plein audit, apres 120 jambes.
        if not isinstance(reponse, dict):
            raise ReponseIllisible(
                "la source de bougies a repondu en texte au lieu de donnees, sur %s "
                "%s [%s -> %s] :\n  %s"
                % (symbole_broker, timeframe, _z(curseur), _z(tranche_fin),
                   str(reponse)[:300]))
        for b in reponse.get("bars", []) or []:
            if b.get("timestamp"):
                par_horodatage[b["timestamp"]] = b
        if tranche_fin >= fin:
            break
        curseur = tranche_fin + dt.timedelta(minutes=pas)

    return [par_horodatage[k] for k in sorted(par_horodatage)]


def _horodatage_bougie(b):
    return dt.datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))


def _decouper(bougies, entree_iso, sortie_iso):
    """(intérieures, bords).

    INTÉRIEURE = la bougie entière tombe dans [entrée, sortie]. Son extrême
    appartient donc certainement au trade.
    BORD = la bougie chevauche l'entrée ou la sortie. Son extrême peut être
    antérieur ou postérieur au trade : on ne s'en sert pas pour calculer, on
    s'en sert pour SAVOIR qu'on a peut-être manqué quelque chose.
    """
    entree, sortie = _utc(entree_iso), _utc(sortie_iso)
    minute = dt.timedelta(minutes=1)
    interieures, bords = [], []
    for b in bougies:
        debut = _horodatage_bougie(b)
        if debut >= entree and debut + minute <= sortie:
            interieures.append(b)
        elif debut + minute > entree and debut < sortie:
            bords.append(b)
    return interieures, bords


def _decimales(*valeurs):
    """Le nombre de décimales du symbole, lu sur les prix plutôt que supposé."""
    n = 0
    for v in valeurs:
        t = str(v)
        if "." in t:
            n = max(n, len(t.split(".")[1].rstrip()))
    return min(n, 8)


def analyser(interieures, bords, sens, entree, sortie, sl, tp):
    """Retourne (plus_haut, plus_bas, tp_first, note, bord_plus_large).

    Les extrêmes se calculent sur les bougies INTÉRIEURES, plus l'entrée et la
    sortie — les deux seuls prix dont on sait avec certitude qu'ils ont été
    touchés pendant le trade.

    `tp_first` vaut "oui", "non" ou "" (indécidable).
    `ecart_bord` est l'ampleur, EN R, de ce qu'une bougie de bord portait au-delà
    de l'extrême retenu — 0 quand il n'y a rien de matériel. Au-dessus de
    `R_ECART_BORD`, le chiffre est une borne et non un maximum. On le COMPTE
    plutôt que de le signaler ligne à ligne : un volume, pas du bruit.
    """
    hauts = [float(b["high"]) for b in interieures] + [entree, sortie]
    bas_ = [float(b["low"]) for b in interieures] + [entree, sortie]
    plus_haut, plus_bas = max(hauts), min(bas_)

    # Ampleur du débordement, rapportée au risque du trade. Sans SL, pas de R —
    # et un trade sans risque initial n'a de toute façon pas de MAE/MFE
    # exploitable (règle R7). On ne compte rien plutôt que d'inventer une échelle.
    ecart_bord = 0.0
    risque = abs(entree - sl) if sl is not None else None
    if risque:
        manque = 0.0
        for b in bords:
            manque = max(manque, float(b["high"]) - plus_haut, plus_bas - float(b["low"]))
        ecart_bord = max(0.0, manque) / risque

    if sl is None or tp is None:
        return plus_haut, plus_bas, "", "", ecart_bord

    achat = sens == "Achat"

    def touche(haut, bas):
        return (haut >= tp if achat else bas <= tp,
                bas <= sl if achat else haut >= sl)

    for b in interieures:
        tp_ok, sl_ok = touche(float(b["high"]), float(b["low"]))
        if tp_ok and sl_ok:
            return plus_haut, plus_bas, "", (
                "SL et TP touches dans la meme bougie M1 (%s) — ordre indecidable"
                % b["timestamp"]), ecart_bord
        if tp_ok:
            return plus_haut, plus_bas, "oui", "", ecart_bord
        if sl_ok:
            return plus_haut, plus_bas, "non", "", ecart_bord

    # Aucune bougie intérieure n'a touché de niveau. Le prix de SORTIE tranche :
    # c'est le dernier point du trade dont on soit certain. C'est ce qui rend
    # `#143001` correct — sortie AU TP, sans qu'aucune bougie entière n'y touche.
    tp_ok, sl_ok = touche(sortie, sortie)
    if tp_ok:
        return plus_haut, plus_bas, "oui", "", ecart_bord

    # ⚠️ NI L'UN NI L'AUTRE ATTEINT PENDANT LE TRADE. On ne répond PAS.
    #
    # Ce code répondait « non » ici, avec ce commentaire : « le TP n'a pas été
    # touché avant le SL, c'est bien "non" au sens d'Edgewonk ». C'était une
    # INTERPRÉTATION, et elle est fausse. Leur propre infobulle dit :
    #
    #     « Ignore how you exited — just focus on which level the price hit
    #       first. »
    #
    # Donc la sortie de l'utilisateur n'entre pas dans la réponse. S'il coupe avant
    # que l'un des deux niveaux soit touché, la question reste ouverte : c'est
    # ce qui se passe APRÈS sa sortie qui la tranche. Répondre « SL first »
    # parce que le trade s'est arrêté là est une réponse fabriquée.
    #
    # Mesuré le 26/08/2026, et trouvé par l'utilisateur en relisant son journal :
    # **21 jambes sur 43** portaient ce « SL first » sans qu'aucun des deux
    # niveaux ait été touché. La moitié du champ était inventée.
    #
    # `None` veut dire « à résoudre plus loin » — `traiter_position` poursuit la
    # simulation au-delà de la sortie, exactement comme pour les paliers.
    # À ne pas confondre avec `""`, qui veut dire « indécidable » : les deux
    # niveaux touchés dans la même bougie M1, et là aucune requête n'y changera
    # rien.
    return plus_haut, plus_bas, None, "", ecart_bord


def niveau(entree, sl, r, achat):
    """Le prix correspondant à `r` fois le risque, du bon côté."""
    risque = abs(entree - sl)
    return entree + r * risque if achat else entree - r * risque


def simuler_paliers(client, symbole_broker, sens, entree, sl, ouverture_iso):
    """Jusqu'où le prix serait allé si la position avait été TENUE.

    Retourne (prix_max_favorable, note).

      * `prix_max_favorable` : le prix le plus favorable atteint avant que le SL
        ne soit touché, borné au niveau 5R. C'est un FAIT, un prix — pas un
        R-multiple : les R se recalculent depuis l'entrée et le SL, un prix
        stocké ne diverge jamais. (Principe du projet : on stocke les faits.)
      * `None` : simulation NON RÉSOLUE — ni le SL ni le 5R n'ont été atteints
        dans les bougies disponibles. On n'invente rien, la note le dit.

    La bougie qui contient l'entrée est EXCLUE, même règle qu'`analyser` : son
    extrême peut être antérieur à l'entrée. Le point de départ est le prix
    d'entrée lui-même, qu'on connaît exactement.
    """
    achat = sens == SENS_ACHAT
    risque = abs(entree - sl)
    if not risque:
        return None, "risque nul (SL = entree) — paliers incalculables"

    cible = niveau(entree, sl, PALIER_MAX, achat)
    depart = _utc(ouverture_iso)
    max_fav = entree
    tranche = dt.timedelta(days=TRANCHE_JOURS)
    vides = 0

    for jour in range(JOURS_MAX):
        debut = depart + tranche * jour
        fin = debut + tranche
        # ⚠️ `.isoformat()` et pas `_z()` : `recuperer` relit ces chaines avec
        # `datetime.fromisoformat`, qui refuse le suffixe « Z » avant Python
        # 3.11. Le « Z » n'est attendu que par le MCP, et c'est `_z` qui le pose,
        # a l'interieur de `recuperer`.
        bougies = recuperer(client, symbole_broker, debut.isoformat(), fin.isoformat())
        if not bougies:
            # Marche ferme (week-end, ferie) -> on saute la tranche.
            # Fin d'historique -> on s'arrete. Le seul discriminant fiable est
            # le temps : une tranche qui mord sur le futur n'existe pas encore.
            if fin > dt.datetime.now(dt.timezone.utc):
                return None, ("historique pas encore disponible au-dela de %s "
                              "— simulation non resolue, le trade repassera"
                              % _z(debut))
            vides += 1
            if vides > VIDES_MAX:
                return None, ("aucune bougie sur %d jours consecutifs depuis %s "
                              "— historique purge cote broker ? simulation non "
                              "resolue" % (vides, _z(debut)))
            continue
        vides = 0

        for b in bougies:
            debut_b = _horodatage_bougie(b)
            if debut_b < depart:
                continue                    # bougie de bord a l'entree : exclue
            haut, bas = float(b["high"]), float(b["low"])
            fav, adv = (haut, bas) if achat else (bas, haut)

            touche_cible = fav >= cible if achat else fav <= cible
            touche_sl = adv <= sl if achat else adv >= sl

            if touche_cible and touche_sl:
                # Les deux dans la meme bougie M1 : l'ordre est indecidable, la
                # meme limite que `tp_touche_en_premier`. On retient ce qui est
                # ACQUIS avant cette bougie — sous-estimation bornee, jamais
                # l'inverse.
                return max_fav, ("5R et SL touches dans la meme bougie M1 (%s) — "
                                 "paliers sous-estimes" % b["timestamp"])
            if touche_cible:
                return cible, ""
            if touche_sl:
                return max_fav, ""

            max_fav = max(max_fav, fav) if achat else min(max_fav, fav)

    return None, ("ni le SL ni le 5R touches en %d jours — simulation non resolue "
                  "(augmenter JOURS_MAX si le cas se repete)" % JOURS_MAX)


def simuler_tp_first(client, symbole_broker, sens, entree, sl, tp, ouverture):
    """Lequel des deux niveaux le prix touche-t-il en PREMIER ? ("oui"/"non"/None)

    La question est celle d'Edgewonk, mot pour mot : « ignore how you exited —
    just focus on which level the price hit first ». La sortie réelle n'entre
    donc pas dans la réponse, et la recherche continue AU-DELÀ d'elle.

    Même parcours que `simuler_paliers`, mêmes garde-fous : on avance par
    tranches d'un jour, une tranche vide dans le passé est un marché fermé
    (on saute), une tranche qui mord sur le futur arrête tout — le trade
    repassera. `None` = non résolu ; on n'invente rien, la colonne reste vide.

    ⚠️ La bougie qui contient l'entrée est exclue : son extrême peut être
    antérieur à l'entrée. Le point de départ est le prix d'entrée lui-même.
    """
    achat = sens == SENS_ACHAT
    if sl is None or tp is None or entree is None:
        return None, ""
    depart = _utc(ouverture)
    tranche = dt.timedelta(days=TRANCHE_JOURS)
    vides = 0

    for jour in range(JOURS_MAX):
        debut = depart + tranche * jour
        fin = debut + tranche
        bougies = recuperer(client, symbole_broker, debut.isoformat(), fin.isoformat())
        if not bougies:
            if fin > dt.datetime.now(dt.timezone.utc):
                return None, ("TP-first non resolu : ni la cible ni le stop "
                              "touches, et l'historique s'arrete a %s — le trade "
                              "repassera" % _z(debut))
            vides += 1
            if vides > VIDES_MAX:
                return None, ("TP-first non resolu : aucune bougie sur %d jours "
                              "consecutifs depuis %s — historique purge, ou "
                              "contrat expire" % (vides, _z(debut)))
            continue
        vides = 0

        for b in bougies:
            if _horodatage_bougie(b) < depart:
                continue                    # bougie de bord a l'entree : exclue
            haut, bas = float(b["high"]), float(b["low"])
            tp_ok = haut >= tp if achat else bas <= tp
            sl_ok = bas <= sl if achat else haut >= sl
            if tp_ok and sl_ok:
                # Les deux dans la meme bougie M1 : indecidable a la minute,
                # comme pendant le trade. On le dit, on ne tire pas au sort.
                return "", ("cible et stop touches dans la meme bougie M1 (%s) "
                            "— TP-first indecidable" % b["timestamp"])
            if tp_ok:
                return "oui", ""
            if sl_ok:
                return "non", ""

    return None, ("TP-first non resolu : ni la cible ni le stop touches en %d "
                  "jours" % JOURS_MAX)


def paliers_depuis(prix_max_favorable, entree, sl, sens):
    """{palier: R-multiple} — soit le palier, soit -1. Rien d'autre.

    Pur calcul, aucune requete : se rejoue a volonte depuis la base.
    """
    risque = abs(entree - sl)
    if not risque or prix_max_favorable is None:
        return {}
    signe = 1.0 if sens == SENS_ACHAT else -1.0
    r_atteint = signe * (prix_max_favorable - entree) / risque
    return {p: (p if r_atteint >= p else -1.0) for p in PALIERS_R}


def traiter_position(client, position, trades):
    """Calcule les extrêmes des jambes d'UNE position. Retourne (maj, notes).

    `maj` : {cle_jambe: {"prix_plus_haut": .., "prix_plus_bas": ..,
                         "tp_touche_en_premier": ..}}
    """
    jambes = [trades[c] for c in position["jambes"] if c in trades]
    if not jambes:
        return {}, []

    ouverture = jambes[0]["ouverture"]
    derniere = max(j["cloture"] for j in jambes)
    brutes = recuperer(client, jambes[0]["symbole_broker"], ouverture, derniere)

    def f(v):
        try:
            return float(str(v).replace(",", "."))
        except (TypeError, ValueError):
            return None

    # --- simulation des paliers : UNE fois par position, pas par jambe.
    # Toutes les jambes partagent l'entree et le SL, donc le meme resultat. La
    # valeur est repliquee, exactement comme sl et tp.
    prix_max, note_paliers = None, ""
    entree_pos, sl_pos = f(jambes[0]["entree"]), f(jambes[0].get("sl"))
    deja = (jambes[0].get("prix_max_favorable") or "").strip()
    if deja:
        prix_max = f(deja)
    elif entree_pos is not None and sl_pos is not None:
        try:
            prix_max, note_paliers = simuler_paliers(
                client, jambes[0]["symbole_broker"], jambes[0]["sens"],
                entree_pos, sl_pos, ouverture)
        except Exception as e:                                # noqa: BLE001
            note_paliers = "paliers non simules (%s)" % str(e).splitlines()[0]

    # ⚠️ LA SERIE COUVRE-T-ELLE VRAIMENT LE TRADE ?
    #
    # Ajoute le 28/08/2026, sur une intuition de l'utilisateur — « la journee n'est
    # pas terminee, Databento n'a peut-etre pas tout ».
    #
    # Le trou est reel et il est SILENCIEUX. Une source de bougies s'arrete la
    # ou son historique s'arrete : Databento borne la journee en cours (mesure,
    # ~12 minutes de retard sur l'horloge), et le MCP cTrader rend simplement ce
    # qu'il a. `analyser` ne voit qu'une liste de bougies : une serie tronquee
    # lui ressemble a une serie complete, et il en tire un plus haut et un plus
    # bas parfaitement plausibles — mais SOUS-ESTIMES.
    #
    # Et le pire est apres : `prix_plus_haut` etant renseigne, la selection de
    # l'etape 3 ne reprendra JAMAIS cette jambe. L'erreur se fige.
    #
    # Le controle est gratuit : la derniere bougie recue doit atteindre la
    # cloture de la jambe. Sinon on n'ecrit RIEN pour elle — la colonne reste
    # vide, la jambe repasse au cycle suivant, et le signalement le dit.
    derniere = None
    if brutes:
        derniere = max(_horodatage_bougie(b) for b in brutes)

    maj, notes, bords_larges = {}, [], []
    if note_paliers:
        notes.append("%s : %s" % (position["cle_position"], note_paliers))

    def _incoherence(entree_f, sl_f, haut, bas, achat):
        """L'ecart, en R, entre le MFE reel et la simulation. 0 si coherent.

        Voir R_SIMULATION_INCOHERENTE : un trade ne survit pas a son propre
        stop, donc une simulation qui s'arrete bien avant le MFE dit que le SL
        saisi n'etait pas en place.
        """
        if prix_max is None or sl_f is None or entree_f is None or entree_f == sl_f:
            return 0.0
        risque = abs(entree_f - sl_f)
        reel = (haut - entree_f) / risque if achat else (entree_f - bas) / risque
        simule = (prix_max - entree_f) / risque if achat else (entree_f - prix_max) / risque
        return max(0.0, reel - simule)
    for j in jambes:
        fin_jambe = _utc(j["cloture"])
        if derniere is None or derniere + MARGE < fin_jambe:
            notes.append(
                "%s : les bougies s'arretent a %s, avant la cloture %s — serie "
                "incomplete, rien n'est ecrit pour cette jambe, elle repassera"
                % (j["cle"], _z(derniere) if derniere else "(aucune)",
                   _z(fin_jambe)))
            continue
        interieures, bords = _decouper(brutes, ouverture, j["cloture"])
        entree_f, sortie_f = f(j["entree"]), f(j["sortie"])
        if entree_f is None or sortie_f is None:
            notes.append("%s : prix d'entree ou de sortie illisible" % j["cle"])
            continue
        haut, bas, tpf, note, ecart = analyser(
            interieures, bords, j["sens"], entree_f, sortie_f, f(j["sl"]), f(j["tp"]))

        # `None` = aucun des deux niveaux touche PENDANT le trade. La reponse
        # est APRES la sortie — c'est la definition d'Edgewonk. On poursuit.
        if tpf is None:
            try:
                tpf, note_tpf = simuler_tp_first(
                    client, j["symbole_broker"], j["sens"], entree_f,
                    f(j["sl"]), f(j["tp"]), ouverture)
            except Exception as e:                            # noqa: BLE001
                tpf, note_tpf = None, ("TP-first non simule (%s)"
                                       % str(e).splitlines()[0])
            if note_tpf:
                notes.append("%s : %s" % (j["cle"], note_tpf))
            if tpf is None:
                tpf = ""            # non resolu : la colonne reste vide

        if note:
            notes.append("%s : %s" % (j["cle"], note))
        if ecart >= R_ECART_BORD:
            bords_larges.append((j["cle"], ecart))

        manque = _incoherence(entree_f, f(j["sl"]), haut, bas,
                              j["sens"] == SENS_ACHAT)
        if manque >= R_SIMULATION_INCOHERENTE:
            notes.append(
                "%s : le prix a franchi le SL saisi AVANT d'atteindre son "
                "extreme (%.1f R d'ecart entre le MFE reel et la simulation), "
                "et le trade a continue. Un trade ne survit pas a son propre "
                "stop : soit ce SL n'est pas le niveau initial, soit la "
                "position a ete geree. Les paliers de ce trade sont "
                "sous-estimes." % (j["cle"], manque))
        dec = _decimales(j["entree"], j["sortie"])
        maj[j["cle"]] = {
            "prix_plus_haut": "%.*f" % (dec, haut),
            "prix_plus_bas": "%.*f" % (dec, bas),
            "tp_touche_en_premier": tpf,
            # vide si non resolu : le trade repassera quand les bougies existeront
            "prix_max_favorable": "" if prix_max is None else "%.*f" % (dec, prix_max),
        }
    return maj, notes, bords_larges
