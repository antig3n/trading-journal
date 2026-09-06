"""Les deux plateformes, et ce qui les distingue. Aucune dependance.

Ce module existe pour une raison simple : a partir du 26/08/2026 le pipeline
sert DEUX sources — cTrader (forex, Prop Firm A) et Tradovate (futures,
Prop Firm B). Tout ce qui differe entre elles est ici, et nulle part ailleurs. Le
reste du code demande « quelle plateforme ? » et n'a jamais a le deviner.

⚠️ C'EST L'UTILISATEUR QUI DECLARE, LE PROGRAMME NE RENIFLE PAS.

Decide le 26/08/2026 (`docs/tradovate.md` §9). Deviner le format d'un CSV marcherait
99 fois et casserait en silence la centieme, le jour ou un export changerait de
colonnes. Le lanceur demande `1` ou `2`, et c'est la reponse qui fait foi.

CE QUI DIFFERE VRAIMENT, ET CE QUI NE DIFFERE PAS

  differe : le lecteur d'export, la source de bougies, le journal Edgewonk
            vise, la segmentation des trades, et le fait que Tradovate porte
            deja ses SL/TP quand l'entree est passee a l'ATM.

  ne differe pas : la base locale, les controles de saisie, le calcul des
            extremes, les paliers, le rendu des graphiques, l'ecriture chez
            Edgewonk. Ces etapes ne connaissent que des jambes.

C'est ce partage qui rend la chaine Tradovate courte a ecrire : elle n'ajoute
qu'un lecteur et une source de prix.
"""

CTRADER = "ctrader"
TRADOVATE = "tradovate"

# La plateforme d'une ligne de base ANTERIEURE au 26/08/2026 est vide : la
# colonne n'existait pas. Toutes ces lignes viennent de cTrader — c'etait la
# seule source. On ne reecrit pas la base pour autant, on lit le vide comme
# cTrader. (Meme principe que la fusion non destructive : on ne touche pas a
# l'existant pour faire plaisir a un schema.)
DEFAUT = CTRADER

# Journaux Edgewonk. L'identifiant figure dans l'URL de chaque appel.
#
# ⚠️ LES DEUX PLATEFORMES VISENT LE MEME JOURNAL — mesure du 26/08/2026.
#
# `docs/tradovate.md` §5 designait 100004 (« Compte B ») comme le journal des
# futures, et ce n'etait pas une invention : 34 trades futures y repondent,
# apparies au centime. Mais `outils/diag_journaux.py` a montre le tableau
# complet, et il change la conclusion :
#
#   100001  « Compte A »   240 trades, 15/10/2025 -> 26/08/2026
#                                   dont 36 FUTURES · Management « Not managed »
#                                   / « Managed »
#   100004  « Compte B »       34 trades, 06/08 -> 21/08, tous futures
#                                   Management « Followed rules » / « Broke rules »
#   100006  « [all] Missed trades »  14 trades EURUSD
#
#   -> aucun identifiant commun : ce sont des COPIES, pas le meme trade.
#
# Les futures vivent donc dans les DEUX, et 100004 s'arrete au 21/08 tandis que
# 100001 va jusqu'au 26/08 : l'import Tradovate a ete rebranche sur le journal
# principal, et 100004 est un vestige que l'utilisateur n'ouvre plus. C'est lui qui
# l'a dit, et la mesure lui donne raison.
#
# Consequence directe et heureuse : dans 100001 les options Management portent
# les BONS noms, donc plus de repli par rating, donc plus de risque d'ecrire
# « Broke rules » la ou on veut dire « Managed ».
#
# *Ce que ca coute de l'avoir cru : rien — aucune ecriture n'avait ete faite.
# `docs/tradovate.md` §5 avait mesure ce qu'il voyait, sur le seul journal qu'il
# avait regarde. Un echantillon d'un ne fait pas une regle non plus.*
# ⚠️ VALEUR D'EXEMPLE. Remplace par l'identifiant de TON journal Edgewonk :
# il figure dans l'URL de l'application une fois le journal ouvert.
BASE_PRINCIPALE = "100001"

# ⚠️ Le bac a sable 100005 « Overall » N'EXISTE PLUS : `GET /databases` n'en
# liste que trois, et il n'en fait pas partie. Constate le 26/08/2026. Les deux
# graphiques de test qu'il portait — trade 17860734, emplacements 1 et 2 — sont
# partis avec lui : le point ouvert du §4 du README est clos par disparition.
#   -> `--base <id>` reste disponible pour viser un autre journal, mais il n'y a
#      plus de bac a sable a viser. Le garde-fou est ailleurs : instantane avant
#      ecriture, et relecture apres.
BASE_BAC_A_SABLE = None

PLATEFORMES = {
    CTRADER: {
        "nom": "cTrader",
        "detail": "forex — Prop Firm A",
        "base_edgewonk": BASE_PRINCIPALE,
        "bougies": "serveur MCP local cTrader",
        # Un seul fichier a deposer : le releve.
        "exports": ("releve",),
        # ⚠️ VALEUR D'EXEMPLE. Remplace par ton numero de compte cTrader :
        # c'est lui qui figure dans le nom des exports (cT_<compte>_...csv).
        "compte": "1234567",
        # cTrader : Edgewonk stocke le symbole du broker, suffixe compris.
        # Mesure du 25/08/2026, 44 jambes appariees sans ambiguite.
        "instrument_edgewonk": "symbole_broker",
    },
    TRADOVATE: {
        "nom": "Tradovate",
        "detail": "futures — Prop Firm B",
        # ⚠️ Edgewonk stocke le PRODUIT (« MNQ »), pas le contrat (« MNQU6 »).
        # Mesure du 26/08/2026 sur le journal 100004 : MGC, MNQ, 6E, NQ, GC,
        # MCL. Cote cTrader il stocke le symbole du broker tel quel. C'est la
        # colonne `symbole` qui porte le produit, `symbole_broker` le contrat.
        "instrument_edgewonk": "symbole",
        # Le meme journal que le forex : c'est la que l'auto-import Tradovate
        # depose desormais, et c'est le seul que l'utilisateur ouvre.
        "base_edgewonk": BASE_PRINCIPALE,
        "bougies": "Databento GLBX.MDP3",
        # UN SEUL fichier — renverse par la mesure du 26/08/2026.
        #
        # `docs/tradovate.md` §5 bis tenait « Position History » pour la piece
        # maitresse, seule porteuse de l'appariement FIFO. Mesure : l'export
        # « Orders » porte l'heure, la quantite, le prix moyen et le notionnel
        # de chaque ordre rempli — de quoi refaire cet appariement soi-meme, et
        # le refaire exactement. Verifie au centime contre cinq trades reels du
        # journal 100004.
        #
        # Un fichier de moins a exporter, a nommer et a confondre.
        "exports": ("orders",),
        # ⚠️ VALEUR D'EXEMPLE. Remplace par ton identifiant de compte Tradovate.
        "compte": "DEMO0000000000001",
    },
}


def normaliser(valeur):
    """Une valeur de colonne -> une plateforme connue. Le vide vaut cTrader."""
    t = (valeur or "").strip().lower()
    return t if t in PLATEFORMES else DEFAUT


def nom(plateforme):
    return PLATEFORMES[normaliser(plateforme)]["nom"]


def base_edgewonk(plateforme):
    return PLATEFORMES[normaliser(plateforme)]["base_edgewonk"]


def colonne_instrument(plateforme):
    """La colonne de la base qui porte le nom d'instrument d'Edgewonk.

    C'est le SEUL element de la cle d'appariement qui differe d'une plateforme
    a l'autre — mesure des deux cotes, jamais generalise de l'un a l'autre.
    """
    return PLATEFORMES[normaliser(plateforme)]["instrument_edgewonk"]


def est(trade, plateforme):
    """Cette ligne de base appartient-elle a cette plateforme ?

    Passe par `normaliser`, donc une ligne d'avant le 26/08 (colonne vide)
    repond bien « cTrader ».
    """
    return normaliser(trade.get("plateforme")) == normaliser(plateforme)


def filtrer(trades, plateforme):
    """{cle: trade} restreint a une plateforme.

    ⚠️ INDISPENSABLE a l'etape 5. `apparier` compare TOUTE la base aux trades
    d'UN journal Edgewonk : sans ce filtre, les 46 jambes cTrader seraient
    cherchees dans le journal futures et inversement — 100 % de « non trouves »,
    et le vrai probleme noye dans le bruit.
    """
    return {c: t for c, t in trades.items() if est(t, plateforme)}
