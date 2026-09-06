"""Étape 5 : écrire dans Edgewonk ce que nous avons produit en plus.

Ordre imposé par ce qui a été mesuré, pas par confort (`docs/edgewonk-api.md` §12) :
instantané -> modify -> PUT -> RELECTURE. Les deux règles non négociables sont
l'instantané avant et la relecture après : un 200 ne prouve rien, `modify`
répond 200 même pour un champ qu'il ignore.

CE QU'ON ÉCRIT
    slPrice, tpPrice            <- ta saisie, lue dans Position Info
    highestPrice, lowestPrice   <- calculés sur les bougies M1 du broker
    originalTpHit               <- calculé, hors de portée d'Edgewonk seul
    ignoreForWinrate            <- break-even, |R| < R_BREAK_EVEN
    inReview                    <- marqueur, quand quelque chose cloche
    screenshots 1 à 4           <- M5, M15, H1, H4 (voir EMPLACEMENTS)

CE QU'ON NE TOUCHE JAMAIS
    Les données d'exécution (scalings, fineScalings, quantity, gain,
    commission, direction, dates) et tout le tagging de l'utilisateur — setup,
    checklistItems, customComments, les quatre familles de commentaires.
    Le tagging est le seul contenu du système qui ne soit pas reproductible.

⚠️ CORRECTION DU 25/08/2026 — « les données d'exécution sont déjà justes via
l'auto-import » (§0) EST FAUX, mais rarement.

Mesuré sur 44 couples : 2 trades portent des prix d'exécution qui divergent
réellement des nôtres.

    NAS100 17925810 : Edgewonk entree 30015.8   nous 30040.35
    USOIL  17925793 : Edgewonk entree 82.17     nous 81.51428571

Nos prix reproduisent le brut du relevé AU CENTIME ((30040.35 - 29958.95) x 3
= 244.20 = le brut declare). Les leurs, non. L'appariement, lui, est bon : gain,
quantité et minutes concordent des deux côtés.

Conséquence : sur ces trades, `rMultiple` restera FAUX côté Edgewonk même avec
un slPrice correct, puisqu'il est calculé serveur depuis l'entrée, le SL et la
sortie. On ne corrige pas les prix — modifier `scalings` n'a jamais été testé et
le risque dépasse le gain — mais on ne se tait pas : le trade est marqué
`inReview`, qui existe déjà dans l'outil et s'affiche là où l'utilisateur travaille.

⚠️ PIÈGE MESURÉ, ET PAYÉ — le champ `multiplier` d'Edgewonk VAUT 1.0, y compris
sur EURUSD et XAUUSD. **Ce n'est PAS la taille du contrat.** Une première
version de ce module comparait (entree - sortie) x quantite x multiplier au
gainGross : elle obtenait 0.00027 face à un brut de 27.00 et a marqué
`inReview` sur 40 trades parfaitement sains. Ne jamais reconstruire un montant
depuis les prix d'Edgewonk. On compare des PRIX à des PRIX — les nôtres, qui
sont vérifiables arithmétiquement contre le relevé.
"""

import io
import json
import os
import re
import time

# ⚠️ Les deux constantes de management et le sens d'achat viennent des modules
# qui font autorite dessus : `core/saisie` decide de ce qu'est OK et KO,
# `core/modele` de ce qu'est un achat. Les redefinir ici en ferait deux
# sources, et un jour deux verites.
from core.modele import SENS_ACHAT                            # noqa: E402
from core.saisie import MANAGEMENT_KO, MANAGEMENT_OK          # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# LES NEUF CHAMPS QU'ON ECRIT, ET RIEN D'AUTRE.
#
# Cette liste est la SOURCE du menu de selection de l'orchestrateur : ajouter un
# champ ici le rend choisissable, l'oublier le rend invisible. Une seule liste,
# donc pas de menu qui derive du code.
#
# `images` n'est pas un champ d'API : c'est le lot des quatre captures. Il est
# dans la meme liste parce que, du point de vue de l'utilisateur, « les images » se
# choisit exactement comme « le stop ».
CHAMPS_ECRITS = (
    ("sl",         ("slPrice",),                  "le stop"),
    ("tp",         ("tpPrice",),                  "la cible"),
    ("extremes",   ("highestPrice", "lowestPrice"), "les extremes (plus haut / plus bas)"),
    ("tp_first",   ("originalTpHit",),            "TP ou SL touche en premier"),
    ("breakeven",  ("ignoreForWinrate",),         "break-even (hors win rate)"),
    ("paliers",    ("alternativeStrategies",),    "les paliers de R"),
    ("management", ("managementComments",),       "le management"),
    ("revue",      ("inReview",),                 "le marqueur de revue"),
    ("images",     ("images",),                   "les quatre captures"),
)

MODE_ECRASER = "ecraser"
MODE_VIDE = "vide"


def _deja_rempli(valeur):
    """Edgewonk porte-t-il DEJA quelque chose dans ce champ ?

    ⚠️ UN BOOLEEN A FALSE EST VIDE. *(Renverse le 29/08/2026.)* La regle
    inverse — « une case decochee est un ETAT, pas une absence » — etait
    defendable en theorie et fausse en pratique : mesure sur les 553 trades des
    quatre journaux, `ignoreForWinrate` n'est **jamais** `null`. Pas une fois.
    Edgewonk le stocke comme un vrai booleen, `false` par defaut, des la
    creation du trade.

    Consequence de l'ancienne regle : `_deja_rempli` repondait « rempli » sur
    TOUS les trades, donc le mode « ne remplir que le vide » — celui par defaut
    de l'orchestrateur — ne pouvait ecrire le break-even sur AUCUN trade.
    Jamais. Mesure : 67 jambes en break-even dans la base, zero ecrite dans le
    journal de test. Le champ `inReview` tombait pareil. La protection ne
    protegeait rien (un `false` par defaut est indiscernable d'un `false` pose
    a la main) et elle avalait deux champs sur neuf.

    `originalTpHit`, lui, EST nullable (64 nulls sur 242) — c'est pourquoi
    TP-first passait et break-even non, dans le meme mode, sur le meme trade.

    Ce que la nouvelle regle preserve : une case COCHEE a la main (`true`)
    reste protegee en mode « vide ». Ce qu'elle abandonne : une case
    deliberement DECOCHEE peut etre recochee par le robot — ce que la decision
    figee du 25/08 autorise deja explicitement pour le break-even (« le robot
    fait autorite, dans les deux sens ; le garde-fou est le R, pas le sens de
    l'ecriture »).

    Un prix a 0.0, lui, EST vide aussi : la mesure du 28/08 a montre des
    `slPrice` a zero venant de leur import, qui ne sont pas des stops.
    """
    if valeur is None:
        return False
    if isinstance(valeur, bool):
        return valeur
    if isinstance(valeur, (int, float)):
        return valeur != 0
    if isinstance(valeur, (list, tuple, dict, str)):
        return len(valeur) > 0
    return True


def filtrer_plan(modify, put, images, trade, mode, champs):
    """Applique le MODE d'ecriture et la SELECTION de champs a un plan de trade.

    Un seul endroit, en bout de chaine, plutot qu'un test dans chacune des neuf
    branches qui construisent le plan : les regles metier restent lisibles, et
    le mode ne peut pas etre oublie sur un champ ajoute plus tard.

    Retourne (modify, put, images) filtres.
    """
    if champs is not None:
        gardes = set()
        for cle, distants, _ in CHAMPS_ECRITS:
            if cle in champs:
                gardes.update(distants)
        modify = {k: v for k, v in modify.items() if k in gardes}
        put = {k: v for k, v in put.items() if k in gardes}
        if "images" not in gardes:
            images = []

    if mode == MODE_VIDE:
        modify = {k: v for k, v in modify.items() if not _deja_rempli(trade.get(k))}
        put = {k: v for k, v in put.items() if not _deja_rempli(trade.get(k))}
        # Les images suivent la meme regle que les huit autres champs, et c'est
        # le seul endroit ou leur sort se decide (depuis le 29/08/2026) :
        #
        #   MODE_VIDE    -> seuls les emplacements VIDES chez eux partent. Une
        #                   capture posee a la main n'est jamais recouverte —
        #                   `envoyer_images` SUPPRIME avant d'envoyer, donc un
        #                   emplacement occupe qu'on inclurait serait detruit
        #                   sans retour possible. C'est l'ancienne regle E1.
        #   MODE_ECRASER -> les quatre repartent, meme identiques. C'est le
        #                   chemin normal apres une retouche du gabarit : les
        #                   PNG du disque font autorite.
        #
        # Et c'est PAR JOURNAL, puisque `trade` est le trade lu dans le journal
        # vise. Un journal neuf recoit tout, un journal deja servi ne recoit
        # que les trous.
        images = [x for x in images
                  if not trade.get("screenshot%dExists" % x[0])]
    return modify, put, images


CHAMPS = (("sl", "slPrice"),
          ("tp", "tpPrice"),
          ("prix_plus_haut", "highestPrice"),
          ("prix_plus_bas", "lowestPrice"))

# Emplacement Edgewonk de chaque timeframe. Les emplacements 5 et 6 restent
# libres pour les captures que l'utilisateur fait lui-meme.
#
# ⚠️ L'ORDRE DOIT SUIVRE `graphiques/rendu.py:TIMEFRAMES`. On ne l'importe pas :
# `rendu` tire matplotlib, et l'etape 5 doit tourner sans le venv (elle est en
# bibliotheque standard pure, comme les etapes 1, 2 et 3). Le prix de cette
# independance est cette duplication — si un timeframe change la-bas, il change
# ici. `verifier_emplacements()` le controle quand les deux sont chargeables.
EMPLACEMENTS = (("M5", 1), ("M15", 2), ("H1", 3), ("H4", 4))


def verifier_emplacements():
    """Compare EMPLACEMENTS a rendu.TIMEFRAMES. Retourne un message ou None.

    N'est appelable que si matplotlib est la. Sert aux diagnostics et aux
    tests, jamais au chemin d'ecriture.
    """
    try:
        from graphiques.rendu import TIMEFRAMES
    except ImportError:
        return None
    attendus = [nom for _, _, nom, _ in TIMEFRAMES]
    notres = [nom for nom, _ in EMPLACEMENTS]
    if attendus != notres:
        return ("EMPLACEMENTS (%s) ne suit plus rendu.TIMEFRAMES (%s)"
                % (", ".join(notres), ", ".join(attendus)))
    return None


def _f(v):
    try:
        return float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None


TOLERANCE_PRIX = 1e-6      # relatif : absorbe l'arrondi de stockage d'Edgewonk


def _marge_arrondi(leur):
    """L'ecart MAXIMAL qu'un simple arrondi peut produire sur `leur`.

    Edgewonk stocke un nombre fixe de decimales ; notre VWAP d'entree en porte
    autant que la moyenne ponderee en produit. Mesure du 26/08/2026 : 4 trades
    signales pour 0.0000045 d'ecart — 1.1696554545 chez nous, 1.16966 chez eux.
    C'est le MEME prix, arrondi. Ils etaient marques `inReview` a tort, et leur
    R declare faux alors qu'il est juste.

    On ne REARRONDIT pas notre valeur : Python arrondit 1.178855 a 1.17885 et
    Edgewonk a 1.17886, donc la comparaison dependrait de la convention de
    chacun. On compare l'ecart a la demi-unite de leur derniere decimale —
    la plus grande erreur qu'un arrondi puisse introduire, quel que soit le
    sens. Une vraie divergence la depasse largement : USOIL 82.17 contre
    81.514 fait 0.656 pour une marge de 0.005.
    """
    texte = repr(float(leur))
    if "." not in texte or "e" in texte or "E" in texte:
        return 0.0
    decimales = len(texte.split(".")[1])
    return 0.5 * (10.0 ** -decimales) * 1.000001      # epsilon : l'egalite passe


def prix_divergents(jambe, trade):
    """Les prix d'execution d'Edgewonk different-ils des NOTRES ?

    On compare prix a prix. Les notres viennent du releve du broker et
    reproduisent le brut au centime ; ce sont eux la reference.

    Retourne (divergent, detail). `None` quand l'info manque : on ne conclut
    pas sur du vide.
    """
    px = {}
    for s in sorted(trade.get("scalings") or [], key=lambda x: x.get("id") or 0):
        px[s.get("type")] = _f(s.get("scalingPrice"))
    ecarts = []
    for type_jambe, champ in (("START_ENTRY", "entree"), ("CLOSE_ENTRY", "sortie")):
        leur, notre = px.get(type_jambe), _f(jambe.get(champ))
        if leur is None or notre is None:
            continue
        # Seuil = le plus large des deux : la tolerance relative habituelle,
        # et la marge d'arrondi de LEUR precision d'affichage.
        seuil = max(TOLERANCE_PRIX * max(abs(leur), 1.0), _marge_arrondi(leur))
        if abs(leur - notre) > seuil:
            ecarts.append("%s %s cote Edgewonk, %s chez nous" % (champ, leur, notre))
    if not px:
        return None, ""
    return bool(ecarts), " ; ".join(ecarts)


def _paliers_de(jambe):
    """{palier: R} pour cette jambe, depuis `prix_max_favorable`. {} si absent."""
    from ctrader.bougies import paliers_depuis
    px = _f(jambe.get("prix_max_favorable"))
    entree, sl = _f(jambe.get("entree")), _f(jambe.get("sl"))
    if px is None or entree is None or sl is None:
        return {}
    return paliers_depuis(px, entree, sl, jambe.get("sens"))


def images_a_envoyer(jambe, dossier_racine):
    """Les PNG DISPONIBLES sur le disque pour cette jambe. Retourne
    [(emplacement, chemin, nom_timeframe)].

    ⚠️ CETTE FONCTION NE DECIDE PLUS RIEN. *(Renverse le 29/08/2026.)* Elle
    inventorie ; c'est le MODE, dans `filtrer_plan`, qui tranche — exactement
    comme pour les huit autres champs.

    Ce qu'elle faisait avant : rendre `[]` des que notre colonne `screenshots`
    portait un horodatage. Une regle anterieure aux deux modes d'ecriture, et
    qui les court-circuitait tous les deux — le verrou se fermait AVANT que le
    mode soit consulte, si bien qu'« ecraser » ne renvoyait aucune image, et
    que « ne remplir que le vide » n'en renvoyait aucune non plus dans un
    journal ou il n'y en avait jamais eu.

    Le defaut de fond etait la : le marqueur est GLOBAL, les journaux non. Une
    poussee vers un journal de test marquait la base, et les images ne
    partaient plus vers le journal reel — silencieusement, pour toujours.
    Mesure du 29/08 : 212 jambes marquees, 5 images dans le Sandbox, et aucun
    moyen d'en envoyer une de plus sans `diag_images.py --reparer`.

    La question « faut-il envoyer ? » se pose maintenant la ou toutes les
    autres se posent : contre le trade LU dans le journal vise. `screenshots`
    reste ecrit, mais comme une trace du dernier envoi confirme — plus comme un
    verrou.
    """
    dossier = (jambe.get("chemin_graphiques") or "").strip()
    if not dossier:
        return []                       # pas de graphique : rien a envoyer
    chemin_dossier = os.path.join(dossier_racine, dossier)
    lot = []
    for nom, emplacement in EMPLACEMENTS:
        chemin = os.path.join(chemin_dossier, "%s.png" % nom)
        if os.path.exists(chemin):
            lot.append((emplacement, chemin, nom))
    return lot


def description_image(jambe, nom_timeframe):
    """`{SYMBOLE}_{AAAA-MM-JJ}_{M5|M15|H1|H4}` — s'affiche dans l'interface."""
    return "%s_%s_%s" % (jambe.get("symbole", "?"),
                         (jambe.get("ouverture") or "")[:10], nom_timeframe)


# ---------------------------------------------------------------- break-even
# Seuil en R et JAMAIS en dollars : l'utilisateur empile des comptes de tailles
# differentes, un seuil en devise rendrait le win rate incomparable d'un compte
# a l'autre.
#
# Historique du reglage : 0.20 -> 0.30 -> 0.15 -> 0.30 (arbitre le 25/08/2026).
# Retour a 0.30 sur decision de l'utilisateur : « tout au-dessus de 0.3 R c'est un
# trade, point barre ». Le detour par 0.15 servait a epargner la jambe tenue du
# 07/08 18:50 (-0.292 R), que 0.30 fait rebasculer en break-even. Consequence
# acceptee et documentee : le seuil prime sur le cas particulier.
R_BREAK_EVEN = 0.30


def r_realise(jambe):
    """Le R du trade, calcule sur NOS prix. None si incalculable.

    ⚠️ Nos prix, pas le `rMultiple` d'Edgewonk : il est calcule serveur et il est
    FAUX sur les trades dont les prix d'execution divergent (mesure : 2 sur 44).
    Les notres reproduisent le brut du releve au centime.

    Sans SL il n'y a pas de risque initial, donc pas de R — regle R7. On ne
    fabrique pas de stop de substitution.
    """
    entree, sl, sortie = (_f(jambe.get("entree")), _f(jambe.get("sl")),
                          _f(jambe.get("sortie")))
    if None in (entree, sl, sortie) or entree == sl:
        return None
    signe = 1.0 if jambe.get("sens") == "Achat" else -1.0
    return signe * (sortie - entree) / abs(entree - sl)


def est_break_even(jambe):
    """|R| < R_BREAK_EVEN. None si le R n'est pas calculable."""
    r = r_realise(jambe)
    return None if r is None else abs(r) < R_BREAK_EVEN


_R_DANS_NOM = re.compile(r"(\d+(?:[.,]\d+)?)\s*R", re.I)


def palier_du_nom(nom):
    """« 3.5R » / « 3,5 R » / « 3R » -> 3.5, 3.5, 3.0. None si illisible.

    On resout par NOM et jamais par identifiant : ceux-ci sont propres a chaque
    setup ET a chaque base (`docs/edgewonk-api.md` §7). Et on PARSE le nom plutot que
    de comparer a une liste figee — « 3.5R » et « 3,5R » sont le meme palier, et
    un renommage cote Edgewonk ne doit pas casser silencieusement.
    """
    m = _R_DANS_NOM.search(nom or "")
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", "."))
    except ValueError:
        return None


# ------------------------------------------------------------------ management
# LE SEUL CHAMP DE TAGGING QUE CE MODULE ECRIT — et c'est une BRECHE assumee
# dans la liste des interdits du §0 d'`docs/edgewonk-api.md`, ouverte par l'utilisateur le
# 26/08/2026.
#
# Elle est legitime parce que la valeur vient de LUI : « ai-je touche a mon stop
# apres l'entree ? » est saisi a la main dans le fichier SL/TP, au meme titre que
# le stop lui-meme. On TRANSPORTE son jugement, on n'en fabrique aucun — c'est
# exactement ce que le reste de la liste protege.
#
# La breche est donc etroite, et doit le rester :
#   * `managementComments` UNIQUEMENT. `preTradeComments`, `entryComments`,
#     `exitComments`, `customComments` et `checklistItems` restent intouchables.
#   * on n'ecrit que si l'utilisateur a saisi OK ou KO. Case vide -> rien, dans aucun
#     sens, meme si le trade porte deja une valeur posee a la main.
#
# MESURE DU 26/08/2026, sur 202 trades : ce champ porte 0 ou 1 entree, jamais 2.
# Remplacer le tableau par un identifiant unique est donc sans perte. Si un
# trade en portait deux un jour, la relecture le dirait — elle compare les ids.
NOMS_MANAGEMENT = {"OK": "not managed", "KO": "managed"}

# Filet de secours si les NOMS ne repondent plus (l'utilisateur peut renommer ces
# deux options quand il veut : il l'a deja fait une fois, « Followed rules » ->
# « Not managed »). Le `rating` porte la SEMANTIQUE, pas l'etiquette : ne pas
# gerer sa position est POSITIVE, la gerer est NEGATIVE — c'est exactement la
# regle de l'utilisateur, « l'objectif c'est not managed ».
# Utilise seulement en second rang, et JAMAIS en silence : le repli est signale.
RATINGS_MANAGEMENT = {"OK": "POSITIVE", "KO": "NEGATIVE"}

TYPE_MANAGEMENT = "MANAGEMENT"


def options_management(commentaires=None, trades_distants=None):
    """({« OK »: id, « KO »: id}, notes) — les deux options de la famille Management.

    DEUX SOURCES, DANS CET ORDRE.

    1. **Le catalogue**, `GET /databases/{db}/comments` — trouve par mesure le
       26/08/2026 (`outils/diag_commentaires.py`). C'est la source de reference :
       elle liste les options QUI EXISTENT, qu'un trade les porte ou non.

    2. **Les trades lus**, en repli. Chaque `managementComments` est un objet
       {id, name}. Ca ne voit que ce qui est REELLEMENT POSE quelque part.
       ⚠️ Ce repli a une limite demontree : le 26/08, apres que l'utilisateur a
       nettoye ses champs Management d'aout, « Managed » n'etait plus portee par
       aucun des 238 trades. Le module a refuse d'ecrire les 23 positions KO —
       refus correct, mais qui n'aurait pas eu lieu d'etre avec le catalogue.

    Dans les deux cas on resout par NOM, jamais par identifiant en dur. Si le nom
    ne repond pas, on retombe sur le `rating`, et on le DIT.
    """
    notes = []

    if commentaires:
        actives = [c for c in commentaires
                   if (c.get("type") or "").upper() == TYPE_MANAGEMENT
                   and c.get("active") and c.get("id") is not None]
        par_nom = {(c.get("name") or "").strip().lower(): c["id"] for c in actives}
        par_rating = {}
        for c in actives:
            par_rating.setdefault((c.get("rating") or "").upper(), c)

        options = {}
        for saisi, nom in NOMS_MANAGEMENT.items():
            if nom in par_nom:
                options[saisi] = par_nom[nom]
                continue
            secours = par_rating.get(RATINGS_MANAGEMENT[saisi])
            if secours is not None:
                options[saisi] = secours["id"]
                # ⚠️ LE NOM DE L'OPTION VISEE EST DANS LA NOTE, ET CE N'EST PAS
                # DECORATIF. Mesure du 26/08/2026, journal futures 100004 : le
                # repli designait « Followed rules » / « Broke rules », les noms
                # Edgewonk par defaut. Mecaniquement sans ambiguite — une seule
                # option active par rating — mais SEMANTIQUEMENT faux : notre
                # champ dit « ai-je touche a mon stop », pas « ai-je respecte
                # mes regles ». Un trade ou l'utilisateur remonte son stop pour
                # verrouiller serait etiquete « Broke rules ».
                #
                # Sans le nom, la note ne montrait qu'un identifiant et le
                # contresens passait. Avec, il saute aux yeux. Le tagging est le
                # seul contenu du systeme qui ne soit pas reproductible : on ne
                # le remplit pas au jugé.
                notes.append(
                    "management : aucune option nommee « %s » — repli sur le "
                    "rating %s, c'est-a-dire « %s » (id %s). Verifier que ce "
                    "libelle veut bien dire la meme chose, ou le renommer cote "
                    "Edgewonk."
                    % (nom, RATINGS_MANAGEMENT[saisi],
                       (secours.get("name") or "?"), secours["id"]))
        return options, notes

    # --- repli : ce que portent les trades
    par_nom = {}
    for trade in (trades_distants or []):
        for o in (trade.get("managementComments") or []):
            if isinstance(o, dict) and o.get("id") is not None:
                par_nom[(o.get("name") or "").strip().lower()] = o["id"]
    return ({saisi: par_nom[nom] for saisi, nom in NOMS_MANAGEMENT.items()
             if nom in par_nom}, notes)


# ─────────────────────────────────────────────── LE SECOND CONTRÔLE DU MANAGEMENT
#
# L'utilisateur saisit OK (plan tenu) ou KO (position gérée) en regardant s'il a
# TOUCHÉ à son stop ou à sa cible après l'entrée — un trailing, un passage au
# break-even. C'est du jugement, et lui seul peut le rendre : ses logs de
# plateforme disent si un niveau a bougé de trois ticks ou trois fois.
#
# Mais sa question a un angle mort, et il l'a nommé lui-même : **il peut n'avoir
# rien bougé et avoir quand même fermé la position avant qu'un niveau soit
# touché.** Ça aussi, c'est gérer. Sa saisie dirait OK ; la vérité est KO.
#
# D'où un second contrôle, qui pose l'autre question : **est-il SORTI sur un de
# ses niveaux ?** Les deux ne se déduisent pas l'une de l'autre.
#
# ⚠️ LA RÈGLE EST ASYMÉTRIQUE, ET C'EST LA MÉCANIQUE DES ORDRES QUI LE VEUT.
# Mesure du 29/08/2026 sur 184 positions : la distance ABSOLUE à un niveau ne
# sépare rien — 29 sorties tombent exactement dessus, puis c'est un continuum
# sans trou jusqu'à 1 R. C'est le SIGNE qui tranche :
#
#     une LIMITE (le TP) se remplit à son prix ou MIEUX, jamais moins bien
#     un STOP se remplit à son prix ou PIRE — c'est le slippage
#
# Vérifié : près du TP, 4 sorties exactement dessus, 4 meilleures, 2 moins
# bonnes — ces 2-là ne sont donc PAS des fills de la limite. Près du SL, 25
# exactement dessus, 52 moins bonnes (slippage, attendu), 7 meilleures — ces
# 7-là ne sont pas des fills du stop.
#
# Le pire slippage mesuré vaut 0,2355 R, d'où la borne à 0,25.
SLIPPAGE_MAX_R = 0.25
MIEUX_MAX_R = 0.25


def sortie_sur_niveau(jambe, sortie_tenue=None):
    """La position est-elle sortie SUR son stop ou sa cible ?

    `sortie_tenue` : le prix de sortie de la jambe RÉELLEMENT TENUE de la
    position — la dernière. Absent, on prend celui de la jambe reçue.

    ⚠️ ON JUGE LA JAMBE TENUE, PAS CHAQUE JAMBE. Un allègement sort au marché
    par définition : le contrôler ferait basculer en « géré » toute position
    sortie en plusieurs fois. Or l'utilisateur l'a dit explicitement — alléger
    parce qu'on est entré trop lourd n'est pas du management. C'est la même
    règle que pour les graphiques (`rendu.jambe_reelle`), et pour la même
    raison : la jambe tenue est celle qui porte la décision.

    Retourne True, False, ou **None quand aucun niveau n'est saisi** — le
    contrôle est alors aveugle, et un contrôle aveugle ne doit pas accuser.
    """
    entree = _f(jambe.get("entree"))
    sortie = _f(sortie_tenue if sortie_tenue is not None else jambe.get("sortie"))
    sl, tp = _f(jambe.get("sl")), _f(jambe.get("tp"))
    if entree is None or sortie is None or (sl is None and tp is None):
        return None
    risque = abs(entree - sl) if sl is not None else abs(entree - tp)
    if not risque:
        return None
    achat = jambe.get("sens") == SENS_ACHAT

    if tp is not None:
        # > 0 : la sortie est MEILLEURE que la cible.
        # ⚠️ Sur un ACHAT, mieux que la cible veut dire PLUS HAUT ; sur une
        # vente, plus BAS. J'avais écrit l'inverse, et le jeu d'essai l'a dit
        # tout de suite : « sortie meilleure que le TP » ressortait en KO et
        # « moins bonne » en OK, exactement à l'envers. La branche SL, elle,
        # était juste — ce qui rendait l'erreur invisible sur la moitié des cas.
        ecart = ((sortie - tp) if achat else (tp - sortie)) / risque
        if -1e-9 <= ecart <= MIEUX_MAX_R:
            return True
    if sl is not None:
        # > 0 : la sortie est MEILLEURE que le stop — impossible pour un fill
        ecart = ((sortie - sl) if achat else (sl - sortie)) / risque
        if -SLIPPAGE_MAX_R <= ecart <= 1e-9:
            return True
    return False


def management_effectif(jambe, sortie_tenue=None):
    """(« OK » | « KO » | «  », note) — la saisie, corrigée par la sortie.

    ⚠️ LE CONTRÔLE NE PEUT QU'ACCUSER, JAMAIS DISCULPER. Un KO saisi reste KO :
    L'utilisateur a vu quelque chose dans ses logs que la sortie ne montre pas. Un
    OK ne devient KO que si la sortie prouve qu'il a fermé ailleurs que sur un
    niveau. L'automatisme ajoute du management, il n'en retire jamais.
    """
    saisi = (jambe.get("management") or "").strip().upper()
    if saisi not in NOMS_MANAGEMENT:
        return "", ""
    if saisi == MANAGEMENT_KO:
        return MANAGEMENT_KO, ""
    sur_niveau = sortie_sur_niveau(jambe, sortie_tenue)
    if sur_niveau is None:
        return MANAGEMENT_OK, ("aucun niveau saisi — le second contrôle du "
                               "management est aveugle sur cette position")
    if sur_niveau:
        return MANAGEMENT_OK, ""
    return MANAGEMENT_KO, ("saisi OK, mais la sortie ne tombe ni sur le stop ni "
                           "sur la cible — position fermee a la main, donc GEREE")


def management_a_ecrire(jambe, trade, options, sortie_tenue=None):
    """([id], note) — ou (None, note) s'il n'y a rien a ecrire.

    Ne renvoie une valeur que si elle DIFFERE de ce que porte deja le trade :
    l'idempotence evite de replanifier 200 champs a chaque cycle.
    """
    saisi, note = management_effectif(jambe, sortie_tenue)
    if not saisi:
        return None, ""                       # case vide : on ne touche a rien

    voulu = options.get(saisi)
    if voulu is None:
        # Echec BRUYANT et jamais silencieux : sans l'identifiant on ne devine
        # pas, on refuse d'ecrire et on le dit.
        return None, ("option « %s » (saisie %s) introuvable cote Edgewonk — "
                      "management non ecrit"
                      % (NOMS_MANAGEMENT[saisi], saisi))

    actuels = [o.get("id") if isinstance(o, dict) else o
               for o in (trade.get("managementComments") or [])]
    if actuels == [voulu]:
        return None, note
    return [voulu], note


def strategies_a_ecrire(trade, paliers, catalogue):
    """La valeur d'`alternativeStrategies` a poser, ou None s'il n'y a rien a changer.

    `paliers`   : {2.0: 2.0, 3.0: -1.0, ...} — produit par `bougies.paliers_depuis`
    `catalogue` : [{id, name, ...}] du setup, tel que renvoye par l'API

    ⚠️ ON NE TOUCHE QUE `rMultiple`. Le `gain` en devise est laisse tel quel :
    L'utilisateur l'a tranche, et nous n'avons pas de quoi le recalculer sans
    reconstruire un montant depuis des prix — precisement ce que la regle 5 du
    README interdit (`multiplier` vaut 1.0 chez Edgewonk, ce n'est pas la taille
    du contrat).
    """
    if not paliers or not catalogue:
        return None, []

    existantes = {s.get("strategyId"): dict(s)
                  for s in (trade.get("alternativeStrategies") or [])}
    voulu, notes, change = [], [], False

    for strategie in catalogue:
        palier = palier_du_nom(strategie.get("name"))
        sid = strategie.get("id")
        if palier is None:
            notes.append("strategie « %s » (id %s) : palier illisible dans le nom, ignoree"
                         % (strategie.get("name"), sid))
            continue
        if palier not in paliers:
            notes.append("strategie « %s » : palier %.4g hors de nos paliers simules, ignoree"
                         % (strategie.get("name"), palier))
            continue
        ligne = existantes.get(sid, {"strategyId": sid, "gain": None})
        ligne = dict(ligne)
        cible = paliers[palier]
        if _f(ligne.get("rMultiple")) is None or abs(_f(ligne.get("rMultiple")) - cible) > 1e-9:
            change = True
        ligne["rMultiple"] = cible
        voulu.append(ligne)

    # les strategies du trade qu'on n'a pas su rattacher : conservees telles quelles
    vus = {l["strategyId"] for l in voulu}
    for sid, ligne in existantes.items():
        if sid not in vus:
            voulu.append(ligne)

    return (voulu if change else None), notes


def preparer(couples, dossier_racine=None, catalogues=None, distants=None,
             commentaires=None, mode=MODE_ECRASER, champs=None,
             sorties_tenues=None):
    """Construit le plan d'ecriture. N'ecrit rien, ne contacte rien.

    `mode` : `MODE_ECRASER` (par defaut, le comportement historique) ecrit des
    qu'une valeur differe. `MODE_VIDE` n'ecrit que dans un champ qu'Edgewonk
    laisse vide — ce qui preserve toute correction faite a la main, captures
    comprises. C'est l'ancienne regle E1 du chantier retroactif, generalisee.

    `champs` : ensemble de cles de `CHAMPS_ECRITS`. `None` = tous.

    `sorties_tenues` : {cle_position: prix de sortie de la jambe TENUE}. Sert
    au second controle du management — sans lui, chaque allegement serait juge
    sur SA sortie au marche et basculerait en « gere ». L'appelant le calcule
    depuis la base complete, parce qu'ici on ne voit que les jambes appariees
    et qu'une position peut n'etre appariee qu'a moitie.

    `dossier_racine` : la racine de `donnees/`, pour resoudre les chemins de
    graphiques. Absent -> aucune image n'est planifiee (mode champs seuls).
    `commentaires` : le catalogue `GET /databases/{db}/comments`. C'est la BONNE
    source des options de la famille Management.
    `distants` : TOUS les trades Edgewonk lus — repli si le catalogue manque,
    avec le point aveugle decrit dans `options_management`.

    Retourne (plans, notes).
    """
    plans, notes = [], []
    options_mgmt, notes_mgmt_init = options_management(
        commentaires,
        distants if distants is not None else [t for _, _, t in couples])
    notes.extend(notes_mgmt_init)
    notes_mgmt = []
    for cle, jambe, trade in couples:
        modify, put = {}, {}
        for local, distant in CHAMPS:
            v = _f(jambe.get(local))
            if v is None:
                continue
            actuel = _f(trade.get(distant))
            if actuel is None or abs(actuel - v) > 1e-9:
                modify[distant] = v

        # --- strategies alternatives : soit le palier, soit -1 (voir
        #     ctrader/bougies.py). Le catalogue depend du SETUP du trade.
        if catalogues is not None:
            setup = trade.get("setup") or {}
            sid = setup.get("id") if isinstance(setup, dict) else setup
            catalogue = catalogues.get(sid) or []
            paliers = _paliers_de(jambe)
            voulu, notes_strat = strategies_a_ecrire(trade, paliers, catalogue)
            for x in notes_strat:
                notes.append("%s : %s" % (cle, x))
            if voulu is not None:
                put["alternativeStrategies"] = voulu

        # --- management : le seul champ de tagging qu'on ecrit (voir ci-dessus)
        mgmt, note_mgmt = management_a_ecrire(
            jambe, trade, options_mgmt,
            (sorties_tenues or {}).get(jambe.get("cle_position")))
        if note_mgmt:
            # ⚠️ DEUX SORTES DE NOTES, ET ELLES NE SE DEDUPLIQUENT PAS PAREIL.
            # « option introuvable cote Edgewonk » est un defaut GLOBAL : une
            # note par trade produirait 137 lignes identiques, il se dit une
            # fois. « saisi OK mais sorti ailleurs » est SPECIFIQUE a un trade :
            # le dedupliquer masquerait 18 corrections derriere une seule ligne.
            if note_mgmt.startswith("saisi OK"):
                notes.append("%s : %s" % (cle, note_mgmt))
            elif note_mgmt not in notes_mgmt:
                notes_mgmt.append(note_mgmt)
                notes.append(note_mgmt)
        if mgmt is not None:
            put["managementComments"] = mgmt

        tpf = jambe.get("tp_touche_en_premier")
        if tpf in ("oui", "non"):
            veut = (tpf == "oui")
            if trade.get("originalTpHit") != veut:
                put["originalTpHit"] = veut

        # --- break-even. `modify` IGNORE ce champ (mesure du 24/08), il faut le PUT.
        #
        # LE ROBOT FAIT AUTORITE, DANS LES DEUX SENS (arbitre le 25/08/2026).
        # Regle de l'utilisateur : « tout au-dessus de 0.3 R c'est un trade, point
        # barre ». Le seuil tranche seul, donc l'automation coche ET decoche,
        # y compris par-dessus une case posee a la main.
        #
        # Le garde-fou n'est plus le sens de l'ecriture, c'est le R : sans SL,
        # `est_break_even` renvoie None (regle R7) et on n'ecrit RIEN, ni dans
        # un sens ni dans l'autre. Les jambes non traitees gardent donc ce que
        # L'utilisateur y a mis a la main ; c'est la saisie du SL qui transfere
        # l'autorite au robot. Tout decochage est signale, jamais silencieux.
        be = est_break_even(jambe)
        if be is not None and bool(trade.get("ignoreForWinrate")) != be:
            put["ignoreForWinrate"] = be
            if be is False:
                notes.append("%s (id %s) : DECOCHE break-even — R = %+.2f, "
                             "au-dela du seuil de %.2f. Ecrase l'etat "
                             "precedent cote Edgewonk."
                             % (cle, trade.get("id"), r_realise(jambe),
                                R_BREAK_EVEN))

        # Prix d'execution divergents cote Edgewonk -> R faux quoi qu'on ecrive.
        divergent, detail = prix_divergents(jambe, trade)
        if divergent:
            if not trade.get("inReview"):
                modify["inReview"] = True
            notes.append(
                "%s (id %s) : prix d'execution divergents — %s. R faux cote "
                "Edgewonk quoi qu'on ecrive. Marque inReview."
                % (cle, trade.get("id"), detail))

        images = (images_a_envoyer(jambe, dossier_racine)
                  if dossier_racine else [])

        modify, put, images = filtrer_plan(modify, put, images, trade, mode, champs)

        if modify or put or images:
            plans.append({"cle": cle, "id": trade.get("id"), "jambe": jambe,
                          "modify": modify, "put": put, "images": images})
    return plans, notes


def envoyer_images(client, base_id, plans):
    """Televerse les PNG, pose les drapeaux, puis RELIT pour confirmer.

    Cede (indice, total, envoyees, echecs, cles_confirmees) apres chaque trade.

    `cles_confirmees` : les cles de jambe dont les images sont confirmees par
    relecture — c'est ce que l'appelant inscrit dans la colonne `screenshots`.
    Une image envoyee mais non confirmee n'y entre pas : au prochain passage on
    la renverra, ce qui est le bon defaut.

    On SUPPRIME avant d'envoyer. Un emplacement deja occupe par une image
    perimee (reprise d'une ancienne review, gabarit retouche depuis) doit etre
    remplace, pas double. Un emplacement vide repond 404, cas normal.
    """
    avec_images = [p for p in plans if p.get("images")]
    envoyees, echecs, confirmees = 0, [], []
    for i, p in enumerate(avec_images, 1):
        drapeaux, poses = {}, []
        for emplacement, chemin, nom in p["images"]:
            try:
                client.supprimer_image(base_id, p["id"], emplacement)
                client.televerser_image(
                    base_id, p["id"], emplacement, chemin,
                    description_image(p["jambe"], nom))
                drapeaux["screenshot%dExists" % emplacement] = True
                poses.append(emplacement)
            except Exception as e:                            # noqa: BLE001
                echecs.append("%s (id %s) %s : %s" % (p["cle"], p["id"], nom, e))

        if drapeaux:
            try:
                client.modifier(base_id, p["id"], drapeaux)
            except Exception as e:                            # noqa: BLE001
                echecs.append("%s (id %s) : drapeaux non poses (%s)" % (p["cle"], p["id"], e))
                yield i, len(avec_images), envoyees, echecs, confirmees
                continue

            # RELECTURE — un 200 ne prouve rien, `modify` a une liste blanche.
            relu = client.trade(base_id, p["id"])
            manquants = [e for e in poses
                         if not relu.get("screenshot%dExists" % e)]
            if manquants:
                echecs.append("%s (id %s) : emplacements %s non confirmes a la relecture"
                              % (p["cle"], p["id"], manquants))
            else:
                envoyees += len(poses)
                # ⚠️ On ne marque le trade QUE si les quatre images sont passees.
                # Trois sur quatre confirmees suffisaient dans une premiere
                # version : le trade etait inscrit « fait » dans la base et
                # l'image manquante n'etait PLUS JAMAIS renvoyee. Un trou
                # definitif, et silencieux. Tant qu'il manque un emplacement,
                # la colonne reste vide et tout le lot repart au prochain
                # passage — le DELETE prealable rend le renvoi sans effet de bord.
                #
                # ⚠️ ET « LES QUATRE » VEUT DIRE QUATRE, PAS « TOUTES CELLES
                # QU'ON AVAIT ». Corrige le 28/08/2026 : la comparaison portait
                # sur `len(p["images"])`, c'est-a-dire le nombre de PNG
                # PRESENTS SUR LE DISQUE. Une position rendue en 2 timeframes
                # sur 4 offrait 2 images, les 2 passaient, et le trade etait
                # marque « fait » — exactement le trou definitif et silencieux
                # que le paragraphe ci-dessus dit empecher. Le commentaire etait
                # juste, le code disait autre chose, et personne ne les avait
                # relus ensemble. Mesure : `20260817-091714-MGCQ6-A`, marque
                # complet avec H1 et H4 seuls, M5 et M15 jamais rendus.
                #
                # Consequence assumee : tant que les 4 PNG n'existent pas, le
                # trade repart a chaque poussee. C'est bruyant et c'est voulu —
                # `outils/diag_images.py` le nomme, et le DELETE prealable rend
                # le renvoi sans effet de bord.
                # On interroge la RELECTURE, pas le compte de ce qu'on
                # vient d'envoyer. Deux raisons legitimes de n'envoyer qu'une
                # partie du lot, et elles appellent des reponses opposees :
                #
                #   rendu partiel (un PNG manque)  -> NE PAS marquer, le trade
                #       doit repasser quand l'image existera ;
                #   regle E1 du chantier retroactif (un emplacement est deja
                #       occupe par une capture de l'utilisateur, on ne le touche
                #       pas) -> MARQUER, il n'y a plus rien a faire.
                #
                # Comparer a `len(p["images"])` acceptait les deux, comparer a
                # `len(EMPLACEMENTS)` les refusait toutes les deux. La question
                # juste n'est pas « combien en ai-je envoye » mais « les quatre
                # emplacements sont-ils occupes MAINTENANT » — et la relecture
                # est deja faite, ca ne coute rien.
                if all(relu.get("screenshot%dExists" % e) for _, e in EMPLACEMENTS):
                    confirmees.append(p["cle"])
        yield i, len(avec_images), envoyees, echecs, confirmees


def instantane(client, base_id, plans, dossier):
    """GET complet de chaque trade AVANT d'y toucher, ecrit sur disque.

    Regle non negociable : c'est ce qui a permis de remplir puis restaurer
    169 trades sans perdre une valeur.
    """
    if not os.path.isdir(dossier):
        os.makedirs(dossier)
    etat = {}
    for i, p in enumerate(plans, 1):
        etat[str(p["id"])] = client.trade(base_id, p["id"])
        yield i, len(plans)
    chemin = os.path.join(dossier, "edgewonk-%s-%s.json"
                          % (base_id, time.strftime("%Y%m%d-%H%M%S")))
    with io.open(chemin, "w", encoding="utf-8") as f:
        f.write(json.dumps(etat, ensure_ascii=False, indent=1))
    yield chemin, None


def appliquer(client, base_id, plans, charge_utile_put):
    """modify -> PUT -> RELECTURE. Retourne (ecrits, echecs, divergences).

    `divergences` : ce que la relecture n'a PAS confirme. Un 200 ne prouve
    rien — `modify` a une liste blanche et ignore le reste en silence.
    """
    ecrits, echecs, divergences = 0, [], []
    for i, p in enumerate(plans, 1):
        try:
            if p["modify"]:
                client.modifier(base_id, p["id"], p["modify"])
            if p["put"]:
                complet = client.trade(base_id, p["id"])
                client.remplacer(base_id, p["id"],
                                 charge_utile_put(complet, p["put"]))
        except Exception as e:                                # noqa: BLE001
            echecs.append("%s (id %s) : %s" % (p["cle"], p["id"], e))
            yield i, len(plans), ecrits, echecs, divergences
            continue

        # RELECTURE — la regle qui a fait ses preuves sur 338 ecritures
        relu = client.trade(base_id, p["id"])
        attendu = dict(p["modify"])
        attendu.update(p["put"])
        for champ, valeur in attendu.items():
            obtenu = relu.get(champ)
            if champ == "alternativeStrategies":
                # Le serveur NE PRESERVE PAS l'ordre de la liste — mesure le
                # 25/08/2026 : 6 relectures, 6 ordres differents, contenu
                # identique. Comparer des listes rendait ce champ
                # structurellement inconfirmable (_f() sur une liste renvoie
                # None, donc conforme=False a tous les coups). La cle metier
                # est le strategyId SEUL.
                #
                # ⚠️ Une premiere version indexait sur (strategyId, setupId).
                # Elle marchait par chance : les trades d'aout avaient deja des
                # strategies, dont le setupId etait recopie dans notre envoi.
                # Sur un trade dont la liste est VIDE, `strategies_a_ecrire`
                # n'ecrit aucun setupId — c'est le serveur qui le pose. La cle
                # etait alors introuvable et 124 ecritures parfaitement passees
                # etaient signalees comme divergentes (26/08/2026).
                # Le setupId est celui du trade, invariant : il n'a rien a faire
                # dans une cle d'identite de palier.
                # `rMultiple` seul est verifie — `gain` est une valeur qu'on
                # s'interdit de toucher, l'exiger ferait echouer la relecture
                # sur un champ qu'on n'a jamais ecrit.
                def _cle_strat(d):
                    return d.get("strategyId")
                att = {_cle_strat(d): _f(d.get("rMultiple")) for d in valeur}
                obt = {_cle_strat(d): _f(d.get("rMultiple"))
                       for d in (obtenu or [])}
                conforme = (att.keys() == obt.keys() and all(
                    att[k] is not None and obt[k] is not None
                    and abs(obt[k] - att[k]) < 1e-6 for k in att))
            elif champ == "managementComments":
                # Le GET renvoie des OBJETS la ou le PUT attend des ids : on
                # compare des ids a des ids. Meme regle que partout ici — un 200
                # ne prouve rien, seule la relecture compte.
                conforme = ([o.get("id") if isinstance(o, dict) else o
                             for o in (obtenu or [])] == list(valeur))
            elif isinstance(valeur, bool):
                # bool(obtenu) et non `obtenu == valeur` : Edgewonk renvoie
                # indifferemment False, None ou 0 pour une case non cochee.
                # Necessaire depuis que le break-even s'ecrit aussi a False.
                conforme = (bool(obtenu) == valeur)
            else:
                o = _f(obtenu)
                conforme = o is not None and abs(o - _f(valeur)) < 1e-6
            if conforme:
                ecrits += 1
            else:
                divergences.append("%s (id %s) : %s attendu %s, relu %s"
                                   % (p["cle"], p["id"], champ, valeur, obtenu))
        yield i, len(plans), ecrits, echecs, divergences
