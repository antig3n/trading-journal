# Journal de trading automatisé

Pipeline Python qui enrichit automatiquement un journal de trading Edgewonk à
partir des exports bruts de deux brokers (cTrader pour le forex, Tradovate pour
les futures) et des données de marché tick-par-tick.

> **Note.** Ce dépôt est une version publique et anonymisée d'un outil personnel.
> Les identifiants de comptes, les clés d'API et les données de trading en ont été
> retirés : `pipeline/core/plateformes.py` porte des valeurs d'exemple, et
> `donnees/` ne contient que des en-têtes de fichiers. Voir `CONFIGURATION.md`.

**Point d'entrée du projet. Tous les chemins cités partent d'ici.**

---

## 1. En une minute

L'utilisateur trade le **forex sur cTrader** et les **futures sur Tradovate**, environ
60 trades par semaine, et les journalise dans **Edgewonk 3**. L'import automatique
d'Edgewonk lui donne l'entrée, la sortie, la quantité et le résultat. **Tout le reste
arrive vide** — et le remplir à la main lui coûtait une journée par semaine.

Ce projet remplit ce reste, à partir des faits :

| ce que le programme écrit | d'où ça vient |
|---|---|
| le stop et la cible d'origine | ta saisie (forex) ou tes propres ordres lus dans l'export (futures) |
| le plus haut et le plus bas atteints | les bougies M1 du broker |
| lequel du TP ou du SL a été touché en premier | les mêmes bougies, y compris **après** ta sortie |
| ce que le trade aurait donné à 1R … 5R | une simulation qui part de ton stop |
| quatre graphiques annotés (M5, M15, H1, H4) | les bougies, avec ton entrée, ta sortie, ton SL et ton TP tracés |
| break-even (hors win rate) | `|R réalisé| < 0,30` |
| managed / not managed | **ta saisie, plus un second contrôle** — voir §3 bis |

**Ce qu'il ne touche jamais :** ton setup, ta checklist, tes commentaires, tes propres
captures. C'est le seul contenu du système qui ne soit pas reproductible.

*Le temps n'est pas le vrai sujet : une saisie de mémoire une semaine plus tard est
imprécise, et un journal imprécis ne produit aucun insight. La donnée de trading n'a
de valeur que si elle est exacte.*

---

## 2. Le geste quotidien

1. Déposer l'export du broker dans **`IMPORT/`** — le seul dossier où tu travailles.
2. Lancer **`journal.py`** (Raycast, ou `python3 pipeline/journal.py`).
3. Répondre aux questions.

```
  Que veux-tu faire ?          1 importer · 2 reprendre · 3 auditer
  Quelle plateforme ?          1 cTrader  · 2 Tradovate
  Dans quel journal ?          la liste est LUE chez Edgewonk, jamais codée en dur
  Sur quelle période ?         1 toute la base · 2 un jour ou une période
  … le fichier de saisie s'ouvre : remplis sl, tp, management …
  Comment écrire chez Edgewonk ?  1 ne remplir que le vide · 2 écraser
  Sur quels champs ?              1 tous · 2 une sélection
  > ENVOYER
  Et maintenant ?              1 stratégies alternatives · 2 menu · q quitter
```

**Le script ne rend la main qu'à `q`.** Une passe par lancement était la vraie friction :
enchaîner deux gestes coûtait de tout relancer et de retraverser les mêmes questions. Le
travail réel n'est pas une passe, c'est une **session**.

Et l'épilogue porte le geste qui n'avait pas de place : **les stratégies alternatives**.
Leurs identifiants sont propres à chaque *setup* (§13), et un trade fraîchement importé
arrive en setup par défaut — il n'y a donc aucun palier à lui donner au moment de la
poussée. Ce n'est pas une panne, c'est l'ordre des choses : les setups se posent dans
Edgewonk **après** l'import, pendant le journaling. La seconde passe est maintenant à une
touche, sur la **même borne** que ce qui vient d'être fait — même plateforme, même journal,
même période. On ne redemande rien : redemander, c'est déjà avoir perdu.

**La période se saisit comme on la dit :** `06082026` pour un jour,
`06082026-12082026` pour une période. Les ponctuations sont libres
(`06/08/2026`, `2026-08-06`, « au » entre les deux), et l'ordre n'a pas
d'importance. Elle borne sur l'**ouverture** du trade : un trade ouvert le 6 et
fermé le 9 appartient au 6 — c'est le jour où la décision a été prise.

⚠️ **Elle ne borne pas l'import du relevé.** Le fichier contient ce qu'il
contient, et en écarter des lignes produirait une base trouée qu'aucun cycle ne
viendrait combler. Elle borne les étapes qui **parcourent la base** : mesurer,
dessiner, pousser — et tous les audits.

**Le journal se choisit** parce que l'utilisateur en crée et en supprime. La liste
vient de `GET /databases` au moment où on demande : une liste en dur aurait
raison le jour où elle est écrite, et tort ensuite, en silence. C'est ce qui
rend un **bac à sable** utilisable — importer pour de vrai, dans un journal
isolé, sans rien risquer.

**Les deux modes d'écriture sont le cœur de l'outil.**

- **Ne remplir que le vide** — Edgewonk garde tout ce qu'il porte déjà. Utilisé pour
  compléter sans risque : aucune correction faite à la main, aucune capture perso ne
  peut être écrasée. C'est le défaut.
- **Écraser** — la base locale fait autorité et réécrit tout champ qui diffère. Utilisé
  quand on vient de recalculer et qu'on veut propager.

Et la sélection de champs permet de ne reprendre qu'une chose — les images seules, le
break-even seul — sans toucher au reste.

---

## 3. Les cinq étapes

C'est une séquence : chacune a besoin de la précédente.

```
  1. IMPORTER    l'export du broker → des JAMBES dans donnees/trades.csv
                 le brut est archivé AVANT toute lecture : seule chose non reconstructible

  2. SAISIR      sl · tp · management, une ligne par POSITION
                 côté futures, pré-remplis depuis tes ordres ; tu relis et tu valides

  3. MESURER     bougies M1 → plus haut, plus bas, TP-first, paliers de R
                 ce qui n'est pas mesurable reste VIDE et repasse au cycle suivant

  4. DESSINER    4 graphiques par position, sur la jambe réellement tenue

  5. POUSSER     écrire dans Edgewonk ce qu'il ne sait pas calculer, et rien d'autre
                 instantané avant · relecture de confirmation après
```

**Grain :** une ligne de base = une **jambe** = un trade Edgewonk. La **position** porte
la protection (un seul SL, un seul TP, un seul management), et la saisie se fait à ce
niveau-là, puis se réplique sur les jambes.

### 3 bis. Le management, et son double contrôle

Tu saisis **OK** (plan tenu) ou **KO** (position gérée) en regardant si tu as *touché* à
ton stop ou à ta cible après l'entrée — un trailing, un passage au break-even. C'est du
jugement, et toi seul peux le rendre : tes logs disent si un niveau a bougé de trois ticks
ou trois fois.

**Mais cette question a un angle mort** : tu peux n'avoir rien bougé et avoir quand même
fermé la position avant qu'un niveau soit touché. Ça aussi, c'est gérer — et ta saisie
dirait OK.

Le programme pose donc l'autre question : **es-tu SORTI sur un de tes niveaux ?**

| ta saisie | la sortie | ce qui part chez Edgewonk |
|---|---|---|
| KO | peu importe | **KO** — tu as vu quelque chose que la sortie ne montre pas |
| OK | sur le TP ou sur le SL | **OK** |
| OK | ailleurs | **KO** — fermée à la main, donc gérée |
| OK | aucun niveau saisi | **OK** — le contrôle est aveugle, il n'accuse pas |

*Le contrôle ne peut qu'accuser, jamais disculper.*

⚠️ **La règle est asymétrique, et c'est la mécanique des ordres qui le veut.** Une
**limite** se remplit à son prix ou **mieux** ; un **stop** à son prix ou **pire** — le
slippage. Une sortie du mauvais côté n'est donc pas un fill du niveau. Mesuré sur 184
positions : la distance *absolue* ne sépare rien (29 sorties tombent exactement sur un
niveau, puis c'est un continuum sans trou jusqu'à 1 R), c'est le **signe** qui tranche.
Borne de slippage : 0,25 R — le pire mesuré vaut 0,2355 R.

⚠️ **Le contrôle juge la jambe RÉELLEMENT TENUE**, pas chaque jambe. Un allègement sort au
marché par définition ; le contrôler ferait basculer en « géré » toute position sortie en
plusieurs fois. Tu l'as dit toi-même : alléger parce qu'on est entré trop lourd n'est pas
du management. Même règle que pour les graphiques, et pour la même raison.

---

## 4. Où vit quoi

```
IMPORT/                  tu déposes ici, et nulle part ailleurs
donnees/trades.csv       LA base — 241 jambes, cTrader et Tradovate mélangés
                         (colonne `plateforme`), une seule depuis le 28/08/2026
donnees/brut/            les exports archivés, jamais modifiés
donnees/instantanes/     un instantané avant chaque écriture
donnees/graphiques/      4 PNG par position
pipeline/journal.py      l'orchestrateur : importer ou auditer
pipeline/jt.py           le moteur : les verbes, pour reprendre à n'importe quelle étape
pipeline/outils/         les diagnostics permanents
archives/CATALOGUE.md    ⭐ les outils archivés et CE QU'ILS ONT TRANCHÉ — à lire
                         avant d'écrire un nouveau diagnostic
JOURNAL.md               pourquoi chaque règle existe, et ce qui a été écarté
```

**Trois documents de référence**, à consulter et non à lire : `docs/ctrader-sltp-protocol.md`
(côté lecture cTrader), `docs/edgewonk-api.md` (côté écriture), `docs/tradovate.md` (futures),
`docs/gabarit-graphiques.md` (apparence).

---

## 4 bis. Reprendre — la troisième porte

Même point d'entrée, sans relevé ni saisie. On choisit la plateforme, le journal et la
période, et on relance **mesurer · dessiner · pousser** sur ce qui est déjà en base.

C'est le geste qui manquait : refaire un dessin ou une écriture n'existait que sous forme de
`jt.py` tapé à la main, donc n'existait pas. Le cas qui l'a fait naître, le 29/08/2026 :
cinq positions rendues **avant** que leurs niveaux soient saisis, donc dessinées sans SL ni
TP, et des captures périmées chez Edgewonk. Rien à ré-importer — juste à redessiner et à
réécrire.

L'étape « dessiner » ne redessine que ce qui a bougé (voir `rendu.txt`, §11), et l'étape
« pousser » repose les deux mêmes questions que l'import : **écraser** ou **ne remplir que
le vide**, sur **tous les champs** ou une sélection.

*Un orchestrateur en ligne de commande de ce genre — une suite de questions qui construit
l'appel — s'appelle un **assistant interactif** (`wizard`, ou `prompt` en anglais).*

---

## 5. Auditer

Même point d'entrée, deuxième volet. Aucun de ces audits n'écrit.

| audit | répond à |
|---|---|
| **un trade** | tout ce qu'on sait de lui, par id Edgewonk ou par clé — et *pourquoi* un champ est vide |
| **cohérence** | incohérences internes du journal, doublons, écarts de prix d'exécution |
| **mesures** | extrêmes, bougies de bord, TP-first recalculé par une **seconde implémentation** |
| **images** | les quatre emplacements des deux côtés, avec réparation possible |
| **tout** | les quatre à la suite |

Deux **actions** restent à part, parce qu'elles écrivent : `outils/oublier.py` (efface un
niveau *et tout ce que le pipeline en a déduit*) et `outils/diag_images.py --reparer`.

---

## 6. Le pipeline en détail

### 6.1 Qui fait quoi

```
  [ TOI ]                                   [ LE PROGRAMME ]

  export du broker
     └─► IMPORT/ ──────────────────────────► archive le brut, jamais modifié
                                             alimente donnees/trades.csv
                                             génère le fichier de saisie

  remplis sl · tp · management
     └─► saisie.csv ───────────────────────► contrôle (rejets / signalements)
                                             réplique sur les jambes de la position

                                             bougies M1 → extrêmes, TP-first, paliers
                                             4 graphiques par position

  choisis le mode et les champs
     └─► ENVOYER ─────────────────────────► instantané, écriture, RELECTURE
```

**Le programme ne devine jamais.** Un niveau qu'il ne peut pas mesurer reste vide, et la
jambe repasse au cycle suivant. Un stop deviné est pire qu'un stop absent : absent, le
trade sort des statistiques de R ; deviné, il produit des R faux ayant l'apparence du
juste.

### 6.2 Si le projet a bougé de place

Le lanceur Raycast est un lien symbolique. S'il ne trouve plus le projet :

```
ln -sf "<nouveau chemin>/journal-sync.sh" ~/Documents/Automation/
```

ou corriger `CHEMIN_DE_SECOURS` dans `journal-sync.sh`. Le marqueur du projet est
`pipeline/journal.py`.

### 6.3 Dépendances — presque aucune, et c'est voulu

Tout le pipeline tourne en **bibliothèque standard pure**, sauf les graphiques
(matplotlib + mplfinance), qui vivent dans `.venv/`. Homebrew refuse les installations
système (PEP 668), d'où le venv.

```
python3 -m venv --system-site-packages .venv
.venv/bin/pip install mplfinance
```

`journal.py` prend le venv s'il existe et retombe sur `python3` sinon — seule l'étape 4
en a besoin. Contrôle : les outils de `outils/` s'importent tous **sans** pandas ni
matplotlib, et c'est testé.

### 6.4 Les verbes, pour déboguer

`journal.py` n'est qu'une façade : il appelle `jt.py`, qui reste le moteur. En cas de
problème, les verbes permettent de reprendre à n'importe quelle étape.

Code dans `pipeline/`, données dans `donnees/`. Rien à installer.

**Le drapeau `--tradovate` s'ajoute à n'importe quel verbe** et vaut pour toute la commande :
il change le lecteur d'export, la source de bougies et le journal Edgewonk visé. Sans lui,
c'est cTrader.

```
python3 jt.py importer --tradovate <orders.csv>
python3 jt.py bougies --tradovate       # Databento, pas le MCP cTrader
python3 jt.py etat                      # ventile les deux plateformes
```

**Les deux réglages d'écriture, en ligne de commande.** Sans eux, le comportement
historique : écraser, sur tous les champs.

```
python3 jt.py pousser --mode vide                  # ne remplir que ce qui est vide chez eux
python3 jt.py pousser --mode ecraser               # la base fait autorité (défaut)
python3 jt.py pousser --champs images              # ne reprendre que les captures
python3 jt.py pousser --champs sl,tp,extremes      # plusieurs, séparés par une virgule
python3 jt.py pousser --mode vide --champs images  # = l'ancienne règle E1 du rétroactif
```

**Les deux bornes, sur n'importe quel verbe et n'importe quel outil.** Un seul lecteur les
comprend (`base.options_ligne`), donc la syntaxe est la même partout.

```
python3 jt.py bougies --periode 06082026              # un jour
python3 jt.py pousser --periode 06082026-12082026     # une période
python3 outils/diag_coherence.py --journal 100004     # un autre journal
python3 outils/diag_tp_first.py --periode 06082026 --journal 100004
```

Les neuf champs choisissables : `sl` · `tp` · `extremes` · `tp_first` · `breakeven` ·
`paliers` · `management` · `revue` · `images`. La liste vit dans `ecriture.CHAMPS_ECRITS`
et **sert à la fois au menu et au contrôle d'argument** — une seule liste, donc pas de menu
qui dérive du code.

```
cd pipeline
python3 jt.py importer ~/Downloads/cT_1234567_20260825_1316.csv
# remplir les colonnes sl et tp dans le fichier annoncé, puis :
python3 jt.py controler ../donnees/saisies/sltp_<horodatage>.csv
python3 jt.py integrer  ../donnees/saisies/sltp_<horodatage>.csv
python3 jt.py bougies      # étape 3 — cTrader ouvert. Idempotent : ne refait rien.
python3 jt.py graphiques   # étape 4 — cTrader ouvert. EXIGE ../.venv/bin/python3
                           #           4 images par position : M5, M15, H1, H4
python3 jt.py pousser      # étape 5 — demande ENVOYER. Instantané avant, relecture après.
python3 jt.py pousser --base <id>     # viser un autre journal (plus de bac à sable)
python3 jt.py etat
```

⚠️ **L'étape 4 exige le venv** : `../.venv/bin/python3 jt.py graphiques`. Les autres
tournent avec n'importe quel `python3`. Ajouter `--refaire` pour régénérer des graphiques
déjà produits — indispensable après un ajustement du gabarit.

**Les diagnostics, en lecture seule.** Ils n'écrivent jamais, ni en local ni chez Edgewonk.
C'est par eux qu'on mesure avant de construire :

```
python3 outils/diag_bougies.py       # transport MCP + extrêmes calculés
python3 outils/diag_bord.py          # une bougie de bord déborde-t-elle du trade ?
python3 archives/mesures/diag_edgewonk.py      # authentification, bases, forme des champs
python3 archives/mesures/diag_edgewonk2.py     # pagination, précision des horodatages
python3 archives/mesures/diag_fuseau.py        # le décalage horaire, mesuré et non supposé
python3 outils/diag_appariement.py   # ce qui SERAIT écrit, champ par champ
                                     #   --tradovate pour viser les futures
python3 outils/diag_ecarts.py        # les divergences de prix d'exécution
python3 archives/mesures/diag_upload.py        # ⚠️ ÉCRIT — upload multipart + gain=null,
                                     #   uniquement dans le bac à sable 100005,
                                     #   instantané avant et restauration après
```

Côté futures, quatre de plus. Deux **dépensent** — quelques centimes chez Databento — et le
disent avant de le faire :

```
python3 archives/mesures/diag_databento.py            # six sondes de metadonnees, 0 $
python3 archives/mesures/diag_tirage.py               # ⚠️ 0,005 $ — la FORME d'une reponse OHLCV
python3 archives/mesures/diag_fuseau_tradovate.py     # ⚠️ ~0,10 $ — le fuseau de l'export, mesure
                                            #   contre le MARCHE et non contre Edgewonk
python3 archives/mesures/diag_edgewonk_tradovate.py   # 0 $ — le nom d'instrument cote Edgewonk
```

**Partir d'un id Edgewonk, et non d'une clé.** l'utilisateur lit son journal dans l'interface :
ce qu'il a sous les yeux est un id, jamais notre clé de jambe. `diag_trade.py` ne sait
déballer qu'une clé — chaque question coûtait donc un aller-retour pour la retrouver à la
main. `diag_id.py` part de l'autre bout : l'id, l'appariement inverse, puis les trois
sources côte à côte, et il **explique** pourquoi le TP/SL first est ce qu'il est.

```
python3 outils/diag_id.py 17926446          # 0 $ — un id, les trois sources, le pourquoi
python3 archives/mesures/reprise_niveaux.py           # 0 $ — les niveaux qu'ils ont et pas nous
python3 archives/mesures/reprise_niveaux.py --proposer  # … pré-remplis, mais les plausibles seulement
```

**Les images obéissent au mode, comme les huit autres champs.** *(Renversé le
29/08/2026.)* `images_a_envoyer` inventorie les PNG du disque et ne décide plus rien ;
c'est `filtrer_plan` qui tranche, **contre le trade lu dans le journal visé** :

| mode | ce qui part |
|---|---|
| ne remplir que le vide | les seuls emplacements **vides chez eux** — une capture posée à la main n'est jamais recouverte |
| écraser | les **quatre**, même identiques — c'est le chemin normal après une retouche du gabarit |

⚠️ **La règle précédente était un verrou local, et il court-circuitait les deux modes.**
`images_a_envoyer` rendait `[]` dès que notre colonne `screenshots` portait un horodatage,
et ce test se faisait *avant* que le mode soit consulté : « écraser » ne renvoyait donc
aucune image, et « ne remplir que le vide » n'en envoyait aucune non plus dans un journal
qui n'en avait jamais reçu. Le défaut de fond : **le marqueur est global, les journaux
non.** Une poussée vers un journal de test marquait la base, et les images cessaient de
partir vers le journal réel — silencieusement, définitivement. Mesuré le 29/08 : 212 jambes
marquées, 5 images dans le Sandbox, aucun moyen d'en envoyer une de plus.

`screenshots` reste écrit, mais comme **trace du dernier envoi confirmé** — plus comme un
verrou. Après un `graphiques --refaire`, le renvoi se demande :
`pousser --mode ecraser --champs images`.

```
python3 outils/diag_images.py               # 0 $ — les deux côtés, emplacement par emplacement
python3 outils/diag_images.py --reparer     # ⚠️ ÉCRIT — efface les marqueurs concernés
```

`diag_images.py` reste le seul à lire les deux côtés à la fois : c'est par lui qu'on
vérifie avant et après une poussée. `--reparer` survit pour un cas résiduel — une colonne
`screenshots` qui ment sur un envoi qui n'a pas eu lieu — mais il n'est plus le remède à
quoi que ce soit de structurel. Les emplacements **5 et 6 sont à l'utilisateur** et ne sont
jamais touchés.

⚠️ **`reprise_niveaux.py` instruit, il ne décide pas.** Quand Edgewonk affiche un SL et un
TP que notre base n'a pas, la tentation est de recopier. On ne le fait pas : ces niveaux
viennent de **leur** import, et la mesure du 28/08/2026 montre qu'ils ne se valent pas
entre eux — certains portent un SL à `0.0`, d'autres sont du mauvais côté de l'entrée,
d'autres ont été traversés alors que la position a continué. « Un stop deviné est pire
qu'un stop absent » vaut aussi pour un stop deviné par quelqu'un d'autre. L'outil rend donc
un verdict en **trois** états — `plausible`, `douteux`, `impossible` — et un fichier de
saisie ordinaire dont les cases `sl` et `tp` restent **vides**. `--proposer` les pré-remplit
pour les seules positions plausibles, jamais pour une douteuse. Dans les deux cas c'est
`jt.py integrer` qui écrit, après ses propres contrôles.

### 6.5 Ce que le code sait déjà, et qu'il ne faut pas redécouvrir

**Segmentation — le grain de la base est la JAMBE, pas la position.**
*(Renversé le 25/08/2026. La formulation antérieure — « notre découpage coïncide avec
celui d'Edgewonk » — était fausse et cassait l'appariement sur 8 trades.)*

L'export cTrader donne **une ligne par sortie** : la colonne « Order ID » est l'ordre de
**clôture**. Et **Edgewonk crée un trade par ligne du relevé**, donc par sortie partielle.
Mesuré et confirmé au centime dans les deux systèmes, sur la position du 07/08 13:43 :

| relevé cTrader (clôture) | net | Edgewonk |
|---|---|---|
| 13:44:34 — 3,00 lots | 12,00 | ✅ un trade |
| 13:44:43 — 0,50 lot | 1,50 | ✅ un trade |
| 13:50:31 — 0,50 lot | 1,50 | ✅ un trade |
| 14:30:01 — 2,00 lots | 302,00 | ✅ un trade |

Une position cTrader, **quatre trades Edgewonk**. 46 lignes de relevé = 46 trades chez eux.
Agréger en 38 positions désalignait la base de 8 trades qui n'auraient jamais trouvé leur
correspondance.

→ **Une ligne de base = une jambe = un trade Edgewonk.** La position survit dans la colonne
`cle_position`, et c'est elle qui porte la saisie du SL/TP : une position n'a qu'une
protection. Le programme réplique ensuite sur ses jambes.

*L'erreur venait du §8 bis d'`docs/edgewonk-api.md`, mesuré sur des trades **futures Tradovate**
puis généralisé à cTrader sans revérification. `docs/tradovate.md` §5 bis portait pourtant
l'avertissement : « la clé d'appariement doit être spécifique à chaque plateforme ».*

**Le prix d'entrée** de l'export est **déjà le VWAP** de la position, identique sur toutes
ses sorties partielles — et il concorde avec celui d'Edgewonk. Il sert de contrôle
d'intégrité, pas de clé.

**Fuseau.** Lu dans l'en-tête (`Opening time (UTC+2)`), jamais supposé — il passera à
UTC+1 en hiver tout seul.

**Clé d'appariement de la saisie.** Uniquement la colonne `cle`
(`20260807-134318-EURUSD-A`). Les autres colonnes du fichier de saisie sont décoratives :
un tableur peut les reformater sans aucune conséquence.

**Deux niveaux de contrôle.** *Rejet*, rien n'est écrit : niveau du mauvais côté de
l'entrée, niveau égal à l'entrée, clé inconnue, clé en double. *Signalement*, écrit après
validation humaine : ni SL ni TP, SL ou TP seul, R:R hors de 0.3–10, |R| réalisé au-delà
de 10, trade sans ligne de saisie. `integrer` refuse de démarrer s'il reste un rejet, mais
passe outre les signalements — c'est l'utilisateur qui juge.

⚠️ **Une case `management` vide est un REJET**, pas un signalement *(arbitré le
26/08/2026)*. C'est le seul contrôle du lot qu'aucune mesure ne peut rattraper après coup :
un SL aberrant se trahit par un R disproportionné, « ai-je bougé mon stop ? » ne se
retrouve nulle part. Un oubli y serait définitif, donc il bloque.

⚠️ **Le |R| réalisé est contrôlé sans avoir besoin du TP** *(ajouté le 26/08/2026)*. Le
NAS100 du 14/08 portait un SL à 0,45 point sur un indice qui bouge de centaines de points.
Le contrôle du R:R l'avait signalé — « R:R de 430,7 » — mais l'alerte a été résolue en
retirant le TP : plus de TP, plus de R:R, plus d'alerte, et le stop aberrant est resté. Il
a produit **+180 R à lui seul** et faussé le journal deux jours durant. Le nouveau contrôle
n'a besoin d'aucun TP : entrée et sortie viennent du relevé, le SL de la saisie.

**Sûreté, vérifiée.** Le brut est archivé **avant** lecture · instantané de la base avant
chaque écriture (`donnees/instantanes/`) · écriture atomique · une valeur non vide n'est
jamais remplacée par du vide. Ré-importer le même relevé est donc **sans effet**
(vérifié : 38 inchangés) et la saisie manuelle survit à tous les ré-imports.

### 6.6 Le schéma de la base

Colonnes de `donnees/trades.csv`, dans l'ordre — **on ajoute en fin de liste, jamais au
milieu** (`pipeline/core/modele.py`) :

```
cle                    ← LA JAMBE : 20260807-134318-EURUSD-A#143001
cle_position           ← la position qui la porte : 20260807-134318-EURUSD-A
compte · symbole · symbole_broker · sens
ouverture              ← commun à toute la position
cloture                ← PROPRE À LA JAMBE
entree                 ← VWAP d'entrée de la position
sortie · volume_lots   ← propres à la jambe
nb_jambes · swaps · commission · brut · net
sl · tp · management                           ← saisie manuelle (étape 2), PAR POSITION,
                                                 puis répliqués sur chaque jambe.
                                                 management : OK = plan tenu,
                                                 KO = position gérée. Une case VIDE
                                                 bloque l'intégration (§9)
prix_plus_haut · prix_plus_bas · tp_touche_en_premier   ← bougies (étape 3), PAR JAMBE :
                                                 la fenêtre entrée→sortie diffère
chemin_graphiques                              ← rendu (étape 4) — renseigné UNIQUEMENT
                                                 sur la jambe réellement tenue
prix_max_favorable                             ← étape 3 : prix le plus favorable atteint
                                                 AVANT le SL, borné au niveau 5R.
                                                 Vide = simulation non résolue.
screenshots                                    ← étape 5 : horodatage de l'envoi CONFIRMÉ
                                                 des 4 captures. Vide = à envoyer.
id_edgewonk                                    ← résultat de l'appariement (étape 5)
source_brut
```

**La clé de jambe porte l'heure de SORTIE** (`#143001`) parce que c'est le seul champ qui
distingue deux sorties partielles : mesuré, l'horodatage de sortie est unique sur 46/46
jambes, là où le prix de sortie échoue sur 44/46 — deux sorties peuvent partager prix,
quantité **et** montant.

**On stocke les faits, pas les statistiques.** Le plus haut et le plus bas sont des faits :
les retrouver demande de refaire des requêtes de bougies, et les brokers purgent.
Le R-multiple, le win rate, l'expectancy se recalculent en une seconde depuis les colonnes
ci-dessus — les stocker créerait deux vérités qui divergeraient.
`tp_touche_en_premier` **est** un fait : si le prix a touché les deux niveaux, seul l'ordre
compte, et cet ordre n'est nulle part ailleurs.

---

## 7. Prérequis technique — le serveur MCP local cTrader

C'est la source de bougies du projet. **Aucune approbation, aucun OAuth** : il
s'authentifie avec la session cTrader déjà ouverte.

**Activation** — dans cTrader : *Paramètres → Serveur MCP*.
Cocher **« Enable MCP Server »**. Laisser **« Allow trading via MCP » DÉCOCHÉ**.
Le serveur écoute sur `http://127.0.0.1:9876/mcp/`.

**Appeler un outil** — `pipeline/outils/ct.sh <nom_outil> '<json>'`, cTrader ouvert :

```
pipeline/outils/ct.sh get_symbols  '{"filter":"XAU"}'
pipeline/outils/ct.sh get_trendbars '{"symbolName":"XAUUSD","timeframe":"m1","from":"2026-08-25T09:00:00Z","to":"2026-08-25T10:00:00Z"}'
```

⚠️ **Ne jamais appeler un outil préfixé `amend_`, `place_`, `close_` ou `cancel_`.**
Ils agissent réellement sur le compte. La case décochée est la protection de premier rang,
pas la seule à respecter.

**Ce que le MCP donne et ne donne pas** — détail mesuré au §7 bis de
`docs/ctrader-sltp-protocol.md`. En résumé : `get_trendbars` est de qualité production ;
`get_order_history` ne porte **aucun** SL/TP et n'est pas déterministe ; aucun outil
n'expose l'historique d'amendements d'une position.

---

## 8. Prérequis technique — Databento, la source de bougies des futures

Côté futures il n'y a **rien** de gratuit : l'API Tradovate est fermée aux comptes prop
firm et Edgewonk ne porte pas les cotations de ces actifs. Sans source de prix, pas
d'extrêmes, pas de TP-first, pas de paliers, pas de graphiques — c'est-à-dire rien de ce
que ce projet apporte.

**Databento, en mode usage — facturé au gigaoctet, sans abonnement.** Dataset `GLBX.MDP3`
(CME, CBOT, NYMEX, COMEX), 125 $ de crédits offerts à l'inscription.

**La clé vit dans le trousseau macOS, jamais dans un fichier ni dans le dépôt** — même
règle que le mot de passe Edgewonk. À créer une fois :

```
security add-generic-password -s databento -a <ton-email> -w
```

(sans la clé sur la ligne : `security` la demandera, elle ne restera donc pas dans
l'historique du shell.)

**Ce qui a été mesuré le 26/08/2026**, six sondes, toutes en 200 :

| | |
|---|---|
| profondeur de `GLBX.MDP3` | depuis le **06/06/2010** — trois ans avant le premier trade futures |
| schémas | `ohlcv-1s`, `ohlcv-1m`, `ohlcv-1h`, `ohlcv-1d`. **Ni 5m ni 15m** |
| symbologie | `MNQU6` se résout tel quel — **aucune table à maintenir** |
| tarif | 70 $/Go en M1, 190 $/Go en H1 |
| coût mesuré | **0,0050 $** une journée entière de M1 sur un contrat |

**Le M5, le M15 et le M30 s'agrègent depuis le M1 ; le H4 depuis le H1.** Piège qui ne se
voit pas : un seau d'agrégation qui mord sur le bord de la fenêtre serait **incomplet**,
donc son plus haut serait sous-estimé en silence. Le client élargit la requête aux bornes
de seau avant de tirer, puis découpe.

**Le cache est à la JOURNÉE, et c'est le chiffre de 0,005 $ qui le décide.** À ce prix on
tire la journée entière plutôt que la fenêtre exacte, et on la garde dans
`donnees/bougies/`. Conséquence : `--refaire`, la reprise des paliers non résolus et la
pagination ne repaient plus rien. Et les bougies déjà lues restent lisibles le jour où le
budget serait épuisé — même raison de fond que `donnees/brut/`.

⚠️ **Ce module ne peut rien acheter par accident** : il ne sert qu'un seul appel,
`get_trendbars`. Tout autre outil est refusé au niveau du code, comme le MCP cTrader refuse
les préfixes `place_` et `amend_`.

---

## 9. Ordre de lecture

1. **`docs/ctrader-sltp-protocol.md`** — côté **lecture**. Priorité au **§2** (où vivent
   réellement les SL/TP, et pourquoi les champs d'ordre sont inutilisables), au **§3 ter**
   (la décision de saisie manuelle) et au **§7 bis** (ce que le MCP local fournit,
   mesuré). Les règles **R1 à R7** au §5 restent la référence du calcul.
2. **`docs/edgewonk-api.md`** — côté **écriture**. Contrat complet de l'API interne, mesuré et
   non supposé. Voir en priorité le **§0 (périmètre d'écriture)** et le **§12 (déroulé
   d'une exécution)**.
3. **`docs/tradovate.md`** — côté **lecture Tradovate** (futures). Priorité au **§5 bis** (la
   segmentation, qui **diffère** de cTrader), au **§5 quater** (la bascule à l'ATM du
   18/08, et ce qu'elle rend automatisable ou non) et au **§9** (Databento, mesuré).
4. **`docs/gabarit-graphiques.md`** puis **`pipeline/graphiques/`** — l'apparence
   (`gabarit.py`) et le cadrage (`rendu.py`). Priorité au **§2** (pourquoi le graphique
   suit la dernière jambe), au **§7** (les quatre timeframes) et au **§10** (ce qui est
   tombé le 25/08 au soir, et pourquoi). `charts.py`, à la racine, n'est qu'un banc
   d'essai sur bougies synthétiques.
5. **`retroactif/LISEZMOI.md`** puis **`INVENTAIRE.md`** — le chantier de reprise de
   l'historique, **terminé le 26/08**. À lire seulement si un nouveau champ doit être posé
   rétroactivement : les trois écarts avec la production (E1, E2, E3) y sont nommés.
6. **`pipeline/`** — le code des étapes 1, 2, 3 et 5. **Les commentaires en tête de chaque
   module portent les faits mesurés qui justifient son comportement, et ce que l'erreur
   inverse a coûté.** C'est là que vit la mémoire du projet : `core/modele.py` pour le
   grain de la base, `ctrader/bougies.py` pour les bougies de bord, `edgewonk/api.py` pour
   les trois règles d'écriture, `edgewonk/appariement.py` pour le fuseau et la troncature.
   Les lire avant de modifier quoi que ce soit.

---

## 10. Les règles qui protègent les données

Elles viennent de tests réels, pas de principes.

**1. Ne jamais construire un `PUT` Edgewonk à la main.** Il remplace l'objet entier : une
clé omise est **effacée** — vérifié. Toujours passer par le constructeur du §0 de
`docs/edgewonk-api.md`. Un `PUT` bâclé efface le tagging de l'utilisateur, seul contenu du système
qui ne soit pas reproductible.

**2. Un statut 200 ne prouve rien.** L'endpoint `modify` accepte tout et **ignore
silencieusement** les champs hors de sa liste blanche. Toujours relire après écriture.

**3. Instantané avant toute écriture.** Vaut pour Edgewonk comme pour la base locale.
Cette règle a permis de remplir puis restaurer 169 trades sans perdre une valeur.

**4. Le brut est archivé avant d'être lu.** `donnees/brut/` contient les exports de
L'utilisateur, horodatés, **jamais modifiés**. C'est la seule chose non reconstructible du
système : `trades.csv` se rejoue depuis le brut, l'inverse est faux.

**5. Ne jamais reconstruire un montant depuis les prix d'Edgewonk.** Le champ `multiplier`
y vaut **1.0** sur les trades importés depuis cTrader, y compris sur EURUSD et XAUUSD :
**ce n'est pas la taille du contrat.**
⚠️ *Nuance mesurée le 26/08/2026 : côté futures il vaut la vraie taille — 20,0 sur NQ. La
règle porte donc sur l'importateur cTrader, pas sur Edgewonk en général. Ça ne change rien
à la conduite à tenir — on ne reconstruit pas leurs montants — mais l'affirmation « vaut 1.0
partout » était trop large.*
**Côté futures, notre propre multiplicateur se déduit de l'export** (`Notional Value / (prix
× quantité)`), et il est vérifié contre le P/L d'Edgewonk au centime : NQ 20, MNQ 2, GC 100,
MGC 10, MCL 100, 6E 125 000. Déduit, jamais tabulé. Un
contrôle qui comparait `(entrée − sortie) × quantité × multiplier` au `gainGross` obtenait
0,00027 face à un brut de 27,00 et a marqué `inReview` sur **40 trades parfaitement sains**
— réparés grâce à l'instantané. On compare des **prix à des prix**, les nôtres étant
vérifiables arithmétiquement contre le relevé.

**6. Un doublon, c'est SIX champs — instrument, sens, entrée, SORTIE, quantité, montant.**
*(28/08/2026, et ça a coûté un trade.)* Le diagnostic déclarait doublon deux trades
partageant instrument, sens, **minute d'entrée**, quantité et gain. Il manquait la
**sortie** — et deux jambes d'une même position partagent toujours leur minute d'entrée,
c'est la définition d'une sortie en plusieurs fois. L'utilisateur a supprimé `16813784` sur ce
verdict ; c'était la jambe `#181426` de la position du 31/03, pas une copie.

Un doublon, c'est le **même trade deux fois** : les deux bouts, pas seulement le premier.
Toute clé dérivée qui identifie un trade doit porter l'entrée **et** la sortie — c'est déjà
vrai de la clé d'appariement (§9), ça l'est tout autant d'un verdict qui autorise une
suppression. *Et un verdict qui déclenche une action destructrice mérite un champ de plus,
pas un de moins.*

**7. Un échantillon de trois ne fait pas une règle.** Deux erreurs de cette journée viennent
de là : la segmentation, généralisée depuis des trades futures, et la précision des
horodatages Edgewonk, conclue sur trois trades de mars qui n'étaient pas représentatifs.
Quand une mesure porte le modèle de données, la refaire sur la population réelle.

---

## 11. Décisions figées

Le raisonnement est dans les documents ; voici les arbitrages à ne pas rouvrir sans raison
nouvelle.

**SL/TP — on saisit les valeurs INITIALES.** *(25/08/2026.)* Le stop et la cible posés à
l'entrée, jamais la valeur affichée après un déplacement. Aucun contrôle ne peut rattraper
l'erreur inverse : un stop remonté passe tous les garde-fous et gonfle R en silence.
Détail et raisonnement : `docs/ctrader-sltp-protocol.md` §3 ter.

**SL/TP initiaux — saisie manuelle.** *(25/08/2026, `docs/ctrader-sltp-protocol.md` §3 ter.)*
Aucun transport automatique n'était à la fois complet, fiable et léger. Trois valeurs par
trade, copiables depuis le panneau *Position Info*, quel que soit le mode d'entrée et
l'appareil. **Abandonnés en connaissance de cause :** le collecteur en tâche de fond
(cadencement, pannes silencieuses, positions de 15 s), le log fichier (aveugle aux trades
mobiles), l'Open API (ne porte pas le niveau initial).

**La base locale est la référence, Edgewonk n'en est qu'un consommateur.** On stocke les
faits, jamais les statistiques. Le brut est archivé et intouchable.

**Reconstruction du stop initial — SPÉCIFICATION DORMANTE.** *(Clarifié le 25/08/2026.)*
Les règles R1→R6 et `R_PRICE_MOVED = 0.50` décrivent comment reconstruire le stop initial
**depuis un historique d'amendements**. Ce chemin a été abandonné au profit de la saisie
manuelle (§3 ter du protocole) : `R_PRICE_MOVED` **n'existe nulle part dans le code**, et
seule **R7** (pas de SL → pas de R) est réellement implémentée. Ces règles restent écrites
parce qu'elles redeviendraient la référence si un transport automatique voyait le jour —
mais elles ne décrivent **aucun comportement actuel**. Ce qui suit est de la conception,
pas de la documentation de code.

SL et cible sont deux chronologies **indépendantes** ;
pour chacune, **la première valeur non nulle gagne**. Un changement ultérieur est classé
par **un seul critère** : la progression du prix en R.
`R_PRICE_MOVED = 0.50` (en dessous → correction d'entrée, la valeur remplace ; au-dessus →
management, le changement est ignoré). Seuil volontairement bas : classer du management en
correction écrase le stop initial et fausse R **silencieusement**, l'erreur inverse est
bénigne.

**Break-even** — `R_BREAK_EVEN = 0.30` *(réglé le 25/08/2026 : 0,20 → 0,30 → 0,15 → 0,30)*,
exprimé **en R et jamais en dollars** : l'utilisateur empile des comptes de tailles différentes, un seuil en
devise rendrait le win rate incomparable. Il pilote le champ `ignoreForWinrate`.
**Seuil seul, pas de règle structurelle** — arbitré le 25/08 : les jambes d'allègement
au-delà du seuil comptent comme des trades perdants. Mesuré sur la position du 07/08 18:50,
deux d'entre elles sont à −0,43 et −0,49 R. C'est assumé.

*Pourquoi le retour à 0,30 : règle de l'utilisateur — « tout au-dessus de 0,3 R c'est un trade,
point barre ». Le détour par 0,15 servait à épargner `#215448` (−0,292 R), la jambe
réellement TENUE du 07/08 18:50, que 0,30 fait rebasculer en break-even. Arbitré : la
lisibilité du seuil vaut mieux qu'un réglage taillé sur un cas.*

⚠️ **Un booléen à `false` est VIDE** *(renversé le 29/08/2026)*. La règle inverse — « une
case décochée est un état, pas une absence » — rendait le break-even **impossible à écrire
en mode « ne remplir que le vide »**, c'est-à-dire dans le mode par défaut de
l'orchestrateur. Mesuré sur les 553 trades des quatre journaux : `ignoreForWinrate` n'est
**jamais** `null`, pas une fois — Edgewonk le stocke à `false` dès la création du trade.
`_deja_rempli` répondait donc « rempli » partout, et le champ était mort. `inReview`
tombait pareil ; `originalTpHit`, lui, **est** nullable (64 nulls sur 242), ce qui
explique que TP-first passait et break-even non, dans le même mode et sur le même trade.
Ce que la nouvelle règle préserve : une case **cochée** à la main reste protégée en mode
« vide ». Ce qu'elle abandonne : une case délibérément **décochée** peut être recochée par
le robot — ce que la décision ci-dessous autorise déjà explicitement.

✅ **Le robot fait autorité, dans les deux sens** *(révisé le 25/08 en fin de soirée)*,
dans `edgewonk/ecriture.py`. Il coche ET décoche, par-dessus une case manuelle s'il le
faut. **Le garde-fou est le R, pas le sens de l'écriture** : sans SL, `est_break_even`
renvoie `None` (règle R7) et rien n'est écrit — les jambes non traitées gardent la main de
L'utilisateur, et c'est la saisie du SL qui transfère l'autorité au robot. Tout décochage est
signalé.

**Management — le seul champ de TAGGING que le robot écrit.** *(Ouvert par l'utilisateur le
26/08/2026.)* `OK` = le plan a été tenu → « Not managed » ; `KO` = la position a été gérée
→ « Managed ». C'est une **brèche assumée** dans la liste des interdits du §0
d'`docs/edgewonk-api.md`, et elle est légitime parce que la valeur vient de **lui** : « ai-je
touché à mon stop après l'entrée ? » se saisit à la main dans le fichier SL/TP, au même
titre que le stop. On **transporte** son jugement, on n'en fabrique aucun — c'est
exactement ce que le reste de la liste protège.

**La brèche est étroite, et doit le rester :** `managementComments` uniquement —
`preTradeComments`, `entryComments`, `exitComments`, `customComments` et `checklistItems`
restent intouchables — et **on n'écrit que si `OK` ou `KO` est saisi**. Case vide, on ne
touche à rien, même si le trade porte déjà une valeur posée à la main.

**Les identifiants d'option se résolvent par NOM, depuis le catalogue.** *(Corrigé le
26/08/2026.)* `GET /databases/{db}/comments` — trouvé par mesure, `archives/mesures/diag_commentaires.py`,
onze URL sondées, une seule répond. C'est la source de référence : elle liste les options
**qui existent**, qu'un trade les porte ou non.

⚠️ **Ne jamais revenir à la déduction depuis les trades lus.** C'était le mécanisme
précédent : chaque `managementComments` étant un objet `{id, name}`, on en tirait le
catalogue. Ça ne voit que ce qui est **déjà posé quelque part**. Mesuré le 26/08 : après un
nettoyage des champs Management d'août, « Managed » n'était plus portée par aucun des 238
trades, et le module a refusé d'écrire les 23 positions `KO`. Refus correct — il ne devine
pas un identifiant — mais aveugle par construction. Le repli existe encore, il n'est plus
le chemin normal, et il se **signale** quand il sert. Si une option est renommée côté
Edgewonk (« Followed rules » → « Not managed » est déjà arrivé), la résolution retombe sur
le `rating` — POSITIVE pour `OK`, NEGATIVE pour `KO` — et le dit.

**Extrêmes de prix et TP-first** — calculés depuis les **bougies M1 du broker**
(`get_trendbars` sur le MCP local), jamais depuis le feed d'Edgewonk. Deux exigences :

- **M1, pas M5.** Vérifié le 25/08 sur la position `284853317` : la bougie M5 contenant la
  sortie s'étend au-delà de la clôture et porte un extrême **postérieur au trade**.
- **Les bougies de bord sont EXCLUES du calcul.** *(Renversé le 25/08 : « en M1 l'erreur
  de bord tombe à 59 secondes » était vrai mais trompeur — elle n'est pas négligeable.)*
  Mesuré sur la jambe `20260807-134318-EURUSD-A#143001` : sortie au TP à 12:30:01Z, et la
  bougie M1 de 12:30 porte un plus haut à 1.15685 — **21,5 pips au-dessus du TP, atteints
  APRÈS la sortie** (publication macro US de 8h30 NY, 41 pips d'amplitude dans la minute).
  → On ne retient que les bougies **entièrement contenues** dans [entrée, sortie], plus les
  deux prix connus exactement : l'entrée et la sortie. Le plus haut redevient alors 1.15470,
  c'est-à-dire le TP — ce qui s'est réellement passé. L'erreur résiduelle est **bornée et
  toujours conservatrice** : les extrêmes sont sous-estimés, jamais surestimés.
  `R_ECART_BORD = 0.10` compte les cas où une bougie de bord dépassait matériellement.
- **Le symbole est `symbole_broker`, avec son suffixe.** *(Tranché le 25/08.)* `get_symbols`
  sur le compte Prop Firm A répond **`XAUUSD.raw`**. Le `XAUUSD` nu était un artefact du
  compte démo. Aucune table de correspondance à maintenir.
- **Une requête par POSITION, pas par jambe** : les jambes partagent leur entrée.
- **La pagination est obligatoire.** Cap de 1000 barres par requête ; la plus longue
  position du relevé du 25/08 dure 16 h 51, soit **1011 barres M1**. Le cas limite est déjà
  dans les données réelles.

**Databento pour les bougies futures, et une INTERFACE identique au MCP cTrader.**
*(26/08/2026.)* `databento/client.py` répond au même appel — `appeler("get_trendbars", …)` —
et rend la même forme de barres. Conséquence directe et voulue : `ctrader/bougies.py`
(extrêmes, bougies de bord, TP-first, paliers, trou du week-end) et `graphiques/rendu.py`
(les quatre images, la jambe réellement tenue) servent les futures **sans une ligne
modifiée**. Écrire un second moteur de calcul aurait créé deux vérités qui divergeraient —
c'est le même raisonnement que « on stocke les faits, pas les statistiques », appliqué au
code.

*Corollaire assumé : `ctrader/bougies.py` porte du code générique. Le dossier est
historique ; le déplacer toucherait onze modules d'une chaîne en production pour un gain
cosmétique. Constaté, écrit, pas corrigé.*

**Graphiques** — **générés depuis les bougies**, jamais capturés. TradingView est une
impasse (pas d'API image, symboles `.raw` inconnus, pas d'annotation programmée).

**Quatre images par POSITION : M5, M15, H1, H4.** *(Tranché le 25/08 au soir.)* Plus de
couple LTF/HTF choisi par la durée — les quatre servent, et Edgewonk a six emplacements.
Emplacements **1 = M5, 2 = M15, 3 = H1, 4 = H4** ; 5 et 6 restent libres.
**Le M1 est hors de l'échelle** : l'utilisateur ne lit jamais en dessous du M5, le M1 ne sert
qu'au calcul des extrêmes où il n'est pas affiché.

⚠️ **Le rendu n'est PAS idempotent sur l'existence des PNG** *(corrigé le
29/08/2026, et ça a coûté cinq graphiques faux)*. Quatre fichiers sur le disque suffisaient
à déclarer la position faite — or le dessin dépend aussi du **SL et du TP** : les deux
bandes en pointillés et les deux rectangles du Position Tool. Une position rendue **avant**
la saisie de ses niveaux gardait donc pour toujours un graphique sans niveaux — deux points
et une diagonale, rien d'autre — sans que rien ne le signale ni ne le résorbe. Même forme
que le verrou des captures, autre étape.

Chaque dossier porte maintenant un `rendu.txt` : la **signature des données** qui ont servi
au dessin (ouverture, clôture, entrée, sortie, sens, SL, TP, liste des timeframes). Elle
n'est écrite que sur un rendu **complet**, et une signature absente ou différente relance le
rendu. Elle ne porte **que des données** : un changement de gabarit ne s'y voit pas et
continue de se demander à la main (`graphiques --refaire`) — c'est une décision, pas un fait.

**Le graphique montre la jambe RÉELLEMENT TENUE, c'est-à-dire la dernière sortie — et
elle seule le porte.** Les jambes d'allègement n'ont pas de graphique : leur coller les
captures de la vraie position encombrerait le journal sans rien apprendre.
L'utilisateur ne prend pas de partiels : une position sortie en plusieurs fois est un
allègement après ajustement du SL. Mesuré sur ses 4 positions multiples, le critère
« dernière sortie » est juste 4 fois sur 4 ; « la plus grosse jambe » se trompe 2 fois
sur 4, dont sur le trade du 07/08 où elle aurait retenu 3 lots soldés en 76 s pour un gain
marginal au lieu de 2 lots tenus 47 min qui portent l'essentiel du résultat (`docs/gabarit-graphiques.md` §2).

Les PNG sont conservés en local : ~65 Ko l'unité, 4 par position, et ils seraient
irreproductibles le jour où le broker aura purgé ses bougies.

**Appariement cTrader ↔ Edgewonk** — aucun identifiant commun. Clé dérivée :
**instrument + sens + minute d'entrée + minute de sortie, en UTC**, puis départage par
montant et quantité. Mesuré le 25/08 : **44 jambes sur 46 appariées, zéro ambiguïté**
(les 2 restantes n'étaient pas encore importées chez Edgewonk).

⚠️ **Edgewonk stocke en UTC, PAS en heure de Paris** — l'affirmation contraire du §9 d'
`docs/edgewonk-api.md` est fausse pour l'importateur cTrader. Mesuré à l'envers pour ne pas
deviner : on a d'abord apparié sur le **montant net**, un pivot qu'aucun fuseau ne décale,
puis lu l'écart sur les couples obtenus. Résultat : 2 h 00 pile en août, donc UTC. La
conversion passe par l'offset porté par le relevé, **jamais par un −2 h en dur** : l'heure
d'hiver casserait un décalage figé, en silence.

⚠️ **Edgewonk TRONQUE les horodatages à la minute.** Conséquence directe : deux jambes
sorties dans la même minute deviennent indiscernables par l'heure seule — le cas existe
déjà (`#134434` à 13:44:34 et `#134443` à 13:44:43 tombent toutes deux sur 11:44). Le
montant et la quantité les départagent ; si les trois coïncidaient, l'appariement refuse
plutôt que de tirer au sort.

**Le VWAP d'entrée est un CONTRÔLE, pas une clé.** Edgewonk et cTrader agrègent les fills
de façon identique — et quand ils divergent, c'est une information : voir §9 « données
d'exécution » ci-dessous.

**Les données d'exécution d'Edgewonk ne sont pas toujours justes.** *(Renversé le 25/08 :
le §0 d'`docs/edgewonk-api.md` les disait « déjà justes via l'auto-import ».)* Sur 44 couples,
**2 portent des prix qui divergent des nôtres** — et nos prix, eux, reproduisent le brut du
relevé au centime. Leur `rMultiple` sera donc faux quoi qu'on y écrive, puisqu'il est
calculé serveur depuis l'entrée, le SL et la sortie. On ne corrige pas leurs prix — toucher
`scalings` n'a jamais été testé — mais le trade est marqué **`inReview`**, qui s'affiche là
où l'utilisateur travaille.

**Tradovate (futures)** — l'API officielle est **fermée aux comptes prop firm**. La voie
retenue est celle des **deux exports CSV** (Position History + Orders) : l'utilisateur a décidé
de **ne pas faire de management sur les futures**, donc la dernière valeur exportée est le
risque initial. L'API interne de la plateforme web a été **délibérément écartée** —
risquer un compte financé pour automatiser de la saisie est un mauvais échange.

⚠️ **La segmentation y diffère de cTrader, et c'est le point dur.** Un trade Edgewonk côté
futures est une **position à plat** — de zéro contrat net à zéro contrat net.
`tradovate/statement.py` suit la quantité nette et ferme la position quand elle repasse à
zéro. *(Renversé le 26/08/2026 : le modèle précédent — composantes connexes par union-find
sur les identifiants d'exécution — a été démenti par le contre-exemple MGCV6 du 17/08.)*
Chaque importateur a sa règle, aucune ne se généralise.

⚠️ **Les SL/TP se lisent des DEUX régimes.** *(Élargi le 28/08/2026.)* Les entrées ATM se
lisent par groupe d'ids consécutifs. Les entrées posées au graphique se lisent par
**fenêtre de position** : côté de fermeture (une entrée ouvre, une protection ferme) et
bornes de la position. Le refus initial de les lire tenait à un manque —
c'est exactement ce qui fait qu'Edgewonk colle des stops à 183 points. Un stop deviné est
**pire qu'un stop absent** : absent, le trade sort des statistiques de R ; deviné, il
produit des R faux ayant l'apparence du juste. Le module ne devine donc jamais, et les
entrées `Chart` partent en saisie manuelle. L'utilisateur étant passé à l'ATM le 18/08, c'est un
arriéré borné, pas une charge récurrente.

**Les SL/TP lus dans l'export sont des SUGGESTIONS, pas des écritures.** *(26/08/2026.)*
Ils arrivent pré-remplis dans le fichier de saisie, où l'utilisateur les valide, et sont ensuite
écrits comme n'importe quelle saisie manuelle. Les poser directement en base paraîtrait plus
court et serait un piège : la règle de fusion remplace une valeur non vide par une autre, si
bien qu'un ré-import du même export **écraserait une correction faite à la main** — sans
bruit, les deux valeurs étant plausibles. Une seule autorité sur la base, et c'est lui.

**Le champ `management` reste saisi à la main, y compris sur les futures.** La règle du §7
de `docs/tradovate.md` dit qu'il vaudra `OK` partout ; c'est une prévision, pas une mesure. Une
case vide bloque, exactement comme côté forex.

**Stratégies alternatives** — *(tranché le 25/08/2026, élargi le 26/08.)* Pour chaque
palier — **1R, 1,5R, 2R, 2,5R, 3R, 3,5R, 4R et 5R**, huit contre cinq à l'origine — la
valeur est **soit le palier, soit −1**. Rien d'autre.

Élargir la liste n'a rien coûté et n'a demandé **aucune requête de bougies** : les paliers
se résolvent depuis le `prix_max_favorable` déjà stocké. C'est le bénéfice direct de « on
stocke les faits, pas les statistiques ». `PALIERS_R`, dans `ctrader/bougies.py`, est le
**seul endroit** où ils sont énumérés ; l'écriture vise le `strategyId` résolu par nom
parsé, donc l'ordre d'affichage chez Edgewonk n'entre nulle part, et un palier absent de
la liste est vu, signalé, puis laissé intact. On simule la tenue
de la position avec le SL initial et on s'arrête au premier des deux atteints. Le prix
monte à 4,5 R puis revient au stop → `4R = +4`, `5R = −1`. **On ne mesure jamais au-dessus
de 5R** : c'est le dernier palier, et aucun champ ne recevrait davantage.
**On ne touche que `rMultiple`, jamais le `gain`** en devise.

⚠️ **La simulation continue APRÈS la sortie réelle**, et c'est toute sa difficulté. Les
extrêmes du trade s'arrêtent à la sortie de l'utilisateur : s'en servir sous-estimerait
systématiquement. Mesuré sur la position du 07/08 13:43 — plus haut pendant le trade
2,17 R, donc −1 pour 3R, 3,5R, 4R et 5R ; or le prix monte à ~6,75 R dans l'heure suivante
et les cinq paliers étaient atteints. On stocke le **prix** le plus favorable
(`prix_max_favorable`), pas les R : les R se recalculent, un prix ne diverge jamais.

Plafond de `JOURS_MAX = 10` jours de recherche. Il ne fabrique **jamais** de valeur :
au-delà, la simulation est déclarée **non résolue**, la colonne reste vide et le trade
repasse au cycle suivant — un trade du matin n'a pas encore de futur.

**Une tranche vide n'est pas la fin de l'historique.** *(Corrigé le 25/08/2026.)* Le
parcours avance par tranches d'un jour et s'arrêtait à la **première** tranche vide — or
le marché ferme le week-end. Mesuré : le NAS100 du **vendredi** 14/08 butait sur le samedi
15 et se déclarait « non résolu, le trade repassera ». C'était faux : la tranche du samedi
est vide à chaque relance, donc il ne se résolvait **jamais**. Tout trade du vendredi dont
les paliers ne se règlent pas avant la clôture était silencieusement perdu.

Le discriminant est le temps, pas le vide : une tranche qui mord sur le **futur** arrête la
recherche (l'historique n'existe pas encore, le trade repassera vraiment) ; une tranche
vide dans le **passé** est un marché fermé, on la saute. `VIDES_MAX = 4` borne la casse si
le broker a réellement purgé — week-end long plus férié.

**Les identifiants de stratégie se résolvent par NOM**, jamais en dur : ils sont propres à
chaque setup ET à chaque base. Le nom est *parsé* (« 3.5R », « 3,5 R » → 3.5) plutôt que
comparé à une liste figée, pour qu'un renommage ne casse pas en silence.

**Hors périmètre** — l'historique du management du stop n'est demandé par **aucun champ
Edgewonk**. Ne pas partir sur des métriques dérivées tant que le remplissage de base n'est
pas livré.

---

## 12. Architecture

```
trading-journal/
├── README.md                    ce point d'entrée
├── JOURNAL.md                   pourquoi chaque règle existe, et ce qui a été écarté
├── ctrader-sltp-protocol.md     référence — côté lecture cTrader
├── edgewonk-api.md              référence — côté écriture Edgewonk
├── tradovate.md                 référence — futures
├── gabarit-graphiques.md        référence — apparence ET cadrage des graphiques
├── charts.py                    banc d'essai du gabarit, sur bougies synthétiques
├── journal-sync.sh              lanceur Raycast → pipeline/journal.py
│
├── IMPORT/                      LE SEUL DOSSIER OÙ TU TRAVAILLES
│   ├── LISEZMOI.txt             la marche à suivre, sur place
│   └── _traites/                exports déjà passés, horodatés
│
├── pipeline/
│   ├── journal.py               L'ORCHESTRATEUR — pose les questions, appelle jt.py.
│   │                            Ne réimplémente rien : l'interface et le moteur sont
│   │                            deux métiers, les mélanger a produit deux orchestrateurs
│   ├── jt.py                    LE MOTEUR — importer / controler / integrer / bougies /
│   │                            graphiques / pousser / etat. Reprise à n'importe quelle
│   │                            étape, et --mode / --champs en ligne de commande
│   ├── core/
│   │   ├── plateformes.py       TOUT ce qui distingue cTrader de Tradovate, et rien
│   │   │                        d'autre : lecteur, bougies, journal Edgewonk, colonne
│   │   │                        d'instrument
│   │   ├── modele.py            colonnes de la base + les DEUX clés (jambe, position)
│   │   ├── base.py              lecture/écriture de trades.csv, fusion non destructive,
│   │   │                        vue « position », instantané avant chaque écriture,
│   │   │                        et REFUS d'une écriture qui perdrait des lignes
│   │   └── saisie.py            fichier sl/tp/management par POSITION + garde-fous
│   ├── ctrader/
│   │   ├── statement.py         relevé CSV → jambes ; le fuseau est LU dans l'en-tête
│   │   ├── mcp.py               client du MCP local — REFUSE les outils d'écriture
│   │   └── bougies.py           étape 3 : extrêmes, TP-first, paliers, et PALIERS_R
│   │                            ⚠️ GÉNÉRIQUE malgré le dossier : sert les deux
│   │                               plateformes. Le nom est historique
│   ├── tradovate/
│   │   ├── statement.py         export « Orders » → jambes, par positions À PLAT
│   │   │                        (flat-to-flat). Multiplicateur déduit de Notional Value
│   │   └── protections.py       Orders → SL/TP. DEUX lectures : brackets ATM par ids
│   │                            consécutifs, et entrées au graphique par FENÊTRE de
│   │                            position (côté de fermeture + bornes) — voir §11
│   ├── databento/
│   │   └── client.py            MÊME interface que ctrader/mcp.py — c'est ce qui évite
│   │                            de dupliquer le calcul. Agrégation M1→M5/M15, cache
│   ├── graphiques/
│   │   ├── gabarit.py           APPARENCE — source unique
│   │   └── rendu.py             les 4 timeframes, le cadrage, le fuseau, et le choix de
│   │                            la jambe réellement tenue. N'importe ni pandas ni
│   │                            matplotlib au niveau module : un diagnostic doit
│   │                            pouvoir réutiliser ses règles sans le venv
│   ├── edgewonk/
│   │   ├── api.py               auth, lecture, modify/PUT, images
│   │   ├── appariement.py       jambe ↔ trade (UTC, minute, départages) + rattraper()
│   │   │                        pour le changement d'heure — branché sur la poussée
│   │   └── ecriture.py          le plan, CHAMPS_ECRITS (la source du menu), les deux
│   │                            modes, break-even, paliers, images, relecture
│   └── outils/                  LES DIAGNOSTICS PERMANENTS — voir §5
│
├── archives/
│   ├── CATALOGUE.md             ⭐ ce que chaque outil archivé a TRANCHÉ. À lire avant
│   │                            d'écrire un nouveau diagnostic
│   ├── mesures/                 les mesures déjà faites (fuseaux, API, coûts)
│   ├── orchestrateurs/          sync.py et futures.sh, remplacés par journal.py
│   └── retroactif/              le chantier d'historique, sa base fusionnée le 28/08
│
└── donnees/
    ├── trades.csv               LA base — 241 jambes, les deux plateformes
    ├── brut/                    exports archivés, jamais modifiés
    ├── saisies/                 LA saisie en cours, seule dans le dossier
    │   └── _traites/            celles déjà intégrées, horodatées
    ├── instantanes/             un avant chaque écriture, local et Edgewonk
    ├── bougies/                 cache Databento, par journée
    ├── controles/               sorties CSV des diagnostics
    └── graphiques/              4 PNG par position + `rendu.txt`, la signature
                                 des données qui ont servi au dessin
```

**Le découpage suit les FRONTIÈRES DE RISQUE, pas les fonctions.** `core/` ne dépend de
rien et ne connaît aucun format externe. `ctrader/` et `tradovate/` lisent des sources
qu'on ne contrôle pas. `edgewonk/` parle à une API interne, non publique, qui cassera un
jour — et ce jour-là, un seul dossier bouge. Tout ce qui touche à l'apparence vit dans
`pipeline/graphiques/`.

**Une seule base depuis le 28/08/2026.** Le chantier rétroactif avait la sienne ; elle a
été fusionnée (241 jambes, aucune collision de clé) et le projet archivé. Ses deux règles
propres n'ont pas été perdues : E1 est devenue le mode « ne remplir que le vide », et le
repêchage du changement d'heure a été branché sur la poussée. *Une règle qu'on peut
demander n'a plus besoin d'un projet à elle.*

**Les diagnostics ne sont pas du décor.** Chacun a été écrit pour trancher une question
*avant* d'écrire du code, et chacun a renversé une supposition. Ceux qui ont fini leur
travail sont dans `archives/mesures/`, avec leur conclusion dans le `CATALOGUE.md` — on
lit la fiche, pas les fichiers.

---

## 13. Vocabulaire Edgewonk

- **Setup** — la stratégie du trade, avec sa **checklist** de critères à cocher.
- **Custom stats** — les étiquettes libres de l'utilisateur, groupées (Entry, Setup TF,
  Mistakes…).
- **Stratégies alternatives** — « qu'aurais-je gagné en tenant jusqu'à 2R, 3R, 5R ? ».
  **Leurs identifiants sont propres à chaque setup ET à chaque journal** : ne jamais les
  coder en dur, les résoudre par nom.
- **`originalTpHit`** — le prix a-t-il touché la cible avant le stop, indépendamment de la
  sortie réelle. Edgewonk ne peut pas le calculer : il n'a pas les données de prix. Nous, si.
- **`ignoreForWinrate`** — exclut le trade du win rate en le comptant comme nul.
- **`inReview`** — ⚠️ **c'est l'étoile « favori » de l'interface**, pas un état de revue.
  *(Constaté le 26/08/2026 : les deux seuls trades étoilés du journal futures sont
  exactement les deux que le pipeline avait marqués.)* Le §9 s'en servait pour rendre visible
  un trade aux prix d'exécution divergents — mais c'est **le marque-page de l'utilisateur** qu'on
  écrit, pas un champ technique. À ne pas utiliser sans son accord.
- **`managementComments`** — la famille de commentaires « Management », deux options chez
  L'utilisateur : **Not managed** (id 826040, rating POSITIVE) et **Managed** (826044,
  NEGATIVE). Les identifiants sont notés ici pour la lecture ; le code les résout **par
  nom** depuis `GET /databases/{db}/comments`, jamais en dur.
- **`scalings` / `fineScalings`** — les jambes agrégées au VWAP, et le détail de chaque
  exécution.

**⚠️ Le bac à sable `100005` n'existe plus.** *(Constaté le 26/08/2026 —
`archives/mesures/diag_journaux.py`.)* `GET /databases` ne liste que trois journaux :

| journal | trades | période | futures | Management |
|---|---|---|---|---|
| **100001** « Compte A » | 240 | 15/10/2025 → 26/08/2026 | **36** | `Not managed` / `Managed` |
| 100004 « Compte B » | 34 | 06/08 → 21/08 | 34 | `Followed rules` / `Broke rules` |
| 100006 « [all] Missed trades » | 14 | — | 0 | — |

**Les deux plateformes visent 100001.** Les futures y sont aussi, et plus à jour que dans
100004 — l'auto-import Tradovate a été rebranché dessus. 100004 en garde 34 copies (aucun
identifiant commun) qu'on n'alimente pas. Et comme 100001 porte les bons libellés
Management, le repli par rating ne se déclenche plus.

Il n'y a donc plus de journal jetable à viser : `--base <id>` reste disponible, mais le
garde-fou est ailleurs — instantané avant écriture, relecture après. Le cloisonnement, lui,
reste structurel : l'identifiant figure dans l'URL de chaque appel.

**Le catalogue des commentaires n'était documenté nulle part** — ni dans `docs/edgewonk-api.md`
§7, ni ailleurs. Onze URL plausibles ont été sondées : **dix rendent 403, pas 404**.
L'API refuse de dire ce qui n'existe pas, donc seule une sonde exhaustive tranche. Retenir
la méthode autant que le résultat : `archives/mesures/diag_commentaires.py` se relance le jour où un
autre catalogue manquera.

---

## 14. Travailler avec l'utilisateur

- Il tranche vite et **accepte le désaccord argumenté** — une recommandation nette avec sa
  raison vaut mieux qu'un éventail d'options.
- Ce qu'il n'accepte pas : le délayage, la sophistication gratuite, et les propositions
  qui ne remplissent aucun champ du livrable.
- Il demande de **mesurer plutôt que supposer**. Plusieurs certitudes de ce projet se sont
  révélées fausses au test — y compris des affirmations de sa part, qu'il a lui-même
  demandé de vérifier plutôt que de croire.
- Il arbitre volontiers **contre** l'automatisation quand elle coûte plus qu'elle ne
  rapporte. La saisie manuelle du SL/TP vient de lui, et c'était le bon appel.
- Les documents disent systématiquement **ce qui a été mesuré** et ce qui reste supposé.
  Respecter cette distinction en les modifiant.

---
