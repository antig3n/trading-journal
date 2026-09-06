#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banc d'essai du gabarit, sur bougies SYNTHÉTIQUES.

    .venv/bin/python3 charts.py

Vérifie le rendu des quatre timeframes sans dépendre du MCP ni d'un trade réel
— utile après une mise à jour de matplotlib ou de mplfinance, qui est en beta
(0.12.10b0) et a déjà tiré pandas 3 sans prévenir.

⚠️ Le gabarit visuel N'EST PAS ICI. Il vit dans `pipeline/graphiques/gabarit.py`,
et le cadrage dans `pipeline/graphiques/rendu.py`. Ne rien coder de graphique ici.

Sortie : /tmp/tj/demo_M5.png, _M15.png, _H1.png, _H4.png
"""

import datetime as dt
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline"))
from graphiques import gabarit                                          # noqa: E402
from graphiques.rendu import TIMEFRAMES, fenetre                        # noqa: E402


def bougies_synthetiques(debut, fin, minutes, prix_pivot, graine=7,
                         volatilite=0.0012):
    """Marche aléatoire plausible, hors week-end, passant près de prix_pivot."""
    rng = np.random.default_rng(graine + minutes)
    idx = pd.date_range(debut, fin, freq="%dmin" % minutes)
    idx = idx[[d.weekday() < 5 for d in idx]]      # le forex ne cote pas le week-end
    n = max(len(idx), 3)
    idx = idx[:n]
    pas = rng.normal(0, volatilite / np.sqrt(n), n).cumsum()
    close = prix_pivot * np.exp(pas - pas[n // 2])              # recentré sur le pivot
    open_ = np.concatenate([[close[0]], close[:-1]])
    amplitude = close * volatilite * 0.5
    haut = np.maximum(open_, close) + np.abs(rng.normal(0, amplitude))
    bas = np.minimum(open_, close) - np.abs(rng.normal(0, amplitude))
    return pd.DataFrame({"Open": open_, "High": haut, "Low": bas, "Close": close},
                        index=pd.DatetimeIndex(idx))


if __name__ == "__main__":
    dossier = "/tmp/tj"
    if not os.path.isdir(dossier):
        os.makedirs(dossier)

    # Un long gagnant sorti au TP, dans l'esprit du 07/08 : 47 minutes.
    entree_dt = dt.datetime(2026, 8, 7, 13, 43, 18)
    sortie_dt = dt.datetime(2026, 8, 7, 14, 30, 1)
    trade = {
        "entry_price": 1.15314, "exit_price": 1.15470,
        "entry_time": entree_dt, "exit_time": sortie_dt,
        "direction": "BUY", "sl": 1.15242, "tp": 1.15470,
    }

    for code, minutes, nom, format_date in TIMEFRAMES:
        debut, fin = fenetre(entree_dt, sortie_dt, minutes)
        df = bougies_synthetiques(debut, fin, minutes, trade["entry_price"])
        titre = "EURUSD · Long · %s · %s → %s" % (
            nom, entree_dt.strftime("%d/%m/%Y %H:%M"), sortie_dt.strftime("%H:%M"))
        chemin = gabarit.rendre(df, trade, titre,
                                "%s/demo_%s.png" % (dossier, nom), format_date)
        print("%-4s %3d bougies  %s" % (nom, len(df), chemin))
