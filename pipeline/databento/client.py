"""Bougies futures via Databento — la source de prix cote Tradovate.

CE MODULE PARLE LA LANGUE DU MCP CTRADER, EXPRES.

    client.appeler("get_trendbars", {"symbolName": .., "timeframe": ..,
                                     "from": .., "to": ..})
        -> {"bars": [{"timestamp", "open", "high", "low", "close", "volume"}, …]}

C'est exactement le contrat de `ctrader/mcp.py`. Consequence directe et
voulue : `ctrader/bougies.py` (extremes, TP-first, paliers) et
`graphiques/rendu.py` (les quatre images) fonctionnent sur les futures SANS UNE
SEULE LIGNE MODIFIEE. Tout ce que le projet a mesure et corrige sur dix jours —
les bougies de bord, la pagination, le trou du week-end, la jambe reellement
tenue — s'applique tel quel. Ecrire un second moteur de calcul aurait cree deux
verites qui divergeraient.

*(Le dossier `ctrader/` porte donc du code generique. Le nom est historique :
deplacer `bougies.py` toucherait onze fichiers d'une chaine en production pour
un gain cosmetique. Constate, assume, ecrit ici pour que personne ne le
redecouvre.)*

──────────────────────────────────────────────────────────────────────────────
DEUX CHOSES QUE DATABENTO NE FAIT PAS, ET COMMENT ON LES CONTOURNE

1. **Pas de schema 5 minutes ni 15 minutes.** Databento n'expose que
   `ohlcv-1s`, `ohlcv-1m`, `ohlcv-1h` et `ohlcv-1d` ; leur documentation
   recommande de sous-echantillonner cote client. On agrege donc le M1 en M5,
   M15 et M30, et le H1 en H4.

   ⚠️ Un seau d'agregation qui mord sur le bord de la fenetre demandee serait
   INCOMPLET, et donc faux : un M5 construit sur trois bougies M1 au lieu de
   cinq porte un plus haut sous-estime, silencieusement. On elargit donc la
   requete jusqu'aux bornes de seau AVANT de tirer, et on decoupe apres.

2. **C'est facture au gigaoctet.** Chaque requete coute. Le projet, lui, rejoue
   volontiers : `--refaire` regenere les graphiques, l'etape 3 repasse sur les
   trades non resolus, et `recuperer` pagine par tranches de 900 barres.
   Sans precaution, la meme minute de marche serait achetee dix fois.

   → **Cache disque, par SYMBOLE, SCHEMA et JOUR UTC.** Une journee de M1 d'un
     contrat pese quelques dizaines de kilo-octets. Une fois tiree, elle est a
     nous : relances, `--refaire` et paliers ne coutent plus rien. Et le jour ou
     Databento purgerait — ou ou le budget serait epuise — les bougies deja
     lues restent lisibles. Meme raison de fond que `donnees/brut/` : ce qu'on
     ne peut pas reconstruire, on le garde.

──────────────────────────────────────────────────────────────────────────────
⚠️ CE QUI EST MESURE, ET CE QUI RESTE SUPPOSE

MESURE le 26/08/2026 (`outils/diag_databento.py`, six sondes, toutes en 200) :

  * l'URL `https://hist.databento.com/v0/…` et l'authentification HTTP Basic
    avec la cle en identifiant et un mot de passe VIDE ;
  * `GLBX.MDP3` remonte au **06/06/2010** — trois ans avant le premier trade
    futures de l'utilisateur. La profondeur n'est pas un sujet ;
  * les schemas exposes sont `ohlcv-1s`, `ohlcv-1m`, `ohlcv-1h`, `ohlcv-1d`.
    **Ni 5m ni 15m** : l'agregation cote client n'est pas un choix, c'est la
    seule voie ;
  * `stype_in=raw_symbol` resout nos contrats tels que l'export les ecrit —
    `MNQU6` -> instrument 42004800. **Aucune table de correspondance**, comme
    pour `XAUUSD.raw` cote cTrader ;
  * tarif : **70 $/Go en `ohlcv-1m`**, 190 $/Go en `ohlcv-1h`. Et surtout,
    `metadata.get_cost` chiffre **0,0050 $ une journee entiere de M1 sur un
    contrat**. C'est ce chiffre qui autorise le cache a la JOURNEE : tirer
    1440 barres quand on en veut trente coute un demi-centieme de dollar, et
    rend gratuite toute relance ulterieure sur cette journee. Le calcul
    inverse — tirer la fenetre exacte a chaque fois — economiserait des
    fractions de centime et repaierait a chaque `--refaire`.

RESTE SUPPOSE — la FORME de la reponse de `timeseries.get_range`, seul point
qu'aucune sonde de metadonnee ne peut trancher :

  * JSON par lignes, un enregistrement OHLCV par ligne ;
  * prix en virgule fixe, entiers, a diviser par 1e9 ;
  * horodatage en nanosecondes depuis l'epoque, dans `hd.ts_event`.

On demande explicitement `pretty_px=false` et `pretty_ts=false` : une forme
BRUTE et deterministe vaut mieux qu'une forme lisible qu'il faudrait deviner.
Si Databento repond autrement, `_barre` leve avec l'enregistrement fautif en
clair — pas un prix aberrant qui passerait pour un MAE. `outils/diag_tirage.py`
tranche la question sur une vraie fenetre, pour un demi-centime.
"""

import base64
import datetime as dt
import hashlib
import io
import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://hist.databento.com/v0"
DATASET = "GLBX.MDP3"          # CME, CBOT, NYMEX, COMEX — les six produits tradés
SERVICE_TROUSSEAU = "databento"

DELAI = 90
TENTATIVES = 2

# Virgule fixe Databento : un prix entier a diviser par 1e9.
ECHELLE_PRIX = 1000000000.0

# timeframe demande -> (schema Databento, nombre de bougies a agreger)
# Le M5/M15/M30 se construisent depuis le M1, le H4 depuis le H1.
AGREGATION = {
    "m1":  ("ohlcv-1m", 1),
    "m5":  ("ohlcv-1m", 5),
    "m15": ("ohlcv-1m", 15),
    "m30": ("ohlcv-1m", 30),
    "h1":  ("ohlcv-1h", 1),
    "h4":  ("ohlcv-1h", 4),
    "d1":  ("ohlcv-1d", 1),
}

# Minutes couvertes par une bougie du schema source.
MINUTES_SCHEMA = {"ohlcv-1m": 1, "ohlcv-1h": 60, "ohlcv-1d": 1440}

EPOQUE = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


class ErreurDatabento(Exception):
    pass


# ------------------------------------------------------------------- la cle

def cle_du_trousseau(service=SERVICE_TROUSSEAU):
    """La cle API depuis le trousseau macOS. JAMAIS en clair dans le depot.

    Meme regle que le mot de passe Edgewonk. La variable d'environnement
    DATABENTO_API_KEY sert de secours (machine sans trousseau, test isole).
    """
    depuis_env = os.environ.get("DATABENTO_API_KEY")
    if depuis_env:
        return depuis_env.strip()
    try:
        return subprocess.check_output(
            ["security", "find-generic-password", "-s", service, "-w"],
            stderr=subprocess.STDOUT).decode("utf-8", "replace").strip()
    except (subprocess.CalledProcessError, OSError):
        raise ErreurDatabento(
            "aucune cle Databento.\n"
            "  A creer une fois, dans un Terminal :\n"
            "    security add-generic-password -s %s -a <ton-email> -w\n"
            "  (sans la cle sur la ligne : « security » la demandera)"
            % service)


# --------------------------------------------------------------- horodatages

def _utc(iso):
    """Une chaine ISO -> datetime aware en UTC. Tolere le suffixe « Z »."""
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(dt.timezone.utc)


def _z(moment):
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _depuis_nanos(nanos):
    return EPOQUE + dt.timedelta(microseconds=int(nanos) // 1000)


# ------------------------------------------------------- lecture d'une reponse

def _prix(valeur, enregistrement):
    """Un prix Databento -> float.

    On a demande `pretty_px=false`, donc on ATTEND un entier en virgule fixe.
    Une valeur deja decimale voudrait dire que le serveur a ignore le drapeau :
    on l'accepte, mais on ne devine pas au-dela.
    """
    texte = str(valeur).strip()
    if not texte or texte.lower() in ("none", "null"):
        raise ErreurDatabento("prix absent dans %r" % (enregistrement,))
    if "." in texte or "e" in texte.lower():
        return float(texte)                 # le serveur a rendu du « pretty »
    try:
        return int(texte) / ECHELLE_PRIX
    except ValueError:
        raise ErreurDatabento("prix illisible (%r) dans %r" % (valeur, enregistrement))


def _barre(enregistrement):
    """Un enregistrement OHLCV Databento -> la forme du MCP cTrader.

    Leve plutot que de deviner : un champ absent ici deviendrait un extreme
    faux plus loin, et un extreme faux ne se voit pas a la lecture.
    """
    entete = enregistrement.get("hd") or {}
    ts = entete.get("ts_event", enregistrement.get("ts_event"))
    if ts is None:
        raise ErreurDatabento("enregistrement sans ts_event : %r" % (enregistrement,))
    texte = str(ts).strip()
    moment = _utc(texte) if "T" in texte else _depuis_nanos(texte)
    barre = {
        "timestamp": _z(moment),
        "open": _prix(enregistrement.get("open"), enregistrement),
        "high": _prix(enregistrement.get("high"), enregistrement),
        "low": _prix(enregistrement.get("low"), enregistrement),
        "close": _prix(enregistrement.get("close"), enregistrement),
        "volume": float(enregistrement.get("volume") or 0),
    }
    if barre["high"] < barre["low"]:
        raise ErreurDatabento(
            "bougie incoherente (high < low) — l'echelle des prix est fausse : %r"
            % (enregistrement,))
    return barre


def _lignes_json(charge):
    """La reponse est du JSON par lignes. Une ligne vide n'est pas une erreur."""
    for ligne in charge.splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            yield json.loads(ligne)
        except ValueError:
            raise ErreurDatabento("reponse illisible, ligne : %r" % ligne[:200])


# ------------------------------------------------------------------- le client

class Client(object):
    """Meme interface que `ctrader.mcp.Client`, meme grammaire d'appel.

    `cache` : dossier des journees deja tirees. None -> pas de cache (a
    n'utiliser que dans un diagnostic : sans lui, chaque relance repaye).
    """

    def __init__(self, cle=None, cache=None, dataset=DATASET, delai=DELAI):
        self.cle = cle
        self.cache = cache
        self.dataset = dataset
        self.delai = delai
        self.tires = 0          # journees reellement achetees pendant la session
        self.relus = 0          # journees servies par le cache
        self._fin_dispo = None  # bord de l'historique, demande une seule fois

    def ouvrir(self):
        """Symetrique de l'ouverture de session MCP : on resout la cle ici,
        pour que l'absence de cle se voie AVANT la premiere position traitee."""
        if self.cle is None:
            self.cle = cle_du_trousseau()
        return self

    # ---------------------------------------------------------------- reseau

    def _get(self, chemin, parametres):
        url = "%s/%s?%s" % (BASE, chemin, urllib.parse.urlencode(parametres))
        jeton = base64.b64encode(("%s:" % self.cle).encode("utf-8")).decode("ascii")
        requete = urllib.request.Request(url, headers={
            "Authorization": "Basic " + jeton,
            "Accept": "application/json",
        })
        dernier = None
        for essai in range(TENTATIVES):
            try:
                with urllib.request.urlopen(requete, timeout=self.delai) as r:
                    return r.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                corps = e.read().decode("utf-8", "replace")[:400]
                # Une 4xx ne s'arrange pas en reessayant, et chaque essai coute
                # potentiellement. On remonte tout de suite, avec le corps.
                raise ErreurDatabento("Databento %s sur %s : %s"
                                      % (e.code, chemin, corps))
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                # ⚠️ `urlopen(timeout=)` leve TimeoutError, PAS URLError — meme
                # piege que dans `ctrader/mcp.py`, capture ici aussi.
                dernier = e
                if essai + 1 < TENTATIVES:
                    time.sleep(2)
        raise ErreurDatabento("Databento injoignable (%s) apres %d tentative(s)"
                              % (dernier, TENTATIVES))

    def fin_disponible(self):
        """Jusqu'ou l'historique existe REELLEMENT, a la minute.

        ⚠️ MESURE DU 26/08/2026, sur le premier cycle reel. Databento ne
        tronque pas une fenetre qui deborde : il REFUSE, en 422
        `data_end_after_available_end`. Demander la journee entiere du jour
        courant — ce que fait le cache a la journee — tombe donc en erreur des
        que le marche n'a pas fini sa journee UTC.

        Et le bord n'est pas « maintenant » : il RETARDE. Mesure du jour, a
        20:12 heure de Paris (18:12 UTC), l'historique s'arretait a 18:00 UTC.
        Se caler sur l'horloge locale echouerait donc aussi, juste moins
        souvent — le pire des cas, une erreur qui n'apparait qu'a certaines
        heures.

        On lit donc le bord chez eux, une fois par session. C'est une
        metadonnee : gratuite.
        """
        if self._fin_dispo is not None:
            return self._fin_dispo
        borne = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
        try:
            charge = self._get("metadata.get_dataset_range", {"dataset": self.dataset})
            plage = json.loads(charge) if isinstance(charge, str) else charge
            brut = (plage or {}).get("end")
            if brut:
                # « 2026-08-26T18:00:00.000000000Z » : on coupe la partie
                # fractionnaire, que `fromisoformat` refuse au-dela de six
                # chiffres, et on repose le fuseau. La seconde suffit largement
                # pour borner une journee.
                texte = str(brut).split(".")[0].replace("Z", "") + "+00:00"
                borne = _utc(texte)
        except (ErreurDatabento, ValueError, TypeError):
            # Repli prudent : une heure de retard couvre le decalage observe.
            # On ne bloque jamais la chaine sur une metadonnee.
            pass
        self._fin_dispo = borne
        return borne

    # ----------------------------------------------------------------- cache

    def _chemin_cache(self, symbole, schema, jour):
        if not self.cache:
            return None
        # Le symbole entre dans le nom de fichier : il est alphanumerique
        # (MNQU6, 6EU6), mais on hache le couple pour ne dependre d'aucune
        # hypothese sur les caracteres autorises.
        empreinte = hashlib.sha1(("%s|%s|%s" % (self.dataset, symbole, schema))
                                 .encode("utf-8")).hexdigest()[:10]
        dossier = os.path.join(self.cache, "%s_%s_%s" % (symbole, schema, empreinte))
        return os.path.join(dossier, "%s.json" % jour.isoformat())

    def _journee(self, symbole, schema, jour):
        """Les bougies d'UNE journee UTC. Cache d'abord, reseau ensuite.

        Une journee vide est mise en cache elle aussi — c'est un fait (marche
        ferme), pas un echec, et la redemander couterait pour rien. Sauf si
        elle est ENCORE EN COURS : l'historique s'y complete encore.
        """
        chemin = self._chemin_cache(symbole, schema, jour)
        if chemin and os.path.exists(chemin):
            try:
                with io.open(chemin, encoding="utf-8") as f:
                    self.relus += 1
                    return json.load(f)
            except (ValueError, OSError):
                pass                        # cache abime : on retire, sans bruit

        debut = dt.datetime.combine(jour, dt.time(0, 0), tzinfo=dt.timezone.utc)
        fin = debut + dt.timedelta(days=1)

        # ⚠️ NE JAMAIS DEMANDER AU-DELA DE CE QUI EXISTE. Databento refuse la
        # fenetre entiere (422) au lieu de la tronquer : sans ce bornage, la
        # journee EN COURS fait echouer toute la position, et un trade du jour
        # ressort en « echec » alors qu'il n'y a simplement rien encore.
        bord = self.fin_disponible()
        if debut >= bord:
            return []                      # journee pas encore commencee chez eux
        fin = min(fin, bord)

        charge = self._get("timeseries.get_range", {
            "dataset": self.dataset,
            "symbols": symbole,
            "schema": schema,
            "stype_in": "raw_symbol",
            "start": _z(debut),
            "end": _z(fin),
            "encoding": "json",
            "pretty_px": "false",
            "pretty_ts": "false",
        })
        barres = [_barre(e) for e in _lignes_json(charge)
                  if e.get("open") is not None]
        barres.sort(key=lambda b: b["timestamp"])
        self.tires += 1

        # Une journee n'est mise en cache que si elle est REVOLUE. Une journee
        # tronquee au bord de l'historique se completera plus tard : la figer
        # maintenant priverait le trade de sa fin, silencieusement.
        journee_close = fin >= debut + dt.timedelta(days=1)
        if chemin and journee_close:
            dossier = os.path.dirname(chemin)
            if not os.path.isdir(dossier):
                os.makedirs(dossier)
            provisoire = chemin + ".tmp"
            with io.open(provisoire, "w", encoding="utf-8") as f:
                json.dump(barres, f)
            os.replace(provisoire, chemin)     # atomique, comme la base
        return barres

    # ------------------------------------------------------------ agregation

    @staticmethod
    def _agreger(barres, minutes_source, facteur):
        """N bougies consecutives -> une. Seaux alignes sur l'epoque UTC.

        Alignement sur l'epoque, donc sur minuit UTC : un M15 tombe a :00, :15,
        :30, :45 et un H4 a 00:00, 04:00… C'est la convention la plus courante,
        et surtout la seule qui ne depende d'aucune heure de session. Un seau
        incomplet n'est PAS filtre ici — c'est `appeler` qui elargit la fenetre
        en amont pour qu'il n'y en ait pas.
        """
        if facteur == 1:
            return barres
        pas = dt.timedelta(minutes=minutes_source * facteur)
        seaux = {}
        for b in barres:
            moment = _utc(b["timestamp"])
            secondes = int((moment - EPOQUE).total_seconds())
            debut = EPOQUE + dt.timedelta(
                seconds=secondes - secondes % int(pas.total_seconds()))
            s = seaux.get(debut)
            if s is None:
                seaux[debut] = dict(b, timestamp=_z(debut))
                continue
            s["high"] = max(s["high"], b["high"])
            s["low"] = min(s["low"], b["low"])
            s["close"] = b["close"]          # les barres arrivent triees
            s["volume"] += b["volume"]
        return [seaux[k] for k in sorted(seaux)]

    # ------------------------------------------------------------- l'appel

    def appeler(self, outil, arguments=None):
        """Seul `get_trendbars` est servi. Tout le reste est refuse.

        Refus explicite plutot que silence : si un jour un module reclamait
        `get_symbols` ou autre chose a cette source, il faut que ca se voie
        immediatement, pas que ca renvoie un dictionnaire vide.
        """
        if outil != "get_trendbars":
            raise ErreurDatabento(
                "Databento ne sert que « get_trendbars » — outil demande : %s" % outil)
        a = arguments or {}
        symbole = (a.get("symbolName") or "").strip()
        timeframe = (a.get("timeframe") or "m1").strip().lower()
        if not symbole:
            raise ErreurDatabento("get_trendbars sans symbolName")
        if timeframe not in AGREGATION:
            raise ErreurDatabento(
                "timeframe %r inconnu — connus : %s"
                % (timeframe, ", ".join(sorted(AGREGATION))))
        schema, facteur = AGREGATION[timeframe]
        minutes_source = MINUTES_SCHEMA[schema]

        debut = _utc(a["from"])
        fin = _utc(a["to"])

        # ⚠️ ON ELARGIT AUX BORNES DE SEAU AVANT DE TIRER. Un M5 dont il manque
        # deux minutes porte un plus haut sous-estime, et rien ne le signale.
        pas = dt.timedelta(minutes=minutes_source * facteur)
        secondes = int(pas.total_seconds())
        d = int((debut - EPOQUE).total_seconds())
        f = int((fin - EPOQUE).total_seconds())
        large_debut = EPOQUE + dt.timedelta(seconds=d - d % secondes)
        large_fin = EPOQUE + dt.timedelta(
            seconds=f + (secondes - f % secondes) % secondes)

        brutes = []
        jour = large_debut.date()
        dernier = large_fin.date()
        while jour <= dernier:
            brutes += self._journee(symbole, schema, jour)
            jour += dt.timedelta(days=1)

        barres = self._agreger(brutes, minutes_source, facteur)
        # On rend la fenetre DEMANDEE : un seau commence avant `from` ou apres
        # `to` a servi a completer les bords, il n'a rien a faire dans la
        # reponse. `bougies.py` ecarte de toute facon les bougies de bord.
        gardees = [b for b in barres if debut <= _utc(b["timestamp"]) < fin]
        return {"bars": gardees}

    def resume(self):
        return "Databento : %d journee(s) tirees, %d relues du cache" % (
            self.tires, self.relus)
