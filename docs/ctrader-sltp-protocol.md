# cTrader — Où vivent les SL/TP : documentation de référence

Objectif : alimenter automatiquement le journal Edgewonk depuis les données cTrader.
*(Formulation initiale — « via l'Open API, sans jamais ouvrir l'interface » — corrigée le
25/08/2026 : la voie retenue est le **serveur MCP local** du client desktop, et le SL/TP
initial est saisi à la main.)*

État : **les inconnues structurantes sont levées.**

---

> ## ⚠️ À LIRE EN PREMIER — ce document a été fortement révisé le 25/08/2026
>
> Il contient des couches successives. **En cas de contradiction, la mention datée la plus
> récente l'emporte.** Les quatre sections qui portent l'état actuel du projet :
>
> | Section | Ce qu'elle établit |
> |---|---|
> | **§2** | `Applied` n'est **pas** le niveau initial — les champs d'ordre sont inutilisables |
> | **§3 ter** | **DÉCISION** : le SL/TP initial est saisi à la main, tout le reste est automatique |
> | **§7 bis** | Ce que le **MCP local** fournit réellement — mesuré, 76 outils listés |
> | **§5** | Les règles **R1 à R7**, inchangées, qui restent la référence du calcul |
>
> Les §3 bis (log fichier) et §7 (Open API) décrivent des pistes **écartées**. Elles sont
> conservées pour ne pas les rouvrir par ignorance, pas parce qu'elles sont actives.

---

## 1. Les trois objets et leurs identifiants

| Bouton | Libellé | ID | Contenu SL/TP |
|---|---|---|---|
| Closing / Closed by | *deals that this deal closes* | `DID` | aucun |
| Requesting order | *order that created this deal* | `OID` | Submitted + Applied |
| Affected position | *position that was affected by this deal* | `PID` | Current + **historique d'amendements** |

Sens de la relation `DID` :

- Deal **Opening** → `Closed by` rempli, `Closing` vide
- Deal **Closing** → `Closing` rempli (liste les deals clôturés), `Closed by` vide

Un deal de clôture peut lister plusieurs deals d'ouverture : offset FIFO d'une
position ouverte en plusieurs fills.

---

## 2. RÉSOLU — sémantique des trois termes

Tooltips cTrader :

| Terme | Tooltip | Nature | Champ API |
|---|---|---|---|
| **Submitted** | *« Submitted stop loss in pips relative to opening price of position »* | pips relatifs | `ProtoOAOrder.relativeStopLoss` |
| **Applied** | *« Absolute applied rate of stop loss »* | prix absolu | `ProtoOAOrder.stopLoss` |
| **Current** | *« Current rate of stop loss »* | état vivant | `ProtoOAPosition.stopLoss` |

**Ce ne sont pas trois moments dans le temps — ce sont deux encodages de la même
instruction, plus un état courant.**

---

### ⚠️ CORRECTION MAJEURE — 25/08/2026 : `Applied` n'est PAS le niveau initial

La phrase qui figurait ici — « au drawing tool → **Applied** ; en distance/pips →
**Submitted** » — **est fausse**. Série de tests réels de l'utilisateur, sur compte démo **et**
sur le compte prop (US500 et XAUUSD, lot minimum) :

| Cas testé | `Submitted` | `Applied` | `Current` | Historique d'amendements |
|---|---|---|---|---|
| Entrée **Market nue**, SL et TP posés **après** l'entrée | vide | **REMPLI** | — | ✅ |
| Idem, puis SL **ajusté plusieurs fois** | vide | **REMPLI — dernière valeur** | — | ✅ |
| Entrée **Position Tool** (SL/TP posés à l'entrée) | **vide** | **VIDE** | **vide** | ✅ |
| Idem, puis SL ou TP déplacé, **même de 0.0001** | vide | **REMPLI** | — | ✅ |

Deux renversements par rapport à ce qui était écrit :

1. **Une protection posée APRÈS l'entrée remplit bien `Applied`.** On croyait l'inverse.
2. **`Applied` conserve la DERNIÈRE valeur, pas la première.** Exactement comme l'export
   Tradovate (`docs/tradovate.md` §6). Sur un stop ajusté cinq fois, `Applied` porte le stop
   trailé — donc **le risque initial n'y est pas**.

Et le cas le plus contre-intuitif : **entrer avec le Position Tool ne remplit aucun
champ, nulle part.** Ni `Submitted`, ni `Applied`, ni `Current`, ni côté ordre de
clôture. La protection existe — elle est bien active, elle protège la position — mais
elle n'est **inscrite que dans l'historique d'amendements**. Il suffit ensuite de la
déplacer d'un pipette pour que `Applied` se remplisse d'un coup.

### Conséquence — les champs d'ordre sont déclassés

`Applied` cumule les deux défauts possibles : **absent** quand l'entrée passe par le
Position Tool, et **faux** (valeur finale) dès qu'il y a du management. Il n'est donc
utilisable **ni comme source, ni comme contrôle croisé**.

→ **L'historique d'amendements de la position devient la source unique du SL et du TP
initiaux.** C'est le seul objet présent et complet dans les quatre cas testés.

Ce n'est pas une dégradation : ça **simplifie** le pipeline. Une seule source, les règles
R1 à R3 appliquées dessus, plus aucune réconciliation entre deux objets qui se
contredisent.

⚠️ **Ça déplace aussi le chemin critique du projet.** Lire l'historique d'amendements par
programme n'est plus un confort, c'est **la condition d'existence du pipeline**. Voir
§3 bis (log desktop) et §7 bis (MCP local).

### Modèle refermé — testé sur `Market` ET sur `Limit`

Le test décisif a été fait : un `Limit` avec SL/TP attachés, laissé se remplir, puis SL
déplacé. **`Applied` porte la valeur finale, exactement comme sur un `Market`.**
Le type d'ordre n'entre pas dans le mécanisme.

**Règle unique, valable partout :**

> `Applied` = **état de la protection après le dernier amendement explicite**.
> Écrit par n'importe quel amendement, quel que soit le type d'ordre.
> **Jamais initialisé par une entrée au Position Tool.**

*Le relevé XAUUSD du §3 laissait penser que `Applied` valait la première valeur. C'était
une lecture erronée d'un panneau consulté en direct, pas un comportement différent. Les
tests du 25/08 sont délibérés et reproductibles ; ils l'emportent.*

### Conséquence pour l'Open API — sévère

Le §2 établit que `Applied` ↔ `ProtoOAOrder.stopLoss` et `Submitted` ↔
`relativeStopLoss`. Si ce mapping tient, alors **l'Open API ne fournit aucun niveau
initial exploitable** :

| Cas d'entrée | Ce que l'API renverrait |
|---|---|
| Position Tool | **rien** — tous les champs vides |
| Market ou Limit, protection amendée ensuite | **la valeur finale**, pas le risque initial |
| Market ou Limit, protection posée une fois et jamais touchée | la bonne valeur — seul cas favorable |

⚠️ *Inférence forte, pas encore mesurée : elle repose sur le mapping tooltip → champ API du
§2, qui n'a pas été vérifié contre une vraie réponse de l'API. À confirmer dès l'accès obtenu.*

**Si elle se confirme, l'approbation Spotware ne résout pas le problème du SL/TP.**
Elle reste utile pour les bougies, les deals et l'appariement — mais le risque initial
vient de l'historique d'amendements, et de lui seul.

---

---

## 3. RÉSOLU — l'historique d'amendements de la position (source serveur)

> ### ⚠️ Deux objets, deux noms — ne jamais les confondre
>
> | Nom | Ce que c'est | Où il vit | Complétude |
> |---|---|---|---|
> | **Historique d'amendements de la position** | la chronologie du panneau *Position Info* | **côté serveur** | ✅ complet, quel que soit l'appareil utilisé |
> | **Log fichier du client** (`JournalAAAAMM.txt`) | ce que le client desktop écrit sur disque | **local au Mac** | ⚠️ partiel — voir §3 bis |
>
> **Le premier est la SOURCE. Le second n'est qu'un TRANSPORT possible, et un transport
> qui perd de la donnée.** Les deux ont longtemps porté le nom de « journal » dans ce
> document — d'où une confusion levée le 25/08/2026.

**C'est la trouvaille centrale.** Le panneau de la **position** (`PID`) contient
une chronologie horodatée à la milliseconde, incluant des événements
**`Modify protection, New SL: x, New TP: y`**.

L'historique complet du management du stop existe et est enregistré.

### Exemple relevé — PID284805395, XAUUSD, 24/08/2026

| Δ | Événement |
|---|---|
| | `Limit OID315432025` — 22:25:00.226 — ↑ 3.48 lots |
| 8s149 | `Opening Deal DID330462118` — 22:25:08.375 — 1.00 lot |
| 298ms | `Opening Deal DID330462123` — 22:25:08.673 — 2.48 lots |
| 0ms | `Position PID284805395` créée — ↑ 3.48 lots |
| | `Modify protection` — New SL **4649.92**, New TP **4651.05** |
| 296ms | `Modify protection` — New SL **4649.92**, New TP **4651.05** |
| 3s137 | `Modify protection` — New SL **4649.31**, New TP 4651.05 |
| 4s761 | `Market OID315432069` — 22:25:16.581 — ↓ 3.48 lots |
| 257ms | `Closing Deal DID330462145` — 22:25:16.838 — 3.48 lots |

### CONFIRMÉ le 25/08/2026 — l'historique d'amendements est **côté serveur**

Position `PID284853317` (XAUUSD, 25/08/2026) : **ouverte et gérée depuis le téléphone**,
puis consultée sur le Mac. Le panneau affiche l'historique **complet** des amendements.

| Δ | Événement |
|---|---|
| | `Market OID315505899` — 11:29:30.344 — ↓ 0.02 lot |
| 286ms | `Opening Deal DID330553084` — 11:29:30.630 — 0.02 lot @ **4626** |
| 0ms | `Position PID284853317` créée — XAUUSD ↓ 0.02 |
| **22s651** | `Modify protection` — New SL **4653.54** |
| 963ms | `Modify protection` — New SL 4653.54, New TP **4597.65** |
| 15m28s | `Market OID315508007` — 11:45:22.448 — ↑ 0.02 lot |
| 290ms | `Closing Deal DID330557407` — 11:45:22.738 — @ **4639.1** |

**Conséquence majeure : la chronologie n'est pas produite par le client, elle est
récupérée du serveur.** Le device qui a passé le trade n'a aucune importance. Le
« trou téléphone » n'existe donc pas au niveau de la donnée — il ne peut exister
qu'au niveau du **transport** choisi pour la lire.

Corollaire : **un endpoint serveur renvoie cette chronologie**, puisque le client
desktop sait l'afficher a posteriori pour une position qu'il n'a jamais vue naître.
C'est l'argument le plus fort en faveur du MCP local (§7 bis).

### Ce cas illustre exactement les règles R1 et R2

**SL posé 22,7 s APRÈS l'entrée**, TP encore 1 s plus tard. C'est le cas dit
« difficile », et il se résout sans ambiguïté :

- R1 — deux chronologies indépendantes : le SL apparaît à l'événement 1, le TP à
  l'événement 2. Les coupler aurait produit un TP fantôme ou un SL retardé.
- R2 — première valeur non nulle : SL = **4653.54**, TP = **4597.65**. Aucun seuil
  n'intervient, le passage de « rien » à « quelque chose » n'est jamais ambigu.
- Risque = 27.54 · objectif = 28.35 · **R:R ≈ 1.03** · sortie 4639.1 → **−0.48 R**.

⚠️ **Le dédoublonnage se fait champ par champ, jamais événement par événement.** Les
deux `Modify protection` portent le **même SL** : au niveau de l'événement, le second
ressemble à un doublon. Il ne l'est pas — il introduit le TP. Ne dédoublonner que si
SL **et** TP sont inchangés.

### Règles de lecture déduites

**La protection est ré-appliquée à chaque fill.** Les deux premiers événements
sont identiques et espacés de 296 ms, ce qui correspond aux 298 ms entre les
deux fills. → **dédoublonner les événements consécutifs de même SL et même TP**
avant toute interprétation, sinon un trade en trois fills ressemble à trois
décisions de management.

**Le premier événement de protection = le risque initial.** Ici 4649.92.

⚠️ *Il était écrit ici que cette valeur « coïncide avec l'`Applied SL` de l'ordre
d'entrée » et que « deux sources indépendantes concordent — bon signal d'intégrité ».
**Retiré le 25/08/2026** : les tests du §2 montrent que `Applied` n'est ni fiable ni
indépendant. La concordance observée sur ce cas précis tient probablement au fait que
l'entrée était un `Limit` — voir la contradiction non résolue au §2.*

**Les événements suivants = le management réel**, horodatés. Ici : SL déplacé de
4649.92 à 4649.31 sur une position longue, soit un **stop élargi**.

**L'ordre d'entrée était un Limit**, créé 8 s avant le premier fill. La capture
« Order info » montrant `Total deals 0` était donc ce même ordre, saisi avant
déclenchement — l'anomalie signalée précédemment est levée.

---

## 3 bis. Le fichier de log du client desktop — un TRANSPORT local, partiel

Découvert le 25/08/2026 en analysant `Journal202608.txt`, le fichier de log du client
cTrader pour macOS. **Il contient exactement l'historique d'amendements que l'Open API
n'expose pas** — en texte brut, sans authentification, sans approbation à attendre.

### Ce qui a été mesuré

918 lignes, du 03/08 au 24/08/2026, 18 journées distinctes.

| Motif | Occurrences | Ce que ça donne |
|---|---|---|
| `Request to amend position PID# (SL: x)` ACCEPTED | 124 | chaque déplacement de stop, horodaté |
| `Request to amend position PID# (TP: x)` ACCEPTED | 88 | idem pour la cible |
| `Request to amend position PID# (remove SL)` | 1 | suppression de protection |
| `Request to amend order OID# (Price/SL/TP)` | 48 | modification d'un ordre **en attente** |
| `Order OID# is FILLED at N, position PID#` | 50 | fill d'entrée, avec le lien OID → PID |
| fills de clôture | 45 | |
| clôtures partielles | 13 | |
| rejets | 9 | à filtrer, ne jamais compter comme événement |

Deux bénéfices annexes :

- **Les événements serveur portent l'heure locale ET l'heure UTC sur la même ligne.** La
  question du fuseau se règle à la source, sans hypothèse à poser.
- **Le lien `OID → PID` figure dans les lignes de fill**, donc le chaînage
  ordre → position s'obtient sans l'API.

### Le trou — et pourquoi il n'est pas gênant

**Sur 84 lignes de création d'ordre, aucune ne mentionne de SL ni de TP.** Le log ne
porte donc **pas** les niveaux attachés au moment de la soumission.

Or c'est exactement ce que l'API donne (`ProtoOAOrder.stopLoss` / `relativeStopLoss`).

→ **Les deux sources sont complémentaires, pas redondantes :**

| | niveaux posés à l'entrée | amendements ultérieurs |
|---|---|---|
| Open API | ⚠️ **voir §2** — rien au Position Tool, valeur finale sinon | ❓ à tester (§7) |
| Log fichier local | ❌ (pas de niveaux à la soumission) | ✅ |

⚠️ **Révisé le 25/08/2026 (soir).** La complémentarité annoncée plus haut ne tient plus
telle quelle : les tests du §2 montrent que l'API ne porte pas non plus le niveau
**initial**. L'historique d'amendements reste la seule source qui le contienne, dans tous
les cas.

Et le cas qui posait problème — **stop posé quelques minutes après l'entrée** — est
couvert par le log seul : le stop y apparaît alors comme un `amend position`.

### Quatre limites, à connaître avant de s'appuyer dessus

1. **Ne capte QUE les trades gérés depuis ce Mac. PROUVÉ le 25/08/2026.**

   Emplacement : `~/cTrader/Journals/<broker>/Journal-AAAA-MM.txt`.
   *(Nommage réel : `Journal-2026-08.txt`, avec tirets.)*

   Expérience naturelle — deux trades du même jour, à cinq minutes d'intervalle, dans le
   même fichier, Mac allumé et journalisant sans interruption :

   ```
   # PID284852977 — passé depuis le MAC
   09:24:19.456 | Request to Sell 1.00 Lots XAUUSD is sent to server
   09:24:19.504 | → ... is ACCEPTED, order OID315505337 created
   09:24:19.792 | → Order OID315505337 is FILLED at 4630.82, position PID284852977
   09:24:24.447 | Request to amend position PID284852977 (SL: 4632.86) is sent to server
   09:24:24.484 | → Request to amend position PID284852977 (SL: 4632.86) is ACCEPTED
   09:24:31.372 | Request to close position PID284852977 is sent to server
   09:24:31.620 | → Order OID315505348 is FILLED at 4631.27, position ... closed

   # PID284853317 — passé et géré depuis le TÉLÉPHONE
   09:45:22.736 | → Order OID315508007 is FILLED at 4639.17, position PID284853317 closed
   ```

   **Une seule ligne pour le trade mobile : le fill de clôture.** Ni ouverture, ni aucun
   des deux `Modify protection` que le panneau *Position Info* affiche pourtant (§3).

   **Modèle : le log enregistre les requêtes émises PAR CE CLIENT, plus les fills de
   clôture reçus.** Un amendement fait ailleurs n'est ni l'un ni l'autre.
   → **Limite structurelle, pas un problème de disponibilité.** Garder le Mac allumé n'y
   changera rien.
2. **Aucun identifiant de compte dans le log — confirmé.** Recherche de `account`,
   `login`, `connect`, `switch` sur le fichier d'août : **zéro occurrence**. Le seul
   indice d'appartenance est le **dossier broker** du chemin. Or un seul existe :
   `Spotware`. ⬜ **Où sont les journaux du compte Prop Firm A ?** À élucider avant de
   compter sur le log pour le compte prop.

2 bis. **Profondeur d'historique — l'atout du log.** Fichiers d'**avril 2025 à ce jour**,
   ~1 000 amendements de position cumulés (pic : 237 en août 2026, 224 en novembre 2025).
   C'est le **seul** actif du projet qui contienne du passé.
3. **Pas de niveaux à la soumission** (ci-dessus).
4. **C'est un log client, non contractuel** : format susceptible de changer, et rotation
   apparente au mois (`Journal202608` = août 2026). Archiver les fichiers au fil de l'eau
   plutôt que de supposer qu'ils restent disponibles.

### Statut

**Ce n'est pas une source, c'est un TRANSPORT — et le moins bon des trois.**
La source est l'historique d'amendements côté serveur (§3). Ce fichier n'en est qu'une
copie partielle, écrite par le client quand il tournait. Si l'API rend l'historique interrogeable
(§7), le log ne sert plus qu'au contrôle croisé — deux sources indépendantes qui
concordent, c'est le meilleur contrôle d'intégrité disponible ici. Si elle ne le rend
pas, le log **devient** le transport du management, lu automatiquement à chaque
exécution du pipeline, sans dépendre d'aucune approbation.

⬜ **À récupérer : le chemin exact du dossier de logs sur le Mac.**

---

## 3 ter. DÉCISION — la saisie du SL/TP reste manuelle, tout le reste est automatique

**Tranché par l'utilisateur le 25/08/2026.** Après avoir mesuré les trois transports possibles
(API, log fichier, collecteur), le constat est qu'aucun n'est à la fois complet, fiable et
léger. La décision est de **ne pas automatiser la lecture du SL/TP initial**.

### Le raisonnement

Trois valeurs par trade — `positionId`, SL, TP — sont **directement copiables** depuis le
panneau *Position Info*, quel que soit le mode d'entrée (Position Tool, Market, Limit) et
quel que soit l'appareil ayant passé l'ordre. La donnée est côté serveur, donc toujours
présente et consultable après coup.

Le coût réel : ~60 trades par semaine, trois valeurs chacun. Quelques minutes, contre
**une journée entière** aujourd'hui. Le gain d'automatisation marginal ne justifie pas :

- un **collecteur** en tâche de fond, avec son cadencement, ses pannes silencieuses et son
  risque de rater les positions de 10 à 40 secondes ;
- une dépendance au **log fichier**, structurellement aveugle aux trades mobiles (§3 bis) ;
- l'attente de l'**approbation Spotware**, qui de toute façon ne résout pas le sujet (§2).

**Ce que la décision achète : fiabilité, résilience, vérifiabilité, contrôle.** Aucune
pièce mobile entre la donnée affichée et la donnée journalisée.

### Ce qui reste automatique — c'est-à-dire tout le reste

MAE/MFE, TP-first, R-multiples, stratégies alternatives, graphiques M5/M15/H1/H4, appariement,
écriture Edgewonk et upload d'images. Mesuré et validé (§7 bis et `docs/edgewonk-api.md`).

### LA RÈGLE DE SAISIE — le SL et le TP **INITIAUX**, jamais la valeur affichée

*(Tranché par l'utilisateur le 25/08/2026. C'était le seul angle mort du §3 ter.)*

**L'utilisateur saisit le stop et la cible qu'il avait posés en entrant. Un stop déplacé
ensuite ne se saisit pas.** La valeur que montre *Position Info* après un déplacement est
la valeur **finale** — la même infirmité qui a disqualifié l'API au §2. Le §3 ter avait
transféré le problème à l'humain sans le nommer ; c'est nommé.

**Pourquoi ça compte :** R se calcule sur le risque initial. Saisir un stop remonté réduit
le risque affiché, donc **gonfle R**, le win rate, l'expectancy, et fait basculer des
trades sous le seuil break-even. Et **aucun contrôle ne peut le rattraper** : un stop
remonté est du bon côté de l'entrée et donne un R:R plausible, donc il passe les quatre
garde-fous ci-dessous. C'est la seule erreur de ce pipeline qui soit silencieuse par
construction — d'où la règle, écrite plutôt que supposée.

**Le management réel n'est pas perdu pour autant** : la sortie effective est dans le
relevé, et les extrêmes, le TP-first et les paliers alternatifs sont calculés sur les
bougies. Le déplacement de stop se lit dans l'écart entre le plan et la sortie, pas dans
le champ SL.

### Format de saisie et garde-fous

*Mis à jour le 26/08/2026 : le format réel diffère de celui esquissé ici à l'origine.*

Le fichier est **généré depuis le relevé**, une ligne par **POSITION** (une position n'a
qu'une protection, quel que soit le nombre de sorties partielles). La clé d'appariement est
la colonne `cle_position`, et **elle seule** : les autres colonnes sont décoratives, un
tableur peut les reformater sans conséquence.

```
cle_position,date,heure,symbole,sens,entree,lots,jambes,net,sl,tp,management
20260807-134318-EURUSD-A,07/08/2026,13:43:18,EURUSD.raw,Achat,1.15314,6.00,4,317.00,1.15242,1.15470,KO
```

**Trois colonnes à remplir.** `sl` et `tp` sont les niveaux **initiaux** (voir la règle
ci-dessus). `management` répond à « ai-je touché à mon stop ou à ma cible après
l'entrée ? » — `OK` = non, le plan a été tenu ; `KO` = oui, la position a été gérée.

Le pipeline ne fait **jamais confiance** à cette saisie. Deux niveaux, et la différence
compte : un **rejet** bloque l'intégration, un **signalement** passe après validation
humaine.

| # | Contrôle | Niveau |
|---|---|---|
| 1 | **Clé** inconnue, ou présente deux fois dans le fichier | rejet |
| 2 | **Sens** — SL du mauvais côté de l'entrée (au-dessus pour un achat, en dessous pour une vente), ou niveau égal à l'entrée. Idem TP en miroir | rejet |
| 3 | **`management` vide ou illisible** | **rejet** |
| 4 | **Exhaustivité** — un trade de la période sans ligne de saisie | signalement |
| 5 | **Complétude** — ni SL ni TP, ou l'un sans l'autre | signalement |
| 6 | **Plausibilité du R:R** — hors de la bande 0,3–10 | signalement |
| 7 | **Plausibilité du R réalisé** — \|R\| au-delà de 10 | signalement |

**Pourquoi le management est un rejet et pas un signalement** *(arbitré par l'utilisateur le
26/08/2026)*. C'est le seul contrôle du lot qu'aucune mesure ne peut rattraper après coup.
Un stop aberrant se trahit par un R disproportionné ; « ai-je bougé mon stop ? » ne se
retrouve nulle part, ni dans le relevé, ni dans les bougies, ni chez Edgewonk. Un oubli y
serait définitif, donc il bloque. Le champ mesure d'ailleurs une **discipline**, pas une
technique — l'objectif déclaré de l'utilisateur est que ce soit `OK` partout — raison de plus
pour le saisir quand le trade est frais.

**Pourquoi le contrôle 7 existe, et pourquoi il ne dépend pas du TP** *(ajouté le
26/08/2026)*. Le NAS100 du 14/08 portait un SL à 0,45 point sur un indice qui bouge de
centaines de points. Le contrôle 6 l'avait bien signalé — « R:R de 430,7 » — mais l'alerte
a été résolue **en retirant le TP** : plus de TP, plus de R:R, plus d'alerte, et le stop
aberrant est resté. Il a produit **+180 R à lui seul** et faussé le journal pendant deux
jours. Le contrôle 7 n'a besoin d'aucun TP : l'entrée et la sortie viennent du relevé, le
SL de la saisie. Signalement et pas rejet — un 12 R existe — mais il ne se tait plus.

*Le contrôle croisé par le log du client desktop, envisagé ici à l'origine, est sans objet :
le log a été écarté (§3 bis), il ne capte que les trades gérés depuis ce Mac.*

### Conséquences sur le reste du projet

- Le **collecteur** est abandonné. Ne pas le rouvrir sans raison nouvelle.
- Le **log fichier** est rétrogradé de transport à **vérificateur**.
- L'**approbation Spotware** sort du chemin critique. Le MCP local couvre les bougies.
- **Le pipeline est écrivable dès maintenant.** Plus aucune dépendance externe.

---

## 4. Conséquences pour le journal

**R = premier événement `Modify protection`.** Sans contrôle croisé : `Applied` a été
déclassé le 25/08/2026 (§2), il est vide sur les entrées au Position Tool et porte la
dernière valeur en cas de management.

**`Current` est inexploitable.** Après clôture, Current SL/TP sont vides : la
protection est effacée à la fermeture, et un journal se remplit toujours après
coup.

**Un trade journalisé = un `PID`, jamais un `DID`.** Prix d'entrée = VWAP de la
position (`ProtoOAPosition.price`), pas le prix d'un fill. Calculer le R sur un
seul fill fausserait la donnée sans que ça se voie.

**L'historique d'amendements sert à une chose, mais dans TOUS les cas : retrouver le SL et
le TP initiaux.** *(Formulation antérieure — « quand ils n'ont pas été posés à l'entrée »
— corrigée le 25/08/2026 : c'est désormais la source unique, y compris quand ils ont
bien été posés à l'entrée.)* Aucun champ Edgewonk ne
demande l'historique du management — l'exit price encapsule déjà son résultat.
Le reste de la chronologie est ignoré.

---

## 5. Règles de reconstruction du SL/TP initial — FIGÉES

Constantes ajustables, à isoler en tête de script.

Objectif unique : renseigner correctement les champs **SL** et **TP** d'Edgewonk.
Rien d'autre.

```
R_BREAK_EVEN      = 0.30   # |résultat| en dessous → coché break-even
                           # au-dessus → DÉCOCHÉ : le robot fait autorité
                           # (réglé le 25/08/2026 : 0.20 -> 0.30 -> 0.15 -> 0.30)
R_PRICE_MOVED     = 0.50   # progression au-delà de laquelle un changement est ignoré
```

### R1 — SL et TP sont deux chronologies indépendantes

Ne jamais les coupler. Le cas courant est un SL posé à l'entrée et un TP ajouté
quelques minutes plus tard.

### R2 — La première valeur gagne

Pour chaque champ séparément, le niveau **initial** est la première valeur non
nulle jamais observée, qu'elle vienne de l'`Applied` de l'ordre d'entrée ou du
premier `Modify protection` qui l'introduit.

Passer de « rien » à « quelque chose » n'est jamais ambigu : aucun seuil requis.
**C'est ce qui lève la circularité** — R est défini par R2, sans recours à un
seuil en R ; les seuils ne servent qu'à classer les changements *suivants*.

### R3 — Un seul critère de coupe

Progression du prix en faveur du trade, mesurée en R (R issu de R2), au moment
du changement :

- **< `R_PRICE_MOVED`** → correction d'entrée : la nouvelle valeur **remplace**
  le niveau initial
- **≥ `R_PRICE_MOVED`** → management (trail, break-even, ajustement de cible) :
  le changement est **ignoré**, le niveau initial est conservé

Le sens du déplacement n'entre pas dans la règle : un critère unique est plus
robuste et suffit à couper au bon endroit.

Pourquoi 0.50 et pas plus haut — asymétrie des erreurs. Classer une correction
en management est bénin : R garde une valeur légèrement grossière. Classer du
management en correction **écrase le SL initial et fausse R silencieusement**,
donc R-multiples et stratégies alternatives. Le danger vient d'un seuil trop
haut. Sous 0.50, un trade serré dérive tout seul sans qu'aucune décision n'ait
été prise ; au-delà, on commence à manger de vrais trails.

### R4 — Convergence en deux passes

Si le niveau initial est remplacé par R3, recalculer R avec la valeur retenue et
reclasser. Les deux valeurs étant proches par construction, ça converge
immédiatement.

### R5 — Cas à faible confiance *(à mesurer avant de construire quoi que ce soit)*

**Correction d'une formulation antérieure :** les règles R2 et R3 tranchent *toujours*.
Parler de cas « indécidable » était imprécis.

- SL posé à l'entrée → décidé, aucun doute.
- SL absent à l'entrée puis posé plus tard → R2 tranche : passer de « rien » à
  « quelque chose » n'est jamais ambigu.
- **Seul cas fragile : un SL déjà posé, puis REMPLACÉ avant le seuil `R_PRICE_MOVED`.**
  R3 le classe en correction et écrase la valeur — mais ç'aurait pu être un
  resserrement précoce, donc du management.

**L'enjeu réel est faible par construction :** une correction est un petit ajustement,
donc les deux valeurs sont proches et l'erreur sur R est mineure. Elle ne compte que si
le remplacement change R de façon matérielle.

**Le TP est encore moins sensible** : il n'entre pas dans le calcul de R. Une erreur n'y
affecte que `originalTpHit` et le RRR planifié, jamais l'expectancy.

**Décision : ne rien construire pour l'instant.** Le script comptera simplement ces cas
(remplacement sous le seuil, et écart relatif de R induit). Après deux ou trois semaines
de données réelles, on saura si le volume est nul ou significatif — et seulement alors on
choisira entre ne rien faire, `inReview`, ou un custom tag dédié dans Edgewonk.

*Rationnel : ne pas bâtir de mécanisme pour un problème dont l'existence n'est pas
démontrée.*

### R6 — Break-even

`R_BREAK_EVEN = 0.30` *(réglé le 25/08/2026 : 0.20 → 0.30 → 0.15 → 0.30)*, en **R et pas
en dollars** : deux comptes de tailles différentes rendraient un seuil en devise
incomparable entre eux. Règle de l'utilisateur : **« tout au-dessus de 0,3 R c'est un trade,
point barre. »**

**Seuil seul, pas de règle structurelle.** Arbitré le 25/08 : les jambes d'allègement
d'une position multiple ne sont PAS écartées d'office. Celles qui dépassent 0,3 R comptent
comme des trades à part entière — mesuré, deux d'entre elles sont à −0,43 et −0,49 R sur
la position du 07/08 18:50. C'est assumé.

✅ **Implémenté le 25/08/2026 au soir** dans `edgewonk/ecriture.py` (`est_break_even`),
écrit par `PUT` — `modify` ignore ce champ.

**LE ROBOT FAIT AUTORITÉ, DANS LES DEUX SENS** *(révisé le 25/08 en fin de soirée, renverse
le « on ne décoche jamais » de la première version)*. Le seuil tranche seul : l'automation
coche et décoche, par-dessus une case manuelle s'il le faut.

**Le garde-fou est le R, pas le sens de l'écriture.** Sans SL il n'y a pas de R (règle R7),
`est_break_even` renvoie `None` et **rien n'est écrit dans aucun sens**. Les jambes non
traitées conservent donc ce que l'utilisateur y a mis à la main ; c'est la saisie du SL qui
transfère l'autorité au robot. Tout décochage est signalé, jamais silencieux.

### R7 — Absence de risque initial

Si aucun SL n'apparaît jamais, le trade est marqué **« pas de risque initial »**.
Ne jamais fabriquer un stop de substitution.

*(Cas déclaré rare : il y a toujours un stop posé dans les 5–10 min.)*

---

## 5 bis. TP first / SL first

Edgewonk pose la question parce qu'il **n'a pas les données de prix** — il ne
voit que les lignes de trade et ne peut pas savoir quel niveau le prix a touché
en premier. D'où son infobulle *« ignore how you exited »*.

Avec les ticks broker, ce champ se calcule : rejouer le chemin de prix entre
l'entrée et la sortie, et voir lequel du SL ou du TP **initial** est atteint en
premier. Champ entièrement automatisable, et hors de portée d'Edgewonk seul.

---

## 6. Cadre prop firm

Prop Firm A encadre l'**exécution** : EA soumis à approbation, HFT, latency
et arbitrage interdits, copy trading restreint (interdit sur cTrader). Aucune
mention de l'accès API en lecture ni de l'export de son propre historique.

Lecture seule de ses propres données via une interface officielle : hors du
champ des restrictions. Un ticket support écrit lève tout doute résiduel.
Le vrai risque est technique — que l'OAuth soit fermé sur un compte prop.

---

## 7. Historique des amendements via l'API — CADUC, conservé pour mémoire

L'historique d'amendements est visible dans l'interface. **Reste à établir s'il est
interrogeable via l'Open API ou seulement rendu par le client.** La doc publique
ne décrit aucun message dédié à l'historique des amendements de position.

**Fait vérifié le 25/08/2026 contre la liste officielle des messages Open API :
aucun message ne retourne l'historique des modifications de SL/TP.** La catégorie
« historique » ne contient que `ProtoOACashFlowHistoryListReq` (dépôts/retraits).
`ProtoOAAmendPositionSLTPReq` existe, mais c'est le message qui **effectue** une
modification — côté écriture, hors de notre permission.

Il reste donc à tester si l'historique est **reconstructible indirectement**. Trois essais
dès l'accès API obtenu, dans cet ordre :

1. **`ProtoOAOrderListByPositionIdReq`** — le seul message qui prend un `PID` en entrée.
   S'il retourne les ordres de protection successifs, l'historique est reconstructible
   par requête. C'est le test à faire en premier.
2. **`ProtoOAOrderDetailsReq`** — détail d'un ordre précis, plus riche que la liste.
3. **`ProtoOAOrderListReq`** — hypothèse : dans cTrader, la protection d'une position est
   portée par un ordre de type `STOP_LOSS_TAKE_PROFIT`. Si c'est le cas, ce message les
   retourne et l'historique se reconstruit par filtrage.
   ⚠️ **Signal négatif** : dans le fil communautaire #38747 (août 2022), un ordre de
   clôture bien typé `STOP_LOSS_TAKE_PROFIT` renvoyait `HasStopLoss` et `HasTakeProfit`
   à **faux**, côté `Order` comme côté `Position`. Le staff Spotware n'a pas eu de
   réponse et le fil s'est terminé sans solution. Un événement d'exécution en direct
   n'est pas une liste d'ordres historiques, donc ça ne tranche pas — mais ça abaisse
   nettement l'espérance.

**Les deux sont tombés le 25/08/2026 au soir, mais la question n'a plus d'enjeu.**
Le §2 montre que même en cas de succès, l'API n'aurait renvoyé **ni** le niveau initial sur
une entrée au Position Tool (champs vides) **ni** ailleurs autre chose que la valeur
finale. La décision du §3 ter — saisie manuelle — rend cette section **caduque**.

*Conservée pour mémoire : un collecteur temps réel écoutant `ProtoOAExecutionEvent` avait
été envisagé puis **abandonné** (voir §3 ter). Ne pas le rouvrir sans raison nouvelle.*

---

## 7 bis. cTrader AI Agent Connect (MCP local) — MESURÉ le 25/08/2026

Spotware a publié des serveurs **MCP officiels** pour cTrader. Le **MCP local** tourne
dans le client desktop sur `http://127.0.0.1:9876/mcp/` et s'authentifie **avec la
session cTrader déjà ouverte** : ni application à faire approuver, ni OAuth, ni
correspondance de cTrader ID. Le compte de la prop firm est celui qui est connecté.

La documentation officielle annonce, côté *Analysis* du MCP **local** uniquement :
*« fetch live prices, historical candles and news; review trade history, portfolio
exposure and risk »*. Le tableau comparatif marque **Trade History ✅ local / ❌ distant**.

La référence REST associée documente notamment :

| Endpoint | Intérêt pour le projet |
|---|---|
| `GET /v1/positions/{positionId}` | position **+ ordres + deals** associés |
| `GET /v1/orders/history` | historique des ordres sur une plage |
| `GET /v1/deals` | exécutions avec `positionId`, `orderId`, prix, horodatage |
| `GET /v1/trendbars` | **OHLCV historique** → les bougies des graphiques |

**Pourquoi cette piste est sérieuse :** le §3 établit que le client desktop sait afficher
la chronologie d'amendements d'une position qu'il n'a pas vue naître. Il la lit donc
depuis le serveur. Le MCP local pilote ce même client.

**Trois réserves, à lever par la mesure :**

1. `/v1/positions` est décrit comme « positions **ouvertes** ». Rien ne garantit que
   `/v1/positions/{id}` réponde sur une position **clôturée** — précisément notre cas.
2. Cette référence REST couvre peut-être la surface **commune** aux deux MCP. Le local
   en expose vraisemblablement davantage, dont l'historique.
3. Aucun endpoint de **ticks**. Sans conséquence : rien en dessous du M5, les extrêmes se
   calculent sur les bougies.

⚠️ **Point prop firm — non négociable.** Ce MCP sait `POST /v1/orders` et clôturer des
positions. Un agent IA capable de passer des ordres sur un compte financé tombe
exactement sous les règles Prop Firm A relatives aux EA. Dans *Paramètres → Serveur
MCP*, « Activer le serveur MCP » et « Autoriser le trading via MCP » sont **deux cases
distinctes** : n'activer que la première. Même garantie structurelle que la permission
*Access info on your accounts* seule côté Open API.

**Mesure à faire, cTrader ouvert :**

```
curl -s http://127.0.0.1:9876/mcp/ \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

### RÉSULTAT — 76 outils exposés, verdict mitigé

Serveur actif sur le port 9876, « Allow trading via MCP » **décoché**, « Require
confirmation » coché. Configuration retenue : lecture seule de fait.

**✅ Ce que le MCP couvre, sans aucune approbation Spotware :**

| Outil | Usage dans le pipeline |
|---|---|
| `get_trendbars` | **les bougies des graphiques** — débloque le cadrage (§ gabarit) |
| `get_deals` | exécutions sur une plage → entrées, sorties, VWAP |
| `get_order_history` | historique des ordres sur une plage |
| `get_positions` | positions (probablement **ouvertes** seulement — à confirmer) |
| `get_symbols`, `get_symbol_details` | digits, tick size, métadonnées |
| `get_server_time` | ancrage de fuseau, sans hypothèse |
| `get_accounts_list`, `get_balance`, `get_account_statistics` | comptes et solde |

**⛔ Ce qu'il ne couvre PAS — et c'est précisément le point bloquant :**

**Aucun outil ne retourne l'historique d'amendements d'une position.** Pas de
`get_position_details`, pas de `get_position_events`, pas de `get_position_history`.
La chronologie que le panneau *Position Info* affiche n'est exposée par aucun des 76
outils. Les seuls outils qui touchent à la protection sont `amend_position` et
`amend_order` — **en écriture**, donc hors périmètre.

### Conséquence stratégique

**Le MCP local remplace l'Open API pour tout le pipeline — sauf pour la seule chose qui
bloque.** Bougies, deals, ordres, symboles, fuseau : tout est là, tout de suite, sans
attendre Spotware. Le risque initial, lui, reste sans transport programmatique.

→ L'approbation Spotware devient **largement redondante**. Elle reste utile comme
seconde implémentation, pas comme déblocage.
→ Le transport du risque initial retombe sur le **log fichier local** (§3 bis), avec son
trou connu sur les trades mobiles. Ce test redevient prioritaire.

### Schémas lus le 25/08/2026 — la question est tranchée, et négativement

| Outil | Paramètres | SL/TP dans la réponse ? |
|---|---|---|
| `get_trendbars` | `symbolName`, `timeframe` (m1…mn1), `from`/`to` **ISO 8601 UTC**, `limit` (défaut 500, **cap 1000**) | sans objet — **c'est notre source de bougies** ✅ |
| `get_positions` | aucun | ✅ SL/TP absolus **et** en pips — mais **positions OUVERTES seulement** |
| `get_pending_orders` | aucun | ✅ SL/TP absolus et en pips — **ordres en attente seulement** |
| `get_deals` | `symbolName`, `count` (défaut 50, **max 200**) | ❌ — et **aucun filtre temporel** |
| `get_order_history` | **aucun** | ❌ **rien** : symbole, sens, volume, prix d'entrée/sortie, pips, profit, horodatages |

**`get_order_history` ne porte aucun SL/TP.** Pas même la valeur finale. Sa description
précise en outre *« Returns trades currently loaded in the repository »* — la réponse
dépend donc de ce que l'interface a chargé, ce qui en fait une source **non
déterministe**, inutilisable telle quelle pour un pipeline.

Les seuls outils porteurs de SL/TP concernent l'état **vivant** (positions ouvertes,
ordres en attente). Or un journal se remplit toujours après coup.

### VERDICT

**Le MCP local est une excellente source de bougies et une source médiocre de trades.
Ce n'est en aucun cas une source de SL/TP.**

- ✅ `get_trendbars` **débloque le cadrage des graphiques** — vraies bougies broker,
  timeframes m1→mn1, plage ISO 8601, 1000 barres par requête à paginer.
- ⚠️ `get_deals` plafonné à 200 et sans plage temporelle → utilisable pour du récent,
  pas pour un rattrapage historique.
- ⛔ Le risque initial n'a **toujours aucun transport programmatique**. Le log fichier
  local (§3 bis) redevient la seule piste.

⚠️ **Prudence d'usage :** ne jamais appeler un outil préfixé `amend_`, `place_`, `close_`
ou `cancel_`. Ils agissent réellement. La case « Allow trading via MCP » décochée est la
protection de premier rang, pas la seule à respecter.

### Appels réels exécutés le 25/08/2026 — sur pièce

**`get_order_history`** — confirmé : **aucun champ SL/TP**. Le format retourné est
`{positionId, symbolName, side, volume, entryPrice, closePrice, pips, grossProfit,
netProfit, swap, commission, openTime, closeTime, label, comment}`, horodatages **ISO 8601
UTC**. Profondeur observée : février → août 2026, mais **lacunaire** (mois entiers
absents) — cohérent avec *« trades currently loaded in the repository »*. Utilisable comme
appoint, jamais comme référence.

*Détail utile : une même `positionId` apparaît sur plusieurs lignes quand la sortie s'est
faite en plusieurs fois (ex. `237407215`, `284858758`). Regrouper par `positionId` et
agréger au VWAP — cohérent avec la règle « un trade = un PID ».*

**`get_trendbars`** — **opérationnel, qualité production.** Retour :
`{bars:[{timestamp, open, high, low, close, volume}], truncated:bool}`, horodatages ISO
8601 UTC, drapeau `truncated` pour piloter la pagination. C'est la source de bougies du
projet.

**✅ VALIDÉ EN PRODUCTION le 25/08/2026.** L'étape 3 du pipeline tourne sur données réelles :
9 jambes calculées, 0 incohérence, extrêmes encadrant toujours l'entrée et la sortie.
Champs exacts confirmés : `bars[]` avec `timestamp` (ISO 8601 UTC, suffixe `Z`), `open`,
`high`, `low`, `close`, `volume`, plus `truncated`.

**Vérification MAE/MFE sur données réelles** — position `284853317` (SELL XAUUSD @ 4626.8,
09:29:30Z → 09:45:22Z, sortie 4639.17), bougies M5 du même appel :

| Mesure | Valeur | En R (risque 26.74) |
|---|---|---|
| Extrême favorable (plus bas) | 4624.19 | 0.10 R |
| Extrême défavorable (plus haut) | 4639.19 | −0.46 R |
| Sortie réelle | 4639.17 | −0.46 R |
| `originalTpHit` | **false** — TP 4597.65 jamais approché | |

→ **MAE/MFE, TP-first et stratégies alternatives sont calculables dès aujourd'hui.**

⚠️ **Prendre les bougies en `m1`, pas en `m5`.** La bougie de sortie 09:45 s'étend
jusqu'à 09:50 et porte un plus haut à 4640.67 postérieur à la clôture : en M5 on
importerait un extrême qui n'appartient pas au trade.

⚠️⚠️ **CORRECTION DU 25/08/2026 — passer en M1 ne suffit PAS.** Il était écrit ici qu'« en
`m1` l'erreur de bord tombe à 59 s », sous-entendu négligeable. **Elle ne l'est pas.**

Mesuré sur la jambe `20260807-134318-EURUSD-A#143001` : sortie au TP à 12:30:01Z, et la
bougie M1 de 12:30 porte un plus haut à **1.15685 — 21,5 pips au-dessus du TP, atteints
après la sortie**. C'était 8h30 à New York, une publication macro : 41 pips d'amplitude
dans la seule minute (open 1.15276, high 1.15685, close 1.15647). Le high suivant le plus
élevé de tout le trade était 1.15379, à 19 minutes de là.

→ **On exclut les bougies de bord du calcul** et on les remplace par les deux prix connus
exactement : l'entrée et la sortie. Le plus haut redevient 1.15470, c'est-à-dire le TP —
ce qui s'est réellement passé. L'erreur résiduelle est bornée et **toujours conservatrice**
(extrêmes sous-estimés, jamais surestimés), là où l'erreur inverse était non bornée,
flatteuse et invisible.

→ Le **prix de sortie tranche le TP-first** quand aucune bougie entière n'a touché de
niveau : c'est le dernier point du trade dont on soit certain.

⚠️ **CORRECTION — le cap de 1000 barres n'est PAS « largement suffisant ».** Il était écrit
que ~16 h de M1 par requête couvraient tout. La plus longue position du relevé du 25/08
dure **16 h 51, soit 1011 barres**. Le cas limite est déjà dans les données réelles :
**la pagination est obligatoire**, pas optionnelle.

### Détail relevé — un onglet `journal` existe, mais en écriture seule

`set_trade_watch_tab` accepte l'énumération `positions, orders, history, price_alerts,
transactions, **journal**`. L'onglet du journal d'exécution est donc bien connu de la
surface MCP — mais seul `get_trade_watch_tab` existe en lecture, et il ne renvoie que le
**nom** de l'onglet actif, pas son contenu. On peut afficher le journal, pas le lire.

*(Noté aussi, sans usage prévu : `add_chart_object` sait poser des objets `risk_reward`
avec entrée/SL/TP sur le graphique réel. Aucun outil de capture d'écran côté MCP, donc
sans intérêt face au rendu matplotlib déjà validé. Ne pas rouvrir ce sujet.)*

---

## 8. Tests restants (secondaires)

- **T2** — entrée avec SL en pips : Submitted se remplit-il, et Applied aussi ?
- **T3** — entrée SL seul, TP ajouté après : le TP apparaît-il en `Modify protection` ? (attendu : oui, ce qui rendrait la discipline d'entrée facultative)
- **T4** — sortie par SL touché : vérifier que l'historique d'amendements survit

---

## 9. Prérequis Open API — comment vérifier l'accès

Ça ne se passe **ni chez la prop firm, ni dans la plateforme cTrader**, mais sur
le portail Spotware.

1. Aller sur **https://openapi.ctrader.com/** et se connecter avec son
   **cTrader ID** (les mêmes identifiants que la plateforme).
2. Page des applications → **Add new app**, description détaillée de l'usage
   (ici : export en lecture seule de son propre historique pour journaling).
3. Soumettre. L'application passe en statut *submitted* et c'est **Spotware**
   qui valide, pas le broker — délai non documenté, réponse par email.
4. Une fois approuvée : configurer les redirect URIs, récupérer les
   identifiants d'application, puis autoriser le **compte de trading** via
   OAuth.

Le point à vérifier : au moment de l'OAuth, **le compte Prop Firm A
apparaît-il dans la liste des comptes autorisables ?** S'il apparaît, l'accès
est ouvert. Sinon, l'architecture change entièrement.

À faire en premier, car l'approbation Spotware introduit un délai d'attente.
