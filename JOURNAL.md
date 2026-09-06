# Journal des révisions

**Ce fichier n'explique pas comment l'outil marche — le `README.md` le fait.**
Il dit *pourquoi* chaque règle existe, et surtout ce qui a été essayé, mesuré et
abandonné. C'est ce qui empêche de refaire un chemin déjà parcouru.

Sorti du README le 28/08/2026 : 911 lignes d'histoire entre le lecteur et la
réponse à « qu'est-ce que cet outil fait ». Les décisions figées, elles, restent
dans le README — ce sont des règles actives, pas de l'histoire.

À lire quand : une règle paraît absurde, une mesure semble à refaire, ou une
idée « évidente » se présente. Il y a de bonnes chances qu'elle soit ici, avec
la raison pour laquelle elle a été écartée.

---

**29/08/2026 — le management gagne un second contrôle, et il est asymétrique.**

L'utilisateur a nommé l'angle mort de sa propre saisie : il peut n'avoir touché ni son stop ni
sa cible — donc saisir OK — **et avoir quand même fermé la position avant qu'un niveau soit
atteint**. Sa question est « ai-je touché à mes ordres » ; celle du contrôle est « suis-je
sorti dessus ». Les deux ne se déduisent pas l'une de l'autre, et c'est ce qui rend le
second contrôle utile plutôt que redondant.

**La distance absolue ne sépare rien.** Mesure sur 184 positions : 29 sorties tombent
exactement sur un niveau (0,000000 R), puis c'est un **continuum sans trou** jusqu'à 1 R et
au-delà. Aucun buffer symétrique ne se dégage — ce qui aurait mené à en choisir un
arbitrairement, donc à trancher au hasard.

**C'est le SIGNE qui tranche, et il vient de la mécanique des ordres.** Une limite se
remplit à son prix ou mieux, jamais moins bien ; un stop à son prix ou pire — c'est le
slippage. Vérifié : près du TP, 4 sorties exactement dessus, 4 meilleures, **2 moins
bonnes** — ces 2-là ne sont donc pas des fills. Près du SL, 25 exactement dessus, 52 moins
bonnes (attendu), **7 meilleures** — pas des fills non plus. Borne de slippage à 0,25 R, le
pire mesuré valant 0,2355.

**Trois garde-fous, chacun pour une raison mesurée :**

- *le contrôle ne peut qu'accuser* — un KO saisi reste KO, l'utilisateur a vu dans ses logs ce
  que la sortie ne montre pas ;
- *il juge la jambe réellement tenue* — un allègement sort au marché par définition, et le
  contrôler ferait basculer toute position sortie en plusieurs fois. L'utilisateur l'a dit :
  alléger parce qu'on est entré trop lourd n'est pas du management ;
- *sans niveau, il se tait* — 4 positions n'ont ni stop ni cible ; un contrôle aveugle qui
  accuserait serait pire qu'un contrôle absent.

**Impact mesuré : 19 positions passent de OK à KO**, 26 sont confirmées, 4 restent non
vérifiables. La règle attrape le MCL du 14/08 et le MGCV6 du 17/08 — deux trades dont on
avait établi *par un autre chemin*, des heures plus tôt, qu'ils avaient été fermés à la
main. Deux confirmations indépendantes valent mieux qu'une démonstration.

**Et le jeu d'essai a attrapé une inversion de signe** dans la branche TP : « sortie
meilleure que la cible » ressortait en KO et « moins bonne » en OK, exactement à l'envers.
La branche SL, elle, était juste — ce qui rendait l'erreur invisible sur la moitié des cas,
et l'aurait laissée passer sans les seize cas achat ET vente.

---

**29/08/2026 — deux bornes : la période, et le journal.**

**La période.** Un diagnostic global sur 241 jambes noie le cas qu'on cherche ; un import
global re-touche des trades qu'on ne voulait pas toucher. La borne réduit le bruit **et**
la surface d'erreur.

*Le lecteur ne coupe pas sur le tiret, il extrait les dates.* « 2026-08-06 » contient deux
tirets et n'est pourtant qu'une seule date : découper dessus donnerait trois morceaux
illisibles. On cherche les **motifs** de date, et leur nombre dit ce qu'on a — une, ou
deux. C'est aussi ce qui rend le séparateur libre. La désambiguïsation JJMMAAAA / AAAAMMJJ
se fait par un contrôle de vraisemblance : `20260806` lu en JJMMAAAA donnerait le mois 26,
donc c'est l'autre lecture.

*Elle borne sur l'OUVERTURE, jamais sur la clôture.* Un trade ouvert le 6 et fermé le 9
appartient au 6 — c'est le jour de la décision, et celui que l'utilisateur a en tête quand il
dit « la journée du 6 ». Filtrer sur la clôture le ferait disparaître de sa propre journée.

*Et elle ne borne pas l'import du relevé.* Le fichier contient ce qu'il contient ; en
écarter des lignes produirait une base trouée qu'aucun cycle ne viendrait combler. Deux
jeux de drapeaux dans l'orchestrateur, explicitement séparés.

**Le journal.** La liste est **lue** chez Edgewonk (`GET /databases`), jamais codée en dur.
L'utilisateur crée et supprime des journaux — un bac à sable est apparu ce jour-là, le
« Compte B » avait disparu avant. Une liste en dur aurait raison le jour où elle est
écrite et tort ensuite, en silence. Si l'appel échoue, on retombe sur le journal configuré
plutôt que d'empêcher de travailler.

`diag_doublons` portait `BASE = "100001"` en dur : chercher des doublons dans le mauvais
journal donnerait une réponse **juste sur les mauvaises données** — la forme d'erreur la
plus difficile à voir.

**Un seul lecteur pour les deux, dans `core/base.options_ligne`.** Huit outils, une
syntaxe. C'est la même règle que `CHAMPS_ECRITS` pour les champs : une source, donc pas de
dérive entre ce que l'orchestrateur propose et ce que l'outil accepte.

---

**29/08/2026 — le premier audit COMPLET, et ce qu'il a trouvé sous les outils.**

Le contrôle le plus fort est passé : `diag_tp_first`, la **seconde implémentation** du
TP-first, recalculée depuis les bougies sans rien emprunter à la première —
**146 jambes croisées, 0 désaccord, 0 indéterminé**. C'est la meilleure affirmation
possible sur les mesures, et elle n'avait jamais été faite sur la base fusionnée.

Deux outils sont tombés, et les deux échecs valaient leur poids.

**Le garde-fou d'hier a servi le jour même.** Au lieu de `'str' object has no attribute
'get'` après 120 jambes, le message a dit : `Symbol not available: MNQU6`, avec le symbole
et la fenêtre. La cause a sauté aux yeux — `diag_bougies` demandait un symbole **futures**
au serveur **cTrader**. La fusion des bases avait mis les deux plateformes dans le même
fichier, et ce module sonde le MCP cTrader : il ne peut parler que de cTrader. *Le bon
réflexe n'est pas de tolérer l'erreur, c'est de ne pas poser la question* — un filtre de
plateforme, plus une exception rattrapée pour qu'un symbole ne fasse jamais tomber le lot.

**`diag_bord` appelait `bougies._borne()`, renommée en `_decouper` depuis des jours.** Le
module était cassé, et personne ne l'avait vu **parce qu'il n'était jamais lancé**. C'est
exactement ce qu'un orchestrateur d'audit sert à révéler : *un outil qu'on ne lance pas ne
vieillit pas, il pourrit.* Et le renommage n'était pas cosmétique — `_decouper` rend deux
listes là où `_borne` en rendait une : les bougies **intérieures** et celles de **bord**,
la distinction même que ce module existe pour examiner.

**Contrôle statique ajouté au passage** : aucun appel vers une fonction absente de
`bougies` dans les 13 outils, `jt.py`, `journal.py` et `rendu.py`. Zéro.

---

**28/08/2026, le premier audit global — il a trouvé trois défauts, tous dans les outils.**

C'était le but. Un audit qui ne trouve rien le premier jour n'audite pas.

**1. Le MCP a répondu en prose, et ce texte a voyagé 300 lignes.** `mcp.appeler` rend le
texte brut quand la charge utile n'est pas du JSON — c'est-à-dire quand le serveur répond
par un message plutôt que par des données. `bougies.recuperer` faisait `(reponse or {}).get`
dessus : plantage sur `'str' object has no attribute 'get'`, après 120 jambes, sans dire ni
quel symbole, ni quelle fenêtre, ni ce que le serveur avait répondu. Le garde nomme
maintenant les trois. *Un `or {}` protège contre `None` et laisse passer tout le reste — il
donne l'apparence d'une précaution sans en être une.*

L'exception est définie **dans `bougies.py`**, pas importée : ce module est générique, il
sert cTrader et Databento, et dépendre de l'exception de l'un des deux le lierait à lui.

**2. `diag_ecarts` lisait le dernier export du dossier — devenu un export Tradovate.**
`KeyError: 'Symbol'`, sans dire quel fichier. Il cherche désormais le dernier fichier qui
*porte les colonnes attendues*. Et comme il est figé sur deux positions du 14/08, c'est une
mesure et non un instrument : archivé.

**3. Un audit qui vomit ses traces est un audit qu'on cesse de lancer.** Trois outils sur
huit sont tombés, et leurs soixante lignes de trace ont noyé les résultats des cinq autres.
Trois changements : la sonde MCP est faite **une fois** avant le lot, et les outils qui en
dépendent sont *sautés* avec une phrase au lieu d'échouer trois fois ; les traces
d'exécution ne s'affichent plus, elles sont **traduites** (« cTrader n'est pas ouvert »,
« identifiants absents du trousseau ») ; et l'audit finit par un **résumé** qui compte les
lancés, les échoués et les sautés.

**5. Et mon propre filtre anti-trace masquait les commandes à taper.** Première version :
cacher toute ligne commençant par quatre espaces. `diag_images` annonçait « pour rendre ces
jambes éligibles : » suivi de **rien**. *Un filtre qui se fie à l'indentation ne distingue
pas une erreur d'une instruction.* Une trace a une forme, pas une indentation :
`Traceback` ouvre le bloc, les lignes indentées le composent, et la première ligne non
indentée le ferme — c'est le type de l'exception, la seule qui vaille d'être montrée. On
garde celle-là, on jette le reste.

**4. Et « réparable » n'était pas tout ou rien.** `20260817-091714-MGCQ6-A` a ses quatre
emplacements vides chez Edgewonk et deux PNG sur le disque — M5 et M15 ne seront jamais
rendus, le contrat était quasi mort à cette date. Il tombait dans « à rendre d'abord »,
donc personne ne renvoyait les deux images qu'on avait, et le trade restait sans **aucune**
capture. *Refuser une réparation partielle, c'est préférer zéro image à deux.*

---

**28/08/2026, la refonte — de 56 fichiers à 39, et de deux orchestrateurs à un.**

L'état des lieux avait sorti trois constats. Les trois ont été traités le jour même.

**Une seule base.** Le chantier rétroactif avait la sienne. Quatre contrôles avant
d'écrire une ligne : mêmes 28 colonnes dans le même ordre, **zéro** collision de clé,
**zéro** collision de dossier d'images, rétroactif mono-plateforme. Aucune n'était garantie
d'avance ; toutes ont été vérifiées, et `fusionner_bases.py` refuse de fusionner si l'une
tombe. 84 + 157 = **241 jambes**, 826 PNG, zéro chemin cassé. Les images ont été **copiées
et non déplacées** : tant que la fusion n'est pas vérifiée, la source doit rester lisible.

**Ses deux règles propres n'ont pas été perdues, elles ont été généralisées.** E1 — ne
jamais recouvrir une capture posée à la main — devient le mode « ne remplir que le vide »,
disponible sur les neuf champs et plus seulement sur les images. Et le repêchage du
changement d'heure a été **branché sur la poussée de production**, où il ne l'était pas.
*Une règle qu'on peut demander n'a plus besoin d'un projet à elle.*

**Le repêchage du changement d'heure n'était branché nulle part.** Huit diagnostics
l'appelaient, `retro.py` l'appelait, `jt.pousser` et `sync.etape5` non. La règle avait été
déplacée dans `appariement.py` le matin même *pour servir la production* — le déplacement
fait, le branchement oublié. Prouvé par un test qui fabrique le cas d'octobre : un faux
journal où la sortie d'un trade est décalée d'une heure. Avant, « non trouvé » ; après,
**repêché 1, non trouvés 0**. La nuance qui décide : l'erreur vient de **leur**
importateur, pas de nos exports — la vigilance à l'import ne l'évite pas.

**Un seul orchestrateur.** `sync.py` (898 lignes) et `jt.py` (633) implémentaient
séparément les mêmes cinq étapes. Divergence mesurée : `jt.py` savait redessiner les
graphiques, `sync.py` non — et `sync.py` était celui que Raycast lançait tous les jours.
`journal.py` ne réimplémente rien : il pose les questions et appelle `jt.py`. *L'interface
et le moteur sont deux métiers ; les mélanger est exactement ce qui a produit les 1 531
lignes qu'on remplace.* Les trois conforts de `sync.py` ont été portés, pas perdus :
trouver le relevé dans `IMPORT/`, ouvrir la saisie dans le Finder, ranger les exports
traités.

**Les deux modes d'écriture, et la subtilité qui les rend justes.** En mode « vide », un
booléen à `False` **n'est pas vide** : une case décochée est un état, pas une absence. Le
traiter comme vide reviendrait à écraser en mode non-écrasant — exactement ce que le mode
promet d'éviter. Un prix à `0.0`, lui, *est* vide : la mesure du matin avait montré des
`slPrice` à zéro venant de leur import, qui ne sont pas des stops. Le filtre est appliqué
**en un seul endroit**, en bout de chaîne, plutôt que dans chacune des neuf branches qui
construisent le plan : les règles métier restent lisibles, et le mode ne peut pas être
oublié sur un champ ajouté plus tard.

Preuve chiffrée sur les images, le cas où une erreur détruirait des captures :
**écraser → 688 images** (4 par trade, dont les emplacements 1 et 2 de l'utilisateur),
**vide → 344** (2 par trade, les siens intacts).

**Un bug d'affichage que seul un log révèle.** `journal.py` écrivait ses questions dans un
tampon pendant que le sous-processus écrivait en direct. Dans un terminal, tout paraît
normal. Redirigé dans un fichier — ce que fait un log de diagnostic — l'ordre s'inverse et
les réponses arrivent avant les questions. *Un log qui ment sur l'ordre des événements est
pire qu'un log absent : c'est celui qu'on lira le jour d'un incident.*

**La documentation, à chaque étape et pas à la fin.** Le journal des révisions est sorti du
README (911 lignes d'histoire entre le lecteur et « qu'est-ce que cet outil fait »).
`archives/CATALOGUE.md` dit ce que chaque outil archivé a tranché — on lit la fiche, pas
les fichiers. Les 13 chemins du README qui pointaient vers des outils déplacés ont été
redressés : *un README qui envoie vers des fichiers absents est la pire forme de
documentation.* Et les deux affirmations périmées — l'union-find de la segmentation
Tradovate, les SL/TP réservés aux entrées ATM — sont marquées comme renversées plutôt que
supprimées : ce qui a été cru compte autant que ce qui est vrai.

---

**28/08/2026 — « 0 image à téléverser » alors qu'il y en avait 16.** Le quatrième bug de
la même famille, et le plus instructif.

Après avoir effacé les marqueurs des 8 trades dont l'utilisateur avait supprimé M5 et M15 à la
main, `retro.py pousser --mois 2026-08` répondait **`0 trade(s) à modifier, 0 image(s)`**.
Les marqueurs étaient bien vides, les PNG bien sur le disque (4/4), les emplacements 1 et 2
bien libres chez Edgewonk. Tout était juste, et rien ne partait.

`ecriture.preparer` n'ajoute une entrée de plan que si `modify or put or images` — et le
chantier rétroactif l'appelle avec `dossier_racine=None`, **exprès**, pour qu'elle ne
planifie aucune image : la règle E1 les recalcule ensuite, en n'écrivant que dans les
emplacements vides. Mais la boucle qui applique E1 parcourt `plans`. Un trade poussé le
26/08, dont tous les champs sont donc déjà justes, sort de `preparer` sans entrée : **E1 ne
pouvait corriger les images que des trades ayant par ailleurs un champ à écrire.**

*Un filtre en amont qui rend un contrôle en aval inatteignable — c'est le quatrième
aujourd'hui, après les graphiques périmés, les images supprimées et le marquage à 2/4. La
signature est toujours la même : deux étapes justes séparément, dont la seconde ne voit
jamais les cas que la première a écartés.*

**Et le correctif du marquage a dû être repris pour ne pas casser E1.** Comparer les
images confirmées à `len(EMPLACEMENTS)` refusait de marquer un envoi E1 — légitimement
partiel, puisqu'il épargne les captures de l'utilisateur — et ces 8 trades seraient repartis à
chaque poussée, indéfiniment. Comparer à `len(p["images"])` acceptait tout, y compris un
rendu incomplet. **La bonne question n'est ni l'une ni l'autre : « les quatre emplacements
sont-ils occupés MAINTENANT ? »** — la relecture est déjà faite, la réponse est gratuite,
et elle distingue les deux cas au lieu de les confondre.

---

**28/08/2026 — effacer un niveau n'est pas vider une case.** `outils/oublier.py`.

Le stop de `20260814-170626-NAS100-V` — vente à 30040,35, stop saisi à 30040,80, soit
**0,45 point de risque sur du NAS100 et +181 R réalisés** — était sur le point de partir
chez Edgewonk. La saisie l'avait pourtant signalé comme R aberrant ; le signalement a été
acquitté, et la valeur est restée. *Un signalement acquitté n'est pas un signalement
résolu.*

Un SL n'est pas une donnée isolée, c'est la racine d'un arbre. Vider la colonne `sl` en
laissant le reste produit un état **pire que l'erreur d'origine** : des valeurs justes en
apparence, calculées depuis un stop qui n'existe plus, qu'aucun cycle ne recalculera
puisqu'elles sont remplies. Ce qui en descend :

| colonne | pourquoi elle tombe avec |
|---|---|
| `prix_max_favorable` | la simulation des paliers part du stop |
| `tp_touche_en_premier` | « le TP avant le stop » n'a pas de sens sans stop |
| `chemin_graphiques` | le gabarit trace le SL en pointillés — et vide, la position repasse à l'étape 4 |
| `screenshots` | ce sont ces PNG-là, déjà chez Edgewonk — et vide, elle repasse à l'étape 5 |

Les deux dernières ne sont pas des données mais des **marqueurs de reprise** : les vider
suffit à faire reconstruire le reste par le cycle normal, sans niveau cette fois, et sans
toucher aux 74 autres positions.

**On efface, on ne corrige pas.** Absent, le trade sort des statistiques de R (règle R7) ;
faux, il produit du R ayant l'apparence du juste. Pour *remettre* un niveau, le chemin
reste le fichier de saisie et `jt.py integrer` — une seule autorité.

⚠️ **Edgewonk garde le sien** : un champ vide chez nous n'est jamais poussé. À supprimer à
la main dans leur interface.

---

**28/08/2026, le passage en réel du diagnostic d'images — trois défauts, dont deux à moi.**

**1. Un trade rendu en 2 timeframes sur 4 était marqué « fait ».** `envoyer_images`
comparait `len(poses)` à `len(p["images"])` — le nombre de PNG **présents sur le disque**,
pas quatre. Le commentaire juste au-dessus disait pourtant, depuis le 25/08 et en toutes
lettres, « on ne marque le trade QUE si les quatre images sont passées », et décrivait le
trou définitif et silencieux que la comparaison laissait ouvert. *Le commentaire était
juste, le code disait autre chose, et personne ne les avait relus ensemble.* Mesuré sur
`20260817-091714-MGCQ6-A`, marqué complet avec H1 et H4 seuls, M5 et M15 jamais rendus
faute de bougies. Conséquence assumée du correctif : tant que les 4 PNG n'existent pas, le
trade repart à chaque poussée — bruyant, voulu, et nommé par `diag_images`.

**2. Mon diagnostic comptait les allègements comme des trous.** Décision du 25/08
(`graphiques/rendu`, §4) : seule la jambe **réellement tenue** reçoit les captures, un
allègement ne représente aucune décision. Première version de `diag_images` : les 35
allègements tombaient dans « à rendre d'abord », **noyant l'unique vraie anomalie sous 34
fausses**. C'est la faute que ce README documente le plus souvent, et je venais de la
refaire.

**3. Et une branche jamais exécutée par son propre test.** `diag_images` a planté en réel
sur le bloc « chez eux, pas chez nous » — sept valeurs attendues, deux fournies. Le jeu
d'essai fabriquait le faux journal **depuis nos jambes** : il ne pouvait produire aucun
orphelin, donc la branche n'avait jamais tourné. *Un jeu d'essai dérivé des données saines
ne teste que les chemins sains.*

**4. Et le correctif du point 2 a raté une fois avant de passer.** J'ai descendu l'import
de `gabarit` dans la fonction qui dessine, vérifié que `rendu` s'importait — il s'importait
— et livré. Il s'importait parce que **mon** environnement de test a pandas ; celui de
L'utilisateur ne l'a pas, et `rendu` l'importait aussi. *Un import vérifié ailleurs que là où il
tourne n'est pas vérifié.* Le contrôle est désormais explicite : les 23 outils de
`outils/` sont importés avec `pandas`, `numpy`, `matplotlib` et `mplfinance` **bloqués par
un `meta_path`**, ce qui teste la seule propriété qui compte — un diagnostic en lecture
seule tourne avec la bibliothèque standard seule.

**Effet de bord utile :** `graphiques/rendu` n'importe plus `gabarit` ni `pandas` au niveau module.
Il portait les règles de décision — `jambes_de_position`, `jambe_reelle` — derrière un
import de matplotlib, donc inaccessibles hors du venv ; la seule issue était de recopier
« quelle jambe est la vraie » ailleurs, c'est-à-dire de garantir qu'un jour les deux
copies divergent.

**État mesuré des images :** 205 jambes tenues complètes (4/4), 35 allègements sans image
par conception, **1** réellement incomplète.

---

**28/08/2026, fin de journée — deux angles morts du même genre, trouvés en une heure.**

**1. Un SL qui arrive rend les graphiques périmés, en silence.** Le gabarit trace le SL et
le TP en pointillés, or `graphiques` saute toute position dont les PNG sont déjà sur le
disque. Les 24 positions qui venaient de gagner leurs niveaux gardaient donc des images
*sans ces lignes* — justes la semaine dernière, fausses aujourd'hui, et rien ne le disait.
`futures.sh` redessine désormais dès que l'intégration a écrit quelque chose.

**2. Une image supprimée chez Edgewonk ne revient jamais.** Même forme exacte : notre
marqueur `screenshots` dit « envoyé », l'emplacement est vide chez eux, personne ne
compare. `outils/diag_images.py` compare, et `--reparer` efface le marqueur pour rendre la
jambe éligible au prochain téléversement.

*Les deux bugs ont la même signature : un cache local qui fait autorité sur un état distant
qu'il ne relit jamais. La règle « la base locale fait foi » reste bonne — ce qui manquait
est le vérificateur qui la confronte, de temps en temps, à ce qu'Edgewonk porte vraiment.*

**Et un troisième, dans le lanceur lui-même :** `futures.sh` appelait `python3` au lieu de
`../.venv/bin/python3`. Les quatre premières étapes passaient, la cinquième mourait sur
`No module named 'pandas'`. Mourir à l'avant-dernière étape est la pire façon de rater :
tout est écrit, rien n'est visible.

---

**28/08/2026, suite — le trou n'était pas dans l'export, il était dans notre lecteur.**

Le paragraphe ci-dessous conclut « c'est un trou de données ». **C'est faux, et
c'est la conclusion qui m'a servi à expliquer trois fois de suite un champ vide.**
L'export `Orders` porte bel et bien les stops et les cibles de ces trades — sous
`Text = Chart` au lieu de `multibracket`. Le MCL du 14/08 : `Stop Buy 82.69` posé
à 11:01, la minute d'entrée, et `Limit Buy 81.48` à 11:10. `protections.py` les
ignorait **par décision**, et la décision était argumentée (§ en-tête du module) :
un « Buy Stop » au-dessus d'un short peut être une protection large ou une entrée
en cassure, rien ne tranche.

Il manquait deux contraintes que l'ordre pris isolément ne porte pas : le **côté**
(une entrée ouvre, une protection ferme) et la **fenêtre** (une protection vit
entre l'ouverture de sa position et l'ouverture de la suivante sur le même
contrat). Avec les deux, le premier `Stop` du côté de fermeture est le SL initial.
**Trois mesures, dans cet ordre :**

| mesure | résultat |
|---|---|
| ordres de protection ayant réellement fermé une position | **20 / 22** retombent au tick près sur notre prix de sortie ; les 2 écarts sont des sorties partielles au VWAP |
| positions ATM déjà en base | **6 / 6** identiques — la règle par fenêtre *subsume* la lecture par ids, elle ne la concurrence pas |
| positions `Chart` du journal | **15 / 18** identiques à Edgewonk, **3 différentes — les 3 où Edgewonk se trompe** |

Les trois erreurs d'Edgewonk ont la même cause, et c'est celle que les deux
contraintes corrigent : il a lu l'ordre d'**entrée** comme une cible
(`20260807-160834`, TP 29645,5 ; `20260818-144959`, TP 1,1589) et un `Limit` du
**lendemain** comme la cible d'un trade de la veille (`20260817-154744`,
TP 4380,2). *Leçon : « rien ne tranche » voulait dire « rien dans l'ordre pris
isolément » — le contexte, lui, tranchait.*

**Effet : 7 positions futures sur 35 avaient un SL/TP, elles sont 31.** Import
rejoué sur copie avant de toucher au réel : 84 jambes avant, 84 après, 24 jambes
complétées, **zéro valeur existante écrasée**, `management` intact. Ce qui sort
du lecteur reste une SUGGESTION relue dans le fichier de saisie — la règle §9 ne
bouge pas.

**⚠️ Et l'export contredit le champ `management` sur 6 positions.** Sept ont un
stop déplacé au-delà du délai d'ajustement (82,69 → 82,43 à +34 min sur le MCL ;
30210,75 → 30234,75 à +117 min sur le MNQ du 14/08) ; six d'entre elles sont
saisies `OK`. Le champ est à l'utilisateur et le code n'y touche pas — mais il le
remplit de mémoire, et l'export, lui, se souvient. Le signalement dit lequel des
deux est en cause, sans trancher.

**Un signalement trop bavard, attrapé à temps.** Première version du détecteur :
« premier stop ≠ dernier stop » → 10 positions signalées sur 32, dont des
micro-ajustements de la première minute (30210,75 → 30210,25 → 30209,75 en 14
minutes, trois états pour un seul stop qu'on pose). Il faut **les deux** marques
— un état posé au-delà du délai d'ajustement **et** un prix différent du premier
— pour parler de management : 10 signalements deviennent 7. *Troisième fois que
ce module se fait avoir de la même façon : un signalement qui se déclenche sur du
sain dresse à ignorer les signalements.*

---

**28/08/2026 — le champ vide n'était pas un bug, et la question posée n'était pas la bonne.**

L'utilisateur voit dans son journal des trades avec un SL, un TP, et **aucune réponse TP/SL
first**. `diag_coherence` en compte 18, tous des futures. La cause est un trou de données,
pas un calcul raté : ce sont des entrées posées au graphique **avant le passage aux brackets
ATM du 18/08**, sans ordre stop lisible dans l'export. Notre base n'a donc aucun niveau, et
le pipeline ne calcule le TP-first que s'il en a deux. **Les niveaux affichés dans Edgewonk
sont les leurs, issus de leur propre import.**

**Le trade `17926446` (MCL du 14/08) a servi de cas d'école, et il a renversé la prémisse.**
L'utilisateur le pensait sorti sur un niveau touché rapidement. Mesure : plus haut `82,53` contre
un SL à `82,69`, plus bas `82,02` contre un TP à `81,48` — soit **2,1 R d'écart**. Ni l'un
ni l'autre n'a été effleuré, la sortie est manuelle à 38 minutes. Le vide était la bonne
réponse. *Leçon : avant d'expliquer pourquoi une valeur manque, vérifier qu'elle devrait
être là.*

**Deux formulations mesurées, exactes, et absurdes.** En construisant le jugement des
niveaux, deux phrases sont sorties telles quelles : « le SL n'a jamais été approché : il
restait 29564 (1.0 R) » sur un stop à `0.0`, et « c'est lui qui a fermé la position » sur un
niveau du mauvais côté de l'entrée. Les deux **habillaient une valeur d'import en protection
réelle**. Un niveau nul ou du mauvais côté n'a pas de distance qui veuille dire quelque
chose : `juger()` le déclare faux, puis se tait. Corollaire du même passage : `%.5g`
affichait `29404.5` en « 29404 », et le lecteur en concluait qu'un niveau n'avait pas été
atteint. Un prix se formate sans perdre de décimale.

**Un stop touché n'est pas un stop douteux quand c'est lui qui a fermé la position.** Sans
cette exception, tout trade sorti au stop — le cas normal — serait signalé. Le défaut
n'existe que si le prix a traversé le niveau et que la sortie s'est faite **mieux** que
lui : la position a alors survécu à sa propre protection.

**Le fichier de reprise contient tout le relevé, pas seulement les 18.** `jt.py controler`
borne son contrôle d'exhaustivité au relevé d'origine : un fichier partiel ferait signaler
comme « sans ligne de saisie » toutes les autres positions du même import. Les lignes déjà
renseignées sont pré-remplies depuis la base, donc les rendre ne coûte rien.

---

**26/08/2026, soir — les futures. La deuxième plateforme entre dans la chaîne.**

**Premier cycle complet, en réel : 35 jambes sur 35 appariées, zéro ambiguïté, 39 champs et
28 images confirmés par relecture, zéro divergence.** Les SL/TP que l'import Edgewonk avait
fabriqués sont écrasés par les nôtres. Le journal futures reçoit pour la première fois des
extrêmes, un TP-first, des paliers et des captures.

**⚠️ Un treizième : le repêchage du changement d'heure vivait dans le mauvais dossier.**
Le diagnostic corrigé a listé **6 trades « qui ne sortent d'aucune de nos bases »**. Cinq
d'entre eux y sont pourtant — dont celui du 31/03, présent sous la clé
`20260331-181419-EURUSD-A#234805`. Ils ne se retrouvaient pas parce que **Edgewonk a mal
résolu le changement d'heure du 29/03 sur leur horodatage de sortie**, et que la clé de
secours qui les repêche vivait dans `retroactif/retro.py`, sous le nom « écart E5 » — comme
si c'était une particularité du chantier d'historique.

C'en est une règle d'appariement : le changement d'heure revient deux fois par an, et **la
production traversera celui du 25/10/2026** exactement comme le chantier a traversé celui de
mars. `rattraper()` vit désormais dans `edgewonk/appariement.py`, et `diag_appariement`
l'applique — *un diagnostic qui ignore une règle que la production applique ne mesure pas la
production.* Vérifié hors ligne sur les 157 jambes du chantier avec les cinq sorties
décalées d'une heure : 152/157 par la clé standard, **157/157 après repêchage**.

**⚠️ Une série de bougies tronquée figeait des extrêmes sous-estimés.** Sur une intuition de
L'utilisateur — « la journée n'est pas terminée, Databento n'a peut-être pas tout ». Le trou est
réel et silencieux : une source s'arrête où son historique s'arrête (Databento borne la
journée en cours, ~12 minutes de retard sur l'horloge ; le MCP rend simplement ce qu'il a),
et `analyser` ne voit qu'une liste de bougies — une série tronquée lui **ressemble** à une
série complète. Il en tire un plus haut et un plus bas plausibles, et faux par défaut.

Le pire vient après : `prix_plus_haut` étant renseigné, la sélection ne reprend **jamais**
cette jambe. L'erreur se fige. Le contrôle est gratuit — la dernière bougie reçue doit
atteindre la clôture — et quand elle ne l'atteint pas, **rien n'est écrit** : la colonne
reste vide, la jambe repasse, et le signalement le dit.

**Verdict rendu — il ne manque aucun trade.** Sur les 243 du journal :

```
cTrader production      49
Tradovate futures       35
chantier rétroactif    157
doublon Edgewonk         1     16813784, jumeau de 17860473
segmentation à mesurer   1     17949360, le 6E du 26/08
                      ----
                       243
```

**`16813784` est un doublon côté Edgewonk**, pas un trou chez nous : il partage instrument,
sens, minute d'entrée, quantité **et** gain au centime avec `17860473`, qui est déjà
apparié. Le changement d'heure du 29/03 a fait entrer deux fois la même position à l'import.
⬜ À supprimer chez eux.

**Reste un seul vrai écart : le 6E du 26/08.** Edgewonk a créé un trade pour la partie
clôturée d'une position **encore ouverte** (2 contrats vendus, 1 racheté). Nous n'en
produisons aucune jambe, par la règle du passage à plat. ⬜ *Leur règle de segmentation
n'est donc pas exactement « flat-to-flat » : à mesurer quand cette position se refermera —
créent-ils un second trade, ou complètent-ils le premier ?*

**⚠️ Un douzième, et je l'ai introduit moi-même en corrigeant un angle mort.**
`diag_appariement` ne regardait que dans un sens — nos jambes sans trade. J'ai ajouté le
sens inverse, et la première version comparait les **49 jambes de production cTrader** aux
**243 trades du journal**, en annonçant « 194 orphelins ». Or ce journal porte **trois**
sources : le forex de production, les 35 futures, et les 157 trades du chantier rétroactif,
qui vit dans sa propre base. 49 + 35 + 157 = 241 — le vrai reste est **2**, la question que
L'utilisateur posait.

*Un compte d'orphelins qui ignore deux des trois sources n'est pas un contrôle : c'est du
bruit qui ressemble à une alerte.* Corrigé — les restants sont confrontés à toutes nos bases
avant conclusion, et la sortie ventile d'où vient chaque trade du journal. Vérifié hors
ligne sur un journal fabriqué depuis nos trois bases plus deux intrus : la ventilation rend
49 / 35 / 157 / **2**, et les deux restants sont bien les intrus.

**⚠️ Un onzième, et c'est le plus mensonger : la moitié du champ TP-first était inventée.**
Trouvé par l'utilisateur en relisant son journal, et tranché par leur propre infobulle :

> *« Ignore how you exited — just focus on which level the price hit first. »*

**La sortie n'entre donc pas dans la réponse.** Quand l'utilisateur coupe avant que l'un des deux
niveaux soit touché, la question reste ouverte, et c'est ce qui se passe **après** sa sortie
qui la tranche. Or le module répondait « SL first » dans ce cas, avec ce commentaire en
toutes lettres : « c'est bien "non" au sens d'Edgewonk, pas un trou ». C'était une
interprétation, écrite comme un fait.

Mesuré sur les 43 jambes qui ont un SL et un TP : **3 ont vraiment touché leur cible,
19 leur stop, et 21 n'ont touché ni l'un ni l'autre** pendant le trade. Ces 21 portaient un
« SL first » que rien ne justifiait — la moitié du champ.

Corrigé : `analyser` renvoie désormais `None` (« à résoudre plus loin ») au lieu de `non`,
et `simuler_tp_first` poursuit au-delà de la sortie avec les garde-fous des paliers — le
trou du week-end, un plafond, et **rien d'écrit** si ça ne se résout pas.

**`JOURS_MAX` passe de 10 à 180 jours, pour les deux champs.** *(28/08 : cinq positions
d'octobre-novembre 2025 repartaient « non résolues » à chaque passage.)* Ce plafond n'a
**jamais** été une décision d'analyse — le commentaire d'origine le dit lui-même : l'utilisateur
soutient que « dans tous les cas c'est soit le SL, soit le 5R, il y a toujours l'un des deux,
même si ça arrive un an après », et le plafond ne servait qu'à se protéger des bougies
*indisponibles*.

⚠️ **J'avais proposé de ne le monter que pour le TP-first**, en soutenant que « tenir une
position forex trois semaines n'est pas une stratégie alternative réaliste ». C'était une
justification inventée, et elle était fausse deux fois : elle contredisait la position de
L'utilisateur écrite au §9, et le raisonnement ne tient pas — **la simulation s'arrête au premier
des deux niveaux atteints**. Tenir la position avec son stop initial, ce n'est pas « tenir
trois semaines », c'est attendre que l'un des deux tombe. Si aucun n'était tombé en dix
jours, la position était simplement encore ouverte : on n'avait pas répondu, on avait coupé
la question.

*Les deux champs posent la même question — « et après, avec le stop initial, que se
passe-t-il ? » — donc ils partagent le même horizon.* Un seul `JOURS_MAX`, et il reste ce
qu'il a toujours été : un garde-fou qui ne fabrique jamais de valeur.
*C'est exactement la leçon du §9 sur les paliers — « la simulation continue APRÈS la sortie
réelle » — qu'un seul des deux champs avait apprise.*

**⚠️ Un dixième, trouvé par l'utilisateur en une phrase : les extrêmes n'ont jamais eu besoin
du SL.** L'étape 3 exigeait un SL pour tout. C'était un raccourci hérité de cTrader, où une
jambe sans SL est simplement une jambe pas encore saisie — le SL servait de marqueur
« prêt », pas de prérequis. Or **le plus haut et le plus bas entre l'entrée et la sortie sont
des faits**, lus dans les bougies ; ils alimentent `updraw` / `drawDown`, qui sont des PRIX.
La règle R7 — « pas de SL, pas de R » — porte sur les R-multiples, jamais sur le MAE/MFE. Et
un graphique n'a pas davantage besoin d'un stop : il montre ce qui s'est passé.

Ce qui exige vraiment un SL, et reste conditionné : `prix_max_favorable` et les paliers (une
simulation a besoin du stop), `tp_touche_en_premier` (« avant le stop » — sans stop, la
question n'a pas de sens), `ignoreForWinrate`, et le comptage des débordements de bord
(mesuré en R).

Conséquence immédiate : **28 positions futures** et une jambe forex, jusque-là sans extrêmes
et sans le moindre graphique, entrent dans la chaîne. *Elles n'ont pas de R, elles ont une
histoire.*

**⚠️ Un neuvième, et c'est celui qui a le plus coûté : 28 `management` saisis, jetés en
silence.** l'utilisateur avait rempli les 36 cases du fichier de saisie. Seules 7 sont arrivées
dans Edgewonk. Cause : dans `core/saisie.controler`, une ligne sans SL **ni** TP était
signalée puis abandonnée — `continue` — et le management partait avec. Invisible tant que le
pipeline ne servait que cTrader, où toute position saisie a un SL. Côté futures, 28 positions
sur 36 sont des entrées posées au graphique, donc sans protection lisible : leur management
n'a jamais été écrit.

*Le management est la seule saisie qu'aucune mesure ne peut retrouver après coup — c'est
même la raison pour laquelle une case vide est un REJET. La jeter parce qu'une AUTRE colonne
est vide était l'exact contraire de l'intention.* Corrigé : une ligne sans SL ni TP mais avec
un management est désormais valide, et n'écrit que le management.

⚠️ **Et ce défaut n'a été trouvé que parce que l'utilisateur a compté les lignes dans son
journal.** Le pipeline affichait « 8 positions prêtes à écrire » sur 36 lignes lues, et
personne — moi le premier — n'a tiqué. J'ai même expliqué l'écart par l'idempotence, sans le
vérifier : c'était faux, l'instantané Edgewonk montrait `managementComments = []` sur les
neuf trades. **Une déduction n'est pas une mesure.**

**⚠️ Un huitième : une écriture a effacé les 46 jambes cTrader.**
`jt.py pousser --tradovate` recevait une vue **filtrée** de la base — les 35 jambes
futures — dans la variable qu'il réécrit à la fin pour y poser la colonne `screenshots`.
Le fichier est donc reparti avec 35 lignes au lieu de 81. **L'instantané pris juste avant a
tout restauré, sans rien perdre** : c'est la première fois que la règle 3 du §8 servait pour
de bon, et elle a servi exactement comme prévu.

Mais un filet qui rattrape n'est pas un garde-fou qui empêche. **`base.ecrire` refuse
désormais toute écriture qui retirerait des jambes**, et le message pose la bonne question :
« écrit-on une vue filtrée au lieu de la base entière ? ». Retirer un trade est rare et
toujours délibéré — `suppression_attendue=True` le dit. *`sync.py` ne pouvait pas tomber
dedans : son étape 5 recharge la base avant d'écrire. C'est la façade qui était juste et le
verbe de débogage qui ne l'était pas — l'inverse de ce qu'on aurait parié.*

*Ce que le premier cycle a coûté en défauts trouvés : huit. Deux dans le client Databento,
deux dans le rendu, un dans la segmentation, un dans un diagnostic, un dans la cible, un
dans le verbe `pousser`. Aucun n'a laissé de trace fausse — les sept premiers sont tombés
avant d'écrire, le huitième a été défait par l'instantané. À chaque étape, quelque chose
comparait ce qu'on croyait à ce que les données disaient.*



**⚠️ Je visais le mauvais journal, et c'est l'utilisateur qui avait raison.** `tradovate.md` §5
désignait 100004 (« Compte B ») comme le journal des futures, et ce n'était pas une
invention : 34 trades y répondent, appariés au centime. Mais il en existe un autre.
`archives/mesures/diag_journaux.py`, écrit pour trancher plutôt que discuter, montre que **100001
porte 36 trades futures, jusqu'au 26/08**, là où 100004 s'arrête au 21/08 — et qu'aucun
identifiant n'est commun aux deux. Ce sont des **copies** : l'auto-import Tradovate a été
rebranché sur le journal principal, et 100004 est un vestige. Les deux plateformes visent
désormais 100001. *Ce paragraphe avait mesuré ce qu'il voyait, sur le seul journal qu'il
avait regardé — un échantillon d'un ne fait pas une règle non plus. Coût de l'erreur : nul,
aucune écriture n'avait été faite.*

**⚠️ Le repli par rating était mécaniquement juste et sémantiquement faux — et il disparaît
avec le bon journal.** Sur le journal
futures 100004, la famille Management contient `Followed rules` (POSITIVE) et `Broke rules`
(NEGATIVE) — les libellés Edgewonk par défaut, là où le journal forex a été renommé en
`Not managed` / `Managed`. Le repli désignait donc une option **unique et sans ambiguïté**,
et pourtant fausse : notre champ dit « ai-je touché à mon stop », pas « ai-je respecté mes
règles ». Un trade où l'utilisateur remonte son stop pour verrouiller un gain — décision saine —
serait étiqueté « Broke rules ». La note ne montrait qu'un identifiant, et le contresens
passait ; elle porte désormais **le libellé visé**. *Le tagging est le seul contenu du
système qui ne soit pas reproductible : c'est le dernier endroit où écrire au jugé.*

**Le délai d'ajustement du stop, mesuré — et le §7 tient.** L'export porte la dernière
mise à jour de chaque ordre : l'écart entre le remplissage de l'entrée et la dernière
modification de son stop dit combien de temps ce stop a continué de bouger. Sur les dix
brackets : **0, 0, 0, 0, 0, 1, 1, 8 minutes — et 186**. Neuf ajustements dans les huit
minutes, c'est-à-dire la routine que l'utilisateur décrit au §7 de `tradovate.md`, confirmée par
la mesure au lieu d'être crue. Et un seul hors norme : le trade que les **bougies** avaient
déjà dénoncé. *Deux méthodes indépendantes, le même trade.* `DELAI_AJUSTEMENT_MAX = 30`,
posé entre 8 et 186. Celui-là ne se contente pas de signaler : il **retire la proposition**
du fichier de saisie, parce qu'un stop mesuré comme faux, proposé avec un avertissement à
côté, se fait accepter par défaut — c'est exactement ce qui était arrivé à ce trade.

**⚠️ RENVERSÉ — la segmentation des futures. Un trade Edgewonk = UN PASSAGE À PLAT.**
`tradovate.md` §5 bis avait établi, sur deux cas, qu'un trade futures serait une
« composante connexe du graphe d'appariement ». Le premier appariement réel a produit le
contre-exemple : la position MGCV6 du 17/08 14:10 donne deux composantes là où Edgewonk n'en a fait **qu'un** trade, entrée au VWAP 4416,4.
Le passage à plat le prédit juste, et explique aussi les deux cas d'origine. **Le compte
tombe : 34 positions à plat avant le 22/08, 34 trades dans leur journal** — l'ancienne
règle en donnait 35. *Un échantillon de deux ne fait pas une règle : c'est le §8, règle 6,
et elle a survécu une journée.* Deux lignes périmées ont été retirées de la base, instantané
pris avant, aucune n'ayant jamais été poussée.

**Quatre défauts trouvés au premier cycle réel, tous dans les données.**

**Une position rendue à moitié était figée pour toujours.** Trois positions Tradovate ont
été enregistrées comme rendues avec 2 ou 3 images sur 4 — leur H4 tombait sur la journée en
cours. La colonne `chemin_graphiques` remplie les excluait de la sélection : sans
`--refaire` elles n'auraient **jamais** été recomplétées, et `--refaire` aurait tout
regénéré, y compris les positions saines. **C'est exactement le bug attrapé le 25/08 sur
l'envoi des captures** — une image échoue, les trois autres sont confirmées, le trade est
inscrit « fait ». Même forme, autre étape. `position_a_rendre` interroge désormais le
**disque** : le PNG est un artefact local, il en est sa propre référence, et le consulter
coûte un `os.path.exists`. Les trois positions repassent d'elles-mêmes, les 41 autres ne
bougent pas.

**Un sixième vérificateur qui mentait — et celui-là est un diagnostic.**
`diag_appariement.py` annonçait « exactement ce qui serait écrit » en n'inspectant que
quatre champs. Les `alternativeStrategies`, `ignoreForWinrate` et surtout
`managementComments` n'y apparaissaient pas — or sur les futures, le management est le seul
champ écrit pour la majorité des trades. Il appelle désormais `ecriture.preparer`, le
**même** constructeur de plan que `jt.py pousser` : ce qu'il montre est ce qui partirait,
par construction et non par ressemblance. *Un contrôle qui montre le tiers du plan en
annonçant le tout est pire qu'absent — il rassure.*

**Un cinquième vérificateur qui mentait.** Le rendu annonçait « 7 positions, 28 images »
avec 23 fichiers sur le disque : le total était un PRODUIT — positions × 4 — pas un
décompte. On compte les fichiers, et on dit combien étaient attendues quand les deux
diffèrent.


**La journée en cours faisait échouer la position du jour.** Databento ne tronque pas une
fenêtre qui dépasse son historique : il la **refuse**, en 422. Le cache à la journée
demandait donc la journée entière du jour courant, et un trade du 26/08 ressortait en
« échec » alors qu'il n'y avait simplement rien encore. Et le bord n'est pas « maintenant » :
mesuré à 18:12 UTC, l'historique s'arrêtait à 18:00 — se caler sur l'horloge locale aurait
échoué aussi, juste moins souvent. On lit donc le bord chez eux, une fois par session, et
une journée tronquée n'est jamais mise en cache : elle se complétera.

**Un trade ne survit pas à son propre stop — nouveau contrôle.** Si le prix a franchi le SL
saisi **avant** d'atteindre son extrême, et que le trade a pourtant continué, ce SL n'était
pas en place. Trouvé sur `20260820-140208-6EU6-A` : stop saisi à 4 pips, plus bas du trade
**1,9 R sous le stop**, position tenue trois heures de plus. C'est le seul contrôle qui
attrape un SL faux **sans** avoir besoin d'un R:R ni d'un |R| réalisé aberrants — les deux
filets qui existaient déjà, et que ce trade a franchis. `R_SIMULATION_INCOHERENTE = 0.50`,
calibré sur 50 jambes des deux plateformes : deux déclenchent, à 2,9 R et 202 R, toutes
deux réelles ; la suivante est à 0,00 R. Le seuil est dans une zone vide.

**⚠️ RENVERSÉ — le Position History n'est pas nécessaire.** `tradovate.md` §5 bis le tenait
pour « la pièce maîtresse », seule porteuse de l'appariement FIFO. Mesuré : l'export
« Orders » donne, pour chaque ordre rempli, son heure, sa quantité, son prix moyen et sa
**valeur notionnelle** — de quoi refaire cet appariement soi-même, et le refaire
*exactement*. Cinq trades du journal 100004, reproduits au centime, gagnants comme perdants. Un fichier de moins à exporter et à confondre. *Le
multiplicateur se déduit lui aussi (`Notional Value / prix × quantité`) : NQ 20, MNQ 2,
GC 100, MGC 10, MCL 100, 6E 125 000. Une table codée en dur aurait été une table à
maintenir.*

**⚠️ RENVERSÉ — Edgewonk stocke le PRODUIT, pas le contrat.** `MGC`, `MNQ`, `6E`, `NQ`,
`GC`, `MCL` — jamais `MNQU6`. La clé d'appariement, reprise telle quelle de cTrader,
n'aurait rien trouvé sur **100 % des jambes**. La colonne à comparer est désormais déclarée
par plateforme et mesurée des deux côtés. *C'est très exactement le §6 de ce document, dans
l'autre sens : une règle mesurée sur une plateforme n'est pas une règle.*

**⚠️ CORRIGÉ — Edgewonk ne tronque pas toujours à la minute côté futures.** 24 trades sur 34
portent des secondes non nulles, les autres non : deux régimes dans le même journal. La clé
compare des minutes, ce qui reste juste dans les deux cas — mais resserrer sur la seconde
aurait paru plus précis et cassé 10 trades sur 34.

**Le fuseau de l'export est mesuré, pas observé : UTC+2.** Et mesuré contre le **marché**,
pas contre Edgewonk : pour dix ordres, sur cinq contrats, de 01:55 à 19:19, on cherche quels
décalages font tomber le prix d'exécution dans la bougie M1 de Databento. UTC+2 colle 10/10,
le suivant 3/10. Confirmé indépendamment : notre `19:19:07` est leur `17:19:07`. *L'heure
d'hiver reste non testée — un export d'août ne contient que de l'été.*

**La forme des réponses Databento est confirmée sur une vraie fenêtre**, pour 0,005 $ :
JSON par lignes, prix entiers en virgule fixe à diviser par 1e9, horodatage en nanosecondes.
Les trois hypothèses du client étaient bonnes.

**Un signalement qui criait au loup, attrapé sur données réelles.** Un `Buy Stop` marqué
`multibracket` suivi de deux ordres opposés a toute la forme d'une entrée ATM. C'était le
**stop de la position précédente**, remplacé après annulation, déclenché sur 2 contrats sur
4 — et lu comme une entrée, il affichait « 20/20 ticks », donc le détecteur de placeholder
se déclenchait. Rien dans l'export ne distingue les deux formes : **seul le FIFO le sait**,
une entrée ouvre une position, un stop la ferme. La suggestion n'accepte donc qu'un bracket
dont l'heure de remplissage coïncide avec une ouverture. *Un signalement qui se déclenche
sur du sain dresse à ignorer les signalements — quatrième fois dans ce projet.*

---

**26/08/2026, soir — la mécanique de la deuxième plateforme.**

**La chaîne Tradovate est écrite, et elle n'a coûté qu'un lecteur et une source de prix.**
Les extrêmes, le TP-first, les huit paliers, les quatre graphiques et toute l'écriture
Edgewonk servent les futures **sans une ligne modifiée** — parce que `databento/client.py`
répond au même appel que le MCP cTrader. C'est le bénéfice direct du découpage par profil
de risque, et il ne s'est pas vu avant aujourd'hui.

**Databento est mesuré, six sondes en 200.** Historique depuis 2010, symbologie brute du
CME résolue telle quelle (`MNQU6` → 42004800, aucune table à maintenir), pas de schéma 5m
ni 15m — l'agrégation côté client était bien obligatoire — et **0,0050 $ la journée entière
de M1 sur un contrat**. C'est ce dernier chiffre qui a décidé du cache à la journée plutôt
qu'à la fenêtre : à ce prix, `--refaire` et la reprise des paliers ne repaient plus rien.

**Un piège d'agrégation qui ne se serait jamais vu.** Un seau M5 construit sur trois
minutes au lieu de cinq porte un plus haut sous-estimé, et rien ne le signale — ni erreur,
ni valeur aberrante, juste un MFE trop bas. Le client élargit donc la fenêtre aux bornes de
seau avant de tirer, puis découpe. Vérifié par test hors ligne.

**⚠️ RENVERSÉ — « l'export Tradovate porte déjà le SL et le TP ».** Vrai pour les entrées
ATM, **faux pour les autres**, et l'export en compte 144 sur 204. Mesure jour par jour :
L'utilisateur est passé à l'ATM le **18/08/2026**, et depuis le 20/08 tout est `multibracket`.
Avant cette date, une entrée posée au graphique et son stop posé au graphique sont deux
lignes que rien ne relie — c'est exactement ce qui fait qu'Edgewonk colle des stops à
183 points. Le module ne devine pas : les 60 entrées `Chart` remplies partent en saisie
manuelle, et la règle du stop inventé s'applique telle quelle. **La bonne nouvelle est le
calendrier** : c'est un arriéré borné, pas une charge récurrente.

**⚠️ CORRIGÉ — le drapeau « ordre modifié » ne détecte pas un placeholder survivant.**
`tradovate.md` §6 disait le bracket du 24/08 « marqué intact » à 20/20 ticks, déduit de
`Version ID = Order ID`. Mesuré : ses deux protections sont marquées **modifiées**. On
détecte donc sur la géométrie — deux jambes exactement au preset — qui elle ne ment pas.
*Le §6 avait été établi sur un regroupement différent : même piège que la segmentation
généralisée sans revérification.*

**Un quatrième vérificateur qui mentait.** La sonde de symbologie affichait « OK » pour
trois contrats que la même réponse listait comme non résolus : `result` porte **tous** les
symboles demandés en clé, avec une **liste vide** pour ceux qui échouent, si bien que tester
la présence de la clé répond toujours oui. Corrigé — on teste le contenu. *Même leçon que le
comparateur d'`alternativeStrategies` et que celui d'`appliquer()` : un contrôle qui ne peut
pas échouer n'est pas un contrôle.*

**Les SL/TP lus sont des suggestions, jamais des écritures.** Les poser directement en base
paraissait plus court. C'était un piège : la règle de fusion remplace une valeur non vide
par une autre, donc un ré-import **écraserait une correction faite à la main**, sans bruit,
les deux valeurs étant plausibles. Ils passent par le fichier de saisie, où l'utilisateur les
valide.

**Le lanceur demande la plateforme — `1` ou `2` — au lieu de renifler le CSV.** En revanche,
une fois Tradovate déclaré, les deux exports sont reconnus à leur **en-tête** : un nom de
fichier se renomme, une en-tête dit ce que le fichier contient.

**Ce qui a été vérifié, et ce qui ne l'a pas été.** Vérifié : l'agrégation et
l'élargissement du client Databento, hors ligne ; la lecture du Position History contre les
**deux** cas mesurés du §5 bis (la position `…044` donne deux trades, la `…180` un seul au
VWAP 29797.375) ; la lecture des brackets contre l'export réel (8 retrouvés, les écarts en
ticks reproduits, les deux anomalies attrapées) ; l'import Tradovate de bout en bout sur une
base jetable, ré-import idempotent compris ; et que le chemin cTrader n'a pas bougé.
**Pas vérifié :** aucune bougie futures réelle n'a encore été tirée, le fuseau de l'export
n'est pas mesuré, et le nom d'instrument côté Edgewonk est inconnu. Trois diagnostics
écrits, trois commandes à lancer — §4.

---

**26/08/2026 — le management, les huit paliers, et la reprise de l'historique.**

**La reprise rétroactive est terminée.** 157 trades, **670 champs et 454 images confirmés
par relecture, 0 échec, 0 divergence**, 79 emplacements de captures manuelles protégés.
Trois lots, relus dans l'interface entre chacun. Le journal y gagne 120 MAE, 90 R-multiples
et 89 MFE qui n'existaient pas, faute de stop. Détail dans `retroactif/INVENTAIRE.md`.

**Le champ `management` entre dans la saisie.** Troisième colonne du fichier SL/TP, `OK` ou
`KO`, écrite dans `managementComments`. C'est le **seul champ de tagging** que le robot
touche, et la brèche est étroite par construction (§9). Une case vide est un **rejet** :
contrairement au stop, qu'un R disproportionné trahit, ce jugement ne se retrouve pas après
coup.

**Le catalogue des commentaires est trouvé — et il fallait le trouver.** Le module déduisait
les options des trades lus. Mesuré : après un nettoyage des champs Management d'août,
« Managed » n'était plus portée par aucun des 238 trades, et les 23 positions `KO` ont été
refusées. Refus correct, mécanisme aveugle. `GET /databases/{db}/comments` répond, onze URL
sondées, dix en 403. **La déduction reste en repli, plus jamais en chemin normal.**

*Piège à ne pas refaire : l'endpoint existait, le code pour le consommer aussi — c'est le
**branchement** qui manquait. `preparer()` acceptait `commentaires=`, aucun des trois
appelants ne le passait. Un paramètre optionnel jamais fourni ne casse rien de visible : il
dégrade en silence vers le repli.*

**Les paliers passent de cinq à huit** — 1R, 1,5R et 2,5R rejoignent 2R, 3R, 3,5R, 4R et
5R. **Zéro requête de bougies** : ils se résolvent depuis le `prix_max_favorable` déjà
stocké. Bénéfice direct de « on stocke les faits, pas les statistiques ».

**Un vérificateur qui mentait, encore.** Le comparateur d'`alternativeStrategies` indexait
sur `(strategyId, setupId)`. Ça marchait par chance — les trades d'août avaient déjà des
stratégies, dont le `setupId` était recopié dans l'envoi. Sur un trade à la liste **vide**,
c'est le serveur qui pose le `setupId` : la clé devenait introuvable et **124 écritures
parfaitement passées** étaient signalées comme divergentes. La clé est le `strategyId`
seul. *Même leçon que la veille : un vérificateur muet est pire qu'absent.*

**Un contrôle de R réalisé, qui ne dépend pas du TP.** Le NAS100 du 14/08 portait un SL à
0,45 point. Le contrôle du R:R l'avait signalé — « R:R de 430,7 » — mais l'alerte a été
résolue en retirant le TP : plus de TP, plus de R:R, plus d'alerte. Le stop est resté et a
produit **+180 R à lui seul**. Le nouveau contrôle n'a besoin d'aucun TP.

**Les 4 orphelines du changement d'heure.** Quatre jambes du 30/03 au 01/04 refusaient de
s'apparier : Edgewonk avait mal résolu le passage à l'heure d'été sur l'horodatage de
**sortie** (+60 min), l'entrée restant juste. Clé de secours plus **discriminante**, pas
plus laxiste — instrument, sens, entrée à la minute, quantité, gain au centime — avec trois
verrous. *Piège de méthode relevé au passage : la première version du diagnostic réaffichait
une variable de boucle survivante et a fait conclure à tort qu'Edgewonk étiquetait mal les
symboles. Toujours réafficher depuis l'objet.*

---

**25/08/2026, nuit — premier cycle complet, et le trou du week-end.**

37 positions saisies, **159 champs et 132 images écrits dans Edgewonk, tous confirmés par
relecture, zéro divergence**. 46/46 appariés. La chaîne a tourné en entier par l'assistant
guidé, sans reprise en ligne de commande.

Deux corrections de la soirée validées en réel : la relecture des listes (les
`alternativeStrategies` se confirment enfin) et le break-even bidirectionnel, qui a décoché
`#141331` (−0,42 R) en le signalant.

**Le bug trouvé dans la sortie du run :** la simulation des paliers s'arrêtait au premier
jour sans bougie. Le week-end en est un. Corrigé — voir §10, « une tranche vide n'est pas
la fin de l'historique ».

⬜ **14 jambes ont un débordement de bougie de bord ≥ 0,10 R**, jusqu'à +1,29 R. Leur
`highestPrice` / `lowestPrice` est une **borne**, pas un maximum, et alimente `updraw` /
`drawDown` chez Edgewonk. À savoir avant de tirer une conclusion d'un MFE dans leurs stats.

⬜ Les écarts de VWAP sur USOIL et NAS100 **ont disparu** après réimport du relevé dans
Edgewonk : la corruption venait de leur import, pas de nos calculs — ce que l'arithmétique
indiquait déjà (nos prix bouclaient au centime avec le brut, pas les leurs).

---


**25/08/2026, fin de soirée (5) — la chaîne est validée en réel, et le robot fait autorité
sur le break-even.**

**Trois faits mesurés contre l'API réelle, qui ferment les derniers points ouverts :**
`gain: null` sur une stratégie inexistante est **accepté** (PUT 200, relu `gain: None`) ·
l'upload multipart est **accepté** (201, `pictureId` et clé posés par le serveur) ·
les 16 captures et les 6 `alternativeStrategies` sont **confirmées par relecture**.

**Un faux positif corrigé — `champs confirmés par relecture : 0`.** Le premier `pousser`
réel a signalé 6 divergences sur `alternativeStrategies`. Elles étaient fausses : contenu
identique, **ordre différent**. Cause réelle, plus profonde que l'ordre — le comparateur de
`appliquer()` n'avait que deux branches, `bool` et numérique via `_f()`. Sur une liste,
`_f()` lève et renvoie `None`, donc `conforme = False` **à tous les coups** : ce champ était
*structurellement inconfirmable*, la requête n'avait même pas besoin de partir. Corrigé par
une comparaison d'ensembles indexés sur `(strategyId, setupId)`, sur `rMultiple` seul —
`gain` est une valeur qu'on s'interdit de toucher, l'exiger ferait échouer la relecture sur
un champ jamais écrit. *Leçon : un vérificateur muet est pire qu'absent — il dresse à
ignorer ses propres alertes.*

**`bool(obtenu)` au lieu de `obtenu == valeur`** pour les booléens : Edgewonk renvoie
indifféremment `False`, `None` ou `0` pour une case non cochée. Sans ça, écrire
`ignoreForWinrate: false` produirait une divergence fantôme à chaque fois.

**⚠️ RENVERSÉ — « on coche, on ne décoche jamais ».** *Décision de l'utilisateur :* « tout
au-dessus de 0,3 R c'est un trade, point barre ». Le robot **coche et décoche**, par-dessus
une case manuelle s'il le faut, et `R_BREAK_EVEN` revient à **0,30**.

Le garde-fou change de nature : ce n'est plus le sens de l'écriture, **c'est le R**. Sans
SL, `est_break_even` renvoie `None` (règle R7) et rien n'est écrit dans aucun sens — les
jambes non traitées gardent la main de l'utilisateur, et **c'est la saisie du SL qui transfère
l'autorité au robot**. Tout décochage est signalé.

Mesuré sur les 9 jambes qui ont un SL : **4 cochées** (les trois allègements du 07/08 13:43
à +0,125 · +0,111 · +0,111 R, et `#215448` à −0,292 R), **1 décochée** (`#185307`, −0,434 R,
posée à la main). Conséquence acceptée : `#215448`, la jambe réellement tenue du 07/08
18:50, sort du win rate pendant que ses deux allègements y comptent comme perdants. Le
seuil prime sur le cas particulier.

**Les deux écarts de VWAP sont tranchés : c'est Edgewonk qui a tort.** Réconciliation avec
le P&L du relevé brut — USOIL `#121014` : (81,51428571 − 80,807) × 7 × 100 = **495,10**, le
brut au centime ; les prix d'Edgewonk donnent **966**. NAS100 `#174947` : nos prix donnent
**244,20**, ceux d'Edgewonk **211,50**. Contrôle négatif sur NAS100 `#141331`, non signalé :
9,6528571 × 7 = **67,57** ✓, et Edgewonk est d'accord. Donc ni appariement erroné, ni
segmentation différente — **l'import Edgewonk a corrompu le prix d'entrée sur ces deux
lignes, et ses propres prix ne bouclent pas avec son propre P&L**. `diag_ecarts.py` peut
être rangé sur ce cas ; `inReview` est le bon verdict.

**Les 2 jambes non appariées** (`20260824-162825-EURUSD-V#163320`,
`20260825-120449-US500-A#120515`) sont les plus récentes : pas encore importées à la main
dans Edgewonk. Comportement normal, pas un défaut d'appariement.

**✅ Le diagnostic du faux positif est confirmé par la mesure, pas par le raisonnement.**
Le `pousser` de contrôle (25/08, 20:44) était construit comme un test réfutable : si les 6
`alternativeStrategies` n'avaient jamais été écrites, l'idempotence les aurait replanifiées.
Le plan est revenu à **1 trade, 1 champ** — donc Edgewonk les détenait déjà, et seul le
vérificateur mentait. Relecture : `champs confirmes PAR RELECTURE : 1`, zéro divergence.
Les signalements passent de 4 à 3 : celui de `#215448` disparaît puisqu'à 0,30 son état
coché est désormais cohérent.

---

**25/08/2026, soirée (4) — `ignoreForWinrate`. L'étape 5 est complète.**

Seuil `R_BREAK_EVEN = 0.30`, calculé sur **nos** prix et jamais sur le `rMultiple`
d'Edgewonk — il est calculé serveur et faux sur les trades aux prix d'exécution divergents.
Sans SL, pas de R, rien n'est écrit : règle R7.

**On coche, on ne décoche jamais.** Ce champ est aussi une case que l'utilisateur coche à la
main. Notre règle sait dire « ce trade EST un break-even » ; elle ne sait pas dire
« celui-là n'en est pas un », parce qu'elle ignore pourquoi il l'a cochée. Décocher
effacerait un jugement humain — ce que ce module s'interdit partout ailleurs. Le cas
inverse est signalé, pas corrigé.

**Mesuré sur les 9 jambes qui ont un SL : 4 seraient marquées** (+0,125 · +0,111 · +0,111 ·
−0,292). La quatrième est `#215448`, la **vraie jambe** de la position du 07/08 18:50 : elle
sort du win rate pendant que ses deux allègements, à −0,434 et −0,491 R, y restent comme
des trades perdants. Conséquence directe du « seuil seul, sans règle structurelle » — à
revoir sur du volume.

---

**25/08/2026, soirée (3) — les stratégies alternatives, et le dépôt git.**

Règle de l'utilisateur : pour chaque palier, **soit le palier, soit −1**. Simple à énoncer,
mais elle demandait une donnée que le pipeline n'avait pas — les bougies **après** la
sortie réelle. Sans elles on sous-estimait systématiquement et en silence (§9).

`ctrader/bougies.py` gagne `simuler_paliers` (le parcours en avant, plafonné à
`JOURS_MAX = 10` qui **signale** au lieu d'inventer) et `paliers_depuis` (pur calcul,
rejouable). La base gagne `prix_max_favorable` — un **prix**, pas un R-multiple.
`edgewonk/ecriture.py` gagne `strategies_a_ecrire`, qui résout les identifiants **par nom
parsé** et ne touche que `rMultiple`.

**Vérifié par test, sans toucher à Edgewonk :** l'exemple même de l'utilisateur (4,5 R puis
retour au stop → `4R = +4`, `5R = −1`), le SL immédiat, le dépassement borné à 5R, les
shorts en miroir, l'indécidabilité quand 5R et SL tombent dans la même bougie M1, la
non-résolution qui n'écrit rien, l'idempotence, et la préservation du `gain` existant.

⚠️ **Un point non testé contre l'API réelle** : quand une stratégie n'existe pas encore sur
le trade, on envoie `gain: null`. Comportement serveur inconnu — à valider sur `100005`.

**Le projet est sous git.** Il ne l'était pas, et on le modifie beaucoup. `donnees/graphiques/`
et `donnees/instantanes/` sont exclus (binaire lourd, et l'historique du dépôt remplace les
instantanés). `donnees/brut/` est versionné : c'est la seule chose non reconstructible.

---

**25/08/2026, soirée (2) — les captures partent vers Edgewonk, et l'écart doc/code est levé.**

Trois champs étaient **documentés depuis le 24/08 mais jamais implémentés** — `edgewonk-api.md`
§12 décrivait un déroulé dont l'étape 8 n'avait été faite qu'au tiers. Constat par grep :
`ignoreForWinrate` et `alternativeStrategies` n'apparaissaient nulle part dans le code, et
`IMAGES` était déclaré dans `api.py` sans un seul appelant. Le README annonçait pourtant la
chaîne « complète de bout en bout ».

| champ | documenté | implémenté |
|---|---|---|
| `slPrice`, `tpPrice`, `highestPrice`, `lowestPrice` | ✅ | ✅ |
| `originalTpHit` *(le SL-first / TP-first)* | ✅ | ✅ |
| `inReview` | ✅ | ✅ |
| **captures 1 à 4** | ✅ | ✅ **fait le 25/08 au soir** |
| **`alternativeStrategies`** | ✅ | ❌ |
| **`ignoreForWinrate`** | ✅ | ❌ |

**Ce qui a été écrit :** `_multipart` à la main dans `api.py` — le projet est en
bibliothèque standard pure, donc pas de `requests`, donc pas de `files=` ; frontière tirée
au hasard à chaque appel, sinon un PNG contenant par malchance la frontière couperait le
corps en deux. Puis `televerser_image` / `supprimer_image`, et `envoyer_images` dans
`ecriture.py` : **supprimer → téléverser → drapeau → relecture**.

**L'idempotence passe par la base locale, pas par `screenshot{n}Exists`.** Arbitré par
L'utilisateur, et c'est le bon sens du projet : leur drapeau reste vrai quand l'image est
périmée — exactement le cas d'une ancienne review reprise après une retouche du gabarit.
La colonne `screenshots` fait foi ; `jt.py graphiques --refaire` la vide, ce qui déclenche
le renvoi tout seul. Les images d'Edgewonk ne peuvent plus diverger des PNG du disque.

**Un bug attrapé par le test, et qui aurait été silencieux :** quand une seule image
échouait, les trois autres étaient confirmées et le trade inscrit « fait » dans la base —
l'image manquante n'aurait **plus jamais** été renvoyée. La colonne n'est désormais
remplie que si les quatre emplacements sont confirmés. Le `DELETE` préalable rend le
renvoi complet sans effet de bord.

**Décisions prises le même soir :** `R_BREAK_EVEN` passe de 0,20 à **0,30**, seuil seul
sans règle structurelle (§9) · les stratégies alternatives valent **soit le palier, soit
−1**, plafond 5R, jamais au-dessus (§4, action 4).

---

**25/08/2026, soirée — l'étape 4 refondue. Le gabarit du matin ne tenait pas.**

Il avait été mis au point sur des bougies **synthétiques bien étalées**, et sur
l'hypothèse que le découpage d'Edgewonk devait être représenté à l'écran. Les deux
prémisses étaient fausses.

| Avant | Après |
|---|---|
| Un graphique par **jambe** | **Un jeu par POSITION**, sur la jambe réellement tenue — la **dernière sortie** |
| Les autres sorties en **points estompés** | **Supprimées.** l'utilisateur ne prend pas de partiels : ce sont des allègements après ajustement du SL, pas des décisions |
| Lignes **Entrée** et **Sortie** + leurs encarts | **Supprimées.** Remplacées par une **diagonale en tirets** entre les deux points |
| Aplats risque/objectif **pleine largeur** à 0,05 | **Rectangles bornés au trade** à 0,16 — le Position Tool de cTrader |
| **LTF M5 + HTF** choisi par la durée | **Quatre images fixes : M5 · M15 · H1 · H4** |
| Marge = **50 % de la durée**, plancher 60 bougies | **60 bougies avant / 30 après** — asymétrique, la structure est derrière l'entrée |
| Toutes les jambes recevaient les mêmes images | **Seule la jambe tenue** porte les captures ; les allègements n'en ont pas |

**Corollaire non évident**, et deuxième piège évité : puisque `chemin_graphiques` n'est
plus renseigné que sur une jambe, filtrer le travail sur « les jambes sans graphique »
relancerait **indéfiniment** le rendu de toute position sortie en plusieurs fois — ses
allègements n'en auront jamais. La sélection passe donc par `rendu.position_a_rendre`,
qui interroge la jambe tenue. Vérifié : deuxième passage à vide, `--refaire` intact.

**Le défaut qui a tout déclenché :** `LTF_TIMEFRAME = "m5"` fixe avec un plancher de
60 bougies fait **5 heures**, quoi qu'il arrive. Une jambe d'1 min 16 s recevait une
fenêtre de 4 h 56 où l'entrée et les quatre sorties tenaient dans trois pixels. Les
marqueurs ne se chevauchaient pas par malchance — **par construction**.

**Le piège évité en écrivant, et qui aurait été silencieux :** `jt.py` passe à l'étape 4
une vue **restreinte** de la position (les jambes sans graphique). Prendre « la dernière
jambe » de ce sous-ensemble aurait dessiné un allègement à la place du trade.
`rendu.jambes_de_position` relit donc la base au lieu de faire confiance à
`position["jambes"]`.

**Ce qui a été vérifié, et ce qui ne l'a pas été :** le nouveau code a été rejoué de bout
en bout contre un **faux serveur MCP** — 4 PNG par position, nommage correct, toutes les
jambes pointant vers le même dossier, et la bonne jambe retenue sur les 4 positions
multiples y compris avec une vue restreinte en entrée. **Rien n'a encore été rendu sur de
vraies bougies** : c'est l'action n°1 du §4.

*Sauvegardes de l'état antérieur en `*.bak-20260825` à côté de chaque fichier touché.*

---

**25/08/2026, fin de journée — la chaîne est livrée, de bout en bout.**
Les cinq étapes écrites et testées en conditions réelles. Ce qui est tombé, et qu'il ne
faut pas re-découvrir :

| Avant | Après |
|---|---|
| Edgewonk = un trade par **position** | **Un trade par SORTIE partielle.** 46 lignes de relevé = 46 trades. Agréger désalignait 8 trades. Le grain de la base est la **jambe** (§5.3) |
| L'erreur de bord M1 est négligeable (59 s) | **21,5 pips** sur une bougie de news. Les bougies de bord sont exclues du calcul (§9) |
| Le MCP répond `XAUUSD` | **`XAUUSD.raw`** sur le compte Prop Firm A. Le nom du relevé est le bon (§9) |
| Edgewonk stocke en heure de Paris | **UTC**, pour l'importateur cTrader. Et **tronqué à la minute** (§9) |
| Données d'exécution « déjà justes via l'auto-import » | **2 trades sur 44** portent des prix faux. Marqués `inReview` (§9) |
| `journal-entries-search` renvoie les trades récents | **Tri par identifiant, pas par date.** Une page de 200 ne montrait aucun trade d'août. Pagination obligatoire |
| `multiplier` = la taille du contrat | **Vaut 1.0 partout.** A coûté 40 `inReview` à tort (§8, règle 5) |

**Ajouté en fin de journée — l'étape 4.** Le gabarit visuel a quitté `charts.py` pour
`pipeline/graphiques/gabarit.py` (apparence) et `rendu.py` (cadrage) ; `charts.py` devient
un banc d'essai sur bougies synthétiques. Deux ajouts imposés par les vraies données :

| Ce que les bougies synthétiques cachaient | Ce qu'il a fallu ajouter |
|---|---|
| deux niveaux ne tombaient jamais au même prix | **fusion** des encarts confondus (`Sortie / TP`) et **empilage** des trop proches — une sortie AU TP est le cas normal d'un trade gagnant |
| une position = un graphique | **sorties de contexte** : chaque jambe montre sa sortie en plein et les autres de sa position en points estompés |
| — | opacité des points de contexte montée de 0,55 à 0,70 : illisibles sur une bougie de forte amplitude |

**Piège d'environnement :** Homebrew refuse les installations système (PEP 668). Le venv
est **optionnel** et n'existe que pour les graphiques — le reste du pipeline est en
bibliothèque standard pure. Et `urlopen(timeout=)` lève `TimeoutError`, **pas** `URLError` :
ne capturer que le second laissait remonter un « timed out » sans contexte. Le premier appel
sur un timeframe que cTrader n'a jamais chargé peut dépasser 25 s — délai porté à 90 s avec
une seconde tentative.

**Ce qui a été validé en réel le même jour :** 46 lignes → 46 jambes sans anomalie ·
ré-import idempotent (0 ajouté, 46 inchangés, saisie préservée) · 9 jambes avec extrêmes
calculés, 0 incohérence · 44/46 appariées avec Edgewonk, 0 ambiguïté · **38 champs écrits
et confirmés par relecture** · instantané et restauration éprouvés une fois de plus, sur
une erreur bien réelle.

---

**25/08/2026 — journée de renversements.** Ce qui a changé, et qu'il ne faut pas
re-découvrir :

| Avant | Après |
|---|---|
| `Applied SL/TP` = le niveau posé à l'entrée | **Faux.** `Applied` = état après le **dernier** amendement, et **vide** sur une entrée au Position Tool. Testé sur `Market` et `Limit`. |
| Le log fichier du client est une source d'amendements | **Non.** Il ne capte que les trades gérés **depuis ce Mac** — prouvé par deux trades du même jour à 5 min d'écart. Écarté. |
| L'approbation Open API est le chemin critique | **Non.** Elle ne porte pas le niveau initial. Sortie du chemin critique. |
| Le MCP local exposera l'historique d'amendements | **Non.** 76 outils, aucun. Mais `get_trendbars` est de qualité production. |
| Extrêmes calculés depuis les **ticks** | **Bougies M1** — l'utilisateur ne descend jamais sous le M5, et les ticks ne sont pas exposés. |
| Un collecteur en tâche de fond capterait les SL/TP | **Abandonné** au profit d'une saisie manuelle assumée (§9). |

**Ce qui a été confirmé le même jour :** l'historique d'amendements est **côté serveur**
(un trade passé au téléphone s'affiche intégralement sur le Mac) · le dédoublonnage des
événements se fait **champ par champ**, jamais événement par événement · MAE/MFE et
TP-first sont calculables depuis les bougies, vérifié sur la position `284853317`.
