#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DIAGNOSTIC EN LECTURE SEULE — ou vit le catalogue des commentaires de trade ?

N'ECRIT RIEN, ni en local ni chez Edgewonk. Que des GET.

LA QUESTION, ET POURQUOI ELLE SE POSE
-------------------------------------
`docs/edgewonk-api.md` §7 documente les endpoints de reference pour les setups, les
checklists, les custom stats, les strategies alternatives et les instruments.
**Il n'en documente aucun pour les QUATRE familles de commentaires** —
`preTradeComments`, `entryComments`, `exitComments`, `managementComments`.

Faute de mieux, `ecriture.options_management` deduit le catalogue des trades
eux-memes : chaque commentaire y est un objet {id, name}. Ca marche tant qu'au
moins un trade porte l'option — et ca casse le jour ou plus aucun ne la porte.

Mesure du 26/08/2026 : c'est arrive. L'utilisateur a nettoye les champs Management
d'aout, « Managed » a disparu des 238 trades, et le module a refuse d'ecrire les
23 positions KO. Refus correct — mais il faut une source qui ne depende pas de
l'usage.

Ce diagnostic sonde les URL plausibles et RAPPORTE ce qui repond. Il ne conclut
pas a la place de la mesure : une 404 est une reponse, pas un echec.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from edgewonk.api import API, Client, ErreurEdgewonk      # noqa: E402

# Le journal se declare en argument : les options de commentaires sont PROPRES
# a chaque journal, exactement comme les strategies alternatives.
#     python3 outils/diag_commentaires.py 100004
BASE = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].isdigit() else "100001"

# Deux temoins connus pour repondre (§7) encadrent les candidats : si eux aussi
# echouent, le probleme est l'authentification, pas l'URL.
CANDIDATS = [
    ("TEMOIN  setups",              "%s/databases/%s/setups" % (API, BASE)),
    ("TEMOIN  custom-stat-groups",  "%s/databases/%s/custom-stat-groups" % (API, BASE)),
    ("trade-comments",              "%s/databases/%s/trade-comments" % (API, BASE)),
    ("trade-comment-groups",        "%s/databases/%s/trade-comment-groups" % (API, BASE)),
    ("comments",                    "%s/databases/%s/comments" % (API, BASE)),
    ("comment-groups",              "%s/databases/%s/comment-groups" % (API, BASE)),
    ("tradeComments",               "%s/databases/%s/tradeComments" % (API, BASE)),
    ("rules",                       "%s/databases/%s/rules" % (API, BASE)),
    ("rule-comments",               "%s/databases/%s/rule-comments" % (API, BASE)),
    ("management-comments",         "%s/databases/%s/management-comments" % (API, BASE)),
    ("trade-comments (hors base)",  "%s/trade-comments" % API),
]


def apercu(rep, largeur=3):
    """Les premiers elements, sans deverser 100 Ko dans le terminal."""
    if isinstance(rep, list):
        return "liste de %d — %s" % (len(rep), rep[:largeur])
    if isinstance(rep, dict):
        return "objet, cles : %s" % sorted(rep)[:12]
    return repr(rep)[:200]


def main():
    print("DIAGNOSTIC — catalogue des commentaires de trade (LECTURE SEULE)")
    print("=" * 68)
    try:
        client = Client().authentifier()
    except ErreurEdgewonk as e:
        print("authentification impossible : %s" % e)
        return 1
    print("authentifie · base %s\n" % BASE)

    trouves = []
    for etiquette, url in CANDIDATS:
        try:
            statut, rep = client._requete("GET", url)
        except ErreurEdgewonk as e:
            msg = str(e)
            code = "404" if " 404 " in msg else ("403" if " 403 " in msg else "erreur")
            print("  %-28s %s" % (etiquette, code))
            continue
        print("  %-28s %s  %s" % (etiquette, statut, apercu(rep)))
        if not etiquette.startswith("TEMOIN"):
            trouves.append((etiquette, url, rep))

    print()
    if not trouves:
        print("Aucun endpoint candidat ne repond.")
        print("-> il faut un HAR de l'onglet Tagging pour trouver la vraie URL.")
        return 0

    print("PISTE(S) TROUVEE(S) — on cherche « Managed » / « Not managed » dedans :")
    for etiquette, url, rep in trouves:
        elements = rep if isinstance(rep, list) else [rep]
        for x in elements:
            if isinstance(x, dict):
                blob = repr(x).lower()
                if "managed" in blob:
                    print("  %s -> %s" % (etiquette, x))
    return 0


def famille_management():
    """Les options de la famille Management de CE journal, nommees.

    ⚠️ POURQUOI CETTE SORTIE EXISTE. `ecriture.options_management` resout les
    deux options PAR NOM — « not managed » et « managed ». Quand le nom ne
    repond pas, elle retombe sur le `rating` (POSITIVE / NEGATIVE) et elle le
    DIT. Le repli est correct tant que la famille ne contient qu'une option de
    chaque rating ; s'il y en a plusieurs, il prend la premiere, et ce n'est
    plus une resolution, c'est un tirage.

    Mesure du 26/08/2026 : sur le journal futures 100004, les deux noms ne
    repondent pas et le repli s'est declenche. D'ou ce bloc — voir de ses yeux
    ce que la famille contient AVANT d'ecrire dedans.
    """
    from edgewonk.api import Client
    client = Client().authentifier()
    commentaires = client.commentaires(BASE)
    familles = {}
    for c in commentaires or []:
        familles.setdefault((c.get("type") or "?").upper(), []).append(c)
    print()
    print("  FAMILLE MANAGEMENT DU JOURNAL %s" % BASE)
    print("  " + "-" * 62)
    mgmt = familles.get("MANAGEMENT") or []
    if not mgmt:
        print("  aucune option de type MANAGEMENT.")
        print("  familles presentes : %s" % ", ".join(sorted(familles)))
        return
    for c in sorted(mgmt, key=lambda x: (not x.get("active"), x.get("id") or 0)):
        print("     id %-10s rating %-10s actif %-5s  %r"
              % (c.get("id"), c.get("rating"), c.get("active"), c.get("name")))
    actives = [c for c in mgmt if c.get("active")]
    for rating in ("POSITIVE", "NEGATIVE"):
        combien = sum(1 for c in actives if (c.get("rating") or "").upper() == rating)
        if combien > 1:
            print("  ⚠ %d options actives en %s : le repli par rating TIRE AU SORT."
                  % (combien, rating))
            print("    Renommer l'option voulue, ou ajuster NOMS_MANAGEMENT.")
        elif combien == 1:
            print("  une seule option active en %s : le repli est sans ambiguite."
                  % rating)
        else:
            print("  ⚠ AUCUNE option active en %s — le management ne pourra pas "
                  "s'ecrire dans ce sens." % rating)


if __name__ == "__main__":
    # `--management` remplace la sonde d'URL par la lecture de la famille : les
    # onze URL n'ont plus a etre sondees, on sait laquelle repond.
    if "--management" in sys.argv:
        famille_management()
    else:
        sys.exit(main())
