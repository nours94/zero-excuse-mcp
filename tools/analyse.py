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

    messages_statut = {
        "en_avance": "Vous progressez plus vite que ce que votre métabolisme théorique prévoit — excellent rythme.",
        "dans_les_temps": "Votre progression réelle correspond bien à ce que prévoit votre métabolisme théorique.",
        "en_retard": "Votre progression réelle est plus lente que ce que votre métabolisme théorique permettrait. Vérifiez votre apport calorique réel.",
    }

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
        "objectif_kg": objectif_kg,
        "ecart_objectif_kg": ecart_objectif,
        "projection_semaines_au_rythme_reel": projection_semaines_reel,
        "projection_semaines_au_rythme_theorique": projection_semaines_theorique,
        "metabolisme": metabo,
        "message": (
            f"{messages_statut[statut]} "
            f"Rythme réel : {rythme_reel_semaine:+.2f} kg/semaine (sur {nb_jours_effectifs} jours, {len(pesees)} pesées). "
            f"Rythme théorique attendu : {rythme_theorique_semaine:+.2f} kg/semaine. "
            + (
                f"À ce rythme réel, vous atteindrez votre objectif dans environ {projection_semaines_reel} semaines."
                if projection_semaines_reel else
                "Impossible d'estimer un délai précis avec les données actuelles."
            )
        ),
    }
