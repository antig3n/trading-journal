"""Étape 2 : le fichier de saisie du SL/TP initial, et ses garde-fous.

Décision figée le 25/08/2026 (voir ctrader-sltp-protocol.md §3 ter) : aucun
transport automatique du SL/TP initial n'était à la fois complet, fiable et
léger. Trois valeurs par trade sont saisies à la main.

⚠️ LA SAISIE SE FAIT PAR POSITION, PAS PAR JAMBE.

Une position cTrader n'a qu'une protection, quel que soit le nombre de sorties
partielles. Faire saisir quatre fois le même SL pour une position sortie en
quatre fois serait redondant ET dangereux : deux valeurs divergentes sur la
même position, et plus personne ne sait laquelle est vraie. Le fichier compte
donc une ligne par position (38 sur le relevé du 25/08, pour 46 jambes), et
`appliquer` réplique la valeur sur chacune des jambes.

Le programme ne fait JAMAIS confiance à cette saisie. Deux niveaux :

  REJET     — la ligne ne peut pas être écrite. Un seul cas : le niveau est du
              mauvais côté du prix d'entrée. Aucune interprétation valable.
  SIGNALEMENT — la ligne est écrite après validation humaine. Tout le reste.

L'appariement s'appuie UNIQUEMENT sur la colonne `cle_position`. Les autres
colonnes du fichier de saisie sont là pour l'œil : un tableur peut les
reformater sans aucune conséquence.
"""

import csv
import io
import os

# Colonnes du fichier remis à l'utilisateur. Seules `sl` et `tp` sont à remplir.
COLONNES_SAISIE = ["cle_position", "date", "heure", "symbole", "sens",
                   "entree", "lots", "jambes", "net", "sl", "tp", "management"]

# ------------------------------------------------------------------ management
# « Ai-je touche a mon stop ou a ma cible apres l'entree ? »
#
#   OK = non, le plan a ete tenu      -> « Not managed » cote Edgewonk
#   KO = oui, la position a ete geree -> « Managed »
#
# Deux lettres, et l'objectif declare de l'utilisateur est que ce soit OK partout :
# sa strategie est censee tenir sans management. Le champ mesure donc une
# DISCIPLINE, pas une technique — raison de plus pour qu'il soit saisi au moment
# ou le trade est frais, a cote du SL et du TP, et jamais reconstitue plus tard.
#
# Une case vide BLOQUE l'integration (choix de l'utilisateur du 26/08/2026) : c'est
# le seul controle du lot qui ne puisse pas etre rattrape par la mesure, donc le
# seul qu'un oubli ferait disparaitre en silence.
MANAGEMENT_OK = "OK"
MANAGEMENT_KO = "KO"


def normaliser_management(valeur):
    """« ok » / « Ko » -> « OK » / « KO ». None si vide ou illisible."""
    t = (valeur or "").strip().upper()
    return t if t in (MANAGEMENT_OK, MANAGEMENT_KO) else None

RR_MIN = 0.3      # en deçà : probable faute de frappe
RR_MAX = 10.0     # au-delà : possible, mais on le montre


def _f(v):
    try:
        return float(str(v).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def generer(positions, chemin, suggestions=None):
    """Écrit le fichier à remplir, une ligne par POSITION, SL/TP vides.

    Les positions déjà renseignées sont pré-remplies : re-générer n'efface
    jamais un travail déjà fait.

    `suggestions` : {cle_position: {"sl": .., "tp": ..}} — des valeurs LUES
    dans un export, proposees a l'utilisateur. Ajoute le 26/08/2026 pour Tradovate,
    dont l'export « Orders » porte les brackets ATM.

    ⚠️ ORDRE DE PRIORITE, ET IL N'EST PAS NEGOCIABLE : ce que porte deja la
    BASE gagne toujours sur une suggestion. La suggestion ne remplit qu'une
    case vide. Sans cette regle, un ré-import du meme export ecraserait une
    correction faite a la main — silencieusement, puisque les deux valeurs sont
    plausibles. La base reste la reference, l'export n'est qu'une proposition.
    """
    suggestions = suggestions or {}
    dossier = os.path.dirname(chemin)
    if dossier and not os.path.isdir(dossier):
        os.makedirs(dossier)
    ordonnees = sorted(positions, key=lambda c: positions[c].get("ouverture", ""))
    with io.open(chemin, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLONNES_SAISIE)
        w.writeheader()
        for cp in ordonnees:
            p = positions[cp]
            ouv = p.get("ouverture", "")
            date = "%s/%s/%s" % (ouv[8:10], ouv[5:7], ouv[0:4]) if len(ouv) >= 10 else ""
            w.writerow({
                "cle_position": cp,
                "date": date,
                "heure": ouv[11:19],
                "symbole": p.get("symbole_broker", ""),
                "sens": p.get("sens", ""),
                "entree": p.get("entree", ""),
                "lots": "%.2f" % p.get("lots", 0),
                "jambes": len(p.get("jambes", [])),
                "net": "%.2f" % p.get("net", 0),
                "sl": p.get("sl", "") or suggestions.get(cp, {}).get("sl", ""),
                "tp": p.get("tp", "") or suggestions.get(cp, {}).get("tp", ""),
                "management": p.get("management", ""),
            })
    return len(ordonnees)


def lire(chemin):
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        lignes = [r for r in csv.DictReader(f)]
    # tolère l'ancien nom de colonne, et un tableur qui aurait renommé
    for r in lignes:
        if "cle_position" not in r and "cle" in r:
            r["cle_position"] = r["cle"]
    return [r for r in lignes if (r.get("cle_position") or "").strip()]


# Au-dela de ce |R| realise, le rapport entre le risque annonce et le mouvement
# reel n'est plus credible. Cale sur la mesure du 26/08/2026 : les deux seules
# valeurs aberrantes de 203 jambes etaient a 180 R et -12.8 R, la suivante a
# 4.4 R. Le seuil laisse donc passer tout ce qui est plausible.
R_ABERRANT = 10.0


def controler(lignes, positions):
    """Retourne (valides, rejets, signalements).

    `positions` est la vue position des trades CONCERNÉS — pas toute la base.
    C'est ce qui borne le contrôle d'exhaustivité au relevé courant : sans ça,
    chaque sync signalerait toutes les positions des semaines précédentes.

    `valides` : {cle_position: {"sl": .., "tp": ..}} — prêt à répliquer, sous
    réserve que l'utilisateur acquitte les signalements.
    """
    valides, rejets, signalements = {}, [], []
    vues = set()

    # ⚠️ LA DETECTION EST PAR LIGNE, PAS PAR LOT. Le chantier retroactif
    # CONCATENE tous ses fichiers mensuels avant d'appeler ce controle : un
    # drapeau global mis a vrai par le seul fichier d'aout ferait rejeter les
    # 148 lignes des dix autres mois, qui n'ont pas la colonne. Le pipeline
    # entier se serait bloque sur une colonne ajoutee pour lui.
    #
    #   cle absente de la ligne  -> ancien format, on laisse passer
    #   cle presente mais vide   -> REJET
    sans_colonne = 0

    for r in lignes:
        cp = (r["cle_position"] or "").strip()
        if cp in vues:
            rejets.append("%s : la position apparait deux fois dans le fichier de saisie" % cp)
            continue
        vues.add(cp)

        p = positions.get(cp)
        if p is None:
            rejets.append("%s : position absente du releve importe — bon fichier de saisie ?" % cp)
            continue

        sl, tp = _f(r.get("sl")), _f(r.get("tp"))
        entree = _f(p.get("entree"))
        if entree is None:
            rejets.append("%s : prix d'entree illisible dans la base" % cp)
            continue

        # --- MANAGEMENT. Rejet et pas signalement : arbitre par l'utilisateur le
        #     26/08/2026. Aucune mesure ne peut retrouver apres coup s'il a
        #     bouge son stop — contrairement au SL, qu'un R aberrant trahit.
        #     Un oubli ici est definitif, donc il bloque.
        mgmt = normaliser_management(r.get("management"))
        if "management" not in r:
            sans_colonne += 1
        elif mgmt is None:
            brut = (r.get("management") or "").strip()
            rejets.append("%s : management %s — attendu %s (plan tenu) ou %s "
                          "(position geree)"
                          % (cp, "non renseigne" if not brut else "illisible (%r)" % brut,
                             MANAGEMENT_OK, MANAGEMENT_KO))
            continue

        nb = len(p.get("jambes", []))
        detail = "%s %s, %.2f lots, net %.2f%s" % (
            p.get("sens"), p.get("symbole_broker"), p.get("lots", 0), p.get("net", 0),
            ", %d sorties" % nb if nb > 1 else "")

        if sl is None and tp is None:
            # ⚠️ ON N'ABANDONNE PAS LA LIGNE POUR AUTANT — corrige le 26/08/2026,
            # apres que le cas se soit produit en reel.
            #
            # Ce `continue` sautait la ligne entiere, donc le MANAGEMENT avec.
            # Invisible tant que le pipeline ne servait que cTrader : la-bas,
            # toute position saisie a un SL. Cote futures, 28 positions sur 36
            # sont des entrees posees au graphique, sans protection lisible dans
            # l'export — et l'utilisateur avait rempli leurs 28 cases `management`.
            # Elles ont ete signalees, puis silencieusement jetees : 7 trades
            # tagges sur 35 au lieu de 35.
            #
            # Le SL et le TP ne sont pas les seules valeurs de cette ligne. Le
            # management est une saisie A PART ENTIERE, la seule qu'aucune
            # mesure ne peut retrouver apres coup — c'est meme la raison pour
            # laquelle une case vide est un REJET. La jeter parce qu'une AUTRE
            # colonne est vide etait l'exact contraire de l'intention.
            signalements.append("%s : ni SL ni TP renseignes (%s)" % (cp, detail))
            if mgmt:
                valides[cp] = {"sl": "", "tp": "", "management": mgmt}
            continue

        achat = p.get("sens") == "Achat"
        bloque = False

        for nom, val, doit_etre_sous in (("SL", sl, achat), ("TP", tp, not achat)):
            if val is None:
                continue
            if val == entree:
                rejets.append("%s : %s egal au prix d'entree (%s)" % (cp, nom, entree))
                bloque = True
            elif doit_etre_sous and val > entree:
                rejets.append("%s : %s a %s, au-dessus de l'entree %s sur un %s"
                              % (cp, nom, val, entree, p.get("sens")))
                bloque = True
            elif (not doit_etre_sous) and val < entree:
                rejets.append("%s : %s a %s, en dessous de l'entree %s sur un %s"
                              % (cp, nom, val, entree, p.get("sens")))
                bloque = True
        if bloque:
            continue

        if sl is None:
            signalements.append("%s : TP seul, pas de SL — R non calculable" % cp)
        elif tp is None:
            signalements.append("%s : SL seul, pas de TP" % cp)
        else:
            risque = abs(entree - sl)
            if risque:
                rr = abs(tp - entree) / risque
                if rr < RR_MIN or rr > RR_MAX:
                    signalements.append("%s : R:R de %.1f, hors de la bande %.1f–%.0f — a verifier"
                                        % (cp, rr, RR_MIN, RR_MAX))

        # --- R REALISE : le seul controle du SL qui ne depende PAS du TP.
        #
        # Mesure du 26/08/2026. Le NAS100 du 14/08 portait un SL a 0.45 point
        # sur un indice qui bouge de centaines de points. Le controle du R:R
        # l'avait bien signale — « R:R de 430.7 » — mais l'utilisateur a resolu
        # l'alerte en retirant le TP. Sans TP, plus de R:R, plus d'alerte, et
        # le stop aberrant est reste : il a produit +180 R a lui seul et fausse
        # tout le journal pendant deux jours.
        #
        # Ici on n'a besoin d'aucun TP : l'entree et la sortie viennent du
        # releve, le SL de la saisie. Un |R| au-dela de R_ABERRANT dit qu'il y a
        # une disproportion entre le risque annonce et le mouvement reel.
        # Signalement et pas rejet : un 12 R existe. Mais il ne se tait plus.
        sortie = _f(p.get("sortie"))
        if sl and sortie is not None and entree is not None and sl != entree:
            signe = 1.0 if p.get("sens") == "Achat" else -1.0
            # ⚠️ NE PAS nommer cette variable `r` : la boucle s'en sert plus bas
            # pour la ligne de saisie, et l'ecraser fait planter `controler`.
            r_reel = signe * (sortie - entree) / abs(entree - sl)
            if abs(r_reel) > R_ABERRANT:
                signalements.append(
                    "%s : R realise de %+.0f — le SL a %s est a %.5g de l'entree %s, "
                    "soit %.0f fois moins que le mouvement reel. Stop initial ou "
                    "break-even ?" % (cp, r_reel, sl, abs(entree - sl), entree,
                                      abs(r_reel)))

        valides[cp] = {"sl": (r.get("sl") or "").strip(),
                       "tp": (r.get("tp") or "").strip(),
                       "management": mgmt or ""}

    if sans_colonne:
        signalements.append(
            "%d ligne(s) de saisie sans colonne « management » (ancien format) — "
            "le champ ne sera pas ecrit pour elles ; regenerer le fichier pour "
            "l'obtenir" % sans_colonne)

    for cp, p in positions.items():
        if cp not in vues:
            signalements.append("%s : aucune ligne de saisie pour cette position (%s %s, %s)"
                                % (cp, p.get("sens"), p.get("symbole_broker"),
                                   p.get("ouverture", "")[:16]))

    return valides, rejets, signalements


def appliquer(trades, positions, valides):
    """Réplique le SL/TP saisi sur chaque JAMBE de la position.

    Retourne (nb_valeurs_ecrites, nb_jambes_touchees, nb_positions).
    """
    valeurs, jambes = 0, set()
    for cp, v in valides.items():
        p = positions.get(cp)
        if p is None:
            continue
        for cle in p.get("jambes", []):
            t = trades.get(cle)
            if t is None:
                continue
            for champ in ("sl", "tp", "management"):
                if v.get(champ):
                    if t.get(champ) != v[champ]:
                        t[champ] = v[champ]
                        valeurs += 1
                    jambes.add(cle)
    return valeurs, len(jambes), len(valides)
