# Configuration

Rien n'est codé en dur dans ce dépôt : ni identifiant de compte, ni clé d'API,
ni mot de passe. Trois choses sont à renseigner avant le premier lancement.

## 1. Les identifiants de comptes et de journaux

Dans `pipeline/core/plateformes.py`, trois valeurs d'exemple sont à remplacer :

| valeur | où la trouver |
|---|---|
| `BASE_PRINCIPALE` | l'identifiant de ton journal Edgewonk, visible dans l'URL une fois le journal ouvert |
| `PLATEFORMES["ctrader"]["compte"]` | ton numéro de compte cTrader, celui qui figure dans le nom des exports `cT_<compte>_….csv` |
| `PLATEFORMES["tradovate"]["compte"]` | ton identifiant de compte Tradovate |

## 2. Les identifiants Edgewonk

Ils sont lus dans le **trousseau macOS**, jamais dans un fichier du dépôt.

```bash
security add-generic-password -s edgewonk -a <ton-email> -w
```

Le mot de passe est demandé de manière interactive : il ne passe ni par
l'historique du shell, ni par un fichier.

## 3. La clé Databento

Nécessaire uniquement pour les bougies des futures. Deux voies, dans cet ordre :

```bash
export DATABENTO_API_KEY="db-…"          # variable d'environnement
security add-generic-password -s databento -a <ton-email> -w   # ou trousseau
```

## 4. Les bougies forex

Elles viennent d'un **serveur MCP cTrader local**. Voir `docs/ctrader-sltp-protocol.md`.

---

Aucune de ces valeurs ne doit être committée. Le `.gitignore` exclut déjà tout
le contenu de `donnees/` et de `IMPORT/`, qui portent les données de trading.
