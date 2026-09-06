#!/usr/bin/env python3
"""Assistant guidé de synchronisation du journal de trading.

Un seul espace de travail pour l'utilisateur : le dossier IMPORT/ à la racine du projet.
Il y dépose, il y édite, le programme fait le reste et le range.

Rien d'automatique n'est irréversible sans confirmation tapée en toutes lettres :
  Y / Q        navigation
  OK           écriture dans la base LOCALE   (instantané pris avant, réversible)
  ENVOYER      écriture dans EDGEWONK         (système externe)

L'assistant n'est qu'une façade : il appelle les mêmes modules que `jt.py`. Les deux
chemins restent utilisables, et déboguer se fait toujours avec les verbes de jt.py.

Grain : une ligne de base = une JAMBE = un trade Edgewonk. La saisie SL/TP se
fait par POSITION (une position n'a qu'une protection), puis se réplique.
"""

import glob
import io
import os
import shutil
import subprocess
import sys
import time

RACINE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RACINE)

from core import base, plateformes as pf, saisie   # noqa: E402
from ctrader import bougies, statement              # noqa: E402
from ctrader.mcp import Client, ErreurMCP           # noqa: E402
from databento import client as databento           # noqa: E402
from tradovate import statement as statement_tradovate   # noqa: E402

# Les deux sources de bougies ne partagent pas leur exception. On les capture
# ensemble plutot que de faire remonter l'une des deux sans contexte.
ERREURS_BOUGIES = (ErreurMCP, databento.ErreurDatabento)

PROJET = os.path.normpath(os.path.join(RACINE, ".."))
IMPORT = os.path.join(PROJET, "IMPORT")
DONNEES = os.path.join(PROJET, "donnees")
BRUT = os.path.join(DONNEES, "brut")
SAISIES = os.path.join(DONNEES, "saisies")
TRADES = os.path.join(DONNEES, "trades.csv")

G, J, R, B, N, GRAS = "\033[32m", "\033[33m", "\033[31m", "\033[34m", "\033[0m", "\033[1m"

# ⚠️ VARIABLE DE MODULE, POSEE UNE FOIS PAR `etape0` ET PLUS JAMAIS TOUCHEE.
#
# L'assistant est un script a passage unique : l'utilisateur declare sa plateforme
# au demarrage, et les cinq etapes s'y tiennent. La passer en argument a chaque
# fonction aurait modifie huit signatures d'une chaine en production pour une
# valeur qui, par construction, ne change pas pendant l'execution. Ce qui
# DEPEND de la plateforme est isole dans `core/plateformes.py` ; ici on ne fait
# que la retenir.
PLATEFORME = pf.CTRADER


def etapes():
    p = pf.PLATEFORMES[PLATEFORME]
    return [
        ("Relevé %s" % p["nom"], "→ base locale"),
        ("SL / TP / management", "→ saisie guidée et contrôles"),
        ("Bougies M1", "→ extrêmes, TP-first, paliers"),
        ("Graphiques", "→ M5 · M15 · H1 · H4"),
        ("Edgewonk", "→ journal %s" % p["base_edgewonk"]),
    ]


# ------------------------------------------------------------------ affichage
def bandeau():
    p = pf.PLATEFORMES[PLATEFORME]
    print("\n" + GRAS + "  JOURNAL DE TRADING — synchronisation" + N)
    print("  " + GRAS + "  %s — %s" % (p["nom"], p["detail"]) + N)
    print("  " + "─" * 44)
    for i, (titre, detail) in enumerate(etapes(), 1):
        print("   %d  %-18s %s" % (i, titre, detail))
    print("  " + "─" * 44)
    print("   bougies : %s" % p["bougies"])
    print("  " + "─" * 44)


def etape(n):
    titre, _ = etapes()[n - 1]
    print("\n" + GRAS + "  ÉTAPE %d — %s" % (n, titre) + N)
    print("  " + "─" * 44)


def dire(txt=""):
    print("  " + txt if txt else "")


def ok(txt):
    dire(G + "✓ " + N + txt)


def alerte(txt):
    dire(J + "! " + N + txt)


def erreur(txt):
    dire(R + "✗ " + N + txt)


def demander(question, choix):
    """choix : dict {saisie_majuscule: description}. Retourne la clé choisie."""
    dire()
    for k, d in choix.items():
        dire("  [%s%s%s] %s" % (GRAS, k, N, d))
    while True:
        try:
            rep = input("\n  > ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print()
            return "Q"
        if rep in choix:
            return rep
        dire(J + "Réponse attendue : %s" % ", ".join(choix) + N)


def quitter(message="Interrompu. Rien n'a été perdu : la base est intacte."):
    dire()
    dire(message)
    dire()
    sys.exit(0)


# ------------------------------------------------------------------- étape 1
def ouvrir(chemin):
    """Ouvre un dossier ou un fichier dans le Finder. Silencieux si ça échoue.

    Confort pur : l'assistant doit rester utilisable sans, donc aucune erreur
    ne remonte — sur une machine sans `open`, on continue comme avant.
    """
    try:
        subprocess.run(["open", chemin], check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:                                        # noqa: BLE001
        pass


def trouver_releve():
    return [f for f in glob.glob(os.path.join(IMPORT, "*.csv"))
            if not os.path.basename(f).startswith("sltp_")]


# ------------------------------------------------------------------- étape 0
def etape0():
    """Quelle plateforme ? C'est l'utilisateur qui declare, jamais le programme.

    ⚠️ ON NE RENIFLE PAS LE FORMAT DU CSV. Tranche le 26/08/2026
    (`docs/tradovate.md` §9) : deviner marcherait 99 fois et casserait en silence la
    centieme, le jour ou un export changerait de colonnes. Une question de deux
    secondes contre un mode de defaillance silencieux, le choix est vite fait.
    """
    global PLATEFORME
    print("\n" + GRAS + "  QUEL JOURNAL SYNCHRONISES-TU ?" + N)
    print("  " + "─" * 44)
    for touche, code in (("1", pf.CTRADER), ("2", pf.TRADOVATE)):
        p = pf.PLATEFORMES[code]
        dire("  [%s%s%s] %-11s %-24s %s"
             % (GRAS, touche, N, p["nom"], p["detail"], p["bougies"]))
    dire("  [%sQ%s] quitter" % (GRAS, N))
    while True:
        try:
            rep = input("\n  > ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print()
            quitter()
        if rep in ("Q", ""):
            quitter()
        if rep in ("1", "2"):
            PLATEFORME = pf.CTRADER if rep == "1" else pf.TRADOVATE
            return PLATEFORME
        dire(J + "Réponse attendue : 1, 2 ou Q" + N)


def _archiver(chemin):
    archive = os.path.join(BRUT, "%s_%s" % (time.strftime("%Y%m%d-%H%M%S"),
                                            os.path.basename(chemin)))
    shutil.copy2(chemin, archive)
    return archive


def _attendre_fichiers(combien, quoi):
    """Boucle jusqu'a ce que IMPORT/ contienne exactement `combien` CSV."""
    if not trouver_releve():
        ouvrir(IMPORT)
    while True:
        rep = demander("", {"Y": "j'ai déposé %s" % quoi, "Q": "quitter"})
        if rep == "Q":
            quitter()
        fichiers = trouver_releve()
        if len(fichiers) == combien:
            return fichiers
        if not fichiers:
            erreur("aucun fichier CSV trouvé dans IMPORT/ (hors sltp_*).")
        elif len(fichiers) < combien:
            erreur("il en manque : %d trouvé(s), %d attendu(s)."
                   % (len(fichiers), combien))
            for f in fichiers:
                dire("    " + os.path.basename(f))
        else:
            erreur("trop de fichiers dans IMPORT/ — %d trouvé(s), %d attendu(s) :"
                   % (len(fichiers), combien))
            for f in fichiers:
                dire("    " + os.path.basename(f))


def _etape1_ctrader():
    dire("Dépose ton export CSV cTrader dans ce dossier :")
    dire()
    dire(B + "    " + IMPORT + N)
    dire()
    fichiers = _attendre_fichiers(1, "le fichier")
    releve = fichiers[0]
    dire()
    ok("relevé trouvé : " + os.path.basename(releve))

    archive = _archiver(releve)
    ok("brut archivé (il ne sera plus jamais modifié)")
    try:
        trades, anomalies = statement.lire(archive)
    except Exception as e:                                   # noqa: BLE001
        erreur("lecture impossible : %s" % e)
        erreur("est-ce bien un export « relevé » de cTrader ?")
        quitter("Rien n'a été écrit dans la base.")
    return trades, anomalies, {}, [releve]


def _etape1_tradovate():
    dire("Dépose ton export %s« Orders »%s de Tradovate dans ce dossier :" % (GRAS, N))
    dire()
    dire(B + "    " + IMPORT + N)
    dire()
    dire("Un seul fichier suffit. Il porte les trades %set%s les brackets ATM :"
         % (GRAS, N))
    dire("l'appariement FIFO se refait depuis les ordres remplis, et il")
    dire("reproduit au centime le découpage d'Edgewonk (mesuré le 26/08).")
    dire()

    fichiers = _attendre_fichiers(1, "le fichier")
    orders = fichiers[0]
    dire()
    ok("export trouvé : " + os.path.basename(orders))

    archive = _archiver(orders)
    ok("brut archivé (il ne sera plus jamais modifié)")

    try:
        trades, anomalies = statement_tradovate.lire(archive)
    except statement_tradovate.ErreurExport as e:
        dire()
        erreur("lecture impossible : %s" % str(e).replace("\n", "\n  "))
        quitter("Rien n'a été écrit dans la base.")

    # Les SL/TP de l'export sont des SUGGESTIONS pre-remplies dans le fichier de
    # saisie, jamais une ecriture directe : voir le docstring de
    # `tradovate.statement.suggestions_sltp`.
    try:
        suggestions, notes = statement_tradovate.suggestions_sltp(trades, archive)
    except Exception as e:                                   # noqa: BLE001
        suggestions, notes = {}, ["brackets illisibles (%s) — SL et TP à saisir "
                                  "entièrement à la main" % e]
    return trades, anomalies + notes, suggestions, [orders]


def etape1():
    etape(1)
    if PLATEFORME == pf.TRADOVATE:
        trades, anomalies, suggestions, releves = _etape1_tradovate()
    else:
        trades, anomalies, suggestions, releves = _etape1_ctrader()

    for d in (BRUT, SAISIES, IMPORT):
        if not os.path.isdir(d):
            os.makedirs(d)

    for a in anomalies:
        alerte(a)

    existants = base.charger(TRADES)
    fusion, ajoutes, completes, inchanges = base.fusionner(existants, trades)
    base.ecrire(TRADES, fusion)

    nb_pos = len({t["cle_position"] for t in trades})
    multi = len({t["cle_position"] for t in trades if t["nb_jambes"] != "1"})
    dire()
    ok("%d jambes lues sur %d positions" % (len(trades), nb_pos))
    if multi:
        dire("   dont %d position(s) donnant plusieurs trades Edgewonk — la base" % multi)
        dire("   suit leur découpage, une ligne par trade de leur côté")
    dire("   ajoutées %d · complétées %d · inchangées %d · base %d jambes"
         % (len(ajoutes), len(completes), len(inchanges), len(fusion)))
    if suggestions:
        dire()
        ok("%d position(s) ont leur SL et leur TP lus dans l'export — ils seront"
           % len(suggestions))
        dire("   pré-remplis dans le fichier de saisie, à toi de les valider")

    # Les clés que CE relevé vient de produire. On ne se fonde pas sur
    # `source_brut` : la fusion garde le premier relevé qui a fait naître un
    # trade, donc au ré-import aucune jambe ne porterait la source courante.
    return {t["cle"] for t in trades}, fusion, releves, suggestions


# ------------------------------------------------------------------- étape 2
def etape2(cles, trades, suggestions=None):
    etape(2)
    positions = base.grouper_en_positions(trades, cles)
    fichier = os.path.join(IMPORT, "sltp_%s.csv" % time.strftime("%Y%m%d-%H%M%S"))
    n = saisie.generer(positions, fichier, suggestions)
    a_remplir = sum(1 for p in positions.values()
                    if not p["sl"] and not p["tp"] and not p["management"])
    multi = sum(1 for p in positions.values() if len(p["jambes"]) > 1)

    dire("Un fichier vient d'être créé dans IMPORT/ :")
    dire()
    dire(B + "    " + os.path.basename(fichier) + N)
    dire()
    dire("%d lignes — une par POSITION, dont %d à remplir." % (n, a_remplir))
    if multi:
        dire("%d position(s) ont plusieurs sorties (colonne %sjambes%s) : tu ne saisis"
             % (multi, GRAS, N))
        dire("le SL et le TP %squ'une fois%s, ils seront appliqués à chaque sortie." % (GRAS, N))
    dire("Trois colonnes à remplir : %ssl%s, %stp%s et %smanagement%s."
         % (GRAS, N, GRAS, N, GRAS, N))
    dire()
    dire("  %smanagement%s — as-tu touché à ton stop ou à ta cible après l'entrée ?"
         % (GRAS, N))
    dire("     %sOK%s = non, le plan a été tenu       → « Not managed » chez Edgewonk"
         % (GRAS, N))
    dire("     %sKO%s = oui, la position a été gérée  → « Managed »" % (GRAS, N))
    dire("     Une case vide %sbloque%s : ce jugement ne se retrouve pas après coup."
         % (GRAS, N))
    dire()
    dire("Le reste des colonnes est là pour t'aider à te repérer et peut être")
    dire("reformaté sans conséquence.")

    if demander("", {"Y": "j'ai rempli et enregistré", "Q": "quitter"}) == "Q":
        quitter()

    while True:
        try:
            lignes = saisie.lire(fichier)
        except Exception as e:                               # noqa: BLE001
            erreur("fichier de saisie illisible : %s" % e)
            if demander("", {"R": "réessayer", "Q": "quitter"}) == "Q":
                quitter()
            continue
        valides, rejets, signalements = saisie.controler(lignes, positions)

        dire()
        if rejets:
            dire(R + GRAS + "REJETS (%d) — bloquants, rien ne sera écrit" % len(rejets) + N)
            for x in rejets:
                dire("   " + x)
            dire()
        if signalements:
            dire(J + GRAS + "SIGNALEMENTS (%d) — à ton jugement" % len(signalements) + N)
            for x in signalements[:30]:
                dire("   " + x)
            if len(signalements) > 30:
                dire("   … et %d autres" % (len(signalements) - 30))
            dire()
        if not rejets and not signalements:
            ok("aucune anomalie.")
            dire()

        dire("%d positions prêtes à écrire." % len(valides))

        choix = {"R": "j'ai corrigé le fichier, re-vérifier", "Q": "quitter"}
        if not rejets and valides:
            choix = {"OK": "écrire dans la base locale",
                     "R": "j'ai corrigé le fichier, re-vérifier",
                     "Q": "quitter"}
        rep = demander("", choix)
        if rep == "Q":
            quitter()
        if rep == "R":
            dire()
            dire("relecture du fichier…")
            continue

        trades = base.charger(TRADES)
        positions = base.grouper_en_positions(trades, cles)
        valeurs, jambes, nb_pos = saisie.appliquer(trades, positions, valides)
        base.ecrire(TRADES, trades)
        dire()
        ok("%d valeurs écrites sur %d jambes, depuis %d positions" % (valeurs, jambes, nb_pos))
        dire("   (instantané pris avant écriture)")
        return fichier, trades


# ------------------------------------------------- la source de bougies
def ouvrir_source_bougies():
    """Le client de bougies de la plateforme courante.

    Les deux repondent au MEME appel — `appeler("get_trendbars", …)` — et c'est
    ce qui permet a `ctrader/bougies.py` et a `graphiques/rendu.py` de servir
    les deux plateformes sans une ligne de difference. Voir l'en-tete de
    `databento/client.py`.
    """
    if PLATEFORME == pf.TRADOVATE:
        return databento.Client(cache=os.path.join(DONNEES, "bougies")).ouvrir()
    return Client().ouvrir()


def prealable_bougies():
    """Ce que l'utilisateur doit avoir prêt, et ce que ça engage."""
    if PLATEFORME == pf.TRADOVATE:
        dire("Les bougies viennent de %sDatabento%s (dataset GLBX.MDP3)." % (GRAS, N))
        dire("Il faut une clé dans le trousseau — voir le README, §6 bis.")
        dire("Chaque journée de marché nouvelle coûte environ %s0,005 $%s ; celles"
             % (GRAS, N))
        dire("déjà tirées sont relues du cache, gratuitement.")
        return {"Y": "calculer", "Q": "passer cette étape"}
    dire("Il faut %scTrader ouvert et connecté au compte Prop Firm A%s," % (GRAS, N))
    dire("avec Paramètres → Serveur MCP → « Enable MCP Server » coché.")
    dire("Le module est en lecture seule : il refuse par construction tout")
    dire("outil d'écriture du MCP.")
    return {"Y": "cTrader est ouvert, calculer", "Q": "passer cette étape"}


# ------------------------------------------------------------------- étape 3
def etape3(trades):
    """Bougies M1 -> plus haut, plus bas, TP-first. Écrit dans la base LOCALE."""
    etape(3)

    # Extrêmes OU simulation de paliers manquants : une simulation non résolue
    # laisse la colonne vide et doit être retentée au cycle suivant.
    # ⚠️ ON NE TRAITE QUE LES JAMBES DE LA PLATEFORME COURANTE : une jambe forex
    # n'a rien a demander a Databento, une jambe futures rien au MCP cTrader.
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
    a_faire = {c: t for c, t in pf.filtrer(trades, PLATEFORME).items()
               if (not t.get("prix_plus_haut"))
               or (t.get("sl") and not t.get("prix_max_favorable"))
               or (t.get("sl") and t.get("tp") and not t.get("tp_touche_en_premier"))}
    if not a_faire:
        ok("rien à calculer : les jambes avec SL ont leurs extrêmes et leurs paliers.")
        return trades
    positions = base.grouper_en_positions(trades, set(a_faire))

    dire("%d jambe(s) sur %d position(s) attendent leurs extrêmes."
         % (len(a_faire), len(positions)))
    dire()
    choix = prealable_bougies()

    if demander("", choix) == "Q":
        alerte("étape 3 passée. La base reste cohérente, tu pourras y revenir.")
        return trades

    try:
        client = ouvrir_source_bougies()
    except ERREURS_BOUGIES as e:
        dire()
        erreur(str(e).replace("\n", "\n  "))
        alerte("étape 3 abandonnée — rien n'a été écrit.")
        return trades
    dire()
    ok("source de bougies ouverte — %s" % pf.PLATEFORMES[PLATEFORME]["bougies"])

    maj_totale, notes, bords, echecs = {}, [], [], []
    for i, cp in enumerate(sorted(positions), 1):
        try:
            maj, n, b = bougies.traiter_position(client, positions[cp], trades)
        except ERREURS_BOUGIES as e:
            echecs.append("%s : %s" % (cp, str(e).splitlines()[0]))
            continue
        maj_totale.update(maj)
        notes += n
        bords += b
        sys.stdout.write("\r     %d/%d positions%s" % (i, len(positions), " " * 12))
        sys.stdout.flush()
    sys.stdout.write("\n")

    if echecs:
        dire()
        dire(R + GRAS + "ÉCHECS (%d)" % len(echecs) + N)
        for x in echecs[:10]:
            dire("   " + x)
    if notes:
        dire()
        dire(J + GRAS + "SIGNALEMENTS (%d)" % len(notes) + N)
        for x in notes[:15]:
            dire("   " + x)
    if bords:
        dire()
        dire("%d jambe(s) ont un débordement de bougie de bord ≥ %.2f R :"
             % (len(bords), bougies.R_ECART_BORD))
        dire("leur plus haut / plus bas est une BORNE, pas un maximum.")
        for c, e in sorted(bords, key=lambda x: -x[1])[:10]:
            dire("   %-34s %+.2f R" % (c, e))

    dire()
    if not maj_totale:
        alerte("aucun extrême calculé — rien à écrire.")
        return trades
    dire("%d jambe(s) prêtes à être complétées." % len(maj_totale))

    if demander("", {"OK": "écrire dans la base locale", "Q": "ne rien écrire"}) == "Q":
        alerte("rien n'a été écrit.")
        return trades

    trades = base.charger(TRADES)
    ecrits = 0
    for cle, valeurs in maj_totale.items():
        t = trades.get(cle)
        if t is None:
            continue
        for champ, v in valeurs.items():
            if v != "" and t.get(champ) != v:
                t[champ] = v
                ecrits += 1
    base.ecrire(TRADES, trades)
    dire()
    ok("%d valeurs écrites sur %d jambes (instantané pris avant)"
       % (ecrits, len(maj_totale)))
    if hasattr(client, "resume"):
        dire("   " + client.resume())
    return trades


# ------------------------------------------------------------------- étape 5
def etape5(trades):
    """Pousse vers Edgewonk ce qu'on a produit EN PLUS. Système EXTERNE."""
    from edgewonk.api import Client, ErreurEdgewonk, charge_utile_put
    from edgewonk.appariement import apparier, rattraper
    from edgewonk import ecriture
    etape(5)

    # Le journal vise depend de la plateforme, et le cloisonnement est
    # STRUCTUREL : l'identifiant figure dans l'URL de chaque appel. Une jambe
    # forex ne peut pas atterrir dans le journal futures par accident.
    BASE_EDGEWONK = pf.base_edgewonk(PLATEFORME)

    # ⚠️ ET ON NE COMPARE QUE LES JAMBES DE CETTE PLATEFORME. `apparier` cherche
    # chaque jambe de la base parmi les trades du journal lu : sans ce filtre,
    # les 46 jambes cTrader seraient cherchees dans le journal Tradovate et
    # ressortiraient toutes en « non trouvees ». Le bruit noierait le signal.
    trades = pf.filtrer(trades, PLATEFORME)

    dire("Cette étape écrit dans %sEdgewonk%s, journal %s%s%s."
         % (GRAS, N, GRAS, BASE_EDGEWONK, N))
    dire("Elle suppose que tu as déjà importé le même relevé chez eux :")
    dire("les identifiants de trade n'existent qu'après leur import.")
    if demander("", {"Y": "le relevé est importé dans Edgewonk, continuer",
                     "Q": "passer cette étape"}) == "Q":
        alerte("étape 5 passée. La base locale reste la référence.")
        return

    try:
        client = Client().authentifier()
    except ErreurEdgewonk as e:
        dire()
        erreur(str(e).replace("\n", "\n  "))
        alerte("étape 5 abandonnée — rien n'a été écrit.")
        return
    dire()
    ok("authentifié")
    distants = client.tous_les_trades(BASE_EDGEWONK)
    ok("%d trades Edgewonk lus" % len(distants))

    couples, sans, ambigus, controles = apparier(trades, distants)
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
    repeches = rattraper(trades, distants, couples, sans)

    dire()
    dire("appariés %d / %d · non trouvés %d · ambigus %d"
         % (len(couples), len(trades), len(sans), len(ambigus)))
    if repeches:
        ok("%d jambe(s) repêchée(s) — changement d'heure, sortie décalée d'1 h "
           "chez eux" % len(repeches))
        for x in repeches[:8]:
            dire("   " + x)
    if sans:
        dire()
        alerte("%d jambe(s) sans trade Edgewonk — sans doute pas encore importées :"
               % len(sans))
        for c in sans[:8]:
            dire("   " + c)
    for x in ambigus[:5]:
        alerte(x)
    for x in controles[:5]:
        alerte(x)

    # Catalogue des stratégies alternatives, un par SETUP. Résolu dynamiquement :
    # les identifiants sont propres à chaque setup ET à chaque base.
    catalogues = {}
    for _, _, trade in couples:
        setup = trade.get("setup") or {}
        sid = setup.get("id") if isinstance(setup, dict) else setup
        if sid and sid not in catalogues:
            try:
                catalogues[sid] = client.strategies(BASE_EDGEWONK, sid)
            except Exception as e:                            # noqa: BLE001
                catalogues[sid] = []
                alerte("stratégies du setup %s illisibles (%s)" % (sid, e))
    if catalogues:
        ok("%d setup(s), %d stratégie(s) alternatives résolues"
           % (len(catalogues), sum(len(v) for v in catalogues.values())))

    # Catalogue des commentaires de trade — la SOURCE des options Management.
    # `GET /databases/{db}/comments`, trouve par mesure le 26/08/2026
    # (`outils/diag_commentaires.py`, 11 URL sondees, une seule repond).
    # Sans lui, `options_management` deduit les options des trades lus : aveugle
    # a toute option que plus aucun trade ne porte. C'est exactement ce qui a
    # fait refuser les 23 positions KO le 26/08 — « Managed » n'etait posee
    # nulle part. Le repli reste en place mais n'est plus le chemin normal.
    try:
        commentaires = client.commentaires(BASE_EDGEWONK)
    except Exception as e:                                    # noqa: BLE001
        commentaires = None
        alerte("catalogue des commentaires illisible (%s) — repli sur les trades" % e)

    plans, notes = ecriture.preparer(couples, DONNEES, catalogues, distants,
                                     commentaires=commentaires)
    if notes:
        dire()
        dire(J + GRAS + "SIGNALEMENTS (%d)" % len(notes) + N)
        for x in notes[:8]:
            dire("   " + x)
    if not plans:
        dire()
        ok("rien à écrire : Edgewonk est déjà à jour.")
        return

    champs = sum(len(p["modify"]) + len(p["put"]) for p in plans)
    images = sum(len(p["images"]) for p in plans)
    dire()
    dire("%d trade(s) à modifier, %d champ(s) au total." % (len(plans), champs))
    if images:
        dire("%d image(s) à téléverser sur %d trade(s)."
             % (images, sum(1 for p in plans if p["images"])))
    for p in plans[:12]:
        detail = dict(p["modify"])
        detail.update(p["put"])
        dire("   %-34s %s" % (p["cle"], detail))
    if len(plans) > 12:
        dire("   … et %d autres" % (len(plans) - 12))

    dire()
    dire(GRAS + "Écriture dans un système EXTERNE." + N)
    dire("Un instantané complet est pris avant, et chaque champ est relu après.")
    if demander("", {"ENVOYER": "écrire dans Edgewonk", "Q": "ne rien écrire"}) == "Q":
        alerte("rien n'a été écrit.")
        return

    dire()
    chemin = None
    for a, b in ecriture.instantane(client, BASE_EDGEWONK, plans,
                                    os.path.join(DONNEES, "instantanes")):
        if b is None:
            chemin = a
        else:
            sys.stdout.write("\r     instantané %d/%d" % (a, b))
            sys.stdout.flush()
    sys.stdout.write("\n")
    ok("instantané : %s" % os.path.basename(chemin or ""))

    ecrits = echecs = divergences = None
    for i, n, ecrits, echecs, divergences in ecriture.appliquer(
            client, BASE_EDGEWONK, plans, charge_utile_put):
        sys.stdout.write("\r     écriture %d/%d" % (i, n))
        sys.stdout.flush()
    sys.stdout.write("\n")
    dire()
    ok("%d champ(s) confirmés PAR RELECTURE" % ecrits)
    for x in (echecs or [])[:8]:
        erreur(x)
    for x in (divergences or [])[:8]:
        erreur("non confirmé : " + x)

    if any(p["images"] for p in plans):
        dire()
        env = ech = None
        confirmees = []
        for i, tot, env, ech, confirmees in ecriture.envoyer_images(
                client, BASE_EDGEWONK, plans):
            sys.stdout.write("\r     captures %d/%d trades" % (i, tot))
            sys.stdout.flush()
        sys.stdout.write("\n")
        ok("%d image(s) confirmées PAR RELECTURE" % (env or 0))
        for x in (ech or [])[:8]:
            erreur(x)

        # La base locale n'enregistre que ce qui est REELLEMENT confirmé : une
        # image non confirmée repartira au prochain passage.
        if confirmees:
            trades = base.charger(TRADES)
            horo = time.strftime("%Y%m%d-%H%M%S")
            for cle in confirmees:
                if cle in trades:
                    trades[cle]["screenshots"] = horo
            base.ecrire(TRADES, trades)
            ok("%d trade(s) marqués dans la base locale" % len(confirmees))

    if not echecs and not divergences:
        dire("   Tout ce qui a été écrit a été relu et confirmé.")


# ------------------------------------------------------------------- étape 4
GRAPHIQUES = None            # renseigné dans etape4 (import paresseux)


def etape4(trades):
    """Quatre graphiques par POSITION : M5, M15, H1, H4.

    Les images vont sur la JAMBE RÉELLEMENT TENUE, et sur elle seule. Les jambes
    d'allègement restent sans graphique : ce sont des trades Edgewonk, mais elles
    ne représentent aucune décision."""
    etape(4)

    # L'import vient AVANT la sélection : `position_a_rendre` vit dans `rendu`,
    # qui tire matplotlib. Autant échouer tout de suite que poser une question
    # à l'utilisateur pour buter ensuite sur une dépendance absente.
    try:
        from graphiques import rendu
    except ImportError as e:                                  # noqa: BLE001
        erreur("matplotlib/mplfinance indisponibles : %s" % e)
        erreur("lancer via .venv/bin/python3 — voir §5.2 du README.")
        alerte("étape 4 passée. La base reste cohérente, tu pourras y revenir.")
        return trades

    # Meme filtre qu'a l'etape 3, et pour la meme raison : le rendu tire des
    # bougies, donc il doit s'adresser a la bonne source.
    positions = base.grouper_en_positions(pf.filtrer(trades, PLATEFORME))
    a_rendre = [cp for cp in sorted(positions)
                if rendu.position_a_rendre(trades, cp)]
    if not a_rendre:
        ok("rien à rendre : les positions calculées ont déjà leurs graphiques.")
        return trades

    dire("%d position(s) attendent leurs graphiques, soit %d images."
         % (len(a_rendre), len(a_rendre) * len(rendu.TIMEFRAMES)))
    dire("Chaque position reçoit %sM5, M15, H1 et H4%s, posées sur la jambe" % (GRAS, N))
    dire("réellement tenue — les allègements n'ont pas de graphique.")
    dire()
    dire("Il faut l'environnement .venv (matplotlib), et :")
    prealable_bougies()
    if demander("", {"Y": "calculer les graphiques", "Q": "passer cette étape"}) == "Q":
        alerte("étape 4 passée.")
        return trades

    try:
        client = ouvrir_source_bougies()
    except ERREURS_BOUGIES as e:
        dire()
        erreur(str(e).replace("\n", "\n  "))
        return trades
    dire()
    ok("source de bougies ouverte — %s" % pf.PLATEFORMES[PLATEFORME]["bougies"])

    racine = os.path.join(DONNEES, "graphiques")
    produits, notes = {}, []
    for i, cp in enumerate(a_rendre, 1):
        p, n = rendu.graphiques_de_position(client, positions[cp], trades, racine)
        produits.update(p)
        notes += n
        sys.stdout.write("\r     %d/%d positions" % (i, len(a_rendre)))
        sys.stdout.flush()
    sys.stdout.write("\n")

    if notes:
        dire()
        dire(J + GRAS + "SIGNALEMENTS (%d)" % len(notes) + N)
        for x in notes[:10]:
            dire("   " + x)
    if not produits:
        alerte("aucun graphique produit.")
        return trades

    dire()
    # On compte les PNG sur le disque, jamais positions x 4.
    images = sum(rendu.images_presentes(d) for d in produits.values())
    attendues = len(produits) * len(rendu.TIMEFRAMES)
    dire("%d position(s) rendues, %d image(s)%s."
         % (len(produits), images,
            "" if images == attendues else " sur %d attendues" % attendues))
    if images < attendues:
        alerte("les positions incomplètes repasseront d'elles-mêmes au prochain "
               "cycle — la sélection interroge le disque, pas la base")
    if demander("", {"OK": "écrire les chemins dans la base", "Q": "ne rien écrire"}) == "Q":
        alerte("les images sont sur le disque, mais la base n'a pas été modifiée.")
        return trades

    trades = base.charger(TRADES)
    reenvoyer = 0
    for cle, dossier in produits.items():
        if cle in trades:
            trades[cle]["chemin_graphiques"] = os.path.relpath(dossier, DONNEES)
            # Les PNG viennent de changer : ceux déjà posés chez Edgewonk sont
            # périmés. On vide la colonne, l'étape 5 les renverra d'elle-même.
            if (trades[cle].get("screenshots") or "").strip():
                trades[cle]["screenshots"] = ""
                reenvoyer += 1
    base.ecrire(TRADES, trades)
    dire()
    ok("%d chemin(s) écrits (instantané pris avant)" % len(produits))
    if hasattr(client, "resume"):
        dire("   " + client.resume())
    if reenvoyer:
        dire("   %d trade(s) verront leurs captures renvoyées à l'étape 5" % reenvoyer)
    dire("   " + B + racine + N)
    return trades


def etape_a_venir(n, prealable=None):
    etape(n)
    if prealable:
        dire(prealable)
        dire()
    alerte("cette étape n'est pas encore écrite.")
    dire("La base locale est à jour et cohérente : tu peux t'arrêter ici")
    dire("sans rien perdre. Le travail déjà fait n'est jamais à refaire.")


# ------------------------------------------------------------------- rangement
def ranger(releves, fichier_saisie):
    dire()
    dire(GRAS + "  RANGEMENT" + N)
    dire("  " + "─" * 44)
    horo = time.strftime("%Y%m%d-%H%M%S")
    if fichier_saisie and os.path.exists(fichier_saisie):
        shutil.move(fichier_saisie, os.path.join(SAISIES, os.path.basename(fichier_saisie)))
        ok("saisie archivée dans donnees/saisies/")
    deplaces = 0
    for releve in (releves or []):
        if releve and os.path.exists(releve):
            corbeille = os.path.join(IMPORT, "_traites")
            if not os.path.isdir(corbeille):
                os.makedirs(corbeille)
            shutil.move(releve, os.path.join(corbeille,
                                             "%s_%s" % (horo, os.path.basename(releve))))
            deplaces += 1
    if deplaces:
        ok("%d export(s) déplacé(s) dans IMPORT/_traites/" % deplaces)
    dire()
    dire("IMPORT/ est prêt pour la prochaine fois.")


def resume():
    trades = base.charger(TRADES)
    if not trades:
        return
    positions = base.grouper_en_positions(trades)
    dates = sorted(t.get("ouverture", "")[:10] for t in trades.values() if t.get("ouverture"))
    dire()
    dire(GRAS + "  ÉTAT DE LA BASE" + N)
    dire("  " + "─" * 44)
    dire("  jambes        %d   (= autant de trades Edgewonk)" % len(trades))
    dire("  positions     %d   (%s → %s)" % (len(positions), dates[0], dates[-1]))
    dire("  avec SL       %d" % sum(1 for t in trades.values() if t.get("sl")))
    dire("  avec TP       %d" % sum(1 for t in trades.values() if t.get("tp")))
    dire("  management    %d" % sum(1 for t in trades.values() if t.get("management")))
    dire("  avec bougies  %d" % sum(1 for t in trades.values() if t.get("prix_plus_haut")))
    # La base porte desormais deux sources : les melanger dans un seul total
    # cacherait qu'une des deux est en retard.
    for code in (pf.CTRADER, pf.TRADOVATE):
        n_p = len(pf.filtrer(trades, code))
        if n_p:
            dire("    %-11s %d jambes" % (pf.PLATEFORMES[code]["nom"], n_p))
    dire()
    dire("  " + B + TRADES + N)


def main():
    etape0()
    bandeau()
    cles, trades, releves, suggestions = etape1()
    fichier_saisie, trades = etape2(cles, trades, suggestions)

    trades = etape3(trades)
    trades = etape4(trades)
    trades = base.charger(TRADES)
    etape5(trades)

    ranger(releves, fichier_saisie)
    resume()
    dire()


if __name__ == "__main__":
    main()
