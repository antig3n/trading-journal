"""Le modèle de trade et les clés canoniques. Aucune dépendance externe.

GRAIN DE LA BASE — révisé le 25/08/2026, sur mesure.

    Une ligne = une JAMBE = une ligne du relevé cTrader = UN trade Edgewonk.

Fait mesuré sur un relevé réel de 46 lignes, confirmé dans Edgewonk : Edgewonk
crée un trade par SORTIE partielle, pas par position. Les 4 sorties de la
position du 07/08 13:43 (nets 12.00, 1.50, 1.50, 302.00) sont 4 trades Edgewonk
distincts, montants concordants à l'unité. Agréger en positions désalignait la
base de 8 trades sur 46 et rendait l'appariement structurellement impossible.

    * `cle`          identifie la JAMBE — s'apparie 1:1 avec un trade Edgewonk
    * `cle_position` regroupe les jambes d'une même position cTrader

La position reste une notion utile : c'est elle qui porte la protection, donc
la saisie manuelle du SL/TP (une position = un SL = un TP). Le programme
réplique ensuite la valeur sur chacune de ses jambes.

Mesuré aussi, et c'est ce qui rend l'appariement possible : l'horodatage de
sortie à la SECONDE suffit à distinguer les jambes (46/46 uniques). Le prix de
sortie, lui, ne suffit pas (44/46) — deux sorties partielles peuvent partager
prix ET quantité ET montant, et ne se distinguer que par l'heure. D'où le
suffixe `#HHMMSS`.
"""

import re
import unicodedata

# ---------------------------------------------------------------- colonnes
# Ordre figé : il définit la base locale. On ajoute EN FIN de liste, jamais au
# milieu.
#
# EXCEPTION assumée le 25/08/2026 : le passage au grain « jambe » a réordonné
# cette liste. C'était sans risque — la base venait d'être créée et se rejoue
# intégralement depuis `donnees/brut/`, qui n'a pas bougé. Ne pas rejouer cette
# exception sans la même garantie.
COLONNES = [
    "cle",                    # LA JAMBE : 20260807-134318-EURUSD-A#143001
    "cle_position",           # la position qui la porte : 20260807-134318-EURUSD-A
    "compte",                 # numéro de compte lu dans le nom du fichier d'export
    "symbole",                # symbole nu, ex. XAUUSD — pour l'œil
    "symbole_broker",         # symbole tel qu'exporté, ex. XAUUSD.raw — POUR LE MCP
    "sens",                   # Achat | Vente
    "ouverture",              # ISO 8601 avec décalage — commun à toute la position
    "cloture",                # ISO 8601 — PROPRE À LA JAMBE
    "entree",                 # VWAP d'entrée de la position, tel que fourni par l'export
    "sortie",                 # prix de sortie de CETTE jambe
    "volume_lots",            # quantité clôturée par CETTE jambe
    "nb_jambes",              # nombre de jambes de la position — 1 dans 34 cas sur 38
    "swaps",                  # les quatre montants sont ceux de CETTE jambe
    "commission",
    "brut",
    "net",
    # --- saisie manuelle (étape 2), saisie PAR POSITION puis répliquée
    "sl",
    "tp",
    # --- extraction bougies (étape 3) — PAR JAMBE : la fenêtre entrée→sortie
    #     diffère d'une jambe à l'autre, donc les extrêmes aussi.
    "prix_plus_haut",
    "prix_plus_bas",
    "tp_touche_en_premier",
    # --- rendu (étape 4) — par jambe, chaque trade Edgewonk ayant ses emplacements
    "chemin_graphiques",
    # --- appariement (étape 5) : résultat, jamais une entrée du raisonnement.
    #     On l'écrit pour que le lien jambe → trade Edgewonk soit relisible.
    "id_edgewonk",
    # --- traçabilité
    "source_brut",
    # --- simulation des stratégies alternatives (étape 3). Le prix le plus
    #     favorable atteint AVANT que le SL ne tombe, borné au niveau 5R.
    #     Un PRIX, pas un R-multiple : les R se recalculent depuis l'entrée et
    #     le SL, un prix stocké ne diverge jamais. Vide = non résolu (bougies
    #     encore indisponibles), le trade repassera au cycle suivant.
    "prix_max_favorable",
    # --- envoi des captures (étape 5). La base locale est la référence : c'est
    #     ELLE qui dit si les images sont à jour chez Edgewonk, pas le drapeau
    #     `screenshot{n}Exists` de leur côté. Deux raisons, mesurées à l'usage :
    #     leur drapeau reste vrai quand l'image est périmée (reprise d'une vieille
    #     review), et interroger un système externe pour savoir s'il est à jour
    #     inverse le principe du projet.
    #     Vide -> à envoyer, en écrasant l'emplacement. Rempli -> déjà fait.
    #     `jt.py graphiques --refaire` le vide, ce qui déclenche le ré-envoi.
    "screenshots",
    # --- saisie manuelle (etape 2), PAR POSITION comme le SL/TP.
    #     « Ai-je touche a mon stop ou a ma cible apres l'entree ? »
    #     OK = non, le plan a ete tenu (« Not managed » cote Edgewonk)
    #     KO = oui, la position a ete geree (« Managed »)
    #
    #     Deux lettres, saisies en meme temps que le SL et le TP : l'information
    #     existe au moment ou l'utilisateur a le trade sous les yeux, et se perd si on
    #     la remet a plus tard. Vide = on n'ecrit rien — meme regle que le SL.
    "management",
    # --- la source du trade. Ajoutee le 26/08/2026, quand Tradovate a rejoint
    #     cTrader dans la meme base.
    #
    #     Une case VIDE vaut cTrader : les 203 jambes anterieures a cette date
    #     viennent toutes de la, c'etait la seule source. On ne reecrit pas la
    #     base pour lui faire plaisir — `core/plateformes.normaliser` lit le
    #     vide comme il faut, partout.
    #
    #     ⚠️ Cette colonne n'est pas decorative : c'est elle qui dit a l'etape 3
    #     quelle source de bougies interroger, et a l'etape 5 quel journal
    #     Edgewonk viser. Sans elle, les jambes forex seraient cherchees dans le
    #     journal futures.
    "plateforme",
]

SENS_ACHAT = "Achat"
SENS_VENTE = "Vente"


def symbole_nu(symbole_broker):
    """XAUUSD.raw -> XAUUSD. Le suffixe dépend du broker, on ne le devine pas.

    ⚠️ Pour le MCP cTrader, c'est `symbole_broker` qu'il faut passer, PAS ce
    symbole nu : mesuré le 25/08/2026, `get_symbols` sur le compte Prop Firm A
    répond « XAUUSD.raw ». Le « XAUUSD » du compte démo était un artefact du
    compte démo.
    """
    return symbole_broker.split(".")[0].strip().upper()


def _ascii(txt):
    txt = unicodedata.normalize("NFKD", txt)
    return "".join(c for c in txt if not unicodedata.combining(c))


def _horo(iso):
    """2026-08-07T13:43:18.644+02:00 -> ('20260807', '134318')"""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})", iso)
    if not m:
        raise ValueError("horodatage illisible : %r" % iso)
    return "".join(m.groups()[:3]), "".join(m.groups()[3:])


def construire_cle_position(ouverture_iso, symbole_broker, sens):
    """20260807-134318-EURUSD-A

    Identifie la POSITION : ce qui porte la protection, donc la saisie SL/TP.
    Toutes les jambes d'une même position partagent cette clé.

    Contient des lettres, donc un tableur la traite comme du texte et n'y touche
    pas.
    """
    jour, heure = _horo(ouverture_iso)
    lettre = "A" if sens == SENS_ACHAT else "V"
    return "%s-%s-%s-%s" % (jour, heure, _ascii(symbole_nu(symbole_broker)), lettre)


def construire_cle_jambe(cle_position, cloture_iso):
    """20260807-134318-EURUSD-A#143001

    Identifie la JAMBE, donc UN trade Edgewonk. L'heure de sortie est le
    discriminant : mesuré unique sur 46/46 jambes, là où le prix de sortie
    échoue sur 44/46.
    """
    _, heure = _horo(cloture_iso)
    return "%s#%s" % (cle_position, heure)


def trade_vide():
    return {c: "" for c in COLONNES}
