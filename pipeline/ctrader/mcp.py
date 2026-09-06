"""Client du serveur MCP local de cTrader. Aucune dépendance externe.

Le serveur tourne DANS le client desktop, sur http://127.0.0.1:9876/mcp/, et
s'authentifie avec la session cTrader déjà ouverte : ni OAuth, ni approbation
Spotware. Il faut donc que cTrader soit lancé et connecté au bon compte.

Activation — cTrader → Paramètres → Serveur MCP :
    « Enable MCP Server »        coché
    « Allow trading via MCP »    DÉCOCHÉ — ne jamais cocher

⚠️ GARDE-FOU EN DUR, plus bas : ce module REFUSE d'appeler tout outil dont le
nom commence par amend_ / place_ / close_ / cancel_ / modify_ / set_. Ces
outils agissent réellement sur un compte financé. La case décochée est la
protection de premier rang ; celle-ci en est une seconde, qui ne dépend pas
d'un réglage d'interface qu'un jour quelqu'un pourrait rétablir.

Ce qu'on utilise ici, et rien d'autre :
    get_symbols     — le nom exact du symbole sur le compte connecté
    get_trendbars   — les bougies (qualité production, mesuré le 25/08/2026)
"""

import json
import time
import urllib.error
import urllib.request

URL = "http://127.0.0.1:9876/mcp/"

# 25 s suffisaient pour du M1 sur une fenêtre de trade. Mesuré le 25/08 : les
# premières requêtes sur un AUTRE timeframe (m5, m15, h1) expirent — cTrader
# doit d'abord télécharger cet historique depuis le serveur, et ça dépasse
# largement le délai. Une fois en cache, c'est instantané. D'où un délai large
# et une seconde tentative : le coût d'attendre est nul, celui d'abandonner une
# position est un graphique manquant.
DELAI = 90
TENTATIVES = 2

# Préfixes d'outils qui ÉCRIVENT sur le compte. Refus au niveau du code.
INTERDITS = ("amend_", "place_", "close_", "cancel_", "modify_", "set_", "delete_")


class ErreurMCP(Exception):
    pass


def _extraire(corps):
    """La réponse est du JSON, ou du SSE (« event: … / data: {…} »)."""
    corps = corps.strip()
    if not corps:
        raise ErreurMCP("réponse vide du serveur MCP")
    if corps.startswith("{"):
        return json.loads(corps)
    dernier = None
    for ligne in corps.splitlines():
        ligne = ligne.strip()
        if ligne.startswith("data:"):
            charge = ligne[5:].strip()
            if charge and charge != "[DONE]":
                dernier = charge
    if dernier is None:
        raise ErreurMCP("réponse MCP illisible : %r" % corps[:200])
    return json.loads(dernier)


class Client(object):
    """Session MCP. À réutiliser d'un appel à l'autre : l'étape 3 en fait
    plusieurs dizaines, rouvrir une session à chaque fois serait inutile."""

    def __init__(self, url=URL, delai=DELAI):
        self.url = url
        self.delai = delai
        self.session = None
        self._compteur = 1

    def _envoyer(self, charge, avec_session=True):
        entetes = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if avec_session and self.session:
            entetes["Mcp-Session-Id"] = self.session
        requete = urllib.request.Request(
            self.url, data=json.dumps(charge).encode("utf-8"),
            headers=entetes, method="POST")
        dernier = None
        for essai in range(TENTATIVES):
            try:
                with urllib.request.urlopen(requete, timeout=self.delai) as r:
                    return r.headers, r.read().decode("utf-8", "replace")
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                # ⚠️ `urlopen(timeout=)` lève TimeoutError (socket.timeout), PAS
                # URLError : ne capturer que URLError laissait remonter un
                # « timed out » brut, sans contexte ni seconde chance.
                dernier = e
                if essai + 1 < TENTATIVES:
                    time.sleep(2)
        raise ErreurMCP(
            "serveur MCP : %s sur %s apres %d tentative(s).\n"
            "  cTrader est-il ouvert, et « Enable MCP Server » coche ?\n"
            "  (un premier appel sur un timeframe non charge peut etre long)"
            % (dernier, self.url, TENTATIVES))

    def ouvrir(self):
        entetes, corps = self._envoyer({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "jt", "version": "1.0"}},
        }, avec_session=False)
        self.session = entetes.get("mcp-session-id") or entetes.get("Mcp-Session-Id")
        _extraire(corps)
        self._envoyer({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self

    def appeler(self, outil, arguments=None):
        """Appelle un outil et retourne l'objet Python de sa réponse."""
        bas = outil.lower()
        for interdit in INTERDITS:
            if bas.startswith(interdit):
                raise ErreurMCP(
                    "REFUS : « %s » est un outil d'écriture. Ce module est en "
                    "lecture seule, par construction." % outil)
        if self.session is None:
            self.ouvrir()
        self._compteur += 1
        _, corps = self._envoyer({
            "jsonrpc": "2.0", "id": self._compteur, "method": "tools/call",
            "params": {"name": outil, "arguments": arguments or {}},
        })
        reponse = _extraire(corps)
        if "error" in reponse:
            raise ErreurMCP("%s : %s" % (outil, reponse["error"]))
        contenu = (reponse.get("result") or {}).get("content") or []
        if not contenu:
            raise ErreurMCP("%s : réponse sans contenu" % outil)
        texte = contenu[0].get("text", "")
        try:
            return json.loads(texte)          # le contenu est du JSON encodé en texte
        except ValueError:
            return texte


if __name__ == "__main__":
    import sys
    outil = sys.argv[1] if len(sys.argv) > 1 else "get_symbols"
    args = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
    print(json.dumps(Client().ouvrir().appeler(outil, args), indent=2, ensure_ascii=False)[:3000])
