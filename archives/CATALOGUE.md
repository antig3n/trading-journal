# Boîte à outils archivée

**Lis cette fiche, pas les fichiers.** Chaque outil ci-dessous a tranché une
question ; la réponse est écrite ici et dans la documentation de référence. Ils
sont archivés parce qu'ils ont fini leur travail, pas parce qu'ils étaient
mauvais — leur valeur est désormais méthodologique : ils montrent *comment* une
question a été tranchée, et se relancent tels quels si le doute revient.

> **Comment s'en servir.** Un problème arrive, l'orchestrateur d'audit ne le
> couvre pas. Avant d'écrire un nouveau script : chercher ici. Si l'un de ces
> outils pose déjà la bonne question, le relancer coûte une commande. Sinon,
> écrire le nouveau — et l'ajouter à cette fiche quand il aura répondu.

Tous sont en **lecture seule**, sauf les deux marqués ⚠️.

---

## Ce qui a été mesuré chez Databento

| outil | la question | la réponse |
|---|---|---|
| `diag_databento.py` | Databento peut-il fournir nos bougies futures ? | Oui. Six sondes de métadonnées, 0 $. Schémas `ohlcv-1m` et `ohlcv-1h` seulement — d'où la ré-agrégation M5/M15/H4 dans `databento/client.py`. |
| `diag_tirage.py` | Quelle tête a un enregistrement OHLCV ? | Prix en virgule fixe à diviser par 1e9, horodatage `ts_event` en nanosecondes. ⚠️ dépense 0,0050 $ par journée tirée. |

## Ce qui a été mesuré chez Tradovate

| outil | la question | la réponse |
|---|---|---|
| `diag_fuseau_tradovate.py` | Dans quel fuseau l'export écrit-il ses heures ? | Paris. Mesuré **contre le marché** et non contre Edgewonk — 10 concordances sur 10. L'export ne porte aucune indication de fuseau, contrairement à cTrader. ⚠️ dépense ~0,10 $ au premier passage. |
| `diag_journaux.py` | Où vivent réellement les trades futures ? | Dans le **100001**, le journal courant — et non dans le 100004 comme la documentation l'affirmait. L'utilisateur avait raison, la mesure le prouve. Écrit pour trancher plutôt que discuter. |
| `diag_edgewonk_tradovate.py` | À quoi ressemble un trade futures chez eux ? | `instrument.name` vaut le symbole **court** (`MNQ`), pas le contrat (`MNQU6`) — l'inverse de cTrader. D'où `plateformes.colonne_instrument()`. |

## Ce qui a été mesuré chez Edgewonk

| outil | la question | la réponse |
|---|---|---|
| `diag_edgewonk.py` | La chaîne d'authentification tient-elle, et quelle est la forme des champs ? | Oui. Forme des dates et des champs : voir `docs/edgewonk-api.md`. |
| `diag_edgewonk2.py` | La recherche est-elle triée par date ? | **Non.** Il faut parcourir toute la base pour retrouver une période — c'est pourquoi `tous_les_trades` pagine intégralement. |
| `diag_commentaires.py` | Où vit le catalogue des commentaires de trade ? | `GET /databases/{db}/comments`. Trouvé par mesure : 11 URL sondées, une seule répond. Non documenté par eux. |
| `diag_upload.py` | Le multipart écrit à la main passe-t-il chez eux ? | Oui, et `gain=null` est accepté. ⚠️ **écrit** — téléverse puis restaure, avec instantané. |

## Ce qui a été mesuré chez cTrader

| outil | la question | la réponse |
|---|---|---|
| `diag_fuseau.py` | Quel décalage horaire, sans le deviner ? | Apparié d'abord sur le montant net (indépendant du fuseau), puis le décalage se **lit** sur les couples obtenus. cTrader porte son fuseau dans son en-tête, et `ctrader/statement.py` le lit. |
| `diag_timeframes.py` | Pourquoi le M5/M15/H1 expire alors que le M1 passe ? | cTrader télécharge l'historique d'un timeframe qu'il n'a pas encore chargé. Mesuré au lieu de gonfler le délai à l'aveugle. |

## Comparaisons ponctuelles, faites

| outil | la question | la réponse |
|---|---|---|
| `diag_ecarts.py` | Nos prix d'exécution collent-ils au relevé brut ? | Oui, sauf deux trades du 14/08 — figés en dur dans le script, ce qui en fait une mesure et non un instrument. *Corrigé au passage le 28/08 : il lisait le dernier export du dossier, devenu un export Tradovate aux colonnes incompatibles.* |

## Réparations ponctuelles, faites

| outil | ce qu'il a réparé |
|---|---|
| `restaurer_inreview.py` | Les 40 `inReview` posés à tort le 25/08. Cause : `multiplier` vaut **1.0** chez Edgewonk, y compris sur EURUSD — ce n'est pas la taille du contrat. Le contrôle comparait des ordres de grandeur incompatibles. Réparé en relisant l'instantané pris avant l'écriture. |

## Le chantier rétroactif

`archives/retroactif/` — le projet complet : son lanceur, sa base, ses relevés,
ses saisies, ses graphiques.

**Il a fait son travail** : 157 jambes d'octobre 2025 à août 2026, reprises,
poussées, vérifiées. Sa base a été **fusionnée dans la production le 28/08/2026**
(241 jambes au total) et ses graphiques rapatriés — ce qui est ici est donc une
copie de l'état d'avant la fusion, gardée comme filet.

| outil | ce qu'il a tranché |
|---|---|
| `diag_retroactif.py` | Le chantier était-il faisable ? Oui — le M1 remonte assez loin pour les extrêmes, et pas seulement les graphiques. |

Ses deux règles propres ont été **reprises dans l'orchestrateur** plutôt que
perdues :

- **E1** — n'écrire que dans les emplacements d'images vides, pour ne jamais
  détruire une capture faite à la main → devient le mode « ne remplir que le
  vide » ;
- **le repêchage du changement d'heure** (`rattraper`) → branché sur la poussée
  de production le 28/08, avec la mesure qui le prouve.

*Une règle qu'on peut demander n'a plus besoin d'un projet à elle.*

---

## Les orchestrateurs remplacés

`archives/orchestrateurs/` — remplacés le 28/08/2026 par `pipeline/journal.py`,
qui pose les questions et appelle `jt.py`, resté le moteur.

| fichier | ce qu'il était | pourquoi il part |
|---|---|---|
| `sync.py` | l'assistant guidé, 898 lignes, lancé par Raycast | il réimplémentait les 5 étapes que `jt.py` implémentait déjà. Mesure du 28/08 : il ne savait pas redessiner les graphiques — et c'était celui qu'on lançait tous les jours. |
| `futures.sh` | l'enchaînement du cycle futures d'un bloc | la question « quelle plateforme ? » est maintenant dans l'orchestrateur. Un script par plateforme n'a plus de raison d'être. |

Ce qu'ils savaient faire et qui a été **porté**, pas perdu : trouver le relevé
dans `IMPORT/`, ouvrir le fichier de saisie dans le Finder, ranger les exports
traités dans `IMPORT/_traites/`.
