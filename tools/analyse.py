"""
Outil : analyse
Analyse approfondie de la progression : compare le rythme réel de perte/prise
de poids (mesuré sur l'historique des pesées) au rythme théorique calculé
depuis le métabolisme de base, et projette le temps restant avant d'atteindre
l'objectif.
"""

from datetime import timedelta, date
from tools.firebase_utils import get_db, trouver_utilisateur_par_email, date_key_paris, datetime_paris_now
from tools.metabolisme import calculer_metabolisme


def _determiner_gravite(objectif_type: str, rythme_reel_semaine: float, statut: str) -> str:
    """
    Détermine la gravité de la situation pour calibrer le ton du verdict :
    catastrophique / mauvais / retard / correct / excellent.
    """
    if objectif_type == "perte":
        if rythme_reel_semaine > 0.3:
            return "catastrophique"  # prise significative alors que l'objectif est de perdre
        if rythme_reel_semaine > 0:
            return "mauvais"  # prise, même légère
        if statut == "en_retard":
            return "retard"
        if statut == "en_avance":
            return "excellent"
        return "correct"
    else:  # prise de poids
        if rythme_reel_semaine < -0.3:
            return "catastrophique"  # perte significative alors que l'objectif est de prendre
        if rythme_reel_semaine < 0:
            return "mauvais"
        if statut == "en_retard":
            return "retard"
        if statut == "en_avance":
            return "excellent"
        return "correct"


def _generer_verdict_zero_excuse(
    gravite, objectif_type, variation_totale, nb_jours_effectifs,
    rythme_reel_semaine, rythme_theorique_semaine, ecart_objectif,
    objectif_kg, poids_fin, projection_semaines_reel,
) -> str:
    """
    Génère le verdict dans l'esprit Zero Excuse : intransigeant et direct
    face à un mauvais résultat, valorisant et cash quand le résultat est bon.
    Ton déterministe — ne dépend pas de la génération du LLM appelant.
    """
    reste = abs(ecart_objectif)
    mot_direction = "perdre" if objectif_type == "perte" else "prendre"
    signe_var = "+" if variation_totale > 0 else ""

    if gravite == "catastrophique":
        return (
            "🚨 ALERTE ZERO EXCUSE — RÉSULTAT CATASTROPHIQUE\n\n"
            f"Ton objectif est de {mot_direction} du poids. Pourtant, sur les {nb_jours_effectifs} derniers jours, "
            f"ton poids a évolué de {signe_var}{variation_totale} kg dans le mauvais sens "
            f"({rythme_reel_semaine:+.2f} kg/semaine, alors que le rythme théorique visé est de {rythme_theorique_semaine:+.2f} kg/semaine). "
            "Tu ne stagnes pas : tu t'éloignes clairement de ton objectif.\n\n"
            "Les fluctuations d'eau ou de sel peuvent expliquer des écarts ponctuels, mais pas une tendance aussi nette sur cette durée. "
            "Il faut arrêter de chercher une explication rassurante : ce que tu fais actuellement ne fonctionne pas.\n\n"
            "Dès aujourd'hui :\n"
            "• chaque repas est enregistré, sans omission ;\n"
            "• les quantités sont réellement mesurées ;\n"
            "• aucun grignotage n'est minimisé ou oublié ;\n"
            "• la pesée est faite chaque matin, dans les mêmes conditions ;\n"
            "• l'apport calorique cible est respecté avec constance.\n\n"
            f"Ton objectif est à {objectif_kg} kg et tu en es à {poids_fin} kg. Il reste {reste:.1f} kg à {mot_direction}. "
            "Si rien ne change, tu ne l'atteindras pas.\n\n"
            "Tu n'as pas besoin d'une nouvelle excuse ni d'une nouvelle promesse. Tu as besoin d'actions mesurables, "
            "répétées chaque jour. Reprends le contrôle maintenant. Zero Excuse."
        )

    if gravite == "mauvais":
        return (
            "⚠️ Le verdict Zero Excuse : ce n'est pas bon.\n\n"
            f"Sur les {nb_jours_effectifs} derniers jours, ton poids est allé dans le mauvais sens "
            f"({rythme_reel_semaine:+.2f} kg/semaine) alors que ton objectif est de {mot_direction} du poids.\n\n"
            "Ce n'est pas une catastrophe, mais ça ne va clairement pas dans la bonne direction. "
            "Il est temps de resserrer les choses : respecte ton apport calorique cible, mesure ce que tu manges, "
            "et pèse-toi chaque matin dans les mêmes conditions.\n\n"
            f"Il te reste {reste:.1f} kg pour atteindre {objectif_kg} kg. Ça ne se fera pas tout seul. "
            "Reprends la main dès aujourd'hui. Zero Excuse."
        )

    if gravite == "retard":
        return (
            "⚠️ Le verdict Zero Excuse : tu n'es pas dans les temps.\n\n"
            f"Tu avances dans la bonne direction ({rythme_reel_semaine:+.2f} kg/semaine), mais trop lentement : "
            f"ton métabolisme permettrait {rythme_theorique_semaine:+.2f} kg/semaine. Ce n'est pas un échec, "
            "mais ce n'est pas suffisant non plus.\n\n"
            "Pas besoin d'être parfait. En revanche, tu dois être régulier et honnête avec toi-même : "
            "vérifie ton apport calorique réel, surveille les portions, et pèse-toi chaque matin dans les mêmes conditions.\n\n"
            f"Il reste {reste:.1f} kg avant {objectif_kg} kg"
            + (f", soit environ {projection_semaines_reel} semaines à ce rythme réel." if projection_semaines_reel else ".")
            + " Tu peux encore reprendre le contrôle, mais cela commence aujourd'hui. Zero Excuse."
        )

    if gravite == "correct":
        return (
            "✅ Le verdict Zero Excuse : c'est dans les clous.\n\n"
            f"Ta progression réelle ({rythme_reel_semaine:+.2f} kg/semaine) correspond bien à ce que ton métabolisme permet "
            f"({rythme_theorique_semaine:+.2f} kg/semaine). Continue exactement comme ça, sans relâchement.\n\n"
            f"Il reste {reste:.1f} kg avant {objectif_kg} kg"
            + (f", soit environ {projection_semaines_reel} semaines à ce rythme." if projection_semaines_reel else ".")
            + " La régularité paie. Zero Excuse."
        )

    # excellent
    return (
        "🎯 Le verdict Zero Excuse : excellent travail.\n\n"
        f"Ta progression réelle ({rythme_reel_semaine:+.2f} kg/semaine) dépasse même ce que ton métabolisme théorique "
        f"permettrait ({rythme_theorique_semaine:+.2f} kg/semaine). C'est du sérieux, continue exactement ainsi.\n\n"
        f"Il reste {reste:.1f} kg avant {objectif_kg} kg"
        + (f", soit environ {projection_semaines_reel} semaines à ce rythme." if projection_semaines_reel else ".")
        + " Ne relâche rien maintenant. Zero Excuse."
    )


def analyser_progression(email: str, jours: int = 21) -> dict:
    """
    Analyse la progression réelle par rapport à l'objectif et au métabolisme.

    Compare le rythme réel de perte/prise de poids (mesuré sur les X derniers
    jours de pesées) au rythme théorique attendu (calculé depuis le
    métabolisme de base), puis projette le temps restant avant d'atteindre
    l'objectif aux deux rythmes.
    """
    user = trouver_utilisateur_par_email(email)
    if not user:
        return {
            "succes": False,
            "message": "Aucun compte Zero Excuse trouvé avec cet email.",
        }

    # 1. Capacité théorique (métabolisme)
    metabo = calculer_metabolisme(email)
    if not metabo.get("succes"):
        return metabo

    uid = user["uid"]
    db = get_db()
    now = datetime_paris_now()
    jours = max(7, min(jours, 90))

    dates = [date_key_paris(now - timedelta(days=i)) for i in range(jours)]
    dates.reverse()  # ordre chronologique

    pesees = []
    for d in dates:
        doc = db.collection("users").document(uid).collection("weights").document(d).get()
        if doc.exists:
            data = doc.to_dict()
            if data.get("exceptional"):
                continue  # on exclut les pesées exceptionnelles, comme l'app
            pesees.append({"date": d, "poids": data.get("weight")})

    if len(pesees) < 2:
        return {
            "succes": True,
            "donnees_insuffisantes": True,
            "message": (
                "Pas assez de pesées non-exceptionnelles sur la période pour "
                "analyser la progression réelle. Continuez à vous peser "
                "régulièrement — reessayez dans quelques jours."
            ),
            "metabolisme": metabo,
        }

    # 2. Rythme réel constaté
    poids_debut = pesees[0]["poids"]
    poids_fin = pesees[-1]["poids"]
    date_debut = pesees[0]["date"]
    date_fin = pesees[-1]["date"]
    nb_jours_effectifs = (date.fromisoformat(date_fin) - date.fromisoformat(date_debut)).days
    nb_jours_effectifs = max(nb_jours_effectifs, 1)

    variation_totale = round(poids_fin - poids_debut, 2)
    rythme_reel_semaine = round(variation_totale / nb_jours_effectifs * 7, 2)

    # 3. Rythme théorique (signé : négatif = perte, positif = gain)
    objectif_type = metabo["objectif_type"]
    rythme_theorique_abs = metabo["variation_estimee_kg_semaine"]
    rythme_theorique_semaine = -rythme_theorique_abs if objectif_type == "perte" else rythme_theorique_abs

    # 4. Comparaison réel vs théorique
    ecart = round(rythme_reel_semaine - rythme_theorique_semaine, 2)
    # Pour la perte : rythme réel plus négatif que théorique = en avance. Pour la prise : l'inverse.
    if objectif_type == "perte":
        if rythme_reel_semaine <= rythme_theorique_semaine - 0.1:
            statut = "en_avance"
        elif rythme_reel_semaine >= rythme_theorique_semaine + 0.2:
            statut = "en_retard"
        else:
            statut = "dans_les_temps"
    else:
        if rythme_reel_semaine >= rythme_theorique_semaine + 0.1:
            statut = "en_avance"
        elif rythme_reel_semaine <= rythme_theorique_semaine - 0.2:
            statut = "en_retard"
        else:
            statut = "dans_les_temps"

    # 5. Projection vers l'objectif au rythme réel
    objectif_kg = metabo["profil"]["objectif_kg"]
    ecart_objectif = round(poids_fin - objectif_kg, 2)  # positif si au-dessus (perte) ou en-dessous (prise)

    projection_semaines_reel = None
    if abs(rythme_reel_semaine) > 0.01:
        if (objectif_type == "perte" and ecart_objectif > 0 and rythme_reel_semaine < 0) or \
           (objectif_type == "prise" and ecart_objectif < 0 and rythme_reel_semaine > 0):
            projection_semaines_reel = round(abs(ecart_objectif / rythme_reel_semaine), 1)

    projection_semaines_theorique = None
    if abs(rythme_theorique_semaine) > 0.01 and abs(ecart_objectif) > 0.01:
        projection_semaines_theorique = round(abs(ecart_objectif / rythme_theorique_semaine), 1)

    # 6. Détermination de la gravité (pour le ton du verdict)
    gravite = _determiner_gravite(objectif_type, rythme_reel_semaine, statut)

    verdict = _generer_verdict_zero_excuse(
        gravite=gravite,
        objectif_type=objectif_type,
        variation_totale=variation_totale,
        nb_jours_effectifs=nb_jours_effectifs,
        rythme_reel_semaine=rythme_reel_semaine,
        rythme_theorique_semaine=rythme_theorique_semaine,
        ecart_objectif=ecart_objectif,
        objectif_kg=objectif_kg,
        poids_fin=poids_fin,
        projection_semaines_reel=projection_semaines_reel,
    )

    return {
        "succes": True,
        "periode_analysee_jours": nb_jours_effectifs,
        "nb_pesees_prises_en_compte": len(pesees),
        "poids_debut_periode": poids_debut,
        "poids_fin_periode": poids_fin,
        "objectif_type": objectif_type,
        "rythme_reel_kg_semaine": rythme_reel_semaine,
        "rythme_theorique_kg_semaine": rythme_theorique_semaine,
        "ecart_kg_semaine": ecart,
        "statut": statut,
        "gravite": gravite,
        "objectif_kg": objectif_kg,
        "ecart_objectif_kg": ecart_objectif,
        "projection_semaines_au_rythme_reel": projection_semaines_reel,
        "projection_semaines_au_rythme_theorique": projection_semaines_theorique,
        "metabolisme": metabo,
        "message": verdict,
    }
