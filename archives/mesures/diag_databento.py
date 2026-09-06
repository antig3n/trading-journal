#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DIAGNOSTIC EN LECTURE SEULE — Databento peut-il fournir nos bougies futures ?

N'ECRIT RIEN, ni en local, ni chez Databento, ni chez Edgewonk. Que des GET.
Et par defaut il ne TELECHARGE aucune donnee facturee : il chiffre d'abord.

LA QUESTION, ET POURQUOI ELLE SE POSE
-------------------------------------
Cote cTrader, les bougies viennent du serveur MCP local : gratuit, sans
approbation, qualite production (`docs/ctrader-sltp-protocol.md` §7 bis). Cote
TRADOVATE, il n'y a rien : leur API est fermee aux comptes prop firm
(`docs/tradovate.md` §1) et Edgewonk ne porte pas les cotations de ces actifs. Sans
source de prix, pas d'extremes, pas de TP-first, pas de paliers, pas de
graphiques — c'est-a-dire tout ce que ce projet apporte.

Databento vend l'historique CME a l'usage, sans abonnement, avec 125 $ de
credits offerts a l'inscription. Sur le papier c'est la bonne piece. Ce
diagnostic verifie que c'est vrai SUR PIECE, avant qu'une ligne de pipeline ne
s'appuie dessus.

CE QU'IL MESURE, DANS CET ORDRE
-------------------------------
  1. l'authentification repond
  2. le dataset GLBX.MDP3 existe, et jusqu'ou remonte son historique
  3. quels schemas il expose  (attendu : pas de 5m ni de 15m — a confirmer)
  4. le tarif reel au gigaoctet, par schema
  5. nos symboles de contrat se resolvent  (MNQU6, MNQZ5, MGCZ5, 6EH6…)
  6. le cout exact d'une fenetre realiste, en dollars

⚠️ METHODE — ON SONDE, ON NE SUPPOSE PAS.

Le contrat de cette API n'a pas ete lu dans leur documentation : la recherche
web etait indisponible au moment d'ecrire. Les URL ci-dessous sont donc des
HYPOTHESES, et ce fichier est construit pour que l'hypothese fausse se voie
au lieu de casser en silence — chaque sonde affiche son code de retour, et une
404 est une REPONSE, pas un echec. C'est exactement ce qui a fait tomber le
catalogue des commentaires d'Edgewonk le 26/08 : onze URL sondees, dix en 403,
une seule bonne. Personne ne l'aurait devinee.

Si une sonde repond autre chose que ce qu'on attend, corriger ICI, puis seulement
ecrire le module de production.

CLE API — trousseau macOS, jamais en clair dans un fichier ni dans le depot.
Meme regle que le mot de passe Edgewonk. A creer une fois, dans un Terminal :

    security add-generic-password -s databento -a <ton-email> -w

(sans la cle sur la ligne : `security` la demandera, elle ne restera donc pas
dans l'historique du shell.)
"""

import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

# --------------------------------------------------------------------- reglages

SERVICE_TROUSSEAU = "databento"
DELAI = 30

# HYPOTHESE a confirmer par la sonde 1. Databento versionne son API historique
# sous /v0/ et nomme ses points d'entree « module.methode ».
BASE = "https://hist.databento.com/v0"

# CME Globex MDP 3.0 — couvre CME, CBOT, NYMEX et COMEX, donc les six produits
# que l'utilisateur trade : MNQ, NQ (CME) · MGC, GC (COMEX) · MCL (NYMEX) · 6E (CME).
DATASET = "GLBX.MDP3"

# Les contrats a resoudre. Format brut du CME, celui qu'affiche Tradovate :
# racine + mois + dernier chiffre de l'annee. Verifie avec l'utilisateur le
# 26/08/2026 : il est en MNQU6 (septembre 2026) et parle de MNQZ6 pour le
# suivant. Les anciens trades vont d'octobre 2025 a aout 2026, donc Z5 (dec
# 2025), H6 (mars), M6 (juin), U6 (sept).
#
# ⚠️ Ces symboles sont ceux de l'INTERFACE Tradovate. Ceux de l'EXPORT n'ont
# pas encore ete vus — aucun export n'est arrive dans le projet a ce jour. Tant
# qu'un vrai export n'a pas ete lu, la correspondance reste une hypothese.
SYMBOLES = ["MNQU6", "MNQZ5", "MNQH6", "NQU6", "MGCZ5", "GCZ5", "MCLF6", "6EH6"]

# Une fenetre courte et ancienne : de quoi chiffrer sans rien telecharger.
FENETRE = ("2026-03-02", "2026-03-03")


class Erreur(Exception):
    pass


# ----------------------------------------------------------------- transport

def cle_du_trousseau(service=SERVICE_TROUSSEAU):
    """La cle API depuis le trousseau macOS. Jamais en clair dans le depot."""
    try:
        return subprocess.check_output(
            ["security", "find-generic-password", "-s", service, "-w"],
            stderr=subprocess.STDOUT).decode("utf-8", "replace").strip()
    except (subprocess.CalledProcessError, OSError):
        raise Erreur(
            "aucune entree « %s » dans le trousseau.\n"
            "  A creer une fois :\n"
            "    security add-generic-password -s %s -a <ton-email> -w"
            % (service, service))


def sonder(cle, chemin, parametres=None):
    """(code, corps) — ne leve jamais sur un code HTTP. Une 404 est une reponse.

    Databento s'authentifie en HTTP Basic avec la cle en guise d'identifiant et
    un mot de passe VIDE. C'est l'hypothese ; si elle est fausse, la sonde 1
    rendra 401 et il faudra corriger ici, pas ailleurs.
    """
    url = chemin if chemin.startswith("http") else "%s/%s" % (BASE, chemin)
    if parametres:
        url += "?" + urllib.parse.urlencode(parametres)
    jeton = base64.b64encode(("%s:" % cle).encode("utf-8")).decode("ascii")
    requete = urllib.request.Request(url, headers={
        "Authorization": "Basic " + jeton,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(requete, timeout=DELAI) as r:
            charge = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(charge)
            except ValueError:
                return r.status, charge
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", "replace")[:400]
    except urllib.error.URLError as err:
        return 0, "injoignable (%s)" % err
    except TimeoutError as err:                                  # noqa: F821
        return 0, "delai depasse (%s)" % err


# ----------------------------------------------------------------- affichage

G, J, R, N, GRAS = "\033[32m", "\033[33m", "\033[31m", "\033[0m", "\033[1m"


def titre(t):
    print()
    print("  " + GRAS + t.upper() + N)
    print("  " + "-" * 62)


def ligne(etiquette, code, corps, apercu=220):
    couleur = G if code == 200 else (J if code else R)
    texte = corps if isinstance(corps, str) else json.dumps(corps, ensure_ascii=False)
    if len(texte) > apercu:
        texte = texte[:apercu] + " …"
    print("  %-28s %s%3s%s  %s" % (etiquette, couleur, code or "---", N, texte))


# -------------------------------------------------------------------- sondes

def main():
    print()
    print(GRAS + "  DIAGNOSTIC DATABENTO — LECTURE SEULE, AUCUNE DEPENSE" + N)
    print("  " + "=" * 62)

    try:
        cle = cle_du_trousseau()
    except Erreur as e:
        print()
        print("  " + R + str(e) + N)
        return 1
    print("  cle lue dans le trousseau (%d caracteres, prefixe %r)"
          % (len(cle), cle[:3]))

    # --- 1. l'authentification et la forme des URL -------------------------
    titre("1. la porte d'entree")
    candidats = [
        ("metadata.list_datasets", None),
        ("metadata.list_publishers", None),
        ("metadata.list_schemas", {"dataset": DATASET}),
    ]
    vivant = False
    for chemin, params in candidats:
        code, corps = sonder(cle, chemin, params)
        ligne(chemin, code, corps)
        if code == 200:
            vivant = True
    if not vivant:
        print()
        print("  " + R + "aucune sonde n'a repondu 200." + N)
        print("  401 -> la cle ou le schema d'authentification est faux (BASE, Basic).")
        print("  404 -> la forme des URL est fausse : corriger BASE et les chemins.")
        print("    0 -> reseau ou delai. Rien d'autre a conclure.")
        return 1

    # --- 2. la profondeur de l'historique ----------------------------------
    #
    # C'est LE point qui decide du chantier : le premier trade futures de
    # L'utilisateur date d'octobre 2025. Si l'historique ne remonte pas au moins
    # jusque-la, une partie des trades restera sans extremes ni graphiques —
    # et il faudra le dire, pas le decouvrir plus tard.
    titre("2. jusqu'ou remonte l'historique de %s" % DATASET)
    code, corps = sonder(cle, "metadata.get_dataset_range", {"dataset": DATASET})
    ligne("get_dataset_range", code, corps)

    # --- 3. les schemas disponibles ----------------------------------------
    #
    # Attendu, d'apres leur documentation : ohlcv-1s, ohlcv-1m, ohlcv-1h,
    # ohlcv-1d — et PAS de 5m ni de 15m. Le M5 et le M15 des graphiques se
    # construiront donc par agregation du M1, cote client. Le H4 depuis le H1.
    # A confirmer ici : c'est une lecture de doc, pas une mesure.
    titre("3. les schemas exposes")
    code, corps = sonder(cle, "metadata.list_schemas", {"dataset": DATASET})
    ligne("list_schemas", code, corps, apercu=400)
    if code == 200 and isinstance(corps, list):
        manquants = [s for s in ("ohlcv-5m", "ohlcv-15m") if s not in corps]
        if manquants:
            print("  " + J + "confirme : %s absent(s) -> agregation cote client"
                  % ", ".join(manquants) + N)

    # --- 4. le tarif reel --------------------------------------------------
    titre("4. le tarif, en dollars par gigaoctet")
    code, corps = sonder(cle, "metadata.list_unit_prices", {"dataset": DATASET})
    ligne("list_unit_prices", code, corps, apercu=500)

    # --- 5. la symbologie --------------------------------------------------
    #
    # Le seul vrai inconnu du chantier. Si les symboles bruts de Tradovate
    # sont ceux du CME, il n'y a AUCUNE table de correspondance a maintenir —
    # exactement la conclusion qu'on avait tiree cote cTrader avec XAUUSD.raw.
    titre("5. nos contrats se resolvent-ils ?")
    code, corps = sonder(cle, "symbology.resolve", {
        "dataset": DATASET,
        "symbols": ",".join(SYMBOLES),
        "stype_in": "raw_symbol",
        "stype_out": "instrument_id",
        "start_date": FENETRE[0],
        "end_date": FENETRE[1],
    })
    ligne("symbology.resolve", code, corps, apercu=600)
    if code == 200 and isinstance(corps, dict):
        trouves = corps.get("result") or {}
        pas_trouves = corps.get("not_found") or []
        # ⚠️ `result` porte TOUS les symboles demandes en cle, avec une LISTE
        # VIDE pour ceux qui ne se resolvent pas. Tester la presence de la cle
        # marquait donc « OK » des symboles que la meme reponse listait juste
        # en dessous comme non resolus (constate le 26/08/2026). C'est le
        # vérificateur qui ment, troisieme fois dans ce projet : on teste le
        # CONTENU, jamais la presence de la cle.
        for s in SYMBOLES:
            marque = G + "OK " + N if trouves.get(s) else J + "?? " + N
            print("     %s %s" % (marque, s))
        if pas_trouves:
            print("  " + J + "non resolus : %s" % ", ".join(map(str, pas_trouves)) + N)
            print("  (normal pour un contrat hors de la fenetre demandee — "
                  "un contrat n'existe qu'entre sa cotation et son echeance)")

    # --- 6. le cout, AVANT de depenser -------------------------------------
    #
    # `get_cost` est une metadonnee : elle ne facture rien. C'est elle qui
    # permet de dire un prix mesure plutot qu'un prix suppose.
    titre("6. ce que couterait une journee de M1")
    code, corps = sonder(cle, "metadata.get_cost", {
        "dataset": DATASET,
        "symbols": "MNQH6",
        "schema": "ohlcv-1m",
        "stype_in": "raw_symbol",
        "start": FENETRE[0],
        "end": FENETRE[1],
    })
    ligne("get_cost (1 contrat, 1 jour)", code, corps)
    if code == 200:
        try:
            cout = float(corps if not isinstance(corps, dict)
                         else corps.get("cost", corps.get("total_cost")))
            print()
            print("  extrapolation grossiere, a titre indicatif seulement :")
            print("     34 trades futures, fenetres de quelques heures -> "
                  "de l'ordre de %.4f $" % (cout * 34))
            print("     " + J + "les 125 $ de credits couvrent tout, tres largement." + N)
        except (TypeError, ValueError):
            pass

    print()
    print("  " + "=" * 62)
    print("  Rien n'a ete telecharge, rien n'a ete facture, rien n'a ete ecrit.")
    print("  Prochaine etape seulement si tout ci-dessus est vert :")
    print("     tirer UNE fenetre de M1 sur UN trade, et en rendre les 4 images.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
