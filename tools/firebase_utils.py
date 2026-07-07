"""
Outil Firebase — Zero Excuse MCP
Connexion à Firestore et vérification des utilisateurs.
"""

import os
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timezone

# ── Initialisation Firebase ─────────────────────────────────────────
def _init_firebase():
    if not firebase_admin._apps:
        # En production sur Render : variable d'environnement FIREBASE_CREDENTIALS
        # contenant le JSON de la clé de service
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")

        if cred_json:
            import json
            import tempfile
            tmp = tempfile.NamedTemporaryFile(
                mode='w', suffix='.json', delete=False
            )
            tmp.write(cred_json)
            tmp.close()
            cred = credentials.Certificate(tmp.name)
        elif cred_path:
            cred = credentials.Certificate(cred_path)
        else:
            raise RuntimeError(
                "Variables d'environnement FIREBASE_CREDENTIALS_JSON "
                "ou FIREBASE_CREDENTIALS_PATH manquantes."
            )

        firebase_admin.initialize_app(cred)

    return firestore.client()


def get_db():
    _init_firebase()
    return firestore.client()


# ── Recherche utilisateur par email ────────────────────────────────
def trouver_utilisateur_par_email(email: str) -> dict | None:
    """
    Recherche un utilisateur Zero Excuse dans Firestore par son email.
    Retourne ses données ou None si introuvable.
    """
    db = get_db()
    users = db.collection("users").where("email", "==", email.lower().strip()).limit(1).get()

    if not users:
        return None

    doc = users[0]
    data = doc.to_dict()
    data["uid"] = doc.id
    return data


# ── Vérification plan utilisateur ──────────────────────────────────
def verifier_plan(email: str) -> dict:
    """
    Vérifie le plan (free/premium) d'un utilisateur Zero Excuse.
    """
    user = trouver_utilisateur_par_email(email)

    if not user:
        return {
            "trouve": False,
            "email": email,
            "plan": None,
            "message": "Aucun compte Zero Excuse trouvé avec cet email.",
        }

    plan = user.get("plan", "free")
    return {
        "trouve": True,
        "uid": user["uid"],
        "email": email,
        "plan": plan,
        "est_premium": plan == "premium",
        "poids_objectif": user.get("goalWeight"),
        "taille_cm": user.get("heightCm"),
        "message": f"Compte Zero Excuse trouvé — plan {plan.upper()}.",
    }


# ── Clé de date ────────────────────────────────────────────────────
def date_key_paris(dt: datetime | None = None) -> str:
    """
    Retourne la date au format YYYY-MM-DD en heure de Paris.
    Utilisé comme clé de document dans Firestore.
    """
    try:
        from zoneinfo import ZoneInfo
        paris = ZoneInfo("Europe/Paris")
    except Exception:
        import pytz
        paris = pytz.timezone("Europe/Paris")

    if dt is None:
        dt = datetime.now(timezone.utc)

    dt_paris = dt.astimezone(paris)
    return dt_paris.strftime("%Y-%m-%d")


def datetime_paris_now() -> datetime:
    """Retourne l'heure actuelle en heure de Paris."""
    try:
        from zoneinfo import ZoneInfo
        paris = ZoneInfo("Europe/Paris")
    except Exception:
        import pytz
        paris = pytz.timezone("Europe/Paris")

    return datetime.now(timezone.utc).astimezone(paris)
