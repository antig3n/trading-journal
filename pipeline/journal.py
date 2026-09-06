#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LE JOURNAL — un seul point d'entrée. Importer, ou auditer.

    ./journal.py            le menu
    ./journal.py importer
    ./journal.py auditer

POURQUOI UN SEUL FICHIER

Il y en avait deux, et ils faisaient la même chose : `sync.py` (898 lignes,
lancé par Raycast) et `jt.py` (633 lignes, en verbes). Deux implémentations des
mêmes cinq étapes, donc deux endroits où corriger, et une divergence mesurée le
28/08/2026 — `jt.py` savait redessiner les graphiques, `sync.py` non. Celui qui
ne savait pas était celui qu'on lançait tous les jours.

Ce module ne réimplémente RIEN. Il pose les questions, et appelle `jt.py`, qui
reste le moteur. L'interface et le moteur sont deux métiers différents : les
mélanger est exactement ce qui a produit les 1 531 lignes qu'on remplace.

LES QUATRE QUESTIONS DE L'IMPORT, ET CE QU'ELLES DÉBLOQUENT

  1. quelle plateforme          cTrader ou Tradovate
  2. quel mode d'écriture       écraser, ou ne remplir que le vide
  3. quels champs               tous, ou une sélection
  4. (si sélection) lesquels

La question 2 n'existait pas : le pipeline écrasait toujours, et la seule façon
de préserver une correction manuelle était la règle E1, qui vivait dans le
chantier rétroactif et ne servait que lui. Elle est maintenant disponible pour
tout le monde, sur tous les champs — c'est le mode « ne remplir que le vide ».
"""

import os
import subprocess
import sys

RACINE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RACINE)

from core import base as noyau, plateformes as pf              # noqa: E402
from edgewonk.ecriture import CHAMPS_ECRITS, MODE_ECRASER, MODE_VIDE  # noqa: E402

G, J, R, N, GRAS, B = ("\033[32m", "\033[33m", "\033[31m", "\033[0m",
                       "\033[1m", "\033[34m")

DONNEES = os.path.normpath(os.path.join(RACINE, "..", "donnees"))
SAISIES = os.path.join(DONNEES, "saisies")
IMPORT = os.path.normpath(os.path.join(RACINE, "..", "IMPORT"))
TRAITES = os.path.join(IMPORT, "_traites")
SAISIES_TRAITEES = os.path.join(SAISIES, "_traites")

# Le venv ne sert qu'aux graphiques (matplotlib, mplfinance). Tout le reste
# tourne en bibliothèque standard pure — voir `graphiques/rendu.py`. On prend
# donc le venv s'il existe, et on retombe sur python3 sinon.
PY_VENV = os.path.normpath(os.path.join(RACINE, "..", ".venv", "bin", "python3"))
PYTHON = PY_VENV if os.path.exists(PY_VENV) else sys.executable


# ─────────────────────────────────────────────────────────────── l'affichage
#
# ⚠️ ON VIDE LE TAMPON APRES CHAQUE LIGNE, ET AVANT CHAQUE SOUS-PROCESSUS.
# Mesure du 28/08/2026 : dans un terminal, Python ecrit ligne par ligne et tout
# parait normal. Des que la sortie part dans un fichier ou un tuyau — ce que
# fait un log de diagnostic — elle devient bufferisee, alors que le
# sous-processus, lui, ecrit directement. Le resultat est un log ou les
# reponses arrivent avant les questions. Un log qui ment sur l'ordre des
# evenements est pire qu'un log absent : c'est celui qu'on lira le jour d'un
# incident.
def _flush():
    try:
        sys.stdout.flush()
    except Exception:                                          # noqa: BLE001
        pass


def titre(txt):
    print()
    print(GRAS + "  " + txt + N)
    print("  " + "─" * 66)
    _flush()


def dire(txt=""):
    print("  " + txt if txt else "")
    _flush()


def ok(txt):
    print("  " + G + "✓ " + N + txt)
    _flush()


def alerte(txt):
    print("  " + J + "! " + N + txt)
    _flush()


def lire(invite):
    try:
        return raw_input(invite)                               # noqa: F821
    except NameError:
        return input(invite)
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit("  Interrompu. Rien n'a été touché.")


def demander(question, choix, defaut=None, montrer_quitter=False):
    """Une question, des choix numérotés. Retourne la clé choisie.

    `choix` : [(cle, libelle, explication|None)]. Le défaut, s'il existe, est
    accepté sur simple Entrée — un enchaînement quotidien ne doit pas coûter
    quatre frappes.

    `q` quitte TOUJOURS ; `montrer_quitter` ne fait que l'afficher, là où c'est
    la sortie normale plutôt qu'une échappatoire.
    """
    print()
    print("  " + GRAS + question + N)
    for i, (_, libelle, explication) in enumerate(choix, 1):
        marque = "  (Entrée)" if defaut and choix[i - 1][0] == defaut else ""
        print("    %s%d%s  %s%s" % (B, i, N, libelle, marque))
        if explication:
            print("        " + explication)
    if montrer_quitter:
        print("    %sq%s  Quitter" % (B, N))
    _flush()
    while True:
        rep = lire("  > ").strip()
        if not rep and defaut:
            return defaut
        if rep.isdigit() and 1 <= int(rep) <= len(choix):
            return choix[int(rep) - 1][0]
        if rep.lower() in ("q", "quitter"):
            # « Rien n'a été touché » serait FAUX là où quitter est la sortie
            # normale : on y arrive après avoir écrit. Le message suit donc
            # l'endroit d'où on part.
            sys.exit("\n  Terminé." if montrer_quitter
                     else "\n  Interrompu. Rien n'a été touché.")
        alerte("Tape un numéro entre 1 et %d, ou q pour quitter." % len(choix))


def appeler(verbe, *args):
    """Lance `jt.py <verbe>` dans un sous-processus, sortie en direct.

    Sous-processus et non import : chaque étape lit la base sur le disque au
    moment où elle démarre. Les enchaîner dans un même processus ferait
    travailler l'étape 4 sur l'état que l'étape 3 avait en mémoire — un piège
    qu'on n'a pas envie de découvrir un jour de fatigue.
    """
    cmd = [PYTHON, os.path.join(RACINE, "jt.py"), verbe] + list(args)
    _flush()
    return subprocess.call(cmd) == 0


def choisir_journal(defaut):
    """Quel journal Edgewonk ? La liste est LUE, jamais codée en dur.

    ⚠️ ON NE FIGE PAS DES IDENTIFIANTS. L'utilisateur crée et supprime des journaux
    — un bac à sable est apparu le 29/08/2026, le « Compte B » a disparu
    avant. Une liste en dur aurait raison le jour où elle est écrite et tort
    ensuite, en silence. `GET /databases` dit la vérité au moment où on
    demande ; si l'appel échoue, on retombe sur le journal configuré plutôt
    que d'empêcher de travailler.
    """
    try:
        from edgewonk.api import Client
        bases = Client().authentifier().bases() or []
    except Exception as e:                                     # noqa: BLE001
        alerte("journaux illisibles (%s) — on garde %s"
               % (str(e).splitlines()[0], defaut))
        return defaut
    if not bases:
        return defaut
    choix = []
    for b in bases:
        bid, nom = str(b.get("id")), (b.get("name") or b.get("label") or "?")
        marque = "  ← celui de cette plateforme" if bid == defaut else ""
        choix.append((bid, "%s — %s" % (bid, nom), marque.strip() or None))
    return demander("Dans quel journal ?", choix, defaut=defaut)


def choisir_periode():
    """Tout, ou une journée, ou une période. Le geste que l'utilisateur a demandé :
    « je veux diagnostiquer plus vite, importer là où il faut seulement »."""
    quoi = demander("Sur quelle période ?", [
        ("tout", "Toute la base", None),
        ("bornee", "Un jour ou une période",
         "06082026 pour un jour · 06082026-12082026 pour une période"),
    ], defaut="tout")
    if quoi == "tout":
        return None
    while True:
        rep = lire("  date ou période > ").strip()
        if not rep:
            return None
        try:
            debut, fin = noyau.lire_periode(rep)
        except ValueError as e:
            alerte(str(e).splitlines()[0])
            continue
        ok("période retenue : %s" % noyau.libelle_periode(debut, fin))
        return rep


# ──────────────────────────────────────────────────────────────── l'import
def trouver_releves():
    """Les CSV déposés dans IMPORT/, le seul dossier où l'utilisateur travaille.

    C'est le geste réel : glisser l'export dans IMPORT/, lancer, répondre. Lui
    faire taper un chemin serait une régression sur `sync.py` — qui les
    trouvait seul depuis le début.
    """
    if not os.path.isdir(IMPORT):
        return []
    return sorted(os.path.join(IMPORT, f) for f in os.listdir(IMPORT)
                  if f.lower().endswith(".csv") and not f.startswith("sltp_"))


def ouvrir(chemin):
    """Ouvre un DOSSIER dans le Finder. Confort pur : jamais bloquant.

    ⚠️ ON N'OUVRE JAMAIS UN FICHIER. `open` le confie à l'application par
    défaut du système — pour un .csv, Excel — et l'utilisateur lit ses fichiers de
    saisie dans Modern CSV. Un fichier qui s'ouvre tout seul dans le mauvais
    programme est une nuisance, pas un confort : on annonce le chemin, il
    ouvre avec ce qu'il veut. Ne sert donc qu'au dossier IMPORT/, à l'instant
    où on lui demande d'y déposer quelque chose.

    ⚠️ ET PAS `open <dossier>` : si une fenêtre du Finder montre déjà ce
    dossier — ou si le Finder est simplement ouvert ailleurs — `open` se
    contente d'activer l'existante, souvent derrière le terminal, et rien ne
    se passe visiblement. On demande donc au Finder une fenêtre NEUVE, par
    AppleScript, qui vient au premier plan. `open` reste le repli.
    """
    script = ('tell application "Finder"\n'
              '  activate\n'
              '  make new Finder window to (POSIX file "%s" as alias)\n'
              'end tell') % chemin
    try:
        if subprocess.call(["osascript", "-e", script],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) == 0:
            return
    except Exception:                                          # noqa: BLE001
        pass
    try:                                    # repli : Finder absent, ou osascript refusé
        subprocess.call(["open", chemin])
    except Exception:                                          # noqa: BLE001
        pass


EDITEUR_CSV = "Modern CSV"


def ouvrir_saisie(chemin):
    """Ouvre le fichier de saisie AVEC MODERN CSV, nommément. Jamais bloquant.

    ⚠️ PAS `open <fichier>` TOUT COURT : le système le confierait à
    l'application par défaut des .csv — Excel — qui reformate les nombres et
    n'est pas l'outil de l'utilisateur. On nomme donc l'application. Si elle n'est
    pas installée, on ne se rabat PAS sur le défaut (ce serait retomber dans
    Excel) : on se contente de révéler le fichier dans le Finder, et le chemin
    reste affiché juste au-dessus.
    """
    try:
        if subprocess.call(["open", "-a", EDITEUR_CSV, chemin],
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL) == 0:
            return True
    except Exception:                                          # noqa: BLE001
        pass
    alerte("%s introuvable — le fichier est révélé dans le Finder." % EDITEUR_CSV)
    try:
        subprocess.call(["open", "-R", chemin])
    except Exception:                                          # noqa: BLE001
        pass
    return False


def archiver_saisie(chemin):
    """Range la saisie INTÉGRÉE dans donnees/saisies/_traites/, horodatée.

    Même raison que `IMPORT/_traites/` : sans ça le dossier accumule un
    fichier par lancement — onze en quatre jours, tous intégrés, tous
    identiques à trois lignes près — et le seul qui compte se perd dedans.
    On DÉPLACE, on ne supprime pas : le fichier porte la saisie manuelle, la
    seule donnée du système qui ne se reconstruise pas.

    Après `integrer` seulement. Une saisie non intégrée reste en vue.
    """
    import time
    if not os.path.exists(chemin):
        return
    if not os.path.isdir(SAISIES_TRAITEES):
        os.makedirs(SAISIES_TRAITEES)
    cible = os.path.join(SAISIES_TRAITEES, os.path.basename(chemin))
    if os.path.exists(cible):
        cible = "%s_%s" % (cible[:-4], time.strftime("%H%M%S")) + ".csv"
    os.rename(chemin, cible)
    ok("saisie rangée dans saisies/_traites/")


def ranger(releves):
    """Déplace les exports traités dans IMPORT/_traites/, horodatés.

    Sans ça, IMPORT/ accumule, et le prochain lancement propose des relevés
    déjà passés — la façon la plus simple de ré-importer deux fois le même
    fichier sans s'en apercevoir.
    """
    import time
    horo = time.strftime("%Y%m%d-%H%M%S")
    n = 0
    for r in releves:
        if not os.path.exists(r):
            continue
        if not os.path.isdir(TRAITES):
            os.makedirs(TRAITES)
        os.rename(r, os.path.join(TRAITES, "%s_%s" % (horo, os.path.basename(r))))
        n += 1
    if n:
        ok("%d export(s) rangé(s) dans IMPORT/_traites/" % n)


def dernier_fichier(dossier, motif):
    if not os.path.isdir(dossier):
        return None
    lot = [os.path.join(dossier, f) for f in os.listdir(dossier)
           if f.startswith(motif) and f.endswith(".csv")]
    return max(lot, key=os.path.getmtime) if lot else None


def choisir_champs():
    """Le menu de sélection. Accepte « 1 3 5 », « 1,3,5 » ou « tous »."""
    print()
    print("  " + GRAS + "Quels champs ?" + N)
    for i, (_, _, libelle) in enumerate(CHAMPS_ECRITS, 1):
        print("    %s%d%s  %s" % (B, i, N, libelle))
    print("        (plusieurs numéros séparés par un espace, ou « tous »)")
    while True:
        rep = lire("  > ").strip().lower().replace(",", " ")
        if rep in ("", "tous", "tout"):
            return None
        nums = [x for x in rep.split() if x.isdigit()]
        gardes = {CHAMPS_ECRITS[int(x) - 1][0] for x in nums
                  if 1 <= int(x) <= len(CHAMPS_ECRITS)}
        if gardes:
            return gardes
        alerte("Tape des numéros entre 1 et %d, ou « tous »." % len(CHAMPS_ECRITS))


def importer():
    plateforme = demander("Quelle plateforme ?", [
        (pf.CTRADER, "cTrader", "forex et indices · bougies via le MCP local"),
        (pf.TRADOVATE, "Tradovate", "futures · bougies via Databento (facturé à l'usage)"),
    ], defaut=pf.CTRADER)
    drapeau = ["--tradovate"] if plateforme == pf.TRADOVATE else []

    journal = choisir_journal(pf.base_edgewonk(plateforme))
    if journal != pf.base_edgewonk(plateforme):
        drapeau += ["--journal", journal]

    periode = choisir_periode()
    # Deux jeux de drapeaux, parce que l'import ne se borne pas : `drapeau`
    # pour l'import, `borne` pour tout ce qui parcourt ensuite la base.
    borne = list(drapeau) + (["--periode", periode] if periode else [])

    titre("1/5 · Import du relevé")
    p = pf.PLATEFORMES[plateforme]
    attendus = len(p["exports"])
    dire("Attendu : %s" % " + ".join(p["exports"]))

    # ⚠️ LE FINDER S'OUVRE ICI, SANS CONDITION. Le conditionner à un dossier
    # vide ne marche pas : le geste quotidien est de déposer l'export PENDANT
    # que le programme attend, et un relevé de la veille encore présent
    # suffisait à ce que la fenêtre ne s'ouvre jamais. L'étape s'appelle
    # « dépose ton export » : on ouvre le dossier où le déposer, point.
    ouvrir(IMPORT)
    chemins = trouver_releves()
    if chemins:
        dire()
        for c in chemins:
            ok("trouvé dans IMPORT/ : %s" % os.path.basename(c))
    # La consigne ne se répète pas : les tours suivants ne réaffichent que le
    # compte — savoir ce qui manque est utile, se faire réexpliquer la
    # manœuvre ne l'est pas.
    montre = False
    while len(chemins) != attendus:
        dire()
        alerte("%d fichier(s) dans IMPORT/, %d attendu(s)." % (len(chemins), attendus))
        if not montre:
            dire("Dépose l'export dans la fenêtre du Finder, puis Entrée.")
            dire("(ou colle un chemin)")
            montre = True
        rep = lire("  > ").strip().strip("'\" ")
        if rep and os.path.exists(rep):
            chemins = [rep]
        else:
            chemins = trouver_releves()
    # ⚠️ La borne ne s'applique PAS à l'import du relevé lui-même : le fichier
    # contient ce qu'il contient, et en écarter des lignes produirait une base
    # trouée qu'aucun cycle ne viendrait combler. Elle borne les ÉTAPES 3, 4
    # et 5 — mesurer, dessiner, pousser — qui parcourent la base.
    if not appeler("importer", *(drapeau + chemins)):
        sys.exit("\n  L'import a échoué. Rien d'autre n'a été lancé.")

    saisie = dernier_fichier(SAISIES, "sltp_")
    if not saisie:
        sys.exit("\n  Aucun fichier de saisie trouvé.")

    titre("2/5 · Saisie")
    dire("Fichier : %s" % saisie)
    dire("Remplis les colonnes sl, tp et management, enregistre, reviens ici.")
    ouvrir_saisie(saisie)
    lire("  Entrée quand c'est fait > ")
    if not appeler("controler", *(drapeau + [saisie])):
        sys.exit("\n  Le contrôle a échoué.")
    if demander("Intégrer cette saisie dans la base ?", [
            ("oui", "Oui, écrire", "un instantané est pris avant"),
            ("non", "Non, m'arrêter là", None)], defaut="oui") != "oui":
        sys.exit("\n  Arrêté. La base n'a pas bougé.")
    if appeler("integrer", *(drapeau + [saisie])):
        archiver_saisie(saisie)
    ranger(chemins)

    return mesurer_dessiner_pousser(borne, depart=3, total=5)


def mesurer_dessiner_pousser(borne, depart=1, total=3):
    """Les étapes MESURER, DESSINER, POUSSER. Communes à l'import et à la reprise.

    Une seule implémentation, appelée de deux endroits : c'est la leçon des deux
    orchestrateurs — celui qui n'était pas lancé tous les jours était celui qui
    savait faire quelque chose de plus.
    """
    titre("%d/%d · Bougies" % (depart, total))
    appeler("bougies", *borne)

    titre("%d/%d · Graphiques" % (depart + 1, total))
    dire("Une position dont les données ont changé depuis son rendu est")
    dire("redessinée d'elle-même — la saisie d'un SL ou d'un TP en fait partie.")
    appeler("graphiques", *borne)

    titre("%d/%d · Poussée vers Edgewonk" % (depart + 2, total))
    mode = demander("Comment écrire chez Edgewonk ?", [
        (MODE_VIDE, "Ne remplir que le vide",
         "préserve tout ce que tu as corrigé à la main, captures comprises"),
        (MODE_ECRASER, "Écraser",
         "la base fait autorité : tout champ qui diffère est réécrit, "
         "captures comprises"),
    ], defaut=MODE_VIDE)
    portee = demander("Sur quels champs ?", [
        ("tous", "Tous les champs", None),
        ("choix", "Une sélection", "utile pour ne reprendre qu'une chose"),
    ], defaut="tous")
    champs = choisir_champs() if portee == "choix" else None

    args = list(borne) + ["--mode", mode]
    if champs:
        args += ["--champs", ",".join(sorted(champs))]
    appeler("pousser", *args)
    return list(borne)


def epilogue(borne):
    """Ce qu'on peut faire SANS relancer le script. Retourne quand on remonte.

    ⚠️ LE CAS QUI L'A FAIT NAITRE *(29/08/2026)* : LES STRATEGIES ALTERNATIVES.
    Leurs identifiants sont propres a chaque SETUP (§13), et un trade fraichement
    importe arrive en setup par defaut. Au moment de la poussee, il n'y a donc
    aucun palier a lui donner — ce n'est pas une panne, c'est l'ordre des choses :
    L'utilisateur pose ses setups dans Edgewonk APRES l'import, quand il fait son
    journaling. Le champ ne pouvait se remplir qu'a une seconde passe, et cette
    seconde passe coutait de tout relancer, relevé compris.

    Elle est maintenant a une touche, sur la MEME borne que ce qui vient d'etre
    fait — meme plateforme, meme journal, meme periode. On ne redemande rien :
    redemander, c'est deja avoir perdu.
    """
    while True:
        quoi = demander("Et maintenant ?", [
            ("paliers", "Mettre à jour les stratégies alternatives",
             "sur ce qui vient d'être traité — après avoir posé les setups chez Edgewonk"),
            ("menu", "Revenir au menu principal", None),
        ], defaut="menu", montrer_quitter=True)
        if quoi == "menu":
            return
        titre("Stratégies alternatives")
        dire("Les paliers se résolvent par NOM, dans le catalogue du SETUP du trade.")
        dire("Un trade resté en setup par défaut n'a aucun palier à recevoir :")
        dire("pose les setups chez Edgewonk d'abord, relance ceci ensuite.")
        appeler("pousser", *(list(borne) + ["--mode", MODE_ECRASER,
                                            "--champs", "paliers"]))


def reprendre():
    """Relancer mesurer / dessiner / pousser SANS import ni saisie.

    ⚠️ POURQUOI CETTE TROISIÈME PORTE *(29/08/2026)*. Il n'y en avait que deux —
    importer, auditer — et la seule façon de refaire une mesure, un dessin ou une
    poussée était de taper `jt.py` à la main. L'utilisateur ne tape pas de commandes,
    et il a raison : un geste qui n'existe que dans une ligne de terminal
    n'existe pas.

    Le cas qui l'a fait naître : cinq positions rendues avant que leurs niveaux
    soient saisis, donc dessinées sans SL ni TP, et des captures périmées chez
    Edgewonk. Rien à ré-importer — le relevé était déjà passé. Il fallait juste
    redessiner et réécrire.
    """
    plateforme = demander("Quelle plateforme ?", [
        (pf.CTRADER, "cTrader", "forex et indices · bougies via le MCP local"),
        (pf.TRADOVATE, "Tradovate", "futures · bougies via Databento (facturé à l'usage)"),
    ], defaut=pf.CTRADER)
    drapeau = ["--tradovate"] if plateforme == pf.TRADOVATE else []

    journal = choisir_journal(pf.base_edgewonk(plateforme))
    if journal != pf.base_edgewonk(plateforme):
        drapeau += ["--journal", journal]

    periode = choisir_periode()
    borne = list(drapeau) + (["--periode", periode] if periode else [])
    return mesurer_dessiner_pousser(borne)


# ───────────────────────────────────────────────────────────────── l'audit
AUDITS = (
    ("trade",     "Un trade en particulier",
     "par id Edgewonk ou par clé de jambe — les trois sources côte à côte"),
    ("coherence", "Cohérence du journal",
     "incohérences internes, doublons, écarts de prix d'exécution"),
    ("mesures",   "Les mesures recalculées",
     "extrêmes, bougies de bord, TP-first par une seconde implémentation"),
    ("images",    "Les captures",
     "les quatre emplacements des deux côtés, avec réparation possible"),
    ("tout",      "Tout auditer", "les quatre ci-dessus, à la suite"),
)

# Un audit = un ou plusieurs outils de `outils/`. La table est ici, en clair :
# ajouter un outil à un audit se voit, et ne se cherche pas dans le code.
#
# `mcp` marque les outils qui exigent cTrader OUVERT. On le vérifie UNE fois
# avant de les lancer, plutôt que de laisser trois outils échouer l'un après
# l'autre — mesure du premier audit global, 28/08/2026 : trois traces
# d'exécution de vingt lignes chacune pour dire « cTrader est fermé ».
OUTILS = {
    "coherence": [("diag_coherence.py", False), ("diag_doublons.py", False)],
    "mesures":   [("diag_bougies.py", True), ("diag_bord.py", True),
                  ("diag_tp_first.py", True)],
    "images":    [("diag_images.py", False)],
}

# Signatures reconnues dans la sortie d'un outil qui a échoué. Traduire une
# trace d'exécution en une phrase est tout l'écart entre un audit lisible et un
# audit qu'on renonce à lire.
CAUSES = (
    ("ErreurMCP", "cTrader n'est pas ouvert, ou « Enable MCP Server » est décoché"),
    ("mot_de_passe_du_trousseau", "identifiants Edgewonk absents du trousseau"),
    ("aucune entree", "identifiants Edgewonk absents du trousseau"),
    ("ErreurDatabento", "Databento a refusé la requête"),
    ("ReponseIllisible", "la source de bougies a répondu en texte au lieu de données"),
    ("KeyError", "un fichier lu n'a pas les colonnes attendues"),
    ("FileNotFoundError", "un fichier attendu n'existe pas"),
)

ECHECS = []


def mcp_ouvert():
    """cTrader répond-il ? Une seule sonde, courte, avant tout le lot."""
    try:
        from ctrader.mcp import Client, ErreurMCP
        Client().ouvrir()
        return True
    except Exception:                                          # noqa: BLE001
        return False


def lancer_outil(nom, *args):
    """Lance un outil, laisse sa sortie défiler, et TRADUIT son échec.

    ⚠️ UN AUDIT NE DOIT PAS S'ARRÊTER SUR UN OUTIL QUI TOMBE, NI VOMIR SA TRACE.
    Mesure du 28/08/2026, premier audit global : trois outils sur huit ont
    planté, et leurs traces d'exécution — soixante lignes — ont noyé les vrais
    résultats des cinq autres. Un audit illisible est un audit qu'on cesse de
    lancer.
    """
    chemin = os.path.join(RACINE, "outils", nom)
    if not os.path.exists(chemin):
        alerte("%s introuvable — archivé ? Voir archives/CATALOGUE.md" % nom)
        ECHECS.append((nom, "fichier absent"))
        return
    print()
    print("  " + B + "─── " + nom + N)
    _flush()
    p = subprocess.Popen([PYTHON, chemin] + list(args),
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    sortie = []
    # ⚠️ UNE TRACE A UNE FORME, PAS UNE INDENTATION.
    # Première version : masquer toute ligne commençant par quatre espaces.
    # Elle masquait aussi les commandes que les outils proposent de taper —
    # `diag_images` annonçait « pour rendre ces jambes éligibles : » suivi de
    # rien. Mesure du 28/08/2026, deuxième audit. *Un filtre qui se fie à
    # l'indentation ne distingue pas une erreur d'une instruction.*
    #
    # La vraie forme : « Traceback (most recent call last): » ouvre le bloc,
    # les lignes indentées le composent, et la première ligne NON indentée le
    # ferme — c'est le type de l'exception, la seule ligne qui vaille d'être
    # montrée. On garde donc celle-là et on jette le reste.
    dans_trace = False
    for ligne in iter(p.stdout.readline, b""):
        texte = ligne.decode("utf-8", "replace")
        sortie.append(texte)
        if texte.startswith("Traceback"):
            dans_trace = True
            continue
        if dans_trace:
            if texte[:1] in (" ", "\t"):
                continue                       # le corps de la trace
            dans_trace = False                 # la ligne d'exception : on la montre
        sys.stdout.write(texte)
    p.stdout.close()
    code = p.wait()
    _flush()
    if code == 0:
        return
    brut = "".join(sortie)
    cause = next((c for m, c in CAUSES if m in brut), None)
    derniere = [l.strip() for l in brut.splitlines() if l.strip()]
    if cause is None:
        cause = derniere[-1][:120] if derniere else "échec sans message"
    print()
    alerte("%s n'a pas pu tourner — %s" % (nom, cause))
    ECHECS.append((nom, cause))


def auditer():
    # ⚠️ REMIS A ZERO A CHAQUE AUDIT. `ECHECS` est un etat de module, et depuis
    # que `main()` boucle, deux audits dans la meme session cumulaient leurs
    # echecs : le second annoncait ceux du premier, deja corriges. Un compteur
    # qui ne se vide pas ment a la deuxieme utilisation.
    del ECHECS[:]
    quoi = demander("Auditer quoi ?", [(c, l, e) for c, l, e in AUDITS],
                    defaut="tout")

    options = []
    if quoi != "trade":                     # un trade précis n'a pas de période
        journal = choisir_journal(pf.base_edgewonk(pf.CTRADER))
        if journal != pf.base_edgewonk(pf.CTRADER):
            options += ["--journal", journal]
        periode = choisir_periode()
        if periode:
            options += ["--periode", periode]

    if quoi == "trade":
        ref = lire("\n  id Edgewonk (ex. 17926446) ou clé de jambe > ").strip()
        if not ref:
            return
        lancer_outil("diag_id.py" if ref.isdigit() else "diag_trade.py", ref)
        return

    cibles = ["coherence", "mesures", "images"] if quoi == "tout" else [quoi]

    # La sonde MCP, UNE fois, et seulement si un outil en a besoin.
    besoin_mcp = any(mcp for c in cibles for _, mcp in OUTILS[c])
    dispo = mcp_ouvert() if besoin_mcp else True
    if besoin_mcp and not dispo:
        print()
        alerte("cTrader n'est pas ouvert (ou « Enable MCP Server » est décoché).")
        dire("Les audits qui lisent des bougies sont sautés — le reste tourne.")

    sautes = []
    for c in cibles:
        titre("Audit · %s" % c)
        for outil, mcp in OUTILS[c]:
            if mcp and not dispo:
                sautes.append(outil)
                continue
            lancer_outil(outil, *options)

    titre("Résumé de l'audit")
    lances = sum(len(OUTILS[c]) for c in cibles) - len(sautes)
    print("  outils lancés    : %d" % lances)
    print("  en échec         : %s%d%s" % ((R if ECHECS else G), len(ECHECS), N))
    for nom, cause in ECHECS:
        print("     %-24s %s" % (nom, cause))
    if sautes:
        print("  sautés (cTrader) : %d" % len(sautes))
        for nom in sautes:
            print("     %s" % nom)
    print()
    if not ECHECS and not sautes:
        ok("Tout a tourné. Aucun de ces outils n'écrit.")
    else:
        dire("Aucun de ces outils n'écrit — sauf `diag_images.py --reparer`, "
             "qu'il faut demander.")


# ────────────────────────────────────────────────────────────────── l'entrée
def main():
    """La boucle. On ne quitte que si on le demande.

    ⚠️ UNE PASSE PAR LANCEMENT ETAIT LA VRAIE FRICTION. Le script faisait une
    chose puis rendait la main au shell ; enchainer deux gestes — importer, puis
    reprendre autre chose — coutait de tout relancer et de retraverser les
    memes questions. Le travail reel n'est pas une passe, c'est une session.
    """
    verbe = sys.argv[1] if len(sys.argv) > 1 else None
    print()
    print(GRAS + "  JOURNAL DE TRADING" + N)
    print("  " + "═" * 66)
    while True:
        if verbe not in ("importer", "reprendre", "auditer"):
            verbe = demander("Que veux-tu faire ?", [
                ("importer", "Importer des trades",
                 "relevé → base → saisie → mesures → graphiques → Edgewonk"),
                ("reprendre", "Reprendre des trades déjà importés",
                 "remesurer, redessiner, réécrire — sans relevé ni saisie"),
                ("auditer", "Auditer",
                 "vérifier, comprendre, diagnostiquer — sans rien écrire"),
            ], defaut="importer", montrer_quitter=True)
        borne = {"importer": importer, "reprendre": reprendre,
                 "auditer": auditer}[verbe]()
        # L'audit n'ecrit rien : il n'y a pas de « et maintenant » a proposer.
        if borne is not None:
            epilogue(borne)
        verbe = None
        print()
        print("  " + "═" * 66)


if __name__ == "__main__":
    sys.exit(main())
