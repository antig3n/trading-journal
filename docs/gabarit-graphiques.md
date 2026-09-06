# Gabarit visuel des graphiques de trade

*Validé par l'utilisateur le 24/08/2026, confronté aux vraies bougies le 25/08 au matin,
**refondu le 25/08 au soir** après comparaison de rendus. Voir le §10 pour ce qui est
tombé ce soir-là.*

| quoi | où |
|---|---|
| l'apparence — couleurs, traits, points, encarts, fond | `pipeline/graphiques/gabarit.py` |
| le cadrage — timeframes, marges, choix de la jambe | `pipeline/graphiques/rendu.py` |
| un banc d'essai sur bougies synthétiques | `charts.py`, à la racine |

**Rien de graphique ne doit être codé ailleurs que dans `gabarit.py`.**

---

## 1. Principe

Le graphique n'est pas une capture d'écran : il est **dessiné à partir des bougies du
broker**. Pas d'indicateurs, pas de template TradingView — en échange, positionnement
exact, rendu identique à chaque trade, prix du broker.

**Quatre images par POSITION : M5, M15, H1, H4.**

---

## 2. Un graphique par POSITION, sur la jambe réellement tenue

**Fait établi par l'utilisateur le 25/08/2026 : il ne prend jamais de partiels.** Une position
sortie en plusieurs fois est un **allègement** consécutif à un ajustement de SL — de la
gestion de risque, pas une décision de trade.

→ Le graphique montre l'entrée et la sortie de **la jambe réellement tenue**, c'est-à-dire
la **dernière sortie**. **Elle seule reçoit les images** : les jambes d'allègement restent
sans graphique, parce qu'elles ne représentent aucune décision.

### Pourquoi la dernière, et pas la plus grosse

Mesuré sur les 4 positions à sorties multiples de la base :

| position | « la plus grosse » | « la dernière » |
|---|---|---|
| 07/08 13:43 | 3,00 lots soldés en 76 s, gain marginal | 2,00 lots tenus 47 min, **l'essentiel du gain** |
| 07/08 18:50 | 3,00 lots soldés en 3 min, l'essentiel de la perte | 1,50 lot tenu **3 h 04**, perte résiduelle |
| 12/08 10:52 | les deux critères coïncident | idem |
| 20/08 18:10 | les deux critères coïncident | idem |

**« La plus grosse » se trompe 2 fois sur 4**, et se trompe sur le trade qui compte.
**« La dernière » est juste 4 fois sur 4** — et la raison vaut mieux que le score : toutes
les jambes partageant la même entrée, la dernière sortie est **par construction** celle qui
a été tenue le plus longtemps. Aucun seuil à calibrer.

⚠️ **Conséquence sur la sélection du travail.** `chemin_graphiques` n'étant renseigné que
sur la jambe tenue, filtrer sur « les jambes sans graphique » relancerait indéfiniment le
rendu des positions multiples. C'est `rendu.position_a_rendre` qui décide, en interrogeant
**cette** jambe.

⚠️ `rendu.jambes_de_position` relit la base plutôt que d'utiliser `position["jambes"]` :
l'appelant passe souvent une vue **restreinte** (les jambes sans graphique), et la dernière
jambe de ce sous-ensemble n'est pas forcément la dernière de la position. Se tromper là
revient à dessiner un allègement à la place du trade.

---

## 3. Structure de l'image

| Élément | Choix | Pourquoi |
|---|---|---|
| Fond | blanc | lisibilité, impression |
| Axe des prix | **à gauche** | les encarts occupent la droite |
| Encarts de cotation | **à droite**, SL et TP seulement | alignés sur leur trait |
| Axes et titre | noir | contraste maximal sur blanc |
| Grille | `#e6e8ec`, pointillés | présente sans concurrencer les bougies |
| Dimensions | 1600 × 900 à 100 dpi | ~65 Ko, très loin de la limite d'upload |

**Verrou :** `AXE_PRIX_A_GAUCHE = True`, explicite — le style de la bibliothèque faisait
auparavant basculer l'axe d'une génération à l'autre.

---

## 4. Ce qui est dessiné

**Deux points et une diagonale.**

- point **bleu** `#1e6fe0` à l'entrée, point **orange** `#e08a00` à la sortie, 10 px, liseré blanc
- une **diagonale en tirets** entre les deux, couleur **neutre** `#5a6270`, épaisseur 1,3

La diagonale dit à elle seule le prix d'entrée, le prix de sortie, le sens et la durée.

⚠️ **Elle est neutre et ne doit pas être colorée par le résultat.** Le résultat est déjà
porté par les deux points et par le niveau atteint ; une diagonale verte qui longe des
bougies vertes disparaît — constaté sur le trade du 07/08.

**Deux niveaux seulement traversent l'image : SL et TP**, en pointillés, épaisseur 0,8
(`#e03b3b` et `#0f9b8e`). Ce sont les niveaux du plan, ils structurent la lecture.

**L'échelle verticale englobe toujours les niveaux**, pas seulement les bougies — sinon le
SL et le TP sortent du cadre et seul le fond teinté reste visible.

---

## 5. Le fond rouge / vert — le rectangle du Position Tool

Deux rectangles, entrée→SL en rouge et entrée→TP en vert, **bornés à la durée du trade**,
opacité `TEINTE_ZONE = 0.16`.

**Bornés, et pas en aplat pleine largeur :** le rectangle dit *quand* le risque a couru.
Et sa frontière porte le **prix d'entrée**, qui n'a plus de ligne à lui — c'est le seul
repère du niveau d'entrée sur toute la largeur.

*L'opacité était à 0,05 : invisible à l'écran. Montée à 0,16 pour retrouver le rendu du
Position Tool de cTrader.*

---

## 6. Encarts de cotation — dérivés, jamais choisis

Le fond de chaque encart est **calculé** depuis la couleur de son trait, par mélange avec
60 % de blanc (`ECLAIRCISSEMENT_ENCART = 0.60`) :

```
#e03b3b  →  #f3b1b1     stop
#0f9b8e  →  #9fd7d2     cible
```

Texte noir, liseré fin à la couleur pleine du trait. **Dérivé et non codé en dur** :
changer une couleur de trait met l'encart à jour, les deux ne peuvent plus se désaccorder.

**Fusion et empilage conservés.** Deux niveaux au même prix donnent un encart (`SL / TP`) ;
en dessous de `ECART_MIN_ENCARTS = 0.030` de la hauteur, celui du dessus remonte. **Le
trait ne bouge jamais** : c'est lui qui porte le niveau exact. Le cas est devenu rare
depuis que seuls SL et TP ont un encart, mais il existe sur un trade serré.

---

## 7. Les quatre timeframes

**Le M1 est hors de l'échelle.** l'utilisateur ne lit jamais en dessous du M5. Le M1 ne sert
qu'au calcul des extrêmes (`ctrader/bougies.py`), où il n'est jamais affiché.

| image | ce qu'elle sert à lire | format de date de l'axe |
|---|---|---|
| **M5** | le trade lui-même | `%H:%M` |
| **M15** | la session | `%d/%m %H:%M` |
| **H1** | le swing | `%d/%m %H:%M` |
| **H4** | la tendance | `%d/%m` |

Les quatre sont produites à chaque fois. Plus de timeframe choisi par la durée, plus de
couple LTF/HTF. **Edgewonk a six emplacements** : les quatre premiers sont pris, deux
restent libres pour ses propres captures.

---

## 8. Cadrage — une marge en BOUGIES

```
BOUGIES_AVANT = 60      # contexte avant l'entrée
BOUGIES_APRES = 30      # contexte après la sortie
```

**En bougies, pas en pourcentage.** Un pourcentage donne trois heures de marge sur un trade
de trois heures et six minutes sur un trade de six minutes : la quantité de contexte à
l'écran change tout le temps. Un nombre de bougies donne toujours la même chose à lire.
*(Remplace `LTF_PART_DU_TRADE` et `LTF_MIN_BOUGIES`, supprimées.)*

**Asymétrique 2:1, volontairement.** La structure qui justifie l'entrée est **derrière** ;
ce qui suit la sortie n'a qu'à confirmer. Le système de l'utilisateur étant réactif sur
structure, ce qu'il revient vérifier en review — la cassure, la double confirmation — se
joue avant l'entrée.

Ce que ça donne sur le trade du 07/08 (47 min) :

| | à l'écran | contexte avant | le trade pèse |
|---|---|---|---|
| M5 | 8 h 17 | 5 h | 9 bougies |
| M15 | 23 h 17 | 15 h | 3 bougies |
| H1 | 3 j 19 h | 2 j 12 h | < 1 bougie |
| H4 | 15 j | 10 j | < 1 bougie |

**Le fuseau.** Le MCP renvoie de l'UTC. Les axes affichent l'heure **locale du relevé**,
reconvertie via l'offset qu'il porte — sinon un trade de 13:44 s'afficherait à 11:44.

---

## 9. Lancer un rendu

```
cd pipeline
../.venv/bin/python3 jt.py graphiques             # ce qui manque seulement
../.venv/bin/python3 jt.py graphiques --refaire   # tout, après un ajustement du gabarit
```

**`--refaire` est indispensable après toute modification de ce gabarit** : sans lui les
anciens rendus restent en place et on compare des images produites par deux versions.

Le banc d'essai, sans MCP ni trade réel — il rend les quatre timeframes :

```
.venv/bin/python3 charts.py     # -> /tmp/tj/demo_M5.png, _M15.png, _H1.png, _H4.png
```

**Sortie des rendus :** `donnees/graphiques/<cle_position>/M5.png`, `M15.png`, `H1.png`,
`H4.png` — **un dossier par POSITION**. ~65 Ko l'image. Le chemin n'est écrit dans la base
que sur la **jambe tenue**.

⚠️ **Les dossiers de l'ancienne organisation** (`<cle_jambe>/LTF.png` + `HTF.png`) ne sont
pas écrasés : ils portent un autre nom. Vider `donnees/graphiques/` avant un `--refaire`
général.

---

## 10. Ce qui est tombé le 25/08/2026 au soir

Le gabarit du matin avait été mis au point sur des bougies **synthétiques bien étalées** et
sur l'hypothèse que le découpage d'Edgewonk devait être représenté. Confronté aux vrais
trades et à la façon dont l'utilisateur trade réellement, il ne tenait pas.

| Avant | Après |
|---|---|
| Un graphique par **jambe** | **Un par position**, sur la jambe réellement tenue (§2) |
| Les autres sorties en **points estompés** | **Supprimées.** Deux sorties à 9 s et 0,1 pip tombent sur le même pixel quel que soit le cadrage — et ce sont des allègements, ils ne l'intéressent pas |
| Lignes horizontales **Entrée** et **Sortie** + leurs encarts | **Supprimées.** Elles barraient l'image pour deux niveaux séparés de 0,9 pip. Remplacées par la **diagonale** (§4) |
| Aplats risque/objectif **pleine largeur** à 0,05 | **Rectangles bornés au trade** à 0,16 — le Position Tool (§5) |
| **LTF M5 + HTF** choisi par la durée | **Quatre images fixes** M5 / M15 / H1 / H4 (§7) |
| Toutes les jambes recevaient les mêmes images | **Seule la jambe tenue** les porte (§2) |
| Marge = **50 % de la durée**, plancher 60 bougies | **60 bougies avant / 30 après** (§8) |

**Le défaut qui a tout déclenché :** `LTF_TIMEFRAME = "m5"` fixe avec un plancher de
60 bougies fait **5 heures**, quoi qu'il arrive. Une jambe d'1 min 16 s recevait donc une
fenêtre de 4 h 56 dans laquelle l'entrée et les quatre sorties tenaient dans trois pixels.
Les marqueurs ne se chevauchaient pas par malchance : ils se chevauchaient par construction.
