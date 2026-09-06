"""Client de l'API interne d'Edgewonk 3. Aucune dépendance externe.

Contrat entièrement repris de `docs/edgewonk-api.md`, reconstitué par capture HAR et
validé en conditions réelles (338 écritures consécutives). API NON
CONTRACTUELLE : elle peut changer sans préavis. C'est le côté fragile du
montage, et c'est pourquoi tout ce qui parle à Edgewonk vit dans ce seul
dossier — le jour où elle casse, un seul dossier bouge.

TROIS RÈGLES QUI VIENNENT DE TESTS RÉELS, PAS DE PRINCIPES

1. **Ne jamais construire un PUT à la main.** Le PUT REMPLACE l'objet entier :
   une clé omise est EFFACÉE (vérifié sur `additionalNotes`). Un PUT bâclé
   efface le tagging de l'utilisateur — le seul contenu du système qui ne soit pas
   reproductible. Passer par `charge_utile_put()`, jamais autrement.

2. **Un statut 200 ne prouve rien.** `modify` répond 200 à tout, y compris pour
   un champ qu'il n'écrit PAS : il a une liste blanche et ignore le reste EN
   SILENCE. Toujours relire après écriture.

3. **`modify` ne peut pas vider un champ.** `null` y est traité comme « non
   fourni » ; `0` écrit bien `0`. Pour remettre à null, il faut le PUT.

MOT DE PASSE : trousseau macOS, jamais en clair dans un fichier ni dans un
dépôt. Ne jamais exporter un HAR contenant /auth/authenticate — le corps y est
en clair.
"""

import binascii
import io
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request

LICENCE = "https://license.edgewonk.app"
API = "https://api.edgewonk.app/v1"
IMAGES = "https://images.edgewonk.app"

SERVICE_TROUSSEAU = "edgewonk"
DELAI = 30
DELAI_IMAGE = 60          # un PNG de 65 Ko passe vite, mais le reseau varie

# Bascule mesuree le 24/08/2026 : 2,07 Mo -> 201, 6,3 Mo -> 403. On refuse en
# amont plutot que de decouvrir un 403 apres coup. Nos rendus font ~65 Ko.
TAILLE_MAX_IMAGE = 5 * 1024 * 1024

# --- champs que `modify` accepte réellement. Mesuré, pas supposé.
MODIFIABLES = ("slPrice", "tpPrice", "highestPrice", "lowestPrice", "inReview",
               "screenshot1Exists", "screenshot2Exists", "screenshot3Exists",
               "screenshot4Exists", "screenshot5Exists", "screenshot6Exists")

# --- présents dans le GET, calculés serveur : ne JAMAIS les renvoyer au PUT.
CALCULES_SERVEUR = (
    "gainPercent", "rMultiple", "rrrPlanned", "rrrRealized", "accountSize",
    "accountBalance", "accountNumber", "updraw", "drawDown", "tpHit", "slHit",
    "positionSize", "riskAmount", "openQuantity", "realizedPcp", "plannedPcp",
    "tiltMeter", "screenshotExists",
    "entryComment", "exitComment", "managementComment",     # les SINGULIERS
)

# --- tableaux d'OBJETS dans le GET, tableaux d'IDENTIFIANTS dans le PUT.
TABLEAUX_OBJETS = ("customComments", "checklistItems", "preTradeComments",
                   "entryComments", "exitComments", "managementComments")

# --- objets dans le GET, identifiant scalaire dans le PUT.
OBJETS_SCALAIRES = ("instrument", "setup")


class ErreurEdgewonk(Exception):
    pass


def mot_de_passe_du_trousseau(service=SERVICE_TROUSSEAU):
    """(identifiant, mot de passe) depuis le trousseau macOS.

    À créer une seule fois, dans un Terminal :
        security add-generic-password -s edgewonk -a <email> -w

    (sans le mot de passe sur la ligne : `security` le demandera, il ne
    restera donc pas dans l'historique du shell.)
    """
    try:
        brut = subprocess.check_output(
            ["security", "find-generic-password", "-s", service],
            stderr=subprocess.STDOUT).decode("utf-8", "replace")
        mdp = subprocess.check_output(
            ["security", "find-generic-password", "-s", service, "-w"],
            stderr=subprocess.STDOUT).decode("utf-8", "replace").strip()
    except subprocess.CalledProcessError:
        raise ErreurEdgewonk(
            "aucune entree « %s » dans le trousseau.\n"
            "  A creer une fois :\n"
            "    security add-generic-password -s %s -a <ton-email> -w"
            % (service, service))
    identifiant = ""
    for ligne in brut.splitlines():
        ligne = ligne.strip()
        if ligne.startswith('"acct"'):
            identifiant = ligne.split("=", 1)[1].strip().strip('"')
            break
    if not identifiant:
        raise ErreurEdgewonk("entree « %s » sans identifiant (-a)" % service)
    return identifiant, mdp


class Client(object):

    def __init__(self, delai=DELAI):
        self.delai = delai
        self.jeton = None          # le blob X-Auth-Token, tel quel
        self.signature = None

    # ------------------------------------------------------------- transport
    def _requete(self, methode, url, corps=None, entetes=None, brut=False,
                 donnees=None):
        """`corps` est encode en JSON ; `donnees` part tel quel (multipart)."""
        e = {"Accept": "application/json"}
        if self.jeton:
            e["X-Auth-Token"] = self.jeton
        if corps is not None:
            e["Content-Type"] = "application/json"
        e.update(entetes or {})
        if donnees is None and corps is not None:
            donnees = json.dumps(corps).encode("utf-8")
        requete = urllib.request.Request(url, data=donnees, headers=e, method=methode)
        try:
            with urllib.request.urlopen(requete, timeout=self.delai) as r:
                charge = r.read()
                if brut:
                    return r.status, charge
                if not charge:
                    return r.status, None
                return r.status, json.loads(charge.decode("utf-8"))
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", "replace")[:300]
            raise ErreurEdgewonk("%s %s -> %s %s" % (methode, url, err.code, detail))
        except urllib.error.URLError as err:
            raise ErreurEdgewonk("%s %s injoignable (%s)" % (methode, url, err))

    # --------------------------------------------------------------- session
    def authentifier(self, identifiant=None, mot_de_passe=None):
        if identifiant is None or mot_de_passe is None:
            identifiant, mot_de_passe = mot_de_passe_du_trousseau()
        _, rep = self._requete("POST", LICENCE + "/auth/authenticate",
                               {"user": identifiant, "password": mot_de_passe})
        return self._retenir(rep)

    def rafraichir(self):
        """À privilégier : `validUntil` est à ~1 h, on prolonge sans remanipuler
        le mot de passe."""
        _, rep = self._requete(
            "POST", LICENCE + "/auth/refresh-token", {},
            entetes={"Authorization": "Bearer %s" % self.signature})
        return self._retenir(rep)

    def _retenir(self, rep):
        if not rep or "authentication" not in rep or "signature" not in rep:
            raise ErreurEdgewonk("reponse d'authentification inattendue")
        self.signature = rep["signature"]
        # L'en-tete est EXACTEMENT le JSON de ces deux champs, tel que renvoye.
        self.jeton = json.dumps({"authentication": rep["authentication"],
                                 "signature": rep["signature"]})
        return self

    def valide_jusqu_a(self):
        try:
            bloc = json.loads(json.loads(self.jeton)["authentication"])
            return bloc.get("validUntil")
        except Exception:                                    # noqa: BLE001
            return None

    # ---------------------------------------------------------------- lecture
    def bases(self):
        _, rep = self._requete("GET", API + "/databases")
        return rep

    def trades(self, base_id, offset=0, limite=200):
        """Liste des trades. Renvoie l'objet complet, champs calcules compris."""
        _, rep = self._requete(
            "POST", "%s/databases/%s/journal-entries-search/%d/%d"
                    % (API, base_id, offset, limite),
            {"orFilter": True, "tradeDate": "EXIT", "excludeFilters": False,
             "timeZone": "Europe/Paris"})
        return (rep or {}).get("data", [])

    def tous_les_trades(self, base_id, page=200, plafond=5000, progression=None):
        """Tous les trades d'une base, pagines.

        MESURE le 25/08/2026 : la recherche N'EST PAS triee par date decroissante.
        Un appel offset=0/limit=200 sur la base 100001 a renvoye des trades de
        novembre 2025 a juillet 2026 — aucun trade d'aout 2026, pourtant
        presents. Prendre la premiere page pour « les trades recents » serait
        une erreur silencieuse : on parcourt tout.
        """
        tous, offset = [], 0
        while offset < plafond:
            lot = self.trades(base_id, offset, page)
            if not lot:
                break
            tous += lot
            if progression:
                progression(len(tous))
            if len(lot) < page:
                break
            offset += page
        return tous

    def strategies(self, base_id, setup_id):
        """Les strategies alternatives d'un setup : [{id, name, ...}].

        ⚠️ Leurs identifiants sont propres a CHAQUE setup ET a CHAQUE base
        (`docs/edgewonk-api.md` §7) : la base 100005 n'en expose qu'une, la 100001
        en a cinq. Ne JAMAIS coder une liste en dur — on resout par nom.
        """
        _, rep = self._requete(
            "GET", "%s/databases/%s/setups/%s/strategies" % (API, base_id, setup_id))
        return rep or []

    def commentaires(self, base_id):
        """Le catalogue des commentaires de trade : [{id, name, type, rating, active}].

        TROUVE PAR MESURE le 26/08/2026 (`outils/diag_commentaires.py`), apres
        que `docs/edgewonk-api.md` §7 l'ait laisse non documente. Onze URL sondees,
        une seule repond : les dix autres rendent 403, pas 404 — l'API refuse
        de dire ce qui n'existe pas, donc seule une sonde exhaustive tranche.

            GET /v1/databases/{db}/comments  ->  200, 8 commentaires

        `type` vaut PRE_TRADE / ENTRY / MANAGEMENT / EXIT, `rating` POSITIVE ou
        NEGATIVE. C'est la source qui manquait : jusque-la le catalogue etait
        deduit des trades, donc aveugle a toute option que plus aucun trade ne
        portait — exactement le cas rencontre quand l'utilisateur a nettoye ses
        champs Management d'aout.
        """
        _, rep = self._requete(
            "GET", "%s/databases/%s/comments" % (API, base_id))
        return rep or []

    def trade(self, base_id, trade_id):
        """Un trade unitairement — 68 cles. A preferer a la recherche pour
        verifier une ecriture : la recherche renvoie 120 Ko pour 200 trades."""
        _, rep = self._requete(
            "GET", "%s/databases/%s/journal-entries/%s" % (API, base_id, trade_id))
        return rep

    # ---------------------------------------------------------------- ecriture
    def modifier(self, base_id, trade_id, champs):
        """POST /modify — partiel et sur. Refuse tout champ hors liste blanche.

        Le serveur, lui, accepterait et ignorerait EN SILENCE avec un 200. On
        prefere echouer bruyamment ici que croire avoir ecrit.
        """
        inconnus = [c for c in champs if c not in MODIFIABLES]
        if inconnus:
            raise ErreurEdgewonk(
                "modify n'ecrit pas ces champs (il repondrait 200 sans rien faire) : %s"
                % ", ".join(inconnus))
        charge = {"id": trade_id}
        charge.update(champs)
        statut, rep = self._requete(
            "POST", "%s/databases/%s/journal-entries/%s/modify" % (API, base_id, trade_id),
            charge)
        return statut, rep

    def remplacer(self, base_id, trade_id, charge):
        """PUT — remplacement COMPLET. La charge doit venir de
        `charge_utile_put()`, jamais d'un dictionnaire ecrit a la main."""
        statut, rep = self._requete(
            "PUT", "%s/databases/%s/journal-entries/%s" % (API, base_id, trade_id),
            charge)
        return statut, rep

    # ------------------------------------------------------------------ images
    def televerser_image(self, base_id, trade_id, emplacement, chemin, description):
        """POST d'un PNG dans l'emplacement `emplacement` (1..6).

        Contrat mesure le 24/08/2026 (`docs/edgewonk-api.md` §5) : reponse 201 avec
        `pictureId`, `xauth`, `screenshotUrl`, `size`. La cle n'a PAS a etre
        renvoyee — le serveur l'associe seul quand on pose `screenshot{n}Exists`.
        """
        if not 1 <= emplacement <= 6:
            raise ErreurEdgewonk("emplacement %r hors de 1..6" % emplacement)
        with io.open(chemin, "rb") as f:
            contenu = f.read()
        if not contenu:
            raise ErreurEdgewonk("image vide : %s" % chemin)
        if len(contenu) > TAILLE_MAX_IMAGE:
            raise ErreurEdgewonk(
                "image de %.1f Mo — au-dela de %.0f Mo le serveur repond 403 (%s)"
                % (len(contenu) / 1048576.0, TAILLE_MAX_IMAGE / 1048576.0, chemin))
        type_contenu, corps = _multipart(
            {"description": description}, os.path.basename(chemin), contenu)
        ancien, self.delai = self.delai, DELAI_IMAGE
        try:
            statut, rep = self._requete(
                "POST", "%s/images/%s/TRADE/%s/%d" % (IMAGES, base_id, trade_id, emplacement),
                donnees=corps, entetes={"Content-Type": type_contenu})
        finally:
            self.delai = ancien
        return statut, rep

    def supprimer_image(self, base_id, trade_id, emplacement):
        """DELETE d'un emplacement. Un emplacement vide repond 404 : ce n'est
        pas une erreur, c'est le cas normal du premier envoi."""
        try:
            statut, _ = self._requete(
                "DELETE", "%s/images/%s/TRADE/%s/%d" % (IMAGES, base_id, trade_id, emplacement))
            return statut
        except ErreurEdgewonk as e:
            if " 404 " in str(e):
                return 404
            raise


def _multipart(champs, nom_fichier, contenu, type_mime="image/png"):
    """Construit un corps multipart/form-data. Retourne (content_type, corps).

    Ecrit a la main parce que le projet est en bibliotheque standard pure : pas
    de `requests`, donc pas de `files=`. La frontiere est tiree au hasard a
    chaque appel, sinon un PNG contenant par malchance la frontiere couperait
    le corps en deux.
    """
    frontiere = "----jt-" + binascii.hexlify(os.urandom(16)).decode("ascii")
    morceaux = []
    for nom, valeur in champs.items():
        morceaux.append(("--%s\r\n" % frontiere).encode("utf-8"))
        morceaux.append(('Content-Disposition: form-data; name="%s"\r\n\r\n'
                         % nom).encode("utf-8"))
        morceaux.append(("%s\r\n" % valeur).encode("utf-8"))
    morceaux.append(("--%s\r\n" % frontiere).encode("utf-8"))
    morceaux.append(('Content-Disposition: form-data; name="file"; filename="%s"\r\n'
                     % nom_fichier).encode("utf-8"))
    morceaux.append(("Content-Type: %s\r\n\r\n" % type_mime).encode("utf-8"))
    morceaux.append(contenu)
    morceaux.append(b"\r\n")
    morceaux.append(("--%s--\r\n" % frontiere).encode("utf-8"))
    return ("multipart/form-data; boundary=%s" % frontiere, b"".join(morceaux))


def charge_utile_put(trade, modifications):
    """Transforme un trade lu par GET en charge utile PUT valide.

    Specification du §0 de `docs/edgewonk-api.md`, verifiee sur le trade 17860739 :
    PUT avec un seul champ modifie -> seul ce champ bouge, 2 custom stats et
    4 commentaires de regles intacts, zero ecart avec l'instantane.

    Un constructeur qui mettrait [] par defaut EFFACERAIT le tagging.
    """
    charge = {}
    for cle, valeur in trade.items():
        if cle in CALCULES_SERVEUR:
            continue
        if cle in TABLEAUX_OBJETS:
            charge[cle] = [x.get("id") if isinstance(x, dict) else x
                           for x in (valeur or [])]
        elif cle in OBJETS_SCALAIRES:
            charge[cle] = valeur.get("id") if isinstance(valeur, dict) else valeur
        else:
            charge[cle] = valeur
    # attendus par le PUT, absents du GET
    charge.setdefault("addNewTradeComments", [])
    charge.setdefault("addNewCustomComments", [])
    charge.update(modifications)
    return charge
