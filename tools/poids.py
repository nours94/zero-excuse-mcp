"""
Outil : poids
Lecture du poids enregistré dans Firebase Zero Excuse.
Même schéma que main.dart (Flutter) et app.js (site web) :
users/{uid}/weights/{YYYY-MM-DD}
"""

from datetime import timedelta
from tools.firebase_utils import get_db, trouver_utilisateur_par_email, date_key_paris, datetime_paris_now


def poids_du_jour(email: str) -> dict:
    """
    Retourne le poids enregistré aujourd'hui pour l'utilisateur, s'il existe.
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

    doc = db.collection("users").document(uid).collection("weights").document(date_key).get()

    if not doc.exists:
        return {
            "succes": True,
            "pese_aujourdhui": False,
            "date": date_key,
            "message": f"Aucune pesée enregistrée pour aujourd'hui ({date_key}).",
        }

    data = doc.to_dict()
    return {
        "succes": True,
        "pese_aujourdhui": True,
        "date": date_key,
        "poids_kg": data.get("weight"),
        "exceptionnel": data.get("exceptional", False),
        "message": f"Poids du {date_key} : {data.get('weight')} kg.",
    }


def historique_poids(email: str, jours: int = 7) -> dict:
    """
    Retourne l'historique des pesées des X derniers jours,
    avec l'évolution jour par jour.
    """
    user = trouver_utilisateur_par_email(email)
    if not user:
        return {
            "succes": False,
            "message": "Aucun compte Zero Excuse trouvé avec cet email.",
        }

    jours = max(1, min(jours, 90))
    uid = user["uid"]
    db = get_db()
    now = datetime_paris_now()

    dates = [date_key_paris(now - timedelta(days=i)) for i in range(jours)]
    dates.reverse()  # ordre chronologique (plus ancien -> plus récent)

    pesees = []
    previous_weight = None
    for date_key in dates:
        doc = db.collection("users").document(uid).collection("weights").document(date_key).get()
        if not doc.exists:
            continue
        data = doc.to_dict()
        weight = data.get("weight")
        variation = None
        if previous_weight is not None and weight is not None:
            variation = round(weight - previous_weight, 1)
        pesees.append({
            "date": date_key,
            "poids_kg": weight,
            "variation_kg": variation,
            "exceptionnel": data.get("exceptional", False),
        })
        previous_weight = weight

    if not pesees:
        return {
            "succes": True,
            "periode": f"{jours} derniers jours",
            "pesees": [],
            "message": f"Aucune pesée enregistrée sur les {jours} derniers jours.",
        }

    poids_debut = pesees[0]["poids_kg"]
    poids_fin = pesees[-1]["poids_kg"]
    variation_totale = round(poids_fin - poids_debut, 1) if (poids_debut is not None and poids_fin is not None) else None

    return {
        "succes": True,
        "periode": f"{jours} derniers jours",
        "pesees": pesees,
        "nb_pesees": len(pesees),
        "poids_actuel": poids_fin,
        "variation_totale_kg": variation_totale,
        "message": (
            f"{len(pesees)} pesée(s) sur les {jours} derniers jours. "
            f"Poids actuel : {poids_fin} kg"
            + (f" ({'+' if variation_totale and variation_totale > 0 else ''}{variation_totale} kg sur la période)." if variation_totale is not None else ".")
        ),
    }
