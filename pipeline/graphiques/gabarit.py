# -*- coding: utf-8 -*-
"""GABARIT VISUEL — source unique de l'apparence des graphiques de trade.

**Rien de graphique ne doit être codé ailleurs que dans ce fichier.**
Toute modification d'apparence passe par le bloc de constantes ci-dessous.

Le graphique n'est pas une capture d'écran : il est DESSINÉ à partir des
bougies du broker. Pas d'indicateurs, pas de template TradingView — en échange,
positionnement exact, rendu identique à chaque trade, prix du broker.

────────────────────────────────────────────────────────────────────────────
RÉVISION DU 25/08/2026 (soir) — ÉPURATION, validée par l'utilisateur sur rendus.

Ce qui a changé, et POURQUOI. Ne pas revenir dessus sans raison nouvelle.

1. **Un graphique par POSITION, plus par jambe.**
   Fait établi par l'utilisateur : il ne prend jamais de partiels. Les sorties
   multiples sont des ALLÈGEMENTS consécutifs à un ajustement de SL — de la
   gestion de risque, pas des décisions de trade. Elles n'ont rien à faire sur
   le graphique.
   → Le graphique montre la position telle qu'il l'a tenue : entrée, et la
     sortie de la jambe réellement tenue (voir `rendu.jambe_reelle`).

2. **Les sorties de contexte estompées ont été SUPPRIMÉES.**
   Elles avaient été ajoutées le 25/08 au matin pour ne pas perdre
   l'information du découpage d'Edgewonk. Elles étaient illisibles — deux
   sorties à 9 secondes et 0,1 pip d'écart tombent sur le même pixel, quel que
   soit le cadrage — et surtout elles ne l'intéressent pas.

3. **Les lignes horizontales Entrée et Sortie, et leurs encarts, ont sauté.**
   Elles barraient toute l'image pour deux niveaux séparés de 0,9 pip et
   saturaient le graphique. Remplacées par une DIAGONALE en tirets entre les
   deux points : un seul trait qui dit le prix d'entrée, le prix de sortie, le
   sens et la durée.
   → Seuls SL et TP traversent l'image, avec leur encart de cotation. Ce sont
     les niveaux du plan, ils structurent la lecture.

4. **Le fond rouge / vert est BORNÉ à la durée du trade** — le rectangle du
   Position Tool de cTrader, pas un aplat pleine largeur. Il dit *quand* le
   risque a couru, et sa frontière porte le prix d'entrée maintenant que la
   ligne d'entrée a sauté. Teinte montée de 0,05 à 0,16 : à 0,05 il était
   invisible.

5. **La diagonale est NEUTRE, pas colorée par le résultat.** Le résultat est
   déjà porté par les deux points et par le niveau atteint. Une diagonale verte
   qui longe des bougies vertes disparaît — constaté sur le trade du 07/08.
────────────────────────────────────────────────────────────────────────────
"""

import logging

import matplotlib
matplotlib.use("Agg")

# mplfinance demande une graisse « medium » que les polices système n'ont pas :
# matplotlib retombe sur 400 et le prévient à chaque figure. Sans effet sur le
# rendu, mais deux lignes de bruit par graphique — donc des centaines par semaine.
logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
import matplotlib.pyplot as plt              # noqa: E402
import mplfinance as mpf                     # noqa: E402
import numpy as np                           # noqa: E402
from matplotlib.patches import Rectangle     # noqa: E402

# ==========================================================================
# CONSTANTES — les seuls réglages d'apparence
# ==========================================================================

LARGEUR_PX, HAUTEUR_PX, DPI = 1600, 900, 100

AXE_PRIX_A_GAUCHE = True     # axe des prix à gauche, encarts de cotation à droite
EPAISSEUR_TRAIT = 0.8        # SL et TP, en pointillés
EPAISSEUR_DIAGONALE = 1.3    # le trait entrée -> sortie
TAILLE_POINT = 10            # les deux repères, entrée et sortie
ECART_MIN_ENCARTS = 0.030    # part de la hauteur sous laquelle deux encarts
                             # se chevauchent et doivent être empilés
ECLAIRCISSEMENT_ENCART = 0.60  # part de blanc mélangée : 0 = couleur pleine, 1 = blanc

TEINTE_ZONE = 0.16           # opacité des rectangles risque / objectif

COUL = {
    "fond":      "#ffffff",
    "grille":    "#e6e8ec",
    "texte":     "#000000",    # axes et titre
    "hausse":    "#0f9b8e",
    "baisse":    "#e03b3b",
    "entree":    "#1e6fe0",
    "sortie":    "#e08a00",
    "sl":        "#e03b3b",
    "tp":        "#0f9b8e",
    "diagonale": "#5a6270",    # neutre — voir le point 5 de l'en-tête
}


def eclaircir(hexa, taux=ECLAIRCISSEMENT_ENCART):
    """Mélange une couleur avec du blanc. Garantit que les encarts restent
    accordés aux traits même si une couleur change."""
    h = hexa.lstrip("#")
    r, v, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = lambda c: int(round(c + (255 - c) * taux))          # noqa: E731
    return "#{:02x}{:02x}{:02x}".format(m(r), m(v), m(b))


def rendre(df, trade, titre, chemin, format_date="%H:%M"):
    """Dessine un graphique et l'écrit en PNG. Retourne le chemin.

    `trade` : {entry_price, exit_price, entry_time, exit_time, direction, sl, tp}
              — la POSITION, avec la sortie de la jambe réellement tenue.
    """
    e_prix, s_prix = trade["entry_price"], trade["exit_price"]
    sl, tp = trade.get("sl"), trade.get("tp")

    style = mpf.make_mpf_style(
        base_mpf_style="classic",
        marketcolors=mpf.make_marketcolors(
            up=COUL["hausse"], down=COUL["baisse"], edge="inherit",
            wick={"up": COUL["hausse"], "down": COUL["baisse"]}, volume="in"),
        facecolor=COUL["fond"], edgecolor=COUL["grille"],
        figcolor=COUL["fond"], gridcolor=COUL["grille"], gridstyle=":",
        y_on_right=not AXE_PRIX_A_GAUCHE,
        rc={"axes.labelcolor": COUL["texte"], "xtick.color": COUL["texte"],
            "ytick.color": COUL["texte"], "text.color": COUL["texte"],
            "axes.edgecolor": COUL["grille"], "font.size": 11})

    fig, axes = mpf.plot(
        df, type="candle", style=style, returnfig=True,
        figsize=(LARGEUR_PX / DPI, HAUTEUR_PX / DPI),
        tight_layout=True, xrotation=0, ylabel="", datetime_format=format_date)
    ax = axes[0]

    def pos(ts):
        """Index de la bougie la plus proche d'un horodatage."""
        return int(np.argmin(np.abs(df.index.values - np.datetime64(ts))))

    # Échelle verticale : elle doit contenir les bougies ET les niveaux, sinon
    # le SL et le TP sortent du cadre et seules les zones teintées restent.
    niveaux = [v for v in (e_prix, s_prix, sl, tp) if v is not None]
    bas = min(df["Low"].min(), *niveaux)
    haut = max(df["High"].max(), *niveaux)
    marge = (haut - bas) * 0.06
    ax.set_ylim(bas - marge, haut + marge)
    _, xe = ax.get_xlim()

    # SL et TP seuls traversent l'image : ce sont les niveaux du plan.
    for valeur, coul in ((sl, COUL["sl"]), (tp, COUL["tp"])):
        if valeur is not None:
            ax.axhline(valeur, color=coul, linestyle="--",
                       linewidth=EPAISSEUR_TRAIT, zorder=4)

    x_e, x_s = pos(trade["entry_time"]), pos(trade["exit_time"])

    # Le rectangle du Position Tool : borné à la DURÉE du trade. Un aplat
    # pleine largeur ne dit pas quand le risque a couru.
    for niveau, coul in ((sl, COUL["sl"]), (tp, COUL["tp"])):
        if niveau is None:
            continue
        y0, y1 = min(e_prix, niveau), max(e_prix, niveau)
        ax.add_patch(Rectangle((x_e, y0), max(x_s - x_e, 0.5), y1 - y0,
                               facecolor=coul, edgecolor="none",
                               alpha=TEINTE_ZONE, zorder=1))

    # La diagonale : entrée -> sortie.
    ax.plot([x_e, x_s], [e_prix, s_prix], color=COUL["diagonale"],
            linestyle="--", linewidth=EPAISSEUR_DIAGONALE, zorder=5)

    ax.plot([x_e], [e_prix], marker="o", markersize=TAILLE_POINT,
            color=COUL["entree"], markeredgecolor="white", markeredgewidth=0.8,
            zorder=6)
    ax.plot([x_s], [s_prix], marker="o", markersize=TAILLE_POINT,
            color=COUL["sortie"], markeredgecolor="white", markeredgewidth=0.8,
            zorder=6)

    # Encarts de cotation à droite : SL et TP uniquement. Fond éclairci, texte
    # noir, liseré à la couleur pleine du trait pour conserver le lien visuel.
    # La fusion et l'empilage restent utiles : sur un trade serré, SL et TP
    # peuvent tomber à moins de 3 % de la hauteur l'un de l'autre.
    etiquettes = [(v, n, c) for v, n, c in
                  ((sl, "SL", COUL["sl"]), (tp, "TP", COUL["tp"])) if v is not None]
    fusionnees = {}
    for prix, nom, coul in etiquettes:
        cle = round(prix, 10)
        if cle in fusionnees:
            fusionnees[cle][0].append(nom)
        else:
            fusionnees[cle] = [[nom], coul]

    y_bas, y_haut = ax.get_ylim()
    ecart = (y_haut - y_bas) * ECART_MIN_ENCARTS
    placees, precedent = [], None
    for prix in sorted(fusionnees):
        noms, coul = fusionnees[prix]
        y = prix if precedent is None else max(prix, precedent + ecart)
        placees.append((prix, y, " / ".join(noms), coul))
        precedent = y
    debord = max((y for _, y, _, _ in placees), default=y_haut) - (y_haut - ecart / 2)
    if debord > 0:
        placees = [(p, y - debord, t, c) for p, y, t, c in placees]

    for prix, y, texte, coul in placees:
        ax.annotate("%s %g" % (texte, prix), xy=(xe, y), xytext=(-6, 0),
                    textcoords="offset points", ha="right", va="center",
                    fontsize=10, color=COUL["texte"],
                    bbox=dict(boxstyle="round,pad=0.3", fc=eclaircir(coul),
                              ec=coul, lw=0.7),
                    zorder=8)

    ax.set_title(titre, color=COUL["texte"], fontsize=13, loc="left", pad=12)
    fig.savefig(chemin, dpi=DPI, facecolor=COUL["fond"], bbox_inches="tight")
    plt.close(fig)
    return chemin
