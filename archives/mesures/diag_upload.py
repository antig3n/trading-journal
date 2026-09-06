#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnostic n°8 — les DEUX mecanismes jamais confrontes a l'API reelle.

    ../.venv/bin/python3 outils/diag_upload.py      (ou n'importe quel python3)

Tout le reste de l'etape 5 a ete valide en conditions reelles. Ces deux-la
ne l'ont jamais ete, et ils ont ete ecrits contre un faux serveur :

  1. **L'upload multipart ecrit a la main.** Le projet est en bibliotheque
     standard pure, donc pas de `requests` : le corps est construit octet par
     octet. Un parseur de test l'accepte — reste a savoir si LEUR serveur
     l'accepte.
  2. **`gain: null` sur une strategie alternative absente du trade.** Quand un
     palier n'existe pas encore, on n'a aucun gain a preserver. Le serveur peut
     l'accepter, l'ignorer, ou refuser. Inconnu.

CE SCRIPT ECRIT — c'est le seul de `outils/` dans ce cas avec
`restaurer_inreview.py`. Il n'ecrit QUE dans le bac a sable 100005, il prend un
instantane avant, et il restaure a la fin. Il refuse tout autre journal.
"""

import io
import json
import os
import sys

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RACINE)

from edgewonk.api import Client, ErreurEdgewonk, charge_utile_put   # noqa: E402

BAC_A_SABLE = "100005"
DONNEES = os.path.normpath(os.path.join(RACINE, "..", "donnees"))


def _png_disponible():
    """N'importe quel PNG deja rendu, sinon l'apercu a la racine."""
    racine_g = os.path.join(DONNEES, "graphiques")
    for dossier, _, fichiers in os.walk(racine_g):
        for f in sorted(fichiers):
            if f.lower().endswith(".png"):
                return os.path.join(dossier, f)
    secours = os.path.normpath(os.path.join(RACINE, "..", "apercu_LTF.png"))
    return secours if os.path.exists(secours) else None


def main():
    png = _png_disponible()
    if not png:
        sys.exit("aucun PNG sous donnees/graphiques/ — lancer `jt.py graphiques` d'abord")
    print("image de test : %s (%d octets)" % (os.path.relpath(png, RACINE), os.path.getsize(png)))

    client = Client().authentifier()
    print("authentifie\n")

    trades = client.tous_les_trades(BAC_A_SABLE, page=50, plafond=50)
    if not trades:
        sys.exit("le bac a sable %s est vide" % BAC_A_SABLE)
    cible = trades[0]
    tid = cible["id"]
    setup = cible.get("setup") or {}
    sid = setup.get("id") if isinstance(setup, dict) else setup
    print("trade cible : %s  (%s, setup %s)"
          % (tid, (cible.get("instrument") or {}).get("name"), sid))

    # --- INSTANTANE, avant toute ecriture. Regle non negociable du projet.
    avant = client.trade(BAC_A_SABLE, tid)
    chemin = os.path.join(DONNEES, "instantanes", "diag-upload-%s.json" % tid)
    if not os.path.isdir(os.path.dirname(chemin)):
        os.makedirs(os.path.dirname(chemin))
    with io.open(chemin, "w", encoding="utf-8") as f:
        f.write(json.dumps(avant, ensure_ascii=False, indent=1))
    print("instantane : %s\n" % os.path.relpath(chemin, DONNEES))

    verdicts = []

    # ---------------------------------------------------------- test 1 : upload
    print("--- TEST 1 : upload multipart ---")
    try:
        client.supprimer_image(BAC_A_SABLE, tid, 6)      # emplacement 6, le moins utilise
        statut, rep = client.televerser_image(
            BAC_A_SABLE, tid, 6, png, "DIAG_upload_multipart")
        print("  POST -> %s  %s" % (statut, {k: rep.get(k) for k in ("pictureId", "size")}))
        client.modifier(BAC_A_SABLE, tid, {"screenshot6Exists": True})
        relu = client.trade(BAC_A_SABLE, tid)
        ok = bool(relu.get("screenshot6Exists"))
        print("  relecture : screenshot6Exists = %r" % relu.get("screenshot6Exists"))
        print("  cle posee par le serveur  : %r" % relu.get("screenshot6key"))
        verdicts.append(("upload multipart", ok))
    except ErreurEdgewonk as e:
        print("  ECHEC : %s" % e)
        verdicts.append(("upload multipart", False))

    # ------------------------------------------ test 2 : gain null sur strategie
    print("\n--- TEST 2 : alternativeStrategies avec gain=null ---")
    try:
        catalogue = client.strategies(BAC_A_SABLE, sid) if sid else []
        print("  strategies du setup : %s"
              % [(s.get("id"), s.get("name")) for s in catalogue])
        if not catalogue:
            print("  AUCUNE strategie sur ce setup — test impossible ici")
            verdicts.append(("gain=null", None))
        else:
            s0 = catalogue[0]
            complet = client.trade(BAC_A_SABLE, tid)
            charge = charge_utile_put(complet, {
                "alternativeStrategies": [
                    {"strategyId": s0["id"], "gain": None, "rMultiple": -1.0}]})
            statut, _ = client.remplacer(BAC_A_SABLE, tid, charge)
            relu = client.trade(BAC_A_SABLE, tid)
            ecrit = relu.get("alternativeStrategies") or []
            print("  PUT -> %s" % statut)
            print("  relecture : %s" % ecrit)
            ok = any(abs((x.get("rMultiple") or 0) + 1.0) < 1e-9 for x in ecrit)
            verdicts.append(("gain=null", ok))
    except ErreurEdgewonk as e:
        print("  ECHEC : %s" % e)
        verdicts.append(("gain=null", False))

    # ------------------------------------------------------------- restauration
    print("\n--- RESTAURATION ---")
    try:
        client.supprimer_image(BAC_A_SABLE, tid, 6)
        client.remplacer(BAC_A_SABLE, tid, charge_utile_put(avant, {}))
        final = client.trade(BAC_A_SABLE, tid)
        ecarts = [c for c in ("alternativeStrategies", "screenshot6Exists",
                              "additionalNotes", "setup")
                  if json.dumps(final.get(c), sort_keys=True, default=str)
                  != json.dumps(avant.get(c), sort_keys=True, default=str)]
        print("  ecarts restants : %s" % (ecarts or "aucun"))
    except ErreurEdgewonk as e:
        print("  ECHEC DE RESTAURATION : %s" % e)
        print("  -> l'instantane est en %s" % chemin)

    print("\n--- VERDICT ---")
    for nom, ok in verdicts:
        print("  %-22s %s" % (nom, {True: "OK", False: "ECHEC", None: "non teste"}[ok]))
    print("\n(le trade %s du bac a sable a ete restaure)" % tid)


if __name__ == "__main__":
    main()
