# Edgewonk 3 — API interne : contrat d'écriture

Reconstitué depuis une capture HAR du 24/08/2026 (remplissage complet d'un trade).
API non contractuelle : peut changer sans préavis. C'est le côté fragile du montage.

---

## 0. PÉRIMÈTRE D'ÉCRITURE — vérifié empiriquement le 24/08/2026

Tests réels sur la base `100005`, trade `17860734`, restauré à l'identique ensuite.

### `modify` n'accepte qu'une liste blanche — et ignore le reste EN SILENCE

`POST /journal-entries/{id}/modify` renvoie **200 dans tous les cas**, y compris pour un
champ qu'il n'écrit pas. Un statut 200 ne prouve donc **rien**. Toujours relire après écriture.

| Champ | `modify` l'écrit ? |
|---|---|
| `slPrice`, `tpPrice` | ✅ |
| `highestPrice`, `lowestPrice` | ✅ |
| `screenshot{n}Exists` | ✅ |
| `inReview` | ✅ |
| `originalTpHit` | ❌ ignoré |
| `ignoreForWinrate` | ❌ ignoré |
| `additionalNotes` | ❌ ignoré |
| `tpHit`, `slHit`, `updraw`, `drawDown`, `riskAmount` | ❌ calculés serveur |
| champ inexistant | ❌ ignoré, 200 quand même |

**`modify` ne peut pas vider un champ.** `null` est traité comme « non fourni ». `0` écrit
bien `0`. Pour remettre à `null`, il faut le `PUT`.

### `originalTpHit` et `ignoreForWinrate` imposent le `PUT`

C'est la contrainte structurante. Le `PUT` est un **remplacement complet** : vérifié, une
clé omise est **effacée** (test sur `additionalNotes`). Il peut en revanche écrire `null`.

### Stratégie retenue

1. **`modify` par défaut** pour `slPrice`, `tpPrice`, `highestPrice`, `lowestPrice`,
   `screenshot{n}Exists` — sûr, partiel, aucun risque pour le reste de l'objet.
2. **`PUT` uniquement pour `originalTpHit` et `ignoreForWinrate`**, en read-modify-write :
   `GET` complet → transformation → `PUT` intégral.
3. **Toujours relire après écriture** et comparer. Le 200 ne vaut rien.

### ✅ Aller-retour `GET` → `PUT` VALIDÉ sur un trade taggé

Testé le 24/08/2026 sur le trade `17860739` (base 100005), porteur de 2 custom stats et de
4 commentaires de règles. `PUT` avec un seul champ modifié → **seul ce champ a bougé**,
tout le tagging intact. Trade restauré ensuite, **zéro écart avec l'instantané**.

Le `PUT` est donc utilisable en toute sécurité **à condition** de construire la charge utile
avec la transformation ci-dessous. Un constructeur qui mettrait `[]` par défaut effacerait
le tagging.

### Transformation `GET` → `PUT` — spécification

**1. Objets → identifiants.** Ces six tableaux sont des **tableaux d'objets** dans le `GET`
et des **tableaux d'identifiants** dans le `PUT` :

```
customComments, checklistItems,
preTradeComments, entryComments, exitComments, managementComments
```
→ `arr.map(x => x.id)`

**2. Objets → identifiant scalaire** : `instrument` et `setup`.

**3. Champs à ne PAS renvoyer** (présents dans le `GET`, calculés serveur) :
`gainPercent`, `rMultiple`, `rrrPlanned`, `rrrRealized`, `accountSize`, `accountBalance`,
`accountNumber`, `updraw`, `drawDown`, `tpHit`, `slHit`, `positionSize`, `riskAmount`,
`openQuantity`, `realizedPcp`, `plannedPcp`, `tiltMeter`, `screenshotExists`,
`entryComment` / `exitComment` / `managementComment` (les singuliers).

**4. Champs à ajouter**, absents du `GET`, attendus par le `PUT` :
`addNewTradeComments: []`, `addNewCustomComments: []`.

**5. `alternativeStrategies`** se renvoie tel quel (le serveur y ajoute `setupId`).

### Interdits — ne doivent jamais être modifiés

### Interdits — ne doivent jamais apparaître dans un payload

`setup` · `checklistItems` · `instrument` · `direction` · `entryDate` · `exitDate` ·
`scalings` · `fineScalings` · `quantity` · `commission` · `gain` · `gainGross` ·
`multiplier` · `outcome` · `customComments` · `preTradeComments` · `entryComments` ·
`exitComments` · ~~`managementComments`~~ *(voir la brèche ci-dessous)*

Ce sont soit les données d'exécution, soit le jugement de l'utilisateur (tagging), qui ne
s'automatise pas.

⚠️ **UNE SEULE BRÈCHE, ouverte par l'utilisateur le 26/08/2026 : `managementComments`.**

Elle est légitime parce que la valeur vient de **lui** : « ai-je touché à mon stop après
l'entrée ? » est saisi à la main dans le fichier SL/TP, au même titre que le stop. On
**transporte** son jugement, on n'en fabrique aucun — c'est exactement ce que le reste de
cette liste protège.

**La brèche est étroite, et doit le rester :**

* `managementComments` **uniquement**. Les quatre autres familles et `checklistItems`
  restent intouchables.
* On n'écrit **que** si `OK` ou `KO` a été saisi. Case vide → rien, dans aucun sens, même
  si le trade porte déjà une valeur posée à la main.
* Les options se résolvent **par nom** depuis `GET /comments` (§7), jamais en dur.

Mesuré le 26/08 sur 202 trades : ce champ porte **0 ou 1** entrée, jamais 2. Écrire un
identifiant unique est donc sans perte, et la relecture le dirait si un trade en portait
deux — elle compare les ids.

⚠️ **CORRECTION DU 25/08/2026 — « déjà justes via l'auto-import » EST FAUX.** Mesuré sur
44 couples réels : **2 trades portent des prix d'exécution qui divergent du relevé broker**.

```
NAS100 17925810 : Edgewonk entrée 30015.8    relevé 30040.35
USOIL  17925793 : Edgewonk entrée 82.17      relevé 81.51428571
```

Les prix du relevé reproduisent le brut **au centime** — `(30040.35 − 29958.95) × 3 =
244,20`, exactement le brut déclaré. Ceux d'Edgewonk, non.

La conclusion pratique ne change pas — **on n'y touche pas**, modifier `scalings` n'a jamais
été testé et le risque dépasse le gain — mais la raison change : ce n'est plus « parce
qu'elles sont justes », c'est « parce que les corriger est trop risqué ». Sur ces trades,
`rMultiple` reste faux quoi qu'on écrive, puisqu'il est calculé serveur depuis l'entrée, le
SL et la sortie. Ils sont donc marqués **`inReview`**.

⚠️ **Ne jamais reconstruire un montant depuis les prix d'Edgewonk pour détecter ça.** Le
champ `multiplier` vaut **1.0**, y compris sur EURUSD et XAUUSD : ce n'est PAS la taille du
contrat. Un contrôle bâti dessus a marqué `inReview` sur 40 trades sains. On compare des
**prix à des prix**.

---

## 1. Base et authentification

```
https://api.edgewonk.app/v1/databases/{databaseId}/...
https://images.edgewonk.app/...      (screenshots)
https://imports.edgewonk.app/...     (imports brokers)
```

En-tête **`X-Auth-Token`** : blob JSON `{"authentication":"{...}","signature":"..."}`.
Le bloc `authentication` contient `userId`, `userName`, **`validUntil`**, `fullyAuthenticated`,
`modules`, `instance` (`eu01`).

### Chaîne d'authentification — RÉSOLUE (24/08/2026)

Serveur d'auth distinct : **`https://license.edgewonk.app`**

**1. Connexion initiale**
```
POST https://license.edgewonk.app/auth/authenticate
Content-Type: application/json
body: {"user":"<email>","password":"<mot de passe>"}
→ 200 {"authentication":"<chaîne JSON>","signature":"<~684 caractères>"}
```

L'en-tête `X-Auth-Token` des appels API est **exactement** `JSON.stringify({authentication, signature})`
tel que renvoyé ici.

**2. Renouvellement — à privilégier**
```
POST https://license.edgewonk.app/auth/refresh-token
Content-Type: application/json
Authorization: Bearer <la valeur de signature>
X-Auth-Token: <le blob complet courant>
body: {}
→ 200 {"authentication":"...","signature":"..."}  (nouveau couple)
```

→ **Une seule authentification par mot de passe, puis on renouvelle.** `validUntil` est à
environ 1 h de l'émission ; rafraîchir avant expiration évite de manipuler le mot de passe
à chaque cycle.

**Stockage du mot de passe :** trousseau macOS, jamais en clair dans un fichier ni dans un
dépôt. Ne jamais exporter un HAR contenant `/auth/authenticate` — le corps est en clair.

### Bases de données (une par compte)
`100001` (principale), `104615`, `104616`, `100006`, `100005`, `100004`

---

## 2. Point de départ : les trades existent déjà

`GET https://imports.edgewonk.app/database/100001`
→ `{"autoCreateInstruments":true,"useDefaultSetup":true,"defaultSetup":572906,"autoImport":true}`

**L'auto-import est actif.** Les trades arrivent seuls, le script n'a donc jamais à
en créer : il ne fait qu'**enrichir des trades existants**. C'est la forme la plus
simple possible.

---

## 2 bis. Lire un trade unitairement

```
GET /v1/databases/{db}/journal-entries/{tradeId}
→ 200, l'objet complet (68 clés)
```

Découvert au test. **À utiliser plutôt que la recherche** pour vérifier une écriture :
la recherche renvoie 120 Ko pour 200 trades.

**Piège de lecture :** l'ordre des tableaux `scalings` et `customComments` n'est pas stable
d'un appel à l'autre. Trier par `id` avant toute comparaison, sinon les diffs produisent des
faux positifs.

---

## 3. Lister les trades

```
POST /v1/databases/{db}/journal-entries-search/{offset}/{limit}
body: {"orFilter":true,"tradeDate":"EXIT","excludeFilters":false,"timeZone":"Europe/Paris"}
```

Renvoie `{"data":[...]}` avec tout l'objet trade, y compris les champs calculés
serveur : `rMultiple`, `rrrPlanned`, `rrrRealized`, `gainPercent`, `accountSize`.

Autre endpoint : `POST /journal-entries-closed`.

---

## 4. Écrire un trade — LE contrat

```
PUT /v1/databases/{db}/journal-entries/{tradeId}
Content-Type: application/json
```

Corps complet observé (1858 octets), champs utiles :

| Champ | Type | Remarque |
|---|---|---|
| `slPrice` / `tpPrice` | number | **les deux champs cibles du projet** |
| `highestPrice` / `lowestPrice` | number | MAE/MFE, **écriture libre** (valeurs de test acceptées telles quelles) |
| `originalTpHit` | bool | le fameux TP-first / SL-first |
| `ignoreForWinrate` | bool | **le vrai drapeau break-even** |
| `outcome` | enum | `WINNER` / `LOSER` / `BREAK_EVEN` — **recalculé serveur**, voir §6 |
| `setup` | int | id de setup |
| `checklistItems` | [int] | ids des items cochés |
| `alternativeStrategies` | [{`strategyId`,`gain`,`rMultiple`}] | les 5 stratégies |
| `additionalNotes` | string | notes libres |
| `preTradeComments` / `entryComments` / `exitComments` / `managementComments` | [int] | onglet règles |
| `customComments` | [int] | custom stats |
| `screenshot{1..6}Exists` | bool | jusqu'à **6** screenshots |
| `screenshot{1..6}key` | string | clé `xauth` renvoyée à l'upload |
| `scalings` | [ ] | jambes : `{scalingDelta, scalingPrice, type: START_ENTRY\|CLOSE_ENTRY, direction, timestamp}` |
| `fineScalings` | [ ] | découpage fin avec `profit` — rôle exact à confirmer |
| `direction` | `BUY`/`SELL` | |
| `entryDate` / `exitDate` | ISO local | `2025-10-15T17:18:00` |
| `commission`, `gain`, `gainGross`, `quantity`, `multiplier`, `instrument` | | |
| `tradeStatus` | `CLOSED` | |

### Mise à jour partielle

```
POST /v1/databases/{db}/journal-entries/{tradeId}/modify
body: {"id":17860561,"screenshot1Exists":true}
```

Accepte un objet partiel. **À privilégier** pour ne toucher que les champs calculés
sans réécrire tout le trade.

---

## 5. Screenshots — chaîne VALIDÉE de bout en bout (24/08/2026)

**Six emplacements** par trade, pas deux.

**1. Upload**
```
POST https://images.edgewonk.app/images/{db}/TRADE/{tradeId}/{n}     n = 1..6
Header : X-Auth-Token  (pas de Content-Type à poser, FormData s'en charge)
multipart/form-data :
  file        : le PNG
  description : libellé (ex. MNQ_2026-08-10_...)
→ 201 {"pictureId":3,"xauth":"95ca96…","screenshotUrl":"images/.../3?xauth=…","size":223569}
```

**2. Flaguer** — la clé n'a **pas** à être renvoyée, le serveur l'associe seul :
```
POST /v1/databases/{db}/journal-entries/{tradeId}/modify
body: {"id":{tradeId},"screenshot3Exists":true}
→ screenshot3key rempli automatiquement, screenshotExists passe à true
```

**3. Relire** — `GET {screenshotUrl}` avec `X-Auth-Token` renvoie bien le PNG.

**4. Supprimer**
```
DELETE https://images.edgewonk.app/images/{db}/TRADE/{tradeId}/{n}   → 200
(404 si l'emplacement est vide)
```
Puis remettre `screenshot{n}Exists: false` via `modify`.

### Limite de taille — mesurée

| Poids | Résultat |
|---|---|
| 224 Ko | 201 ✅ |
| 2,07 Mo | 201 ✅ |
| 6,3 Mo | **403** ❌ |
| ~28 Mo | échec réseau |

La bascule est entre 2 et 6 Mo (vraisemblablement 5 Mo). Un graphique généré pèse
60 à 250 Ko : marge très confortable.

---

## 6. Comportements serveur — vérifiés au test

**`ignoreForWinrate` pilote `outcome`.** Confirmé : `ignoreForWinrate: true` via `PUT` fait
passer `outcome` de `WINNER` à `BREAK_EVEN`. Ne jamais écrire `outcome` directement, il est
recalculé. C'est là que `R_BREAK_EVEN = 0.30` s'applique — dans les **deux sens** :
`ignoreForWinrate: false` est écrit aussi, et ramène `outcome` à `WINNER`/`LOSER`.

**Les R-multiples sont calculés serveur** (`rMultiple`, `rrrPlanned`, `rrrRealized`) à partir
de l'entrée, du SL et de la sortie. Vérifié : un trade sans `slPrice` a `rMultiple: null`
(trade `17860738`). **Pas de stop, pas de R** — ce qui valide la règle R7 côté lecture.

**`highestPrice` / `lowestPrice` alimentent `updraw` et `drawDown`**, qui apparaissent dès
l'écriture. C'est le MAE/MFE d'Edgewonk exprimé en pourcentage.

**Précision décimale conservée** : `29758.12345` relu à l'identique. Cinq décimales passent,
aucun arrondi côté serveur.

**Idempotence** : deux `modify` identiques d'affilée, aucun effet de bord.

**Débit** : une quarantaine d'appels enchaînés sans pause, aucun 429, aucun ralentissement.
Les ~180 appels hebdomadaires ne poseront pas de problème.

---

## 7. Données de référence (pour construire les payloads)

| Endpoint | Contenu |
|---|---|
| `GET /setups` | setups + checklists imbriquées |
| `GET /checklists` | items avec `id`, `name`, `active`, `isRequired` |
| `GET /custom-stat-groups` | groupes de custom stats et leurs ids |
| `GET /setups/{id}/strategies` | stratégies alternatives + statistiques |
| `GET /instruments` | instruments et ids |
| `GET /comments` | **le catalogue des quatre familles de commentaires** — trouvé le 26/08/2026 |

### `GET /databases/{db}/comments` — trouvé par mesure le 26/08/2026

Ce document n'a longtemps documenté **aucun** endpoint pour les quatre familles de
commentaires (`preTradeComments`, `entryComments`, `exitComments`, `managementComments`).
Faute de mieux, le code déduisait le catalogue **des trades eux-mêmes** — aveugle à toute
option que plus aucun trade ne porte. Le cas s'est produit (voir §13 bis).

`archives/mesures/diag_commentaires.py` a sondé onze URL plausibles. **Une seule répond ; les dix
autres rendent 403, pas 404** — l'API refuse de dire ce qui n'existe pas, donc seule une
sonde exhaustive tranche. Retenir la méthode autant que le résultat.

```
GET /v1/databases/{db}/comments   ->  200, 8 commentaires
[{"id": 826040, "active": true, "type": "MANAGEMENT",
  "rating": "POSITIVE", "name": "Not managed", "order": 0}, …]
```

`type` vaut `PRE_TRADE` / `ENTRY` / `MANAGEMENT` / `EXIT` ; `rating` vaut `POSITIVE` ou
`NEGATIVE`. **Relevé sur la base `100001` :** Management = `826040` « Not managed »
(POSITIVE) et `826044` « Managed » (NEGATIVE).

→ **Résoudre par `name`, jamais par identifiant en dur** — même règle que pour les
stratégies alternatives. Si le nom ne répond plus (l'utilisateur a déjà renommé « Followed
rules » en « Not managed »), retomber sur le `rating`, qui porte la sémantique, **et le
dire**.

### Relevé au 24/08/2026

**Setups :** `538090` S/D Liquidation Reversal · `572906` Reactive Reversal ·
`572908` Breakout Continuation

**Custom stat groups :**
- `8` **Entry** — Retracement (2097256), No retracement (2097259)
- `7` **Setup TF** — M5 (1941832), M15 (1941831) *(M1/M3/H4 inactifs)*
- `1` **Mistakes** — Rule violation (1936984), Timing (1936983), No setup (1995299)

**Stratégies alternatives : elles sont propres à chaque setup ET à chaque base.**
Vérifié — la base `100005`, setup `570131`, n'expose qu'une seule stratégie : `6906` (« 2R »),
alors que la base `100001` en a cinq (`6898`, `6899`, `6901`, `6902`, `6903`).

→ **Ne jamais coder une liste en dur.** Résoudre dynamiquement via
`GET /v1/databases/{db}/setups/{setupId}/strategies`, et faire correspondre par `name`
(« 2R », « 3R », « 3.5R »…) plutôt que par identifiant.

**Instruments :** EURUSD.raw, XAUUSD.raw, GBPUSD.raw, USDJPY.raw, USDCAD.raw,
EURJPY.raw, US500.raw, US30.raw, NAS100.raw, UKOIL.raw, USOIL.raw, et les futures
NQ, MNQ, GC, MGC, MCL, 6E.

---

## 8. Le market-data d'Edgewonk — TRANCHÉ : on ne mappe pas

```
POST /v1/databases/{db}/market-data/trades/{tradeId}/prepare
→ {"mapped":false,"chartReady":false,"candleInterval":"1min",
   "highestPrice":null,"lowestPrice":null,"originalTpHit":null,
   "instrumentId":...,"canonicalSymbolId":null,...}
```

Edgewonk sait calculer lui-même `highestPrice`, `lowestPrice`, `originalTpHit` et son
graphique intégré — mais seulement une fois le trade mappé à un symbole canonique.
`canonicalSymbolId: null` et `providerSymbol: null` : leur résolveur n'arrive pas à
rattacher `USDCAD.raw`. Les suffixes brokers (`.raw`, `.pro`, `.ecn`, `.m`) sont la
cause classique.

**Décision : ne pas mapper.** Leur symbole canonique n'est pas le feed d'Prop Firm A.
Mapper produirait des extrêmes issus d'une source de référence alors que les entrées et
sorties viennent des fills réels — deux prix différents dans le même trade, exactement
l'incohérence silencieuse que le projet cherche à éliminer.

Les ticks broker étant disponibles via l'Open API, on calcule soi-même et on écrit
directement ces trois champs, librement inscriptibles.

*(Aucun risque pour les données existantes : le mapping n'aurait jamais touché les prix
d'exécution, seulement ce qu'Edgewonk calcule.)*

---

## 8 bis. `scalings` vs `fineScalings` — RÉSOLU, et ça règle les fills partiels

Mesuré sur le trade `17860734` (base 100005), rempli en deux fois :

```
fineScalings : ENTRY  1 lot  @ 29809.75  17:16:43  order 0  profit null
               ENTRY  3 lots @ 29793.25  17:18:17  order 1  profit null
               EXIT   4 lots @ 29758.50  20:45:00  order 2  profit 311

scalings     : START_ENTRY  4 @ 29797.375  17:16:43
               CLOSE_ENTRY  4 @ 29758.50   20:45:00
```

**(1 × 29809.75 + 3 × 29793.25) / 4 = 29797.375** — exact.

- **`fineScalings` = les exécutions réelles**, une ligne par fill : `delta`, `price`,
  `timestamp`, `order`, et `profit` porté uniquement par la sortie.
- **`scalings` = les jambes agrégées au VWAP**, c'est ce que le journal affiche.

### Conséquence : les fills partiels ne posent pas de problème

⚠️⚠️ **ATTENTION — CE QUI SUIT NE VAUT QUE POUR LES FUTURES TRADOVATE.**
*Renversé le 25/08/2026 pour cTrader. Voir l'encadré en fin de section.*

**Une position ouverte en plusieurs fills reste UN seul trade Edgewonk**, avec un prix
d'entrée au VWAP. Le doute était fondé sur une intuition, pas sur une mesure : elle
était fausse.

Et c'est une bonne nouvelle pour l'appariement : le VWAP d'Edgewonk correspond
**exactement** à `ProtoOAPosition.price` de cTrader, documenté comme
*« VWAP price based on all executions linked »*. Les deux systèmes agrègent pareil.

→ **La règle « un trade journalisé = une position cTrader (`PID`) » est confirmée.**

### Les sorties partielles se comportent à l'identique — MESURÉ

Balayage en lecture seule des **829 trades des six journaux** :

| | nombre |
|---|---|
| Trades avec **entrées** multiples | 29 (~3,5 %) |
| Trades avec **sorties** multiples | 6 (~0,7 %) |
| Trades dont `scalings` compte plus de 2 jambes | **0** |

Exemple `17926444` (MGC, 3 lots, base 100001) :

```
fineScalings EXIT : 1 lot  @ 4424.20  17:03:01  profit 8
                    2 lots @ 4406.00  20:45:03  profit 325
scalings CLOSE_ENTRY : 3 @ 4412.06666667  20:45:03
```

(1 × 4424.20 + 2 × 4406.00) / 3 = **4412.0666…** — exact.

→ **`scalings` compte toujours exactement deux jambes**, quel que soit le nombre de fills.
Entrée et sortie sont agrégées au VWAP, et l'horodatage retenu est celui du **dernier**
fill de chaque côté.

---

### ⚠️ RENVERSEMENT DU 25/08/2026 — côté cTrader, Edgewonk DÉCOUPE

**Tout ce qui précède a été mesuré sur des trades FUTURES Tradovate** (`17860734` MNQ,
`17926444` MGC) puis généralisé à cTrader **sans revérification**. La généralisation est
fausse, et elle a coûté une refonte du modèle de données.

Mesuré et confirmé au centime dans les deux systèmes, position cTrader du 07/08/2026
13:43, sortie en quatre fois :

| relevé cTrader (clôture) | net | Edgewonk |
|---|---|---|
| 13:44:34 — 3,00 lots | 12,00 | trade `17925771` |
| 13:44:43 — 0,50 lot | 1,50 | trade `17925769` |
| 13:50:31 — 0,50 lot | 1,50 | trade `17925770` |
| 14:30:01 — 2,00 lots | 302,00 | trade `17925779` |

**Une position cTrader = quatre trades Edgewonk.** 46 lignes de relevé = 46 trades.

Le chiffre qui semblait confirmer l'agrégation — « trades avec sorties multiples : 6
(0,7 %) » — était en réalité **la preuve du contraire**, mal lue : si l'importateur découpe
à l'entrée, presque aucun trade Edgewonk ne peut avoir de sortie multiple.

`docs/tradovate.md` §5 bis portait déjà l'avertissement — « la clé d'appariement doit être
spécifique à chaque plateforme » — rangé comme une particularité Tradovate au lieu de
déclencher la vérification côté cTrader.

**Le sujet des fills partiels est clos pour Tradovate. Pour cTrader, la règle est :
une ligne de relevé = une jambe = un trade Edgewonk.**

---

## 9. Appariement cTrader ↔ Edgewonk

**Il n'existe aucun identifiant commun.** L'appariement se fait par **clé dérivée** :

```
instrument + direction + horodatage d'entrée + prix d'entrée
```

L'horodatage à la seconde plus l'instrument est déjà quasi unique ; le prix d'entrée
sert d'arbitre.

**Fuseau horaire — ⚠️ CORRIGÉ LE 25/08/2026 : Edgewonk stocke en UTC, pas en heure de
Paris.** L'affirmation antérieure (« tout normaliser en heure de Paris ») est fausse pour
l'importateur cTrader.

Mesuré à l'envers pour ne pas deviner : appariement d'abord sur le **montant net** — un
pivot qu'aucun fuseau ne décale — puis lecture de l'écart sur les couples obtenus.
Résultat **2 h 00 pile** en août, donc UTC. `docs/tradovate.md` §5 bis avait relevé les mêmes
2 h en notant que « le traitement du fuseau semble différer d'un importateur à l'autre » :
il ne différait pas, c'est cette section qui était fausse.

→ Convertir via l'**offset porté par le relevé**, jamais par un −2 h en dur : en hiver le
relevé sort en UTC+1 et un décalage figé casserait en silence.

⚠️ **Edgewonk TRONQUE les horodatages à la minute** sur ces trades : `13:43:18` → `11:43:00`,
`14:30:01` → `12:30:00`. Deux jambes sorties dans la même minute deviennent donc
indiscernables par l'heure seule — le cas existe déjà. Le **montant** et la **quantité** les
départagent.

**Clé retenue, mesurée à 44/46 sans ambiguïté :** instrument + sens + minute d'entrée UTC +
minute de sortie UTC, départage par montant puis quantité. Le VWAP d'entrée sert de
**contrôle d'intégrité**, pas de clé.

⚠️ **`journal-entries-search` n'est PAS trié par date.** Le tri se fait par identifiant,
c'est-à-dire par ordre d'insertion. Une page de 200 sur la base 100001 a renvoyé des trades
de novembre 2025 à juillet 2026, **sans aucun trade d'août 2026** pourtant présent. Prendre
la première page pour « les trades récents » est une erreur silencieuse : **paginer jusqu'à
épuisement**.

**Prix d'entrée à utiliser : le VWAP**, c'est-à-dire `scalings[START_ENTRY].scalingPrice`
côté Edgewonk et `ProtoOAPosition.price` côté cTrader. Les deux agrègent à l'identique
(voir §8 bis). Ne jamais apparier sur le prix d'un fill individuel.

En cas d'ambiguïté résiduelle, `fineScalings` donne l'horodatage de chaque exécution,
ce qui permet de recouper avec les deals cTrader un par un.

### Volume d'appels

Pas d'endpoint de traitement par lot : **un `modify` par trade**. 60 trades ≈ 60 requêtes,
quelques secondes. Avec les screenshots (2 uploads + 1 flag par trade) ≈ 180 appels.
Séquentiel, léger délai entre appels.

---

## 10. Screenshots — génération, pas de capture

**TradingView est une impasse :** aucune API publique d'export d'image pour un compte
retail, les services tiers de capture ne connaissent pas `EURUSD.raw` (retour au problème
du feed de référence), et l'annotation par programme n'y est pas possible. cTrader n'offre
rien de mieux, et piloter son interface est la fragilité qu'on refuse.

**On génère l'image depuis les bougies de l'Open API** (`ProtoOAGetTrendbarsReq`), avec
marqueurs d'entrée et de sortie plus les niveaux SL/TP.

Exigence assouplie par l'utilisateur : plus besoin d'un drawing tool précis, il faut voir la
structure du setup et situer l'entrée et la sortie.

### Règles de cadrage (constantes ajustables)

⚠️ **Périmé le 25/08/2026 au soir.** Le cadrage ne se décide plus ici : voir
`docs/gabarit-graphiques.md` §7–8. En résumé — **quatre images par POSITION** (M5, M15, H1,
H4), marge de **60 bougies avant l'entrée et 30 après la sortie**, et le graphique suit
la **jambe réellement tenue** (la dernière sortie), pas le découpage d'Edgewonk.

**Ce qu'on perd :** les indicateurs et le template visuel personnel. On obtient un
graphique en bougies propre, identique à chaque fois, aux prix du broker. Suffisant pour
lire une structure et situer des exécutions ; pas pour retrouver l'écran d'origine.

Upload : voir §5. Six emplacements disponibles.

---

## 11. Bases et environnement de test

`GET /v1/databases` → les six journaux :

| id | nom |
|---|---|
| 100001 | Compte A *(courant)* |
| 104615 | 80K FTMO |
| 104616 | 10K Funding Pips |
| 100006 | [all] Missed trades |
| 100005 | **Overall** — contient les 6 trades futures de test |
| 100004 | Compte B |

Le jeton se trouve dans `localStorage.currentUser` (le blob `X-Auth-Token` tel quel) et le
journal courant dans `localStorage.currentDatabase`. Utile pour rejouer des tests depuis la
console du navigateur sans manipuler d'identifiants.

**Cloisonnement :** l'identifiant de base est dans l'URL de chaque appel. Aucun état
implicite, aucun risque d'écrire dans le mauvais journal.

**Trades de test (base 100005), état d'origine restauré le 24/08/2026 :**
`17860734` MNQ · `17860735` GC · `17860736` `17860737` `17860738` `17860739` MGC.
Importés, non journalisés : setup par défaut, aucun tag, aucune note, aucun screenshot.

---

## 12. Déroulé d'une exécution

Ordre imposé par ce qui a été mesuré, pas par confort.

```
1.  S'authentifier          POST license.edgewonk.app/auth/authenticate   (une seule fois)
                            puis /auth/refresh-token pour prolonger
2.  Lire cTrader            deals + ordres + journal d'événements de position
3.  Construire le canonique base locale, application des règles R1 à R7
4.  Lister les trades       POST /journal-entries-search/{offset}/{limit}
5.  Apparier                instrument + sens + minute d'entrée + minute de sortie
                            (UTC, tronqué à la minute — voir §9)
                            départage par montant puis quantité ; le VWAP
                            d'entrée est un CONTRÔLE, pas une clé
6.  INSTANTANÉ              sauvegarder l'état de chaque trade avant d'y toucher
7.  Écrire par `modify`     slPrice, tpPrice, highestPrice, lowestPrice
8.  Écrire par `PUT`        originalTpHit, ignoreForWinrate, alternativeStrategies
                            (read-modify-write, transformation du §0)
9.  Générer les graphiques  M5 + M15 + H1 + H4 depuis les bougies cTrader,
                            un jeu par POSITION (pas par jambe)
10. Uploader                emplacement 1 = M5, 2 = M15, 3 = H1, 4 = H4
11. Flaguer                 modify {screenshot1Exists … screenshot4Exists}
12. RELIRE ET COMPARER      un 200 ne prouve rien
```

**Deux règles non négociables :** l'instantané avant écriture (étape 6) et la relecture
après (étape 12). Elles ont fait leurs preuves sur 338 écritures consécutives.

### Conventions

- **Emplacements 1 = M5, 2 = M15, 3 = H1, 4 = H4.** *(Révisé le 25/08 au soir : c'était
  1 = LTF, 2 = HTF.)* Les emplacements 5 et 6 restent libres pour ses propres captures.
- ⚠️ **Seule la jambe réellement tenue reçoit des captures** — c'est-à-dire un trade
  Edgewonk par POSITION. Les trades correspondant aux allègements restent **sans
  screenshot**, volontairement : ils ne représentent aucune décision de trading. Sur un
  relevé de 46 jambes / 38 positions, ça fait **152 uploads**, pas 184.
- **Description d'image** : `{SYMBOLE}_{AAAA-MM-JJ}_{M5|M15|H1|H4}` — elle s'affiche dans
  l'interface.
- **`inReview: true`** pour marquer un trade dont le SL ou le TP initial est indécidable
  (règle R5). Le champ est écrivable par `modify` et existe déjà dans l'outil : inutile
  de tenir une liste à part, le signalement vit là où l'utilisateur travaille.

---

## 13. Note opérationnelle — faire passer un fichier vers le navigateur

Encoder un PNG en base64 pour l'injecter dans la page coûte cher. Méthode retenue :

1. copier le fichier dans **`/mnt/user-data/outputs/`**
2. créer un `<input type="file">` temporaire dans la page
3. le remplir avec `mcp__claude-in-chrome__file_upload`
4. lire `input.files` en JavaScript — ce sont de vrais objets `File`, postables tels quels

Les chemins du dossier Mac connecté et de `/tmp` sont **refusés** par cet outil ;
seul le dossier de sortie de la session passe.

---

## 13 bis. État d'implémentation — relevé le 26/08/2026

Ce document décrit un **contrat**, pas un état du code. Les deux ont divergé : le §12
décrit un déroulé dont l'étape 8 n'a longtemps été faite qu'au tiers.

| ce que le contrat prévoit | dans `pipeline/edgewonk/` |
|---|---|
| `slPrice`, `tpPrice`, `highestPrice`, `lowestPrice` par `modify` | ✅ |
| `originalTpHit` par `PUT` | ✅ |
| `inReview` par `modify` | ✅ |
| upload des captures + drapeaux | ✅ **validé en réel le 25/08 au soir** — 16 captures confirmées par relecture |
| `alternativeStrategies` par `PUT` | ✅ validé en réel · `gain: null` accepté par le serveur · ⚠️ le serveur **ne préserve pas l'ordre** de la liste : comparer par `strategyId` **seul**, jamais par position ni par `(strategyId, setupId)` — voir ci-dessous |
| `managementComments` par `PUT` | ✅ **livré le 26/08/2026** — le SEUL champ de tagging écrit, et une brèche assumée dans le §0. Valeur saisie à la main (`OK`/`KO`), options résolues par nom depuis `GET /comments` (§7). Case vide → rien n'est écrit, dans aucun sens |
| `ignoreForWinrate` par `PUT` | ✅ depuis le 25/08 au soir — **coche ET décoche** : le robot fait autorité *(révisé le 25/08 en fin de soirée)*. Sans SL, rien n'est écrit dans aucun sens. Une case non cochée est relue `False`, `None` **ou** `0` : comparer sur `bool()` |

⚠️ **`(strategyId, setupId)` était un piège, pas une clé** *(corrigé le 26/08/2026)*.
La clé composée marchait par chance : les trades d'août avaient déjà des stratégies, dont
le `setupId` était recopié dans notre envoi. Sur un trade dont la liste est **vide**, on
n'envoie aucun `setupId` — c'est le serveur qui le pose. La clé devenait introuvable et
**124 écritures parfaitement passées** étaient signalées comme divergentes. Le `setupId`
est celui du trade, invariant : il n'a rien à faire dans une clé d'identité de palier.

**Les paliers sont au nombre de huit depuis le 26/08** : 1R, 1,5R, 2R, 2,5R, 3R, 3,5R, 4R,
5R. Ils ne sont énumérés qu'à un seul endroit, `ctrader/bougies.py`, et se résolvent sans
aucune requête de bougies depuis le `prix_max_favorable` stocké.

**Tenir ce tableau à jour.** C'est lui qui empêche de croire qu'un champ part chez
Edgewonk parce qu'il est documenté ici.

---

## 14. Ce qui reste à vérifier

Le contrat d'écriture est **entièrement validé en conditions réelles** : 169 `PUT` de
remplissage puis 169 de restauration sans une erreur ni un écart, et la chaîne d'images
de bout en bout avec de vrais graphiques.

Il ne reste qu'un point, mineur : le comportement sur une **sortie** en plusieurs fills
(§8 bis). Le mécanisme est connu, l'exemple manque.
