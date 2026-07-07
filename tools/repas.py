"""
Outil : repas
Enregistrement et historique des repas dans Firebase Zero Excuse.
"""

from datetime import timezone
from firebase_admin import firestore
from tools.firebase_utils import get_db, trouver_utilisateur_par_email, date_key_paris, datetime_paris_now


def enregistrer_repas(
    email: str,
    aliments: list[str],
    calories: int,
    proteines: float | None = None,
    glucides: float | None = None,
    lipides: float | None = None,
    repas_type: str = "repas",
    notes: str = "",
) -> dict:
    """
    Enregistre un repas analysé par ChatGPT dans Firebase Zero Excuse.
    Appelé après que ChatGPT a analysé la photo de l'assiette.

    Structure Firestore :
    users/{uid}/meals/{YYYY-MM-DD}/{repas_id}
    """
    user = trouver_utilisateur_par_email(email)

    if not user:
        return {
            "succes": False,
            "message": (
                "Aucun compte Zero Excuse trouvé avec cet email. "
                "Connectez-vous d'abord à l'application Zero Excuse."
            ),
        }

    uid = user["uid"]
    db = get_db()
    now = datetime_paris_now()
    date_key = date_key_paris(now)

    # Heure du repas (HH:MM heure de Paris)
    heure = now.strftime("%H:%M")

    # ID du repas : date + heure (permet plusieurs repas par jour)
    repas_id = f"{date_key}_{now.strftime('%H-%M-%S')}"

    repas_data = {
        "date": date_key,
        "heure": heure,
        "repas_type": repas_type,  # "petit_dejeuner", "dejeuner", "diner", "collation", "repas"
        "aliments": aliments,
        "calories": calories,
        "proteines_g": proteines,
        "glucides_g": glucides,
        "lipides_g": lipides,
        "notes": notes,
        "source": "chatgpt_vision",  # Analysé par ChatGPT
        "createdAt": firestore.SERVER_TIMESTAMP,
    }

    # Enregistrement dans users/{uid}/meals/{repas_id}
    db.collection("users").doc(uid).collection("meals").doc(repas_id).set(repas_data)

    # Mise à jour du compteur calorique du jour dans users/{uid}/daily_calories/{date}
    daily_ref = db.collection("users").doc(uid).collection("daily_calories").document(date_key)
    daily_doc = daily_ref.get()

    if daily_doc.exists:
        daily_data = daily_doc.to_dict()
        total_cal = (daily_data.get("total_calories", 0) or 0) + calories
        nb_repas = (daily_data.get("nb_repas", 0) or 0) + 1
        daily_ref.update({
            "total_calories": total_cal,
            "nb_repas": nb_repas,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        })
    else:
        total_cal = calories
        nb_repas = 1
        daily_ref.set({
            "date": date_key,
            "total_calories": calories,
            "nb_repas": 1,
            "createdAt": firestore.SERVER_TIMESTAMP,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        })

    return {
        "succes": True,
        "repas_id": repas_id,
        "date": date_key,
        "heure": heure,
        "aliments": aliments,
        "calories_repas": calories,
        "total_calories_jour": total_cal,
        "nb_repas_jour": nb_repas,
        "message": (
            f"✅ Repas enregistré dans Zero Excuse — {calories} kcal. "
            f"Total du jour : {total_cal} kcal ({nb_repas} repas)."
        ),
    }


def historique_repas(email: str, jours: int = 7) -> dict:
    """
    Retourne l'historique des repas des X derniers jours.
    """
    user = trouver_utilisateur_par_email(email)

    if not user:
        return {
            "succes": False,
            "message": "Aucun compte Zero Excuse trouvé avec cet email.",
        }

    uid = user["uid"]
    db = get_db()
    now = datetime_paris_now()

    # Dates des X derniers jours
    from datetime import timedelta
    dates = []
    for i in range(jours):
        d = now - timedelta(days=i)
        dates.append(date_key_paris(d))

    # Récupération des repas
    repas_par_jour = {}
    calories_par_jour = {}

    for date_key in dates:
        # Repas du jour
        repas_docs = (
            db.collection("users")
            .doc(uid)
            .collection("meals")
            .where("date", "==", date_key)
            .order_by("heure")
            .get()
        )

        repas_du_jour = []
        total_cal = 0
        for doc in repas_docs:
            data = doc.to_dict()
            repas_du_jour.append({
                "heure": data.get("heure", "?"),
                "repas_type": data.get("repas_type", "repas"),
                "aliments": data.get("aliments", []),
                "calories": data.get("calories", 0),
                "proteines_g": data.get("proteines_g"),
                "glucides_g": data.get("glucides_g"),
                "lipides_g": data.get("lipides_g"),
            })
            total_cal += data.get("calories", 0) or 0

        if repas_du_jour:
            repas_par_jour[date_key] = repas_du_jour
            calories_par_jour[date_key] = total_cal

    # Calcul de la moyenne calorique
    if calories_par_jour:
        moyenne = int(sum(calories_par_jour.values()) / len(calories_par_jour))
    else:
        moyenne = 0

    return {
        "succes": True,
        "email": email,
        "periode": f"{jours} derniers jours",
        "repas_par_jour": repas_par_jour,
        "calories_par_jour": calories_par_jour,
        "moyenne_calories_jour": moyenne,
        "jours_avec_repas": len(repas_par_jour),
        "message": (
            f"Historique des {jours} derniers jours — "
            f"moyenne {moyenne} kcal/jour sur {len(repas_par_jour)} jours enregistrés."
        ),
    }


def bilan_calorique_jour(email: str) -> dict:
    """
    Retourne le bilan calorique du jour en cours avec les objectifs
    calculés depuis le profil Zero Excuse de l'utilisateur.
    """
    user = trouver_utilisateur_par_email(email)

    if not user:
        return {
            "succes": False,
            "message": "Aucun compte Zero Excuse trouvé avec cet email.",
        }

    uid = user["uid"]
    db = get_db()
    date_key = date_key_paris()

    # Repas du jour
    repas_docs = (
        db.collection("users")
        .doc(uid)
        .collection("meals")
        .where("date", "==", date_key)
        .order_by("heure")
        .get()
    )

    repas_jour = []
    total_cal = 0
    total_prot = 0.0
    total_gluc = 0.0
    total_lip = 0.0

    for doc in repas_docs:
        data = doc.to_dict()
        cal = data.get("calories", 0) or 0
        total_cal += cal
        total_prot += data.get("proteines_g") or 0
        total_gluc += data.get("glucides_g") or 0
        total_lip += data.get("lipides_g") or 0
        repas_jour.append({
            "heure": data.get("heure", "?"),
            "aliments": data.get("aliments", []),
            "calories": cal,
        })

    # Objectif calorique depuis le profil (BMR simplifié si pas de métabolisme calculé)
    poids_objectif = user.get("goalWeight") or user.get("diagnosticObjectif") or 70
    taille_cm = user.get("heightCm") or 170

    # Estimation TDEE simplifié (activité modérée) pour la perte de poids
    # BMR Mifflin-St Jeor approximatif sans genre → valeur moyenne
    bmr = 10 * poids_objectif + 6.25 * taille_cm - 5 * 30 + 5
    objectif_cal = int(bmr * 1.4)  # Activité légère
    objectif_deficit = max(1200, objectif_cal - 300)  # Déficit de 300 kcal

    reste = objectif_deficit - total_cal

    return {
        "succes": True,
        "date": date_key,
        "repas_du_jour": repas_jour,
        "total_calories": total_cal,
        "total_proteines_g": round(total_prot, 1),
        "total_glucides_g": round(total_gluc, 1),
        "total_lipides_g": round(total_lip, 1),
        "objectif_calorique": objectif_deficit,
        "calories_restantes": reste,
        "statut": (
            "✅ Dans l'objectif" if reste >= 0
            else f"⚠️ Dépassement de {abs(reste)} kcal"
        ),
        "message": (
            f"Bilan du {date_key} : {total_cal} kcal consommées sur {objectif_deficit} kcal objectif. "
            f"{'Il reste ' + str(reste) + ' kcal.' if reste > 0 else 'Objectif dépassé de ' + str(abs(reste)) + ' kcal.'}"
        ),
    }
