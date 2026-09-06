"""Les SL et TP de Tradovate, lus dans l'export « Orders ».

CE QUE CE MODULE FAIT, ET CE QU'IL REFUSE DE FAIRE

Il rend une protection pour les entrees passees a l'**ATM** (`Text =
multibracket`), lues par groupe d'ids consecutifs — et, DEPUIS LE 28/08/2026,
pour les entrees posees au graphique (`Text = Chart`), lues par FENETRE DE
POSITION. Les deux lectures sont mesurees, la seconde a ete refusee pendant
deux jours, et le paragraphe suivant dit pourquoi elle ne l'est plus.

──────────────────────────────────────────────────────────────────────────────
LE FAIT QUI DECIDE DE TOUT — mesure du 26/08/2026 sur l'export de 204 ordres

L'export ne porte aucun lien de parente entre une entree et ses protections.
Il n'y a que des ordres, a la queue leu leu. Deux regimes coexistent :

  `Text = multibracket`  (45 ordres) — poses en BLOC par l'ATM. Ids consecutifs,
      dans l'ordre : entree, puis la cible (Limit, sens oppose), puis le stop
      (Stop, sens oppose). Le groupe se lit sans ambiguite.

  `Text = Chart`         (144 ordres) — poses un par un au graphique. Un « Buy
      Stop » 183 points au-dessus d'un short peut y etre un stop de protection
      large OU un ordre d'entree en cassure. **Rien dans le fichier ne
      tranche.** C'est exactement l'erreur qu'Edgewonk commet : il ramasse le
      Stop le plus proche dans le temps et le colle en SL — d'ou les stops a
      183 points et les cibles a 0,5 point du §5 de `docs/tradovate.md`.

⚠️ CE RAISONNEMENT ETAIT JUSTE, ET IL LUI MANQUAIT DEUX CONTRAINTES.
*(Renverse le 28/08/2026, apres mesure. Le texte d'origine est conserve
ci-dessus : il dit exactement ce qui manquait.)*

« Rien dans le fichier ne tranche » etait faux — rien dans **l'ordre pris
isolement** ne tranche. Deux contraintes exterieures le font :

  1. le **COTE**. Un ordre d'entree est du cote qui OUVRE la position ; une
     protection est du cote qui la FERME. Le « Buy Stop au-dessus d'un short »
     n'est ambigu que si on oublie qu'on est deja short.
  2. la **FENETRE**. Une protection vit entre l'ouverture et la fermeture de
     SA position, bornee par l'ouverture de la suivante sur le meme contrat.

Avec les deux, le premier `Stop` du cote de fermeture est le SL initial, et le
premier `Limit` la cible. **Trois mesures le valident** (28/08/2026) :

  * sur les 22 ordres de protection qui ont REELLEMENT ferme une position, le
    prix de l'ordre retombe sur notre prix de sortie **20 fois au tick pres** —
    les 2 ecarts sont des sorties partielles au VWAP (MCL 11 lots, 6E 4 lots) ;
  * sur les 6 positions ATM deja en base, la regle par fenetre rend
    **exactement** ce que la lecture par ids avait ecrit. Ce n'est pas une
    regle concurrente, c'est la meme, generalisee ;
  * sur les 18 positions `Chart` du journal, elle donne **15 valeurs
    identiques a Edgewonk et 3 differentes — les 3 ou Edgewonk se trompe**,
    toujours pour la meme raison : il ignore le cote et la fenetre. Il a lu
    l'ordre d'ENTREE comme une cible (`20260807-160834`, TP 29645.5 ;
    `20260818-144959`, TP 1.1589) et un Limit du **lendemain** comme la cible
    d'un trade de la veille (`20260817-154744`, TP 4380.2).

Ce qui ne change pas : la valeur qui sort d'ici reste une SUGGESTION, relue
dans le fichier de saisie. « Un stop devine est pire qu'un stop absent » (§4 du
README) tient toujours — c'est justement pourquoi un stop MESURE, lui, doit
etre lu plutot que laisse vide.

CE QUE LA MESURE DIT DU CALENDRIER, et pourquoi ce n'est pas une mauvaise
nouvelle : l'utilisateur est passe a l'ATM le **18/08/2026**. Avant, tout est
`Chart` ; depuis le 20/08, tout est `multibracket`.

    06/08 -> 17/08   Chart 100 %          -> saisie manuelle
    18/08            Chart 24 / bracket 3
    19/08            Chart  1 / bracket 3
    20/08            Chart  3 / bracket 22
    21/08            Chart  0 / bracket 6
    24/08            Chart  3 / bracket 11 -> automatique

La partie manuelle est donc un ARRIERE borne — une douzaine de trades — pas une
charge recurrente.
──────────────────────────────────────────────────────────────────────────────

LA VALEUR LUE EST LA VALEUR FINALE, et c'est assume.

Tradovate versionne ses ordres, mais l'export n'en donne que le dernier etat
(`docs/tradovate.md` §6, demontre : le preset ATM pose 20/20 ticks, et les groupes
affichent 6, 7, 9, 52, 100, 193 ticks). L'utilisateur a tranche le 25/08 qu'il ne
fait **pas** de management sur les futures : la derniere valeur EST donc le
risque initial, par construction.

Cette decision reste AUDITABLE, et c'est ce qui la rend acceptable : un stop
resserre vers le break-even sans que la cible bouge fait exploser le R:R. Neuf
groupes sur onze tombent entre 3,2 et 4,1 — la signature de ses setups. Un
groupe a 12,5 sortait du lot, et c'etait bien un stop resserre. D'ou
`RR_MANAGEMENT`, qui SIGNALE sans jamais corriger.
"""

import csv
import io
import re

# Au-dela de ce R:R, le stop a probablement ete resserre apres l'entree : la
# valeur lue n'est plus le risque initial. Cale sur la mesure du 25/08/2026 —
# neuf groupes entre 3,2 et 4,1, un seul a 12,5. Le seuil laisse passer toute la
# bande normale et n'attrape que ce qui en sort franchement.
RR_MANAGEMENT = 6.0

# Le preset ATM de l'utilisateur pose 20 ticks de chaque cote. Quand les deux
# jambes valent EXACTEMENT ce nombre, le placeholder a probablement survecu :
# les niveaux lus sont ceux du preset, pas ceux du trade.
#
# ⚠️ Le drapeau « ordre modifie » (Version ID != Order ID) NE SUFFIT PAS a le
# detecter. Mesure du 26/08/2026 : le bracket du 24/08 16:35 porte 20/20 ticks
# ET ses deux protections sont marquees modifiees. `docs/tradovate.md` §6 le disait
# « marque intact » — c'etait faux, mesure sur un regroupement different. On
# detecte donc sur la GEOMETRIE, qui elle ne ment pas.
#
# Un vrai trade a 1:1 sur exactement 20 ticks existe : c'est un SIGNALEMENT,
# jamais un rejet ni une correction.
PRESET_ATM_TICKS = 20.0

# ------------------------------------- le stop a-t-il ete bouge LONGTEMPS apres ?
#
# Le §7 de `docs/tradovate.md` repose sur une phrase de l'utilisateur : « j'ajuste mon
# bracket une fois apres l'entree, puis je n'y touche plus ». C'est ce qui rend
# la derniere valeur exportee utilisable comme risque INITIAL. Jusqu'ici, rien
# ne le verifiait.
#
# Or l'export porte de quoi le faire : la colonne `Timestamp` d'un ordre est sa
# DERNIERE mise a jour. L'ecart entre le remplissage de l'entree et la derniere
# modification de son stop mesure donc directement combien de temps ce stop a
# continue de bouger.
#
# MESURE du 26/08/2026, sur les dix brackets de l'export :
#
#     0, 0, 0, 0, 0, 1, 1, 8 minutes … et 186 minutes.
#
# Neuf ajustements dans les huit minutes — la routine decrite au §7, confirmee.
# Et un seul a plus de trois heures : la position 6EU6 du 20/08 14:02, dont les
# BOUGIES disaient deja que le stop n'etait pas en place (le prix est passe
# 1,9 R dessous sans que le trade se termine). **Deux methodes independantes,
# le meme trade.**
#
# 30 minutes tombe donc dans une zone vide — entre 8 et 186 — et n'est pas un
# seuil ajuste sur un cas. Signalement, jamais correction : on ne sait pas quel
# etait le niveau initial, et on ne l'invente pas.
DELAI_AJUSTEMENT_MAX = 30.0

# Ids consecutifs : un groupe ATM est cree d'un bloc. L'ecart observe entre
# l'entree et sa derniere protection ne depasse jamais 6 sur l'export mesure ;
# on laisse de la marge sans ouvrir la porte a un rapprochement fortuit.
ECART_ID_MAX = 12

TEXTE_ATM = "multibracket"
# Les ordres que l'ATM ne pose pas : sorties manuelles et liquidation
# automatique. Ils ne sont jamais une entree.
TEXTES_SORTIE = ("Exit", "AutoLiq")


def _f(txt):
    t = (txt or "").strip().replace(",", "")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def lire(chemin):
    """L'export « Orders » -> liste de dicts normalises, tries par Order ID.

    Aucune interpretation ici : uniquement de la lecture. `Order ID` est un
    entier croissant chez Tradovate, et c'est cet ordre-la qui porte
    l'information de groupe — pas l'ordre des lignes du fichier, qu'un tri de
    tableur peut avoir change.
    """
    with io.open(chemin, encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f))
    ordres = []
    for r in lignes:
        r = {k: (v or "").strip() for k, v in r.items() if k}
        brut = r.get("Order ID") or ""
        if not re.match(r"^\d+$", brut):
            continue
        ordres.append({
            "id": int(brut),
            "contrat": r.get("Contract", ""),
            "produit": r.get("Product", ""),
            "sens": r.get("B/S", ""),
            "type": r.get("Type", ""),
            "statut": r.get("Status", ""),
            "texte": r.get("Text", ""),
            "quantite": _f(r.get("Quantity")),
            "limite": _f(r.get("Limit Price")),
            "stop": _f(r.get("Stop Price")),
            "prix_fill": _f(r.get("Avg Fill Price")),
            "heure": r.get("Fill Time") or r.get("Timestamp") or "",
            "horodatage": r.get("Timestamp", ""),
            "modifie": (r.get("Version ID") or "") != brut,
            "pas": _f(r.get("_tickSize")),
        })
    ordres.sort(key=lambda o: o["id"])
    return ordres


def _minutes(depart, arrivee):
    """Minutes ecoulees entre deux horodatages « MM/JJ/AAAA HH:MM:SS ».

    None si l'un des deux est illisible : on ne signale rien plutot que de
    signaler sur une donnee qu'on n'a pas su lire.
    """
    import datetime as dt
    try:
        a = dt.datetime.strptime((depart or "").strip(), "%m/%d/%Y %H:%M:%S")
        b = dt.datetime.strptime((arrivee or "").strip(), "%m/%d/%Y %H:%M:%S")
    except ValueError:
        return None
    return (b - a).total_seconds() / 60.0


def _oppose(sens):
    s = (sens or "").strip().lower()
    return "Sell" if s.startswith("buy") else ("Buy" if s.startswith("sell") else "")


def _meme_sens(a, b):
    return (a or "").strip().lower()[:1] == (b or "").strip().lower()[:1]


def groupes_atm(ordres):
    """Les triplets (entree, cible, stop) poses en bloc par l'ATM.

    La forme est mesuree, pas supposee : dans un groupe `multibracket`, l'entree
    vient d'abord, puis la cible (Limit, sens oppose) et le stop (Stop, sens
    oppose), en ids consecutifs. On EXIGE les trois, dans une fenetre d'ids
    serree — deux ordres qui se ressemblent a vingt minutes d'ecart ne forment
    pas un bracket, et un rapprochement approximatif ici deviendrait un R faux
    plus loin.

    Retourne une liste de dicts, un par entree ATM identifiee.
    """
    par_id = {o["id"]: i for i, o in enumerate(ordres)}
    groupes = []
    for i, e in enumerate(ordres):
        if e["texte"] != TEXTE_ATM or e["texte"] in TEXTES_SORTIE:
            continue
        oppose = _oppose(e["sens"])
        if not oppose:
            continue
        cible = stop = None
        for suivant in ordres[i + 1:i + 4]:
            if suivant["id"] - e["id"] > ECART_ID_MAX:
                break
            if suivant["contrat"] != e["contrat"] or suivant["texte"] != TEXTE_ATM:
                continue
            if not _meme_sens(suivant["sens"], oppose):
                continue
            if suivant["type"] == "Limit" and cible is None and suivant["limite"] is not None:
                cible = suivant
            elif suivant["type"] == "Stop" and stop is None and suivant["stop"] is not None:
                stop = suivant
        if cible is None and stop is None:
            continue
        groupes.append({"entree": e, "cible": cible, "stop": stop})
    return groupes, par_id


def protections(chemin):
    """{ (contrat, sens, heure_de_fill) : {"sl", "tp", "entree", "signalement"} }

    ⚠️ CE QUI SORT D'ICI EST UN CANDIDAT, PAS UN FAIT.

    Mesure du 26/08/2026, et elle a coute un faux signalement : l'ordre 921706
    du 24/08 est un `Buy Stop` marque `multibracket`, suivi de deux ordres
    opposes — il a donc toute la FORME d'une entree ATM. C'en est en realite le
    **stop de la position precedente**, remplace apres annulation du premier
    (1.16845 -> 1.16805), qui s'est declenche sur 2 des 4 contrats. Lu comme une
    entree, il portait « 20/20 ticks », et le detecteur de placeholder criait au
    loup.

    Rien dans l'export ne distingue les deux formes. **Seul le FIFO le sait** :
    une entree OUVRE une position, un stop la ferme. C'est donc
    `tradovate/statement.suggestions_sltp` qui tranche, en n'acceptant qu'un
    bracket dont l'heure de remplissage coincide avec l'ouverture d'une
    position. Ce module ne compte plus les entrees sans bracket et n'emet plus
    de signalement par bracket : il rend des candidats, et les notes qui restent
    portent sur la couverture d'ensemble.

    *Leçon deja vue trois fois ici : un signalement qui se declenche sur du sain
    dresse a ignorer les signalements.*

    Retourne (candidats, notes).
    """
    ordres = lire(chemin)
    groupes, _ = groupes_atm(ordres)
    trouvees, notes = {}, []

    for g in groupes:
        e = g["entree"]
        if e["statut"] != "Filled":
            continue                       # bracket annule avant d'entrer
        sl = g["stop"]["stop"] if g["stop"] else None
        tp = g["cible"]["limite"] if g["cible"] else None
        entree = e["prix_fill"]
        signalement = ""

        # Controle le plus direct : depuis combien de temps ce stop bougeait-il
        # encore ? Il precede les autres parce qu'il mesure un FAIT (une date),
        # la ou le R:R et la geometrie mesurent une vraisemblance.
        retard = _minutes(e["heure"], g["stop"]["horodatage"]) if g["stop"] else None
        if retard is not None and retard > DELAI_AJUSTEMENT_MAX:
            signalement = ("stop encore modifie %.0f minutes apres l'entree — "
                           "au-dela de %.0f, ce n'est plus l'ajustement d'entree : "
                           "la valeur lue n'est pas le risque initial"
                           % (retard, DELAI_AJUSTEMENT_MAX))

        if not signalement and sl is not None and tp is not None and entree is not None and sl != entree:
            rr = abs(tp - entree) / abs(entree - sl)
            if rr > RR_MANAGEMENT:
                # On SIGNALE, on ne corrige pas : la valeur lue reste celle de
                # l'export. C'est a l'utilisateur de dire si le stop a bouge.
                signalement = ("R:R de %.1f — au-dela de %.0f, le stop a "
                               "probablement ete resserre apres l'entree : la "
                               "valeur lue n'est plus le risque initial"
                               % (rr, RR_MANAGEMENT))
        if sl is None:
            signalement = "bracket sans stop dans l'export"
        elif tp is None and not signalement:
            signalement = "bracket sans cible dans l'export"
        elif not signalement and e["pas"] and entree is not None:
            en_ticks = lambda a, b: round(abs(a - b) / e["pas"], 1)
            if (en_ticks(entree, sl) == PRESET_ATM_TICKS
                    and en_ticks(tp, entree) == PRESET_ATM_TICKS):
                signalement = ("%g / %g ticks — c'est exactement le preset ATM : "
                               "le bracket n'a probablement jamais ete ajuste, "
                               "et ces niveaux ne sont pas ceux du trade"
                               % (PRESET_ATM_TICKS, PRESET_ATM_TICKS))

        trouvees[(e["contrat"], e["sens"], e["heure"])] = {
            "sl": sl, "tp": tp, "entree": entree,
            "quantite": e["quantite"], "id": e["id"],
            "signalement": signalement,
            # ⚠️ Un stop dont on SAIT qu'il n'est pas le niveau initial ne doit
            # pas etre propose dans le fichier de saisie. Le proposer avec un
            # avertissement a cote reviendrait a le faire accepter par defaut —
            # c'est deja arrive une fois, sur ce trade exactement : le R:R de
            # 12,5 avait signale, l'alerte a ete acquittee, le stop est reste.
            # « Un stop devine est pire qu'un stop absent » (§4 du README) vaut
            # a plus forte raison pour un stop qu'on a mesure comme faux.
            "sl_douteux": bool(retard is not None
                               and retard > DELAI_AJUSTEMENT_MAX)}

    return trouvees, notes


# Minutes de marge autour de la fenetre d'une position. Mesure du 28/08/2026 :
# sur 32 positions, AUCUNE protection n'est posee avant l'entree — les delais
# observes vont de 0 a 186 minutes apres. La marge amont ne couvre donc qu'un
# arrondi a la seconde, pas un usage.
MARGE_FENETRE = 2.0


def _naif(horodatage):
    import datetime as dt
    try:
        return dt.datetime.strptime((horodatage or "").strip(),
                                    "%m/%d/%Y %H:%M:%S")
    except ValueError:
        return None


def protections_par_fenetre(ordres, positions):
    """Les protections posees au graphique, une position a la fois.

    `positions` : liste de dicts triee par ouverture, portant au moins
    `cle_position`, `symbole_broker`, `sens`, `ouverture`, `cloture` (la
    DERNIERE des jambes) — des datetimes naifs dans le fuseau de l'export.

    Retourne {cle_position: {"sl", "tp", "signalement", "sl_douteux",
    "stop_deplace", "delai"}}.

    ⚠️ LA FENETRE EST BORNEE PAR LA POSITION SUIVANTE SUR LE MEME CONTRAT.
    Sans cette borne, un stop pose pour le trade suivant tombe dans la fenetre
    du precedent : mesure du 06/08, ou `20260806-152630-MNQU6-V` (close a
    15:29) et `20260806-153001-MNQU6-V` (ouverte a 15:30) se partagent le meme
    ordre a 29522,5. Ici ca ne change rien — on prend le PREMIER stop — mais
    compter sur cette chance serait un bug en attente.
    """
    import datetime as dt

    marge = dt.timedelta(minutes=MARGE_FENETRE)
    ouvertures = {}
    for p in positions:
        ouvertures.setdefault(p["symbole_broker"], []).append(p["ouverture"])
    for contrat in ouvertures:
        ouvertures[contrat].sort()

    resultat = {}
    for p in positions:
        debut, fin = p["ouverture"], p["cloture"]
        suivante = next((o for o in ouvertures[p["symbole_broker"]] if o > debut),
                        None)
        borne = fin + marge
        if suivante is not None and suivante < borne:
            borne = suivante
        ferme = _oppose(p["sens_broker"])

        fenetre = []
        for o in ordres:
            if o["contrat"] != p["symbole_broker"]:
                continue
            if o["type"] not in ("Stop", "Limit"):
                continue
            if o["texte"] in TEXTES_SORTIE:
                continue
            if not _meme_sens(o["sens"], ferme):
                continue
            t = _naif(o["horodatage"])
            if t is None or not (debut - marge <= t <= borne):
                continue
            fenetre.append((t, o))
        fenetre.sort(key=lambda x: (x[0], x[1]["id"]))

        stops = [(t, o) for t, o in fenetre if o["type"] == "Stop" and o["stop"] is not None]
        cibles = [(t, o) for t, o in fenetre if o["type"] == "Limit" and o["limite"] is not None]
        if not stops and not cibles:
            continue

        sl = stops[0][1]["stop"] if stops else None
        tp = cibles[0][1]["limite"] if cibles else None
        delai = (stops[0][0] - debut).total_seconds() / 60.0 if stops else None

        # ⚠️ « LE STOP A BOUGE » N'EST PAS « LE STOP A ETE GERE ».
        # Premiere version, mesuree le 28/08/2026 : « premier != dernier »
        # signalait 10 positions sur 32 — dont des micro-ajustements de la
        # premiere minute (30210,75 -> 30210,25 -> 30209,75 en 14 minutes,
        # trois etats pour un seul stop qu'on pose). Un signalement qui se
        # declenche sur du sain dresse a ignorer les signalements ; c'est la
        # troisieme fois que ce module se fait avoir de la meme facon.
        #
        # Le management, tel que l'utilisateur le definit — « ai-je touche a mon
        # stop apres l'entree ? » — a deux marques, et il faut LES DEUX :
        # un etat pose au-dela du delai d'ajustement, ET un prix qui differe
        # du premier. Le lot passe alors de 10 signalements a 7, dont 6
        # contredisent un `management = OK` saisi de memoire.
        tardifs = [(t, o) for t, o in stops[1:]
                   if (t - debut).total_seconds() / 60.0 > DELAI_AJUSTEMENT_MAX
                   and o["stop"] != stops[0][1]["stop"]]
        deplace = bool(tardifs)
        if deplace:
            dernier = tardifs[-1]
            achat_pos = p["sens_broker"].strip().lower().startswith("buy")
            resserre = ((dernier[1]["stop"] > stops[0][1]["stop"]) if achat_pos
                        else (dernier[1]["stop"] < stops[0][1]["stop"]))
            mgmt = {"vers": "resserre" if resserre else "elargi",
                    "de": stops[0][1]["stop"], "a": dernier[1]["stop"],
                    "minutes": (dernier[0] - debut).total_seconds() / 60.0}
        else:
            mgmt = None

        signalement, douteux = "", False

        # ⚠️ LE COTE, AVANT TOUT LE RESTE. Un stop du mauvais cote de l'entree
        # n'est pas un stop : c'est la preuve que la fenetre a ramasse un ordre
        # qui ne lui appartient pas. On jette, on ne signale pas « a verifier ».
        entree = p.get("entree")
        achat = p["sens_broker"].strip().lower().startswith("buy")
        if entree is not None:
            if sl is not None and ((sl >= entree) if achat else (sl <= entree)):
                signalement = ("stop lu a %.10g, du mauvais cote d'une entree a "
                               "%.10g — ordre etranger a la position, ignore"
                               % (sl, entree))
                sl, douteux = None, True
            if tp is not None and ((tp <= entree) if achat else (tp >= entree)):
                signalement = ("cible lue a %.10g, du mauvais cote d'une entree a "
                               "%.10g — ordre etranger a la position, ignoree"
                               % (tp, entree))
                tp = None

        # Meme seuil que pour l'ATM, et pour la meme raison : au-dela, ce n'est
        # plus l'ajustement d'entree, c'est du management. La valeur lue n'est
        # alors plus le risque initial, et un stop qu'on SAIT faux ne doit pas
        # etre propose (cf. `sl_douteux` du chemin ATM).
        if sl is not None and delai is not None and delai > DELAI_AJUSTEMENT_MAX:
            signalement = ("stop pose %.0f minutes apres l'entree — au-dela de "
                           "%.0f, ce n'est plus l'ajustement d'entree"
                           % (delai, DELAI_AJUSTEMENT_MAX))
            douteux = True

        if not signalement and sl is not None and tp is not None \
                and entree is not None and sl != entree:
            rr = abs(tp - entree) / abs(entree - sl)
            if rr > RR_MANAGEMENT:
                signalement = ("R:R de %.1f — au-dela de %.0f, le stop a "
                               "probablement ete resserre apres l'entree"
                               % (rr, RR_MANAGEMENT))

        resultat[p["cle_position"]] = {
            "sl": sl, "tp": tp, "signalement": signalement,
            "sl_douteux": douteux, "stop_deplace": deplace, "management": mgmt,
            "delai": delai, "nb_stops": len(stops), "nb_cibles": len(cibles)}
    return resultat
