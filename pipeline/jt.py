#!/usr/bin/env python3
"""jt — journal de trading, chaîne locale.

    jt.py importer <relevé.csv>     étape 1 : archive le brut, alimente la base,
                                              génère le fichier de saisie
                                              (sl · tp · management)
    jt.py controler <saisie.csv>    contrôle la saisie, n'écrit rien
    jt.py integrer  <saisie.csv>    contrôle puis réplique le SL/TP sur les jambes
    jt.py bougies                   étape 3 : extrêmes et TP-first via le MCP
    jt.py graphiques [--refaire]    étape 4 : M5 + M15 + H1 + H4, par position
                                    --refaire : régénère tout, même l'existant
                                    (à utiliser après un ajustement du gabarit)
    jt.py pousser [--base <id>]     étape 5 : écrire dans Edgewonk
                                    --base pour viser le bac à sable 100005
    jt.py etat                      résumé de la base

    --tradovate                     sur N'IMPORTE QUELLE commande : viser les
                                    futures au lieu du forex. Change le lecteur
                                    d'export, la source de bougies (Databento
                                    au lieu du MCP cTrader) et le journal
                                    Edgewonk. Par défaut : cTrader.

                                    jt.py importer --tradovate <orders.csv>
                                    jt.py bougies --tradovate

La base locale est la référence. Edgewonk n'en est qu'un consommateur.

Grain : une ligne de base = une JAMBE = un trade Edgewonk. La saisie SL/TP se
fait au niveau de la POSITION, puis se réplique sur ses jambes.
"""

import os
import shutil
import sys
import time

RACINE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RACINE)

from core import base, plateformes as pf, saisie   # noqa: E402
from edgewonk import ecriture                      # noqa: E402
from ctrader import bougies as mod_bougies          # noqa: E402
from ctrader import statement                      # noqa: E402
from ctrader.mcp import Client, ErreurMCP           # noqa: E402
from databento import client as databento           # noqa: E402
from tradovate import statement as statement_tradovate   # noqa: E402

ERREURS_BOUGIES = (ErreurMCP, databento.ErreurDatabento,
                   mod_bougies.ReponseIllisible)

# Posee une fois par `main`, depuis `--tradovate`. Meme raison que dans
# `sync.py` : la plateforme ne change pas pendant une execution, et la passer en
# argument a chaque verbe aurait modifie sept signatures pour rien.
PLATEFORME = pf.CTRADER

# La borne de travail et le journal visé, posés une fois par `main` depuis
# `--periode` et `--journal`. Même raison que PLATEFORME : ils ne changent pas
# pendant une exécution, et les passer en argument aurait modifié sept
# signatures pour rien.
PERIODE = (None, None)
JOURNAL = None


def _borner(trades, quoi="jambes"):
    """Restreint un lot à PERIODE, et le DIT. Une borne silencieuse est un
    piège : on croit voir toute la base et on n'en voit qu'un jour."""
    debut, fin = PERIODE
    if not debut:
        return trades
    lot = base.filtrer_periode(trades, debut, fin)
    print("période %s : %d %s sur %d"
          % (base.libelle_periode(debut, fin), len(lot), quoi, len(trades)))
    return lot


def source_bougies():
    """Le client de bougies de la plateforme courante — meme interface."""
    if PLATEFORME == pf.TRADOVATE:
        return databento.Client(cache=os.path.join(DONNEES, "bougies")).ouvrir()
    return Client().ouvrir()

DONNEES = os.path.normpath(os.path.join(RACINE, "..", "donnees"))
BRUT = os.path.join(DONNEES, "brut")
TRADES = os.path.join(DONNEES, "trades.csv")
SAISIES = os.path.join(DONNEES, "saisies")


def _titre(txt):
    print("\n" + txt)
    print("-" * len(txt))


def _bloc(titre, items, limite=None):
    if not items:
        return
    _titre("%s (%d)" % (titre, len(items)))
    montres = items if limite is None else items[:limite]
    for i in montres:
        print("  " + i)
    if limite is not None and len(items) > limite:
        print("  … et %d autres" % (len(items) - limite))


def _archiver(chemin):
    archive = os.path.join(BRUT, "%s_%s" % (time.strftime("%Y%m%d-%H%M%S"),
                                            os.path.basename(chemin)))
    shutil.copy2(chemin, archive)
    print("brut archivé : %s" % os.path.relpath(archive, DONNEES))
    return archive


def importer(chemins):
    """Étape 1. UN fichier de chaque cote : le releve cTrader, ou l'export
    « Orders » de Tradovate.

    Cote Tradovate, un seul export suffit — mesure le 26/08/2026 : l'appariement
    FIFO se refait depuis les ordres remplis et reproduit au centime le
    decoupage d'Edgewonk. Le meme fichier porte les brackets ATM.
    """
    attendus = len(pf.PLATEFORMES[PLATEFORME]["exports"])
    if len(chemins) != attendus:
        sys.exit("%s attend %d fichier(s) : %s"
                 % (pf.nom(PLATEFORME), attendus,
                    " ".join(pf.PLATEFORMES[PLATEFORME]["exports"])))
    for c in chemins:
        if not os.path.exists(c):
            sys.exit("export introuvable : %s" % c)

    for d in (BRUT, SAISIES):
        if not os.path.isdir(d):
            os.makedirs(d)

    # 1. archiver le brut AVANT toute lecture : c'est la seule chose non
    #    reconstructible du systeme.
    archives = [_archiver(c) for c in chemins]

    suggestions = {}
    if PLATEFORME == pf.TRADOVATE:
        try:
            trades, anomalies = statement_tradovate.lire(archives[0])
        except statement_tradovate.ErreurExport as e:
            sys.exit(str(e))
        suggestions, notes = statement_tradovate.suggestions_sltp(trades, archives[0])
        anomalies = anomalies + notes
    else:
        trades, anomalies = statement.lire(archives[0])

    positions_lues = len({t["cle_position"] for t in trades})
    print("export lu    : %d jambes, %d positions" % (len(trades), positions_lues))
    _bloc("Anomalies de lecture", anomalies, limite=20)

    existants = base.charger(TRADES)
    fusion, ajoutes, completes, inchanges = base.fusionner(existants, trades)
    copie = base.ecrire(TRADES, fusion)

    _titre("Base")
    print("  ajoutés    : %d" % len(ajoutes))
    print("  complétés  : %d" % len(completes))
    print("  inchangés  : %d" % len(inchanges))
    print("  total      : %d jambes" % len(fusion))
    if copie:
        print("  instantané : %s" % os.path.relpath(copie, DONNEES))

    # 2. fichier de saisie, borné aux positions de CET export.
    #    On se fonde sur les clés que l'export vient de produire, PAS sur
    #    `source_brut` : la fusion garde le premier relevé qui a fait naître un
    #    trade, donc un ré-import ne se retrouverait dans aucune source.
    cles = {t["cle"] for t in trades}
    positions = base.grouper_en_positions(fusion, cles)
    fichier = os.path.join(SAISIES, "sltp_%s.csv" % time.strftime("%Y%m%d-%H%M%S"))
    n = saisie.generer(positions, fichier, suggestions)

    a_remplir = sum(1 for p in positions.values() if not p["sl"] and not p["tp"])
    _titre("À toi")
    print("  fichier    : %s" % fichier)
    print("  %d positions, dont %d à remplir" % (n, a_remplir))
    if suggestions:
        print("  %d position(s) ont leur SL/TP pré-remplis depuis l'export" % len(suggestions))
    print("  Remplis les colonnes sl, tp et management, puis :")
    print("    python3 jt.py controler %s" % fichier)


def _positions_concernees(trades, lignes):
    """Borne le contrôle d'exhaustivité au(x) relevé(s) d'où sortent ces positions.

    Sans cette borne, chaque contrôle signalerait toutes les positions des
    semaines précédentes comme « sans ligne de saisie ».
    """
    cps = {(r.get("cle_position") or "").strip() for r in lignes}
    sources = {t.get("source_brut") for t in trades.values()
               if t.get("cle_position") in cps and t.get("source_brut")}
    cles = {c for c, t in trades.items() if t.get("source_brut") in sources}
    return base.grouper_en_positions(trades, cles or None)


def _controler(chemin):
    if not os.path.exists(chemin):
        sys.exit("fichier de saisie introuvable : %s" % chemin)
    trades = base.charger(TRADES)
    if not trades:
        sys.exit("la base est vide — importer un relevé d'abord")
    lignes = saisie.lire(chemin)
    positions = _positions_concernees(trades, lignes)
    valides, rejets, signalements = saisie.controler(lignes, positions)

    _bloc("REJETS — ces lignes ne seront pas écrites", rejets)
    _bloc("Signalements — à valider par toi", signalements, limite=40)
    _titre("Résumé")
    print("  lignes lues     : %d" % len(lignes))
    print("  prêtes à écrire : %d positions" % len(valides))
    print("  rejets          : %d" % len(rejets))
    print("  signalements    : %d" % len(signalements))
    return trades, positions, valides, rejets, signalements


def controler(chemin):
    _, _, valides, rejets, _ = _controler(chemin)
    if not rejets and valides:
        print("\n  Rien de bloquant. Pour écrire :")
        print("    python3 jt.py integrer %s" % chemin)


def integrer(chemin):
    trades, positions, valides, rejets, _ = _controler(chemin)
    if rejets:
        sys.exit("\nRien n'a été écrit : corrige les rejets d'abord.")
    if not valides:
        sys.exit("\nAucune ligne à écrire.")

    valeurs, jambes, nb_pos = saisie.appliquer(trades, positions, valides)
    copie = base.ecrire(TRADES, trades)
    _titre("Écrit")
    print("  %d valeurs sur %d jambes, depuis %d positions" % (valeurs, jambes, nb_pos))
    if copie:
        print("  instantané : %s" % os.path.relpath(copie, DONNEES))


def bougies():
    """Étape 3 en ligne de commande. Même code que l'assistant, sans les questions."""
    trades = base.charger(TRADES)
    # Une jambe est a traiter si elle a un SL et qu'il lui manque SOIT ses
    # extremes, SOIT sa simulation de paliers. Le second cas compte : une
    # simulation non resolue (bougies pas encore disponibles) laisse la colonne
    # vide, et doit etre retentee au cycle suivant.
    # Filtre par plateforme : une jambe forex n'a rien a demander a Databento,
    # et une jambe futures rien a demander au MCP cTrader.
    # ⚠️ LES EXTREMES NE DEPENDENT PAS DU SL — corrige le 26/08/2026, sur une
    # remarque de l'utilisateur, et elle est juste.
    #
    # Cette selection exigeait un SL pour tout. C'etait un raccourci hérité de
    # cTrader, ou une jambe sans SL etait simplement une jambe pas encore
    # saisie : le SL servait de marqueur « pret », pas de prerequis.
    #
    # Le plus haut et le plus bas entre l'entree et la sortie sont des FAITS,
    # lus dans les bougies. Ils alimentent `updraw` / `drawDown` chez Edgewonk,
    # qui sont des PRIX, pas des R. La regle R7 — « pas de SL, pas de R » — porte
    # sur les R-multiples, jamais sur le MAE/MFE.
    #
    # Ce qui exige VRAIMENT un SL, et reste donc conditionne :
    #   `prix_max_favorable` et les paliers  (une simulation a besoin du stop)
    #   `tp_touche_en_premier`               (« avant le stop » — sans stop, la
    #                                         question n'a pas de sens)
    #   `ignoreForWinrate`                   (un R, donc un risque)
    #   le comptage des debordements de bord (mesure EN R)
    #
    # Cote futures, 28 positions sur 35 sont des entrees posees au graphique
    # sans protection lisible : elles restaient sans extremes et sans le moindre
    # graphique. Elles n'ont pas de R, elles ont une histoire.
    a_faire = {c: t for c, t in _borner(pf.filtrer(trades, PLATEFORME)).items()
               if (not t.get("prix_plus_haut"))
               or (t.get("sl") and not t.get("prix_max_favorable"))
               or (t.get("sl") and t.get("tp") and not t.get("tp_touche_en_premier"))}
    if not a_faire:
        print("rien a calculer : les jambes avec SL ont leurs extremes et leurs paliers")
        return
    positions = base.grouper_en_positions(trades, set(a_faire))
    print("%d jambes sur %d positions" % (len(a_faire), len(positions)))
    try:
        client = source_bougies()
    except ERREURS_BOUGIES as e:
        sys.exit(str(e))
    print("source de bougies : %s" % pf.PLATEFORMES[PLATEFORME]["bougies"])
    maj_totale, notes, bords, echecs = {}, [], [], []
    total = len(positions)
    for i, cp in enumerate(sorted(positions), 1):
        # Une position = une requete de bougies, et une longue position en
        # demande plusieurs. Sans ce retour, l'attente ressemble a un blocage.
        sys.stdout.write("\r  %d/%d  %-30s" % (i, total, cp))
        sys.stdout.flush()
        try:
            maj, n, b = mod_bougies.traiter_position(client, positions[cp], trades)
        except ERREURS_BOUGIES as e:
            echecs.append("%s : %s" % (cp, str(e).splitlines()[0]))
            continue
        maj_totale.update(maj)
        notes += n
        bords += b
    sys.stdout.write("\r  %d/%d positions traitees%s\n" % (total, total, " " * 20))
    _bloc("Echecs", echecs)
    _bloc("Signalements", notes, limite=20)
    if bords:
        _titre("Debordements de bord >= %.2f R (%d)" % (mod_bougies.R_ECART_BORD, len(bords)))
        for c, e in sorted(bords, key=lambda x: -x[1]):
            print("  %-34s %+.2f R" % (c, e))
    ecrits = 0
    for cle, valeurs in maj_totale.items():
        t = trades.get(cle)
        if t is None:
            continue
        for champ, v in valeurs.items():
            if v != "" and t.get(champ) != v:
                t[champ] = v
                ecrits += 1
    copie = base.ecrire(TRADES, trades)
    _titre("Ecrit")
    print("  %d valeurs sur %d jambes" % (ecrits, len(maj_totale)))
    if hasattr(client, "resume"):
        print("  %s" % client.resume())
    if copie:
        print("  instantane : %s" % os.path.relpath(copie, DONNEES))


def graphiques(refaire=False):
    """Étape 4 en ligne de commande. Demande .venv (matplotlib).

    `refaire` régénère les graphiques déjà produits : c'est ce qu'on lance après
    avoir touché au gabarit, sinon les anciens rendus resteraient en place et on
    comparerait des images faites avec deux versions différentes.
    """
    try:
        from graphiques import rendu
    except ImportError as e:
        sys.exit("matplotlib/mplfinance indisponibles (%s)\n"
                 "  lancer via .venv/bin/python3 — voir le README, §5.2." % e)
    trades = base.charger(TRADES)
    # La selection se fait par POSITION, en interrogeant la jambe reellement
    # tenue : c'est la seule qui porte `chemin_graphiques`. Filtrer sur « les
    # jambes sans graphique » relancerait indefiniment les positions multiples.
    positions = base.grouper_en_positions(_borner(pf.filtrer(trades, PLATEFORME)))
    a_rendre = [cp for cp in sorted(positions)
                if rendu.position_a_rendre(trades, cp, refaire)]
    if not a_rendre:
        print("rien a rendre : les positions calculees ont deja leurs graphiques")
        print("  (--refaire pour les regenerer apres un ajustement du gabarit)")
        return
    if refaire:
        print("MODE --refaire : les graphiques existants seront ecrases")
    print("%d position(s) a rendre, %d images" % (len(a_rendre),
                                                  len(a_rendre) * len(rendu.TIMEFRAMES)))
    try:
        client = source_bougies()
    except ERREURS_BOUGIES as e:
        sys.exit(str(e))
    print("source de bougies : %s" % pf.PLATEFORMES[PLATEFORME]["bougies"])

    racine = os.path.join(DONNEES, "graphiques")
    produits, notes = {}, []
    for i, cp in enumerate(a_rendre, 1):
        p, n = rendu.graphiques_de_position(client, positions[cp], trades, racine)
        produits.update(p)
        notes += n
        sys.stdout.write("\r  %d/%d  %-34s" % (i, len(a_rendre), cp))
        sys.stdout.flush()
    sys.stdout.write("\r  %d/%d positions traitees%s\n" % (len(a_rendre), len(a_rendre), " " * 24))
    _bloc("Signalements", notes, limite=15)
    if not produits:
        sys.exit("aucun graphique produit")
    reenvoyer = 0
    for cle, dossier in produits.items():
        if cle in trades:
            trades[cle]["chemin_graphiques"] = os.path.relpath(dossier, DONNEES)
            # Les PNG viennent de changer : ceux deja poses chez Edgewonk sont
            # perimes. On vide la colonne, qui n'est plus qu'une trace du
            # dernier envoi confirme.
            #
            # ⚠️ CA NE SUFFIT PLUS A LES FAIRE REPARTIR *(29/08/2026)*. La
            # colonne a cesse d'etre un verrou : c'est le MODE qui decide, et
            # « ne remplir que le vide » ne touchera pas un emplacement occupe
            # chez eux, meme perime. Apres une retouche du gabarit, le renvoi
            # se demande — `pousser --mode ecraser --champs images`.
            if (trades[cle].get("screenshots") or "").strip():
                trades[cle]["screenshots"] = ""
                reenvoyer += 1
    copie = base.ecrire(TRADES, trades)
    if reenvoyer:
        print("  %d trade(s) ont des captures perimees chez Edgewonk" % reenvoyer)
        print("  -> pousser --mode ecraser --champs images pour les renvoyer")
    _titre("Rendu")
    # On compte les PNG sur le disque, jamais positions x 4 : un timeframe qui
    # echoue ferait mentir le total.
    images = sum(rendu.images_presentes(d) for d in produits.values())
    attendues = len(produits) * len(rendu.TIMEFRAMES)
    print("  %d position(s), %d image(s)%s"
          % (len(produits), images,
             "" if images == attendues else "  (sur %d attendues)" % attendues))
    if hasattr(client, "resume"):
        print("  %s" % client.resume())
    print("  %s" % racine)
    if copie:
        print("  instantane : %s" % os.path.relpath(copie, DONNEES))


# ⚠️ Le bac a sable 100005 n'existe plus (mesure du 26/08/2026, voir
# `core/plateformes.py`). `--base <id>` reste utilisable pour viser un autre
# journal, mais il n'y a plus de journal jetable a viser.
BASE_BAC_A_SABLE = pf.BASE_BAC_A_SABLE


def pousser(base_id=None, mode=None, champs=None):
    """Étape 5. Demande ENVOYER en toutes lettres : système EXTERNE.

    `mode` / `champs` : voir `ecriture.preparer`. Par défaut — et c'est le
    comportement historique — on écrase tout champ qui diffère, sur tous les
    champs. L'orchestrateur les fait choisir ; la ligne de commande garde le
    défaut pour ne rien casser des habitudes.

    `base_id` permet de viser le bac à sable (100005) au lieu du journal réel,
    sans éditer le code. Le cloisonnement est structurel : l'identifiant figure
    dans l'URL de chaque appel — et il depend de la PLATEFORME : 100001 pour le
    forex cTrader, 100004 pour les futures Tradovate.
    """
    base_id = base_id or pf.base_edgewonk(PLATEFORME)
    from edgewonk.api import Client, ErreurEdgewonk, charge_utile_put
    from edgewonk.appariement import apparier, rattraper
    from edgewonk import ecriture

    # ⚠️ DEUX VUES, ET IL NE FAUT PAS LES CONFONDRE.
    #
    #   `trades`  la base ENTIERE — c'est elle qu'on reecrira a la fin.
    #   `a_pousser` les seules jambes de cette plateforme — c'est elles qu'on
    #             compare aux trades du journal lu.
    #
    # Le filtre est indispensable a l'appariement : sans lui, les jambes de
    # l'autre source ressortiraient toutes en « non trouvees » et noieraient les
    # vraies.
    #
    # ⚠️ MAIS IL NE DOIT JAMAIS DEVENIR LA BASE. Defaut introduit et corrige le
    # 26/08/2026 : `trades` portait la vue filtree, et la fin de cette fonction
    # ecrit `trades` dans `donnees/trades.csv` pour y poser la colonne
    # `screenshots`. Le premier `pousser --tradovate` a donc reecrit la base avec
    # ses 35 jambes futures seules — **les 46 jambes cTrader ont disparu**.
    # Rattrape par l'instantane pris avant ecriture, sans rien perdre.
    #
    # C'est exactement la regle 3 du §8 qui a servi, et c'est la premiere fois
    # qu'elle sert pour de bon. `sync.py` ne pouvait pas tomber dedans : son
    # etape 5 recharge la base avant d'ecrire.
    trades = base.charger(TRADES)
    a_pousser = _borner(pf.filtrer(trades, PLATEFORME))
    if not a_pousser:
        sys.exit("aucune jambe %s dans la base" % pf.nom(PLATEFORME))
    try:
        client = Client().authentifier()
    except ErreurEdgewonk as e:
        sys.exit(str(e))
    print("authentifie")
    distants = client.tous_les_trades(base_id)
    print("%d trades Edgewonk lus" % len(distants))

    couples, sans, ambigus, controles = apparier(a_pousser, distants)
    # ⚠️ LE REPECHAGE DU CHANGEMENT D'HEURE — branche le 28/08/2026, et il ne
    # l'etait NULLE PART en production.
    #
    # `rattraper()` retrouve une jambe dont Edgewonk a mal resolu le changement
    # d'heure sur SON horodatage de sortie : entree, quantite et gain
    # concordent, seule la sortie est decalee d'une heure. Huit diagnostics
    # l'appelaient, `retro.py` l'appelait, les deux poussees de production non.
    #
    # Le chantier retroactif a traverse le changement du 29/03 grace a elle. La
    # production traversera celui du 25/10/2026 — et l'erreur vient de LEUR
    # importateur, pas de nos exports : la vigilance de l'utilisateur a l'import ne
    # l'evite pas. Sans cette ligne, les trades a cheval seraient comptes
    # « non trouves » et jamais pousses, en silence.
    #
    # La regle avait ete deplacee ici pour servir la production. Le deplacement
    # avait ete fait, le branchement non — la meme forme que les quatre autres
    # trous de la journee : un correctif ecrit, jamais appele.
    repeches = rattraper(a_pousser, distants, couples, sans)

    _titre("Appariement")
    print("  apparies    : %d / %d" % (len(couples), len(a_pousser)))
    if repeches:
        print("  repeches    : %d (changement d'heure — sortie decalee d'1 h chez eux)"
              % len(repeches))
        for x in repeches[:8]:
            print("     %s" % x)
    print("  non trouves : %d" % len(sans))
    _bloc("Non trouves — deja importes dans Edgewonk ?", sans, limite=10)
    _bloc("Ambigus", ambigus)
    _bloc("Controles d'integrite", controles)

    # Catalogue des strategies alternatives, un par SETUP rencontre. Resolu
    # dynamiquement : les identifiants sont propres a chaque setup ET a chaque
    # base (`docs/edgewonk-api.md` §7), les coder en dur casserait en silence.
    catalogues = {}
    for _, _, trade in couples:
        setup = trade.get("setup") or {}
        sid = setup.get("id") if isinstance(setup, dict) else setup
        if sid and sid not in catalogues:
            try:
                catalogues[sid] = client.strategies(base_id, sid)
            except Exception as e:                            # noqa: BLE001
                catalogues[sid] = []
                print("  strategies du setup %s illisibles (%s)" % (sid, e))
    if catalogues:
        print("  %d setup(s), %d strategie(s) alternatives resolues"
              % (len(catalogues), sum(len(v) for v in catalogues.values())))

    # Catalogue des commentaires de trade — la SOURCE des options Management.
    # `GET /databases/{db}/comments`, trouve par mesure le 26/08/2026
    # (`outils/diag_commentaires.py`, 11 URL sondees, une seule repond).
    # Sans lui, `options_management` deduit les options des trades lus : aveugle
    # a toute option que plus aucun trade ne porte. C'est exactement ce qui a
    # fait refuser les 23 positions KO le 26/08 — « Managed » n'etait posee
    # nulle part. Le repli reste en place mais n'est plus le chemin normal.
    try:
        commentaires = client.commentaires(base_id)
    except Exception as e:                                    # noqa: BLE001
        commentaires = None
        print("  catalogue des commentaires illisible (%s) — repli sur les trades" % e)

    # La sortie de la jambe TENUE de chaque position — la derniere par heure de
    # cloture. Calculee sur la base COMPLETE et pas sur les jambes appariees :
    # une position dont un allegement n'est pas apparie donnerait sinon la
    # mauvaise jambe, et le second controle du management jugerait la mauvaise
    # sortie.
    sorties_tenues = {}
    for cle, t in sorted(trades.items(), key=lambda x: x[1].get("cloture", "")):
        sorties_tenues[t.get("cle_position") or cle] = t.get("sortie")

    plans, notes = ecriture.preparer(
        couples, DONNEES, catalogues, distants, commentaires=commentaires,
        mode=mode or ecriture.MODE_ECRASER, champs=champs,
        sorties_tenues=sorties_tenues)
    _bloc("Signalements", notes, limite=10)
    _titre("Plan d'ecriture")
    champs = sum(len(p["modify"]) + len(p["put"]) for p in plans)
    images = sum(len(p["images"]) for p in plans)
    print("  %d trades a modifier, %d champs au total" % (len(plans), champs))
    if images:
        print("  %d image(s) a televerser sur %d trade(s)"
              % (images, sum(1 for p in plans if p["images"])))
    for p in plans[:15]:
        detail = dict(p["modify"]); detail.update(p["put"])
        print("  %-34s id %-10s %s" % (p["cle"], p["id"], detail))
    if len(plans) > 15:
        print("  … et %d autres" % (len(plans) - 15))
    if not plans:
        print("\n  rien a ecrire.")
        return

    print("\n  Ceci ecrit dans EDGEWONK, systeme externe.")
    print("  Un instantane complet est pris avant. Tape ENVOYER pour confirmer.")
    try:
        if input("  > ").strip().upper() != "ENVOYER":
            sys.exit("\nRien n'a ete ecrit.")
    except (EOFError, KeyboardInterrupt):
        sys.exit("\nRien n'a ete ecrit.")

    _titre("Instantane")
    chemin = None
    for a, b in ecriture.instantane(client, base_id, plans,
                                    os.path.join(DONNEES, "instantanes")):
        if b is None:
            chemin = a
        else:
            sys.stdout.write("\r  %d/%d trades sauvegardes" % (a, b))
            sys.stdout.flush()
    print("\n  %s" % chemin)

    _titre("Ecriture")
    ecrits = echecs = divergences = None
    for i, n, ecrits, echecs, divergences in ecriture.appliquer(
            client, base_id, plans, charge_utile_put):
        sys.stdout.write("\r  %d/%d trades" % (i, n))
        sys.stdout.flush()
    print()
    print("  champs confirmes PAR RELECTURE : %d" % ecrits)
    _bloc("Echecs", echecs or [])
    _bloc("Divergences — ecrites mais NON confirmees a la relecture", divergences or [])

    # --- images
    confirmees = []
    if any(p["images"] for p in plans):
        _titre("Captures")
        env = ech = None
        for i, tot, env, ech, confirmees in ecriture.envoyer_images(
                client, base_id, plans):
            sys.stdout.write("\r  %d/%d trades" % (i, tot))
            sys.stdout.flush()
        print()
        print("  images confirmees PAR RELECTURE : %d" % (env or 0))
        _bloc("Echecs", ech or [])

        # La base locale enregistre ce qui est REELLEMENT confirme, jamais ce
        # qu'on a tente : une image non confirmee sera renvoyee au prochain
        # passage, et c'est le bon defaut.
        if confirmees:
            # On RECHARGE la base entiere avant d'ecrire : `a_pousser` n'en est
            # qu'une vue, et la reecrire effacerait l'autre plateforme.
            trades = base.charger(TRADES)
            horo = time.strftime("%Y%m%d-%H%M%S")
            for cle in confirmees:
                if cle in trades:
                    trades[cle]["screenshots"] = horo
            copie = base.ecrire(TRADES, trades)
            print("  %d trade(s) marques dans la base locale" % len(confirmees))
            if copie:
                print("  instantane : %s" % os.path.relpath(copie, DONNEES))

    if not echecs and not divergences:
        print("\n  Tout ce qui a ete ecrit a ete relu et confirme.")


def etat():
    trades = base.charger(TRADES)
    if not trades:
        print("base vide")
        return
    positions = base.grouper_en_positions(trades)
    avec_sl = sum(1 for t in trades.values() if t.get("sl"))
    avec_tp = sum(1 for t in trades.values() if t.get("tp"))
    avec_ext = sum(1 for t in trades.values() if t.get("prix_plus_haut"))
    multi = sum(1 for p in positions.values() if len(p["jambes"]) > 1)
    dates = sorted(t.get("ouverture", "")[:10] for t in trades.values() if t.get("ouverture"))
    _titre("Base locale")
    print("  jambes        : %d   (= autant de trades Edgewonk)" % len(trades))
    print("  positions     : %d   dont %d sorties en plusieurs fois" % (len(positions), multi))
    print("  période       : %s → %s" % (dates[0], dates[-1]))
    print("  avec SL       : %d" % avec_sl)
    print("  avec TP       : %d" % avec_tp)
    print("  management    : %d" % sum(1 for t in trades.values() if t.get("management")))
    print("  avec bougies  : %d" % avec_ext)
    comptes = sorted({t.get("compte", "") for t in trades.values()})
    print("  comptes       : %s" % ", ".join(c for c in comptes if c))
    for code in (pf.CTRADER, pf.TRADOVATE):
        lot = pf.filtrer(trades, code)
        if lot:
            print("  %-13s : %d jambes, %d avec SL, %d avec bougies"
                  % (pf.PLATEFORMES[code]["nom"], len(lot),
                     sum(1 for t in lot.values() if t.get("sl")),
                     sum(1 for t in lot.values() if t.get("prix_plus_haut"))))


def main():
    global PLATEFORME
    if len(sys.argv) < 2:
        print(__doc__)
        return
    argv = list(sys.argv[1:])

    # Le drapeau est accepte n'importe ou dans la ligne : on le retire des
    # arguments avant tout le reste, pour qu'aucun verbe n'ait a le connaitre.
    for drapeau, code in (("--tradovate", pf.TRADOVATE), ("--ctrader", pf.CTRADER)):
        while drapeau in argv:
            argv.remove(drapeau)
            PLATEFORME = code
    if "--plateforme" in argv:
        i = argv.index("--plateforme")
        if i + 1 >= len(argv) or argv[i + 1] not in pf.PLATEFORMES:
            sys.exit("--plateforme attend : %s" % ", ".join(sorted(pf.PLATEFORMES)))
        PLATEFORME = argv[i + 1]
        del argv[i:i + 2]
    # --periode / --journal : lus par le même lecteur que les diagnostics, puis
    # retirés pour qu'aucun verbe n'ait à les connaître.
    global PERIODE, JOURNAL
    try:
        PERIODE, JOURNAL = base.options_ligne(argv)
    except ValueError as e:
        sys.exit(str(e))
    for drapeau in ("--periode", "--journal"):
        if drapeau in argv:
            i = argv.index(drapeau)
            del argv[i:i + 2]

    if PLATEFORME != pf.CTRADER:
        print("PLATEFORME : %s — journal Edgewonk %s"
              % (pf.nom(PLATEFORME), JOURNAL or pf.base_edgewonk(PLATEFORME)))
    if JOURNAL and JOURNAL != pf.base_edgewonk(PLATEFORME):
        print("⚠ JOURNAL VISÉ : %s (au lieu de %s)"
              % (JOURNAL, pf.base_edgewonk(PLATEFORME)))

    cmd, args = argv[0], argv[1:]
    actions = {"importer": importer, "controler": controler, "integrer": integrer}
    if cmd == "etat":
        etat()
        return
    if cmd == "bougies":
        bougies()
        return
    if cmd == "graphiques":
        graphiques("--refaire" in args)
        return
    if cmd == "pousser":
        base_id = JOURNAL
        if "--base" in args:
            i = args.index("--base")
            if i + 1 >= len(args):
                sys.exit("--base attend un identifiant de journal (ex. 100005)")
            base_id = args[i + 1]
        if base_id and base_id != pf.base_edgewonk(PLATEFORME):
            print("⚠ JOURNAL VISÉ : %s (au lieu de %s)"
                  % (base_id, pf.base_edgewonk(PLATEFORME)))

        # --mode / --champs : les deux réglages que l'orchestrateur fait
        # choisir. Absents, on garde le comportement historique — écraser,
        # sur tous les champs — pour qu'une ligne de commande écrite avant
        # aujourd'hui fasse encore exactement la même chose.
        mode = None
        if "--mode" in args:
            i = args.index("--mode")
            if i + 1 >= len(args) or args[i + 1] not in (ecriture.MODE_ECRASER,
                                                         ecriture.MODE_VIDE):
                sys.exit("--mode attend : %s ou %s"
                         % (ecriture.MODE_ECRASER, ecriture.MODE_VIDE))
            mode = args[i + 1]
        champs = None
        if "--champs" in args:
            i = args.index("--champs")
            if i + 1 >= len(args):
                sys.exit("--champs attend une liste : %s"
                         % ",".join(c for c, _, _ in ecriture.CHAMPS_ECRITS))
            connus = {c for c, _, _ in ecriture.CHAMPS_ECRITS}
            champs = {x.strip() for x in args[i + 1].split(",") if x.strip()}
            inconnus = champs - connus
            if inconnus:
                sys.exit("champ(s) inconnu(s) : %s\nconnus : %s"
                         % (", ".join(sorted(inconnus)), ", ".join(sorted(connus))))
        if mode == ecriture.MODE_VIDE:
            print("MODE : ne remplir que les champs vides chez Edgewonk "
                  "— rien de rempli ne sera touché")
        if champs:
            print("CHAMPS : %s" % ", ".join(sorted(champs)))
        pousser(base_id, mode=mode, champs=champs)
        return
    if cmd not in actions:
        print(__doc__)
        sys.exit("commande inconnue : %s" % cmd)
    if not args:
        sys.exit("il manque le fichier : jt.py %s <fichier.csv>" % cmd)
    if cmd == "importer":
        importer(args)          # une liste : 1 fichier cTrader, 2 pour Tradovate
    else:
        actions[cmd](args[0])


if __name__ == "__main__":
    main()
