# Tradovate — état des lieux

Compte futures chez **Prop Firm B** (prop firm). Instruments : MNQ, NQ, MGC, GC, MCL, 6E, 6J, M6E.
Analyse du 25/08/2026 sur un export de 204 ordres (mois en cours).

---

## 1. L'API existe et répond au besoin — mais elle est fermée

Tradovate versionne les ordres : **une nouvelle `orderVersion` est créée à chaque
modification**. L'historique complet se récupère par :

```
GET /orderVersion/deps?masterid={orderId}
```

`/orderVersion/item?id=` renvoie une version précise, donc potentiellement périmée —
c'est `deps` qu'il faut interroger.

C'est l'équivalent exact des événements `Modify protection` de cTrader, et ça résoudrait
proprement le problème des brackets.

**Mais l'accès API officiel demande** un compte live financé à 1 000 $ minimum, un
abonnement à 25 $/mois, et une licence données CME pour le temps réel. **Les comptes prop
firm et évaluation en sont explicitement exclus**, quel que soit le solde affiché : ce ne
sont pas des comptes clients au sens de Tradovate.

→ **Le compte Prop Firm B n'y a très probablement pas droit.** À confirmer auprès du support.

---

## 2. L'export CSV — ce qu'il contient vraiment

**Mesuré : 204 lignes, 204 `Order ID` uniques, aucun doublon.**
→ **Une ligne par ordre, pas une ligne par version. L'historique n'y est pas.**

Ce qu'on y trouve quand même :

| Signal | Valeur |
|---|---|
| `Version ID` ≠ `Order ID` | **l'ordre a été modifié au moins une fois** — 37 lignes sur 204 |
| `Stop Price` / `Limit Price` | la valeur **finale**, après toutes les modifications |
| `Text` | `Chart` (144), `multibracket` (45), `Exit` (12), `AutoLiq` (3) |
| `Type` | Limit 69, Market 68, Stop 67 |
| `Status` | Filled 89, Canceled 90, **Rejected 25** — à filtrer |
| `_tickSize` | présent par ligne, indispensable pour raisonner en ticks |

**Pas de lien de parenté explicite** entre l'ordre d'entrée et ses protections. Le
rapprochement se fait par produit, sens opposé, proximité temporelle, et surtout
**identifiants d'ordre adjacents** — un groupe OSO est créé d'un bloc, ses ids se suivent.

---

## 3. Le problème du placeholder — mesuré

Le preset ATM de l'utilisateur pose **TP 20 ticks / SL 20 ticks** à l'entrée. Ces niveaux ne
sont jamais les vrais : il les ajuste dans les minutes qui suivent.

Sur les 14 protections de bracket que le rapprochement a permis d'apparier :

```
écarts finaux à l'entrée, en ticks :
6, 7, 7, 9, 20, 20, 22, 24, 28, 29, 29, 52, 100, 193

modifiées : 14 / 14        jamais modifiées : 0 / 14
```

**Bonne nouvelle : dans cet échantillon, le placeholder ne survit jamais.** l'utilisateur ajuste
systématiquement. Deux niveaux tombent à 20 ticks pile, mais leurs ordres sont marqués
comme modifiés — c'est une coïncidence, pas un placeholder oublié.

**Nuance importante :** seuls 45 ordres sur 204 sont des `multibracket`. Les 144 autres sont
posés directement au graphique (`Text = Chart`), donc au bon niveau d'emblée — aucun
problème de placeholder pour eux, et seulement 13 d'entre eux ont été modifiés. Mais l'usage
de l'ATM est récent et va croître.

---

## 4. Pourquoi le CSV ne suffit pas

Il donne la valeur **finale** d'un ordre, et un simple booléen « a été modifié ».
Il ne permet donc **pas de distinguer** :

- « j'ai remplacé le placeholder par mon vrai stop » → c'est le risque initial, on le veut
- « j'ai remplacé le placeholder, puis j'ai trailé » → la valeur finale est le stop trailé,
  pas le risque initial

Or **R se calcule sur le risque initial**. Prendre la valeur finale fausserait tous les
R-multiples sur les trades gérés.

→ **Il faut l'historique des versions. Donc l'API.**

---

## 5. Alerte — les SL/TP Tradovate déjà présents dans Edgewonk semblent faux

⚠️ **Le journal cité ici n'est pas celui qu'il faut alimenter.** *(Corrigé le 26/08/2026.)*
`archives/mesures/diag_journaux.py` a montré le tableau complet : les futures existent dans **deux**
journaux distincts, sans aucun identifiant en commun — donc en deux copies.

| journal | trades | période | futures | Management |
|---|---|---|---|---|
| **100001** « Compte A » | 240 | 15/10/2025 → 26/08/2026 | **36** | `Not managed` / `Managed` |
| 100004 « Compte B » | 34 | 06/08 → 21/08 | 34 | `Followed rules` / `Broke rules` |
| 100006 « [all] Missed trades » | 14 | — | 0 | — |

100004 s'arrête au 21/08, 100001 va jusqu'au 26/08 : **l'import Tradovate a été rebranché
sur le journal principal**, et 100004 est un vestige. L'utilisateur le disait — « le Prop Firm B 50K,
il existe pas, on n'utilise que le Compte A » — et la mesure lui donne raison.

→ **Le pipeline vise 100001 pour les DEUX plateformes.** Et comme ce journal porte les bons
libellés Management, le repli par rating disparaît, avec lui le risque d'écrire
« Broke rules » là où on veut dire « Managed ».

*Ce que ça a coûté de l'avoir cru : rien — aucune écriture n'avait été faite. Ce paragraphe
avait mesuré ce qu'il voyait, sur le seul journal qu'il avait regardé. Un échantillon d'un
ne fait pas une règle non plus.*

Ce qui suit reste vrai des trades de 100004, et l'était aussi de ceux de 100001 :

Base `100004` (Compte B) : 30 trades sur 34 ont un `slPrice`, 27 un `tpPrice`.
Edgewonk **importe donc bien** quelque chose côté Tradovate. Mais les valeurs ne tiennent
pas debout :

| Trade | Sens | Entrée | SL | TP |
|---|---|---|---|---|
| 17860744 | SELL MNQ | 29334 | 29517.75 | **29333.5** |
| 17860745 | SELL MNQ | 29348.5 | 29522.5 | 29336.25 |

Un stop à **183 points** de l'entrée sur MNQ, et une cible à **0,5 point** : ce n'est pas
une géométrie de trade réelle. Les niveaux eux-mêmes existent bien dans le CSV (ce sont de
vrais ordres Stop), mais **ils paraissent rattachés aux mauvais trades**.

*Réserve : le rapprochement croise deux fuseaux horaires et n'a pas été vérifié ordre par
ordre. Mais l'ordre de grandeur suffit à conclure que la donnée est inexploitable.*

→ **Les données Tradovate actuellement dans Edgewonk sont à recalculer, pas seulement à
compléter.** C'est un argument de plus pour construire le pipeline.

---

## 5 bis. La segmentation — et pourquoi le Position History n'est PAS nécessaire

⚠️ **RENVERSÉ le 26/08/2026.** Ce paragraphe tenait « Position History » pour la pièce
maîtresse : lui seul porterait l'appariement FIFO des exécutions, donc la segmentation
d'Edgewonk. **C'est faux.** L'export « Orders » donne, pour chaque ordre rempli, son heure,
sa quantité, son prix moyen et sa **valeur notionnelle**. De quoi refaire l'appariement
FIFO soi-même — et le refaire *exactement*.

Vérifié contre les trades réels du journal 100004, cinq sur cinq, au centime :

| notre reconstruction | trade Edgewonk | écart |
|---|---|---|
| NQ SELL 13:03→13:15, q 2 | `17860742` | **0,00** |
| NQ SELL 13:25→13:25, q 2 | `17860743` | **0,00** |
| MNQ SELL 13:26→13:29, q 2 | `17860744` | **0,00** |
| MNQ SELL 13:30→13:35, q 1 | `17860745` | **0,00** |
| MNQ BUY 11:43→14:07, q 2 | `17860746` | **0,00** |

*Les montants eux-mêmes ne sont pas reproduits ici : c'est l'écart qui porte
la démonstration, et il est nul cinq fois sur cinq.*

Segmentation, horodatages, quantités et P/L : identiques. **Un fichier de moins à exporter,
à nommer et à confondre.** Le paragraphe qui suit décrit la règle mesurée, qui reste vraie —
c'est seulement la source qui change.

**Le multiplicateur se déduit de l'export, il n'est pas tabulé.** `Notional Value / (prix ×
quantité)` donne NQ 20, MNQ 2, GC 100, MGC 10, MCL 100, 6E 125 000. Une table codée en dur
serait une table à maintenir, et une table fausse produit des montants plausibles.

---

## 5 bis (suite). L'export « Position History » — ce qu'il avait appris

Colonnes : `Position ID`, `Pair ID`, `Buy Fill ID`, `Sell Fill ID`, `Paired Qty`,
`Buy Price`, `Sell Price`, `P/L`, `Bought Timestamp`, `Sold Timestamp`, plus les agrégats
de position (`Bought`, `Avg. Buy`, `Sold`, `Avg. Sell`).

C'est **l'appariement FIFO des exécutions**, groupé par position.

### ⚠️ RENVERSÉ le 26/08/2026 — un trade Edgewonk = UN PASSAGE À PLAT

Ce qui suit était la règle établie le 25/08 sur deux cas. Elle est **fausse**, et la vraie
règle est plus simple : **tout ce qui se passe sur un contrat entre deux moments où le
compte est plat forme un trade Edgewonk.**

**Le contre-exemple qui tranche — position MGCV6 du 17/08 14:10 :**

```
14:10:50  vente 2 @ 4416.0      les rachats de 14:17 et 14:18 partagent le fill
14:12:20  vente 4 @ 4416.6      de 14:10 -> composante A+B
14:17:38  achat 1 @ 4416.8
14:18:54  achat 1 @ 4417.0      le rachat de 15:07 consomme le fill de 14:12
15:07:06  achat 4 @ 4407.0      -> composante C
```

La règle des composantes prédit **deux** trades là où Edgewonk n'en a fait
**qu'un**, entrée au VWAP **4416,4** — la position entière. Le passage à
plat, lui, le prédit juste, et il explique aussi les deux cas d'origine : `…044` repasse à
plat entre ses deux appariements, `…180` non.

**Et le compte tombe : 34 positions à plat ouvertes avant le 22/08, 34 trades dans le
journal 100004.** L'ancienne règle en donnait 35.

*La règle des composantes n'était pas absurde : elle collait aux deux seuls cas alors
disponibles. C'est le §8 du README, règle 6, mot pour mot — un échantillon de deux ne fait
pas une règle. Elle a survécu une journée.*

⚠️ **Une position encore ouverte ne produit aucune jambe.** Un trade Edgewonk naît du retour
à plat ; une sortie partielle n'en est pas un. Le cas est signalé et la position entrera au
cycle suivant, complète.

---

### Ce que la règle des composantes avait vu (conservé pour l'historique)

Vérifié au centime près :

| Ligne Position History | Trade Edgewonk |
|---|---|
| Pair `…057`, qté 2, achat 29347.25, vente 29334.00, P/L **−53.00** | `17860744` qté 2, entrée 29334, sortie 29347.25, gain **−53** |
| Pair `…077`, qté 1, achat 29348.25, vente 29348.50, P/L **0.50** | `17860745` qté 1, entrée 29348.5, sortie 29348.25, gain **0.5** |

Ces deux appariements appartiennent à **une seule** `Position ID` (`611750920044`), et
Edgewonk en a fait **deux trades distincts**.

Mais la position `611750920180` a elle aussi deux appariements — qui **partagent le même
`Buy Fill ID`** — et Edgewonk n'en a fait **qu'un seul** trade, entrée au VWAP 29797.375.

→ *Conclusion de l'époque, invalidée le 26/08 : « un trade Edgewonk = une composante
connexe du graphe d'appariement ». Les deux observations ci-dessus restent exactes ; c'est
l'inférence qui était trop savante pour deux cas.*

⚠️ **Ceci contredit la règle « un trade = une position » établie côté cTrader.** Les deux
importateurs ne segmentent pas de la même façon. **La clé d'appariement doit être
spécifique à chaque plateforme.**

Pour Tradovate, apparier sur le **groupe d'appariements** : quantité, prix d'achat, prix de
vente et P/L, qui concordent exactement.

### Fuseau horaire — TRANCHÉ le 26/08/2026, par la mesure

**L'export Tradovate écrit ses heures en UTC+2.** Mesuré contre le marché, pas contre
Edgewonk : pour dix ordres remplis, sur cinq contrats et à des heures allant de 01:55 à
19:19, on a cherché quels décalages font tomber le prix d'exécution **dans la bougie M1**
de Databento à cette minute-là. UTC+2 colle sur **10/10** ; le suivant sur 3/10. Un
décalage faux fait sortir le prix de la bougie, sauf coïncidence — et dix ordres ne
coïncident pas dix fois. `archives/mesures/diag_fuseau_tradovate.py`.

**Confirmé indépendamment par Edgewonk**, qui stocke bien en UTC côté Tradovate aussi :
notre `19:19:07` devient `17:19:07` chez eux. Deux heures pile, comme côté cTrader.
L'observation initiale de ce paragraphe était juste ; elle est maintenant mesurée.

⚠️ **Ce qui n'est PAS tranché : l'heure d'hiver.** L'export ne couvre qu'août. Un décalage
FIXE de +2 et l'heure locale de Paris sont indiscernables sur ces données. Le code retient
« Paris », qui suit le changement d'heure tout seul plutôt qu'un +2 figé qui dériverait
d'une heure en novembre — en silence, et sur des extrêmes qui resteraient plausibles. La
sortie du diagnostic est déjà groupée par mois : un export couvrant novembre tranchera de
lui-même.

⚠️ **Edgewonk ne tronque PAS toujours à la minute côté futures.** 24 trades sur 34 portent
des secondes non nulles (`2026-08-11T17:19:07`), les autres non — deux régimes dans le même
journal. La clé compare des **minutes**, ce qui reste juste dans les deux cas. Resserrer sur
la seconde aurait paru plus précis et cassé 10 trades sur 34.

⚠️ **Edgewonk stocke le PRODUIT, pas le contrat.** `MGC`, `MNQ`, `6E`, `NQ`, `GC`, `MCL` —
jamais `MNQU6`. Côté cTrader il stocke le symbole du broker, suffixe compris. La colonne à
comparer est donc déclarée par plateforme, et mesurée des deux côtés
(`core/plateformes.colonne_instrument`). Chercher `MNQU6` n'aurait rien trouvé, sur 100 %
des jambes.

---

## 5 ter. Pourquoi les SL/TP Tradovate d'Edgewonk sont faux — expliqué

Le stop de `17860744` était `29517.75`. On le retrouve dans l'export des ordres :

```
611750920046 — MNQ Buy Stop 2 @ 29517.75 — Canceled — Text = Chart — 08/06 15:27:29
```

Un **Buy Stop 183 points au-dessus** d'un short entré à 29334, une minute après l'entrée.
Ce n'est pas un stop de protection : c'est un **ordre d'entrée en cassure**, posé au
graphique, jamais déclenché, puis annulé.

→ **Edgewonk ne distingue pas un ordre de protection d'un ordre d'entrée.** Il ramasse
n'importe quel `Stop` ou `Limit` proche dans le temps et le colle en SL ou TP.

**Conséquence directe :** les 144 ordres `Text = Chart` de l'export empoisonnent la donnée,
alors que les 45 `Text = multibracket` sont, eux, de vraies protections rattachées à leur
entrée. **Le passage récent de l'utilisateur à l'ATM améliore donc mécaniquement la qualité de
ses données** — et le pipeline devra filtrer sur `Text` pour ne retenir que les vraies
protections.

---

## 5 quater. La bascule à l'ATM du 18/08 — et ce qu'elle change vraiment

**Mesuré le 26/08/2026 sur l'export de 204 ordres, jour par jour.** C'est le fait qui
décide de ce que ce pipeline peut automatiser et de ce qu'il ne peut pas.

| jour | `Chart` | `multibracket` |
|---|---|---|
| 06/08 → 17/08 | 113 | 0 |
| 18/08 | 24 | 3 |
| 19/08 | 1 | 3 |
| 20/08 | 3 | 22 |
| 21/08 | 0 | 6 |
| 24/08 | 3 | 11 |

**Avant le 18/08, aucun SL/TP n'est récupérable de l'export**, et ce n'est pas un défaut du
lecteur : l'information n'y est pas. Une entrée posée au graphique et son stop posé au
graphique sont deux lignes qui ne se ressemblent en rien — c'est exactement ce qui fait
qu'Edgewonk colle des stops à 183 points (§5 ter).

**Depuis le 20/08, tout est lisible.** Un groupe ATM est créé d'un bloc : entrée, puis
cible (`Limit`, sens opposé), puis stop (`Stop`, sens opposé), en identifiants consécutifs.
Le module retrouve les **8 brackets** des entrées réellement remplies, et reproduit au tick
près les écarts du §6.

→ **La partie manuelle est un arriéré borné — 60 ordres remplis du 06 au 17/08 — pas une
charge récurrente.** Ces positions passent par le fichier de saisie, exactement comme une
position cTrader. `⚠️` Et la règle du §4 du README s'applique telle quelle : **un stop
retrouvé de mémoire est inventé, pas imprécis.** Une case laissée vide reste vide.

### Quatre garde-fous, et pourquoi ils ne corrigent jamais

**Le délai d'ajustement — le plus direct des quatre.** *(Mesuré le 26/08.)* Le §7 repose
sur une phrase de l'utilisateur : « j'ajuste mon bracket une fois après l'entrée, puis je n'y
touche plus ». C'est ce qui rend la valeur finale utilisable comme risque initial. Rien ne
le vérifiait. Or l'export porte la **dernière mise à jour** de chaque ordre : l'écart entre
le remplissage de l'entrée et la dernière modification de son stop mesure exactement combien
de temps ce stop a continué de bouger.

```
0, 0, 0, 0, 0, 1, 1, 8 minutes  …  et 186 minutes
```

Neuf ajustements dans les huit minutes — **la routine du §7, confirmée par la mesure**. Et
un seul à plus de trois heures : la position 6EU6 du 20/08 14:02, dont les **bougies**
disaient déjà que le stop n'était pas en place (le prix est passé 1,9 R dessous sans que le
trade se termine). *Deux méthodes indépendantes, le même trade.*
→ `DELAI_AJUSTEMENT_MAX = 30` minutes, dans une zone vide entre 8 et 186.

⚠️ **Et celui-là ne se contente pas de signaler : il retire la proposition.** Un stop dont
on a *mesuré* qu'il n'est pas le niveau initial n'est pas pré-rempli dans le fichier de
saisie. Le proposer avec un avertissement à côté reviendrait à le faire accepter par
défaut — c'est déjà arrivé une fois, sur ce trade exactement : le R:R de 12,5 avait
signalé, l'alerte a été acquittée, le stop est resté et a faussé le R.



**Le R:R anormal.** Un stop resserré vers le break-even sans que la cible bouge fait
exploser le R:R. Au-delà de **6:1**, le module signale que la valeur lue n'est plus le
risque initial. Retrouvé sur l'export : le groupe du 20/08 14:00, à 12,5.

**Le placeholder ATM survivant.** Le preset pose 20 ticks de chaque côté. Quand les deux
jambes valent exactement ce nombre, le bracket n'a probablement jamais été ajusté et les
niveaux ne sont pas ceux du trade. Retrouvé : le groupe du 24/08 16:35, à 20/20.

**La simulation qui contredit le trade.** *(Trouvé le 26/08 dans les données réelles.)*
Si le prix a franchi le SL saisi **avant** d'atteindre son extrême, et que le trade a
pourtant continué, alors ce SL n'était pas en place à ce moment-là. **Un trade ne survit
pas à son propre stop.** Le cas : `20260820-140208-6EU6-A`, entrée 1,16935, stop saisi
1,16895 (4 pips) — le plus bas du trade est **1,16820, soit 1,9 R sous le stop**, et la
position a tenu trois heures de plus avant de sortir exactement au stop. Le R:R de 12,5
avait signalé quelque chose ; l'alerte a été acquittée et le stop est resté.
→ `R_SIMULATION_INCOHERENTE = 0.50` dans `ctrader/bougies.py`. Calibré sur 50 jambes
réelles des deux plateformes : **deux déclenchent**, à 2,9 R et 202 R d'écart, et les deux
sont de vrais cas ; la valeur suivante est à 0,00 R. Le seuil est posé dans une zone vide,
pas ajusté sur un cas.

⚠️ **Correction du §6 de ce document.** Il disait ce groupe « marqué intact », déduit du
drapeau `Version ID ≠ Order ID`. **C'est faux, mesuré** : ses deux protections sont marquées
*modifiées*. Le drapeau ne détecte pas un placeholder survivant. On détecte donc sur la
**géométrie**, qui elle ne ment pas. *Le §6 avait été établi sur un regroupement différent —
même piège que la segmentation généralisée sans revérification.*

---

## 6. L'export garde la valeur FINALE — démontré

Le preset ATM pose **20 ticks / 20 ticks**. Si l'export conservait la valeur initiale, les
quatorze groupes de bracket afficheraient tous 20/20. Écarts réellement observés :

```
date         SL ticks   TP ticks   R:R
18/08            9         29      3.2
19/08           58        231      4.0
20/08            6         24      4.0
20/08            8        100     12.5   <-- anomalie
20/08           16         64      4.0
20/08            7         28      4.0
20/08           52        193      3.7
21/08            7         29      4.1
21/08           22         84      3.8
24/08            7         28      4.0
24/08           20         20      1.0   <-- ATM jamais touché
```

**C'est donc bien le dernier état qui est exporté.** Le groupe du 24/08 16:36, avec ses deux
jambes marquées intactes à 20 ticks, montre à quoi ressemble un bracket non ajusté.

### Le bon détecteur de management : l'anomalie de R:R

Neuf groupes sur onze tombent entre **3,2 et 4,1** — la signature des setups visés par
L'utilisateur (3 à 4 R). Ces couples SL/TP ont été posés ensemble, à l'entrée.

Un stop resserré vers le break-even sans que la cible bouge **fait exploser le R:R** :
c'est le cas du 20/08 à 14h00, **12,5:1**.

→ **Règle de détection : R:R au-delà de 6:1 ⇒ stop probablement resserré, trade marqué.**
Elle s'appuie sur la signature statistique réelle, pas sur un seuil arbitraire.

*Un critère antérieur — « le stop a-t-il franchi l'entrée du côté du gain » — s'est révélé
insuffisant : on peut resserrer très près du break-even sans jamais le franchir.*

---

## 7. DÉCISION — pas de management sur les futures

**L'utilisateur a tranché le 25/08/2026 : aucun trade management sur Tradovate.** Il ajuste son
bracket une fois après l'entrée, puis n'y touche plus.

Raison donnée : sa stratégie est censée tenir sans management, qui reste un bonus en cours
de mise en place. Il assume le risque, y compris celui de perdre le compte.

**Conséquence : la dernière valeur exportée EST le risque initial, par construction.**
Le sujet Tradovate se résout donc **entièrement par les deux exports CSV**, sans API, sans
zone grise, sans abonnement.

**Décision annexe : ne pas passer par l'API interne de la plateforme web.** L'asymétrie est
mauvaise — risquer un compte financé pour automatiser de la saisie sur une part minoritaire
du volume. Écarté délibérément, pas par ignorance.

**La règle reste auditable :** si l'utilisateur dérive un jour vers du management, le détecteur
de R:R le signalera de lui-même. La décision n'est donc pas irréversible et ne demande
aucune discipline aveugle.

---

## 8. Ce qu'il reste à faire

| | état au 26/08/2026 |
|---|---|
| Lecture de l'export → jambes (FIFO + composantes connexes) | ✅ **UN seul export suffit** — vérifié au centime contre 5 trades réels (§5 bis) |
| SL/TP depuis les brackets ATM | ✅ 8 brackets retrouvés, les deux garde-fous validés sur données réelles |
| Source de bougies | ✅ `databento/client.py` — six sondes vertes, **et la forme de la réponse confirmée** (§9) |
| Choix de plateforme au lancement | ✅ livré — `1` cTrader / `2` Tradovate |
| Fuseau de l'export | ✅ **UTC+2, mesuré 10/10 contre les bougies du marché** (§5 bis) |
| Nom d'instrument côté Edgewonk | ✅ **le PRODUIT, pas le contrat** — clé corrigée (§5 bis) |
| **Premier `pousser` réel** | ✅ **passé le 26/08** — 35/35 appariées, 39 champs et 28 images confirmés par relecture, zéro divergence |
| Recalculer les SL/TP faux déjà chez Edgewonk | ✅ écrasés par les nôtres au premier cycle |
| Supprimer le journal `100004` | ⬜ 34 copies des trades futures, arrêtées au 21/08, que le pipeline n'alimente pas |
| Heure d'hiver | ⬜ non testable sur un export d'août — relancer le diagnostic sur novembre |

**Toutes les hypothèses bloquantes sont tombées.** Ce qui reste n'est plus de la mesure :
c'est un premier cycle, à faire sur le bac à sable `100005` avant le journal réel.

**Priorité :** cTrader d'abord — c'est fait depuis le 26/08/2026. Le chantier futures est
**dégelé**, et sa chaîne est écrite.

---

## 9. La source de bougies — DÉCIDÉE le 26/08/2026 : Databento

### Ce que le chantier n'avait pas, et qui bloquait tout

L'export CSV donne les trades. Il ne donne **aucun prix de marché** — donc pas d'extrêmes,
pas de TP-first, pas de paliers, pas de graphiques. Côté cTrader ce trou est comblé par le
serveur MCP local, gratuit et sans approbation. Côté Tradovate il n'y a **rien** : leur API
est fermée aux comptes prop firm (§1), et Edgewonk ne porte pas les cotations de ces
actifs.

### Ce qui a été tranché, et pourquoi

**Databento**, en mode *usage-based* : facturation au gigaoctet consommé, **sans
abonnement**. Quand ils ont basculé le temps réel en forfait mensuel en 2025, l'historique à
la demande a été explicitement conservé — et c'est la seule partie qui nous intéresse.
Dataset `GLBX.MDP3` : CME, CBOT, NYMEX, COMEX, donc les six produits tradés (MNQ, NQ, MGC,
GC, MCL, 6E). **125 $ de crédits offerts à l'inscription**, valables 6 mois.

**Écartés, en connaissance de cause :**

| | pourquoi |
|---|---|
| **Polygon** | les futures sont un abonnement séparé, ~199 $/mois. Hors de proportion pour 34 trades |
| **Interactive Brokers** | gratuit avec un compte, mais impose d'ouvrir ce compte, de souscrire au flux CME **et** de laisser tourner TWS ou la Gateway en permanence. Une pièce mobile de plus, exactement ce que ce projet refuse |
| **L'API interne de la plateforme web Tradovate** | déjà écartée (§7) : risquer un compte financé pour automatiser de la saisie est un mauvais échange. Ne pas rouvrir |

### Deux points établis, et leur statut

⚠️ **Pas de schéma 5 minutes ni 15 minutes — CONFIRMÉ par la mesure du 26/08/2026.**
`metadata.list_schemas` répond : `mbo`, `mbp-1`, `mbp-10`, `tbbo`, `trades`, `bbo-1s`,
`bbo-1m`, `ohlcv-1s`, **`ohlcv-1m`**, **`ohlcv-1h`**, `ohlcv-1d`, `definition`,
`statistics`, `status`. Ni 5m ni 15m. Le M5, le M15 et le M30 s'agrègent donc depuis le M1,
et le H4 depuis le H1 — `databento/client.py`, `AGREGATION`.

⚠️ **Et l'agrégation a un piège qui ne se voit pas :** un seau qui mord sur le bord de la
fenêtre demandée serait **incomplet**, donc son plus haut serait sous-estimé, en silence.
Le client élargit la requête jusqu'aux bornes de seau avant de tirer, puis découpe. Vérifié
par test hors ligne : une fenêtre 14:02→14:08 rend un M5 construit sur ses cinq minutes,
pas sur trois.

**Trois autres faits mesurés le 26/08/2026, tous en 200 :**

- l'historique de `GLBX.MDP3` remonte au **06/06/2010**, trois ans avant le premier trade
  futures de l'utilisateur — la profondeur n'est pas un sujet ;
- le tarif est de **70 $/Go en `ohlcv-1m`** et 190 $/Go en `ohlcv-1h` ;
- `metadata.get_cost` chiffre **0,0050 $ une journée entière de M1 sur un contrat**.

**Ce dernier chiffre décide de l'architecture du cache.** À un demi-centième de dollar la
journée, on tire la journée ENTIÈRE et on la garde sur disque, plutôt que la fenêtre exacte
du trade. Conséquence directe : `--refaire`, la reprise des paliers non résolus et la
pagination par tranches de 900 barres ne repaient plus rien. Et les bougies déjà lues
restent lisibles le jour où le budget serait épuisé — même raison de fond que
`donnees/brut/`.

*Ordre de grandeur de la facture totale : quelques dollars sur les 125 $ de crédits.*

**La symbologie n'est pas un sujet — MESURÉ le 26/08/2026, des deux côtés.**

L'export « Orders » écrit ses contrats en `MNQU6`, `6EU6`, `MGCZ6`, `MGCV6`, `MCLU6`,
`NQU6`, `GCZ6`, `MGCQ6`, `M6EU6`, `6JU6` — le format brut du CME, pas seulement celui de
l'interface. Et `symbology.resolve` sur `GLBX.MDP3` les résout tels quels
(`MNQU6` → instrument 42004800). **Aucune table de correspondance à maintenir**, exactement
la conclusion tirée pour `XAUUSD.raw` côté cTrader. L'hypothèse est fermée par la mesure,
pas par la vraisemblance.

### Ce qu'il faut mesurer avant d'écrire une ligne de pipeline

`pipeline/archives/mesures/diag_databento.py` — **lecture seule, aucune dépense** : il chiffre avant
de télécharger. Six sondes : l'authentification, la profondeur de l'historique (le premier
trade futures date d'octobre 2025 — si l'historique ne remonte pas jusque-là, il faudra le
dire), les schémas exposés, le tarif réel au gigaoctet, la résolution des contrats, et le
coût exact d'une fenêtre.

✅ **Les six sondes sont passées le 26/08/2026, toutes en 200.** Les URL supposées étaient
les bonnes, et l'authentification HTTP Basic avec la clé en identifiant et un mot de passe
vide fonctionne.

⚠️ **Un vérificateur qui mentait, trouvé au passage — le quatrième de ce projet.** La sonde
de symbologie affichait « OK » pour `MNQZ5`, `MGCZ5` et `MCLF6` alors que la même réponse
les listait juste en dessous comme non résolus. Cause : `result` porte **tous** les symboles
demandés en clé, avec une **liste vide** pour ceux qui échouent — tester la présence de la
clé répond donc toujours oui. Corrigé : on teste le contenu. *Même leçon que le comparateur
d'`alternativeStrategies` et que le vérificateur d'`appliquer()` : un contrôle qui ne peut
pas échouer n'est pas un contrôle.*

**Ce qu'aucune sonde de métadonnée ne peut dire, et qui reste donc supposé :** la FORME
d'un enregistrement OHLCV — JSON par lignes, prix entiers en virgule fixe à diviser par
1e9, horodatage en nanosecondes dans `hd.ts_event`. Une erreur d'échelle ne planterait
pas : elle produirait des extrêmes plausibles et faux. `archives/mesures/diag_tirage.py` tranche sur
une vraie fenêtre, pour 0,005 $.

### La forme de la chaîne Tradovate — écrite le 26/08/2026

Plus courte que celle de cTrader, mais **pas pour la raison qu'on croyait**. L'export porte
le SL et le TP **des seules entrées ATM** (§5 quater) : c'est vrai de tous les trades
depuis le 20/08, et faux de tous ceux d'avant. La saisie manuelle ne disparaît donc pas,
elle se vide — et la colonne `management` reste à remplir dans tous les cas, `OK` partout
tant que la règle du §7 tient.

**Le lanceur demande la plateforme au démarrage — `1` = cTrader, `2` = Tradovate.** Il ne
renifle pas le format du CSV : deviner marcherait 99 fois et casserait en silence la
centième. C'est l'utilisateur qui déclare ce qu'il importe.

*(Nuance, et elle ne contredit pas la règle : une fois « Tradovate » déclaré, les DEUX
exports sont reconnus à leur **en-tête** — « Pair ID » n'existe que dans le Position
History, « Order ID » que dans les Orders. Un nom de fichier se renomme, se déplace, gagne
un « (1) » ; une en-tête dit ce que le fichier contient. Un fichier qui porte les deux
marqueurs, ou aucun, est refusé au lieu d'être deviné.)*

**Ce qui n'a demandé aucune ligne nouvelle**, et c'est le bénéfice du cloisonnement par
profil de risque : le calcul des extrêmes, le TP-first, les huit paliers, les quatre
graphiques et toute l'écriture Edgewonk. `databento/client.py` répond au **même appel** que
le MCP cTrader — `appeler("get_trendbars", …)` — donc `ctrader/bougies.py` et
`graphiques/rendu.py` servent les futures sans une ligne modifiée. Tout ce que ces modules
ont appris en dix jours — les bougies de bord, le trou du week-end, la jambe réellement
tenue — s'applique tel quel.

**⚠️ CE PARAGRAPHE A ÉTÉ RENVERSÉ — 26/08/2026.** Il disait qu'un trade Edgewonk côté
futures était une **composante connexe du graphe d'appariement**, calculée par union-find
sur les `Buy Fill ID` / `Sell Fill ID`, et il s'appuyait sur deux cas mesurés qui
concordaient. Le contre-exemple **MGCV6 du 17/08** l'a démenti.

**La règle réelle : une position À PLAT.** De zéro contrat net à zéro contrat net.
`tradovate/statement.py` suit la quantité nette et ferme la position quand elle repasse à
zéro. C'est mécanique, ça ne suppose rien, et ça reproduit exactement ce qu'Edgewonk
fabrique. *Deux cas qui concordent ne font pas une règle — c'est la leçon la plus chère du
chantier futures.*

**⚠️ Et les SL/TP ne sont plus réservés aux entrées ATM — 28/08/2026.** Ce document dit
plus bas qu'une entrée posée au graphique sort sans SL ni TP. C'était vrai tant qu'on
lisait un ordre isolé. Deux contraintes extérieures le rendent lisible : le **côté** (une
entrée ouvre la position, une protection la ferme) et la **fenêtre** (une protection vit
entre sa position et la suivante sur le même contrat). Le premier `Stop` du côté de
fermeture est le SL initial. Validé trois fois — voir `JOURNAL.md` au 28/08.

⚠️ **Ce qui reste supposé : la clé d'appariement avec Edgewonk.** Elle est reprise telle
quelle de cTrader (instrument, sens, minute d'entrée, minute de sortie, en UTC). Les trois
faits sur lesquels elle repose n'ont été vérifiés que sur l'importateur cTrader — le nom
d'instrument surtout : `MNQU6` ou `MNQ` ? `archives/mesures/diag_edgewonk_tradovate.py` le mesure
avant qu'une ligne ne soit écrite. Le §6 du README rappelle ce qu'a coûté une
généralisation non revérifiée, et c'était déjà entre ces deux plateformes-là.
