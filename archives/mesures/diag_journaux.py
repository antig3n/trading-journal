#!/usr/bin/env python3
"""DIAGNOSTIC EN LECTURE SEULE — ou vivent REELLEMENT les trades futures ?

N'ecrit rien, nulle part. Que des GET.

LA QUESTION, ET POURQUOI ELLE SE POSE

`docs/tradovate.md` §5 dit que les trades futures sont dans le journal **100004
(« Compte B »)**, et la mesure lui donne raison : 34 trades y repondent,
appariés au centime avec notre base. Mais l'utilisateur dit ne travailler que dans
le **Compte A (100001)** — et il y voit ses futures, avec leur
Management correctement rempli.

Les deux affirmations ne peuvent pas etre fausses en meme temps, et aucune n'est
a croire sur parole. Trois hypotheses, et une seule mesure les separe :

  A. les memes trades existent dans les DEUX journaux (double import) ;
  B. 100004 est un journal qu'il n'ouvre plus, aliment� par l'auto-import ;
  C. l'interface presente plusieurs journaux sous une seule vue, et le « Compte A » qu'il regarde contient en fait les deux.

Le discriminant est l'IDENTIFIANT de trade : s'il est le meme des deux cotes,
c'est le meme trade ; s'il differe, ce sont deux copies.

CE QU'IL AFFICHE, journal par journal : combien de trades, sur quelle periode,
quels instruments, et — pour chacun — les options de la famille Management avec
leurs libelles. C'est ce dernier point qui decide de ce qu'on peut ecrire.
"""

import collections
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from edgewonk.api import Client, ErreurEdgewonk                # noqa: E402

G, J, R, N, GRAS = "\033[32m", "\033[33m", "\033[31m", "\033[0m", "\033[1m"

# Les racines de produits futures. Servent a reconnaitre un trade futures quel
# que soit le journal qui le porte.
FUTURES = ("NQ", "MNQ", "GC", "MGC", "MCL", "6E", "M6E", "6J")


def main():
    print()
    print(GRAS + "  DIAGNOSTIC — QUEL JOURNAL PORTE QUOI" + N)
    print("  " + "=" * 68)
    try:
        client = Client().authentifier()
    except ErreurEdgewonk as e:
        print("\n  " + R + str(e).replace("\n", "\n  ") + N)
        return 1

    bases = client.bases() or []
    print("  %d journal(aux) sur le compte" % len(bases))

    par_id = {}
    for b in bases:
        bid = str(b.get("id"))
        nom = b.get("name") or b.get("label") or "?"
        print()
        print("  " + GRAS + "%s — %s" % (bid, nom) + N)
        print("  " + "-" * 68)
        try:
            trades = client.tous_les_trades(bid)
        except Exception as e:                                # noqa: BLE001
            print("  " + R + "illisible (%s)" % e + N)
            continue
        par_id[bid] = trades
        if not trades:
            print("  vide")
            continue

        instruments = collections.Counter(
            (t.get("instrument") or {}).get("name") for t in trades)
        dates = sorted((t.get("entryDate") or "")[:10] for t in trades if t.get("entryDate"))
        futures = [t for t in trades
                   if (t.get("instrument") or {}).get("name") in FUTURES]
        print("  %d trades · %s -> %s" % (len(trades), dates[0], dates[-1]))
        print("  dont FUTURES : %s%d%s" % (GRAS, len(futures), N))
        print("  instruments  : %s"
              % ", ".join("%s(%d)" % (i, n) for i, n in instruments.most_common(12)))

        try:
            commentaires = client.commentaires(bid)
        except Exception as e:                                # noqa: BLE001
            print("  " + J + "commentaires illisibles (%s)" % e + N)
            continue
        mgmt = [c for c in (commentaires or [])
                if (c.get("type") or "").upper() == "MANAGEMENT" and c.get("active")]
        if not mgmt:
            print("  " + J + "aucune option Management active" + N)
        else:
            libelles = ", ".join("%r (id %s, %s)"
                                 % (c.get("name"), c.get("id"), c.get("rating"))
                                 for c in mgmt)
            attendus = {"not managed", "managed"}
            trouves = {(c.get("name") or "").strip().lower() for c in mgmt}
            marque = G + "OK" + N if attendus <= trouves else J + "A RENOMMER" + N
            print("  Management   : %s  [%s]" % (libelles, marque))

    # --- le discriminant : les identifiants se recoupent-ils ?
    print()
    print("  " + GRAS + "LES MEMES TRADES SONT-ILS DANS PLUSIEURS JOURNAUX ?" + N)
    print("  " + "-" * 68)
    ids = {b: {t.get("id") for t in ts} for b, ts in par_id.items()}
    croise = False
    for a in sorted(ids):
        for b in sorted(ids):
            if a >= b:
                continue
            communs = ids[a] & ids[b]
            if communs:
                croise = True
                print("  %s et %s partagent %d identifiant(s) — MEME journal, "
                      "vu deux fois" % (a, b, len(communs)))
    if not croise:
        print("  Aucun identifiant commun : ce sont des journaux DISTINCTS.")
        print("  Un trade futures visible dans deux d'entre eux serait donc une")
        print("  COPIE, pas le meme trade — et il faudrait choisir lequel le")
        print("  pipeline alimente.")

    print()
    print("  " + "=" * 68)
    print("  Rien n'a ete ecrit.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
