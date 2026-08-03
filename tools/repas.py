"""
Outil : repas
Enregistrement et historique des repas dans Firebase Zero Excuse.
"""

from datetime import timezone
from firebase_admin import firestore
from tools.firebase_utils import get_db, trouver_utilisateur_par_email, date_key_paris, datetime_paris_now
from tools.supabase_photo import uploader_photo_depuis_chatgpt

# Correspondance entre le repas_type transmis par ChatGPT et le tag
# affiché dans le journal photo du site (même vocabulaire que suggestMealType()
# côté app.js, pour que la photo ChatGPT s'affiche cohérente avec celles du site).
_REPAS_TYPE_VERS_TAG = {
    "petit_dejeuner": "petit-dejeuner",
    "dejeuner": "dejeuner",
    "diner": "diner",
    "collation": "snack",
}


def _tag_repas(repas_type: str, now) -> str:
    if repas_type in _REPAS_TYPE_VERS_TAG:
        return _REPAS_TYPE_VERS_TAG[repas_type]
    h = now.hour + now.minute / 60
    if 5 <= h < 10.5:
        return "petit-dejeuner"
    if 10.5 <= h < 14.5:
        return "dejeuner"
    if 14.5 <= h < 17.5:
        return "gouter"
    if 17.5 <= h < 21.5:
        return "diner"
    return "snack"


def enregistrer_repas(
    email: str,
    aliments: list[str],
    calories: int,
    proteines: float | None = None,
    glucides: float | None = None,
    lipides: float | None = None,
    repas_type: str = "repas",
    notes: str = "",
    photo_download_link: str | None = None,
    photo_mime_type: str = "image/jpeg",
) -> dict:
    """
    Enregistre un repas analysé par ChatGPT dans Firebase Zero Excuse.
    Appelé après que ChatGPT a analysé la photo de l'assiette.

    Structure Firestore :
    users/{uid}/meals/{YYYY-MM-DD_HH-MM-SS}
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

    # Photo envoyée par l'utilisateur dans la conversation ChatGPT (optionnelle) :
    # on la re-héberge sur Supabase et on l'ajoute au MÊME journal photo que
    # celles prises depuis le site, avec un flag "source" pour les distinguer.
    photo_url = None
    if photo_download_link:
        photo_url = uploader_photo_depuis_chatgpt(photo_download_link, uid, photo_mime_type)
        if photo_url:
            db.collection("users").document(uid).collection("meal_notes").document(date_key).set({
                "date": date_key,
                "photos": firestore.ArrayUnion([{
                    "url": photo_url,
                    "uploadedAt": now.isoformat(),
                    "meal": _tag_repas(repas_type, now),
                    "source": "chatgpt",
                }]),
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }, merge=True)

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
        "photo_url": photo_url,
        "source": "chatgpt_vision",  # Analysé par ChatGPT
        "createdAt": firestore.SERVER_TIMESTAMP,
    }

    # Enregistrement dans users/{uid}/meals/{repas_id}
    db.collection("users").document(uid).collection("meals").document(repas_id).set(repas_data)

    # Mise à jour du compteur calorique du jour dans users/{uid}/daily_calories/{date}
    daily_ref = db.collection("users").document(uid).collection("daily_calories").document(date_key)
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
        "photo_enregistree": photo_url is not None,
        "total_calories_jour": total_cal,
        "nb_repas_jour": nb_repas,
        "message": (
            f"✅ Repas enregistré dans Zero Excuse — {calories} kcal. "
            f"Total du jour : {total_cal} kcal ({nb_repas} repas)."
            + (" Photo associée." if photo_url else "")
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
        # Repas du jour — tri fait en Python (pas de .order_by ici) pour éviter
        # de dépendre d'un index composite Firestore sur (date ==, heure asc).
        repas_docs = (
            db.collection("users")
            .document(uid)
            .collection("meals")
            .where("date", "==", date_key)
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

        repas_du_jour.sort(key=lambda r: r["heure"])

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

    # Repas du jour — tri fait en Python (pas de .order_by ici) pour éviter
    # de dépendre d'un index composite Firestore sur (date ==, heure asc).
    repas_docs = (
        db.collection("users")
        .document(uid)
        .collection("meals")
        .where("date", "==", date_key)
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

    repas_jour.sort(key=lambda r: r["heure"])

    # Objectif calorique — formule Harris-Benedict (identique à metabolic_service.dart)
    a = user.get("diagnosticAnswers") or {}
    sexe = str(a.get("sexe") or "Homme")
    age = int(a.get("age") or 30)
    taille_cm = int(a.get("taille") or user.get("heightCm") or 170)
    poids = float(a.get("poids") or 80.0)

    if sexe == "Homme":
        bmr = 88.36 + (13.4 * poids) + (4.8 * taille_cm) - (5.7 * age)
    else:
        bmr = 447.6 + (9.25 * poids) + (3.1 * taille_cm) - (4.3 * age)

    tdee_repos = bmr * 1.2
    kcal_min = 1500.0 if sexe == "Homme" else 1200.0
    objectif_type = str(a.get("objectifType") or "perte")
    if objectif_type == "prise":
        objectif_calorique = tdee_repos + 300
    else:
        objectif_calorique = max(kcal_min, min(tdee_repos, tdee_repos - 500))

    reste = objectif_calorique - total_cal

    if objectif_type == "prise":
        statut = (
            "✅ Objectif surplus atteint" if reste <= 0
            else f"⚠️ Encore {round(reste)} kcal à manger pour atteindre le surplus visé"
        )
        message = (
            f"Bilan du {date_key} : {total_cal} kcal consommées sur {round(objectif_calorique)} kcal objectif (surplus). "
            + ("Objectif atteint, continuez ainsi." if reste <= 0 else f"Il reste {round(reste)} kcal à manger aujourd'hui.")
        )
    else:
        statut = (
            "✅ Dans l'objectif" if reste >= 0
            else f"⚠️ Dépassement de {abs(round(reste))} kcal"
        )
        message = (
            f"Bilan du {date_key} : {total_cal} kcal consommées sur {round(objectif_calorique)} kcal objectif. "
            f"{'Il reste ' + str(round(reste)) + ' kcal.' if reste > 0 else 'Objectif dépassé de ' + str(abs(round(reste))) + ' kcal.'}"
        )

    return {
        "succes": True,
        "date": date_key,
        "objectif_type": objectif_type,
        "repas_du_jour": repas_jour,
        "total_calories": total_cal,
        "total_proteines_g": round(total_prot, 1),
        "total_glucides_g": round(total_gluc, 1),
        "total_lipides_g": round(total_lip, 1),
        "objectif_calorique": round(objectif_calorique),
        "calories_restantes": round(reste),
        "statut": statut,
        "message": message,
    }


def _recalculer_total_jour(db, uid: str, date_key: str) -> tuple[int, int]:
    """
    Recalcule le total calorique et le nombre de repas du jour à partir
    des repas réellement présents (plus fiable qu'un compteur incrémental
    qui peut se désynchroniser après une modification ou suppression).
    """
    repas_docs = (
        db.collection("users")
        .document(uid)
        .collection("meals")
        .where("date", "==", date_key)
        .get()
    )
    total_cal = 0
    nb_repas = 0
    for doc in repas_docs:
        total_cal += doc.to_dict().get("calories", 0) or 0
        nb_repas += 1

    daily_ref = db.collection("users").document(uid).collection("daily_calories").document(date_key)
    daily_ref.set({
        "date": date_key,
        "total_calories": total_cal,
        "nb_repas": nb_repas,
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }, merge=True)

    return total_cal, nb_repas


def modifier_repas(
    email: str,
    repas_id: str,
    aliments: list[str] | None = None,
    calories: int | None = None,
    proteines: float | None = None,
    glucides: float | None = None,
    lipides: float | None = None,
    repas_type: str | None = None,
    notes: str | None = None,
) -> dict:
    """
    Corrige un repas déjà enregistré (par exemple si ChatGPT s'est trompé
    dans l'identification des aliments). Seuls les champs fournis sont mis
    à jour ; les autres restent inchangés. Le total calorique du jour est
    automatiquement recalculé.
    """
    user = trouver_utilisateur_par_email(email)
    if not user:
        return {"succes": False, "message": "Aucun compte Zero Excuse trouvé avec cet email."}

    uid = user["uid"]
    db = get_db()
    ref = db.collection("users").document(uid).collection("meals").document(repas_id)
    doc = ref.get()

    if not doc.exists:
        return {
            "succes": False,
            "message": f"Aucun repas trouvé avec l'identifiant {repas_id} pour ce compte.",
        }

    updates = {}
    if aliments is not None:
        updates["aliments"] = aliments
    if calories is not None:
        updates["calories"] = calories
    if proteines is not None:
        updates["proteines_g"] = proteines
    if glucides is not None:
        updates["glucides_g"] = glucides
    if lipides is not None:
        updates["lipides_g"] = lipides
    if repas_type is not None:
        updates["repas_type"] = repas_type
    if notes is not None:
        updates["notes"] = notes

    if not updates:
        return {"succes": False, "message": "Aucune modification fournie."}

    ref.update(updates)

    date_key = doc.to_dict().get("date")
    total_cal, nb_repas = _recalculer_total_jour(db, uid, date_key)

    return {
        "succes": True,
        "repas_id": repas_id,
        "champs_modifies": list(updates.keys()),
        "total_calories_jour": total_cal,
        "nb_repas_jour": nb_repas,
        "message": f"✅ Repas corrigé. Total du jour recalculé : {total_cal} kcal ({nb_repas} repas).",
    }


def supprimer_repas(email: str, repas_id: str) -> dict:
    """
    Supprime un repas enregistré par erreur (ex. mauvaise photo, doublon).
    Le total calorique du jour est automatiquement recalculé.
    """
    user = trouver_utilisateur_par_email(email)
    if not user:
        return {"succes": False, "message": "Aucun compte Zero Excuse trouvé avec cet email."}

    uid = user["uid"]
    db = get_db()
    ref = db.collection("users").document(uid).collection("meals").document(repas_id)
    doc = ref.get()

    if not doc.exists:
        return {
            "succes": False,
            "message": f"Aucun repas trouvé avec l'identifiant {repas_id} pour ce compte.",
        }

    date_key = doc.to_dict().get("date")
    ref.delete()
    total_cal, nb_repas = _recalculer_total_jour(db, uid, date_key)

    return {
        "succes": True,
        "repas_id": repas_id,
        "total_calories_jour": total_cal,
        "nb_repas_jour": nb_repas,
        "message": f"🗑️ Repas supprimé. Total du jour recalculé : {total_cal} kcal ({nb_repas} repas).",
    }
