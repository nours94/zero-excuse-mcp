"""
Script de rappel quotidien — Zero Excuse
Envoie un email aux utilisateurs qui ne se sont pas encore pesés aujourd'hui.
Exécuté une fois par jour via GitHub Actions (voir .github/workflows/reminder-email.yml).

Variables d'environnement requises (secrets GitHub) :
- FIREBASE_CREDENTIALS_JSON : le JSON du compte de service Firebase (même que sur Render)
- GMAIL_ADDRESS : l'adresse Gmail d'envoi
- GMAIL_APP_PASSWORD : le mot de passe d'application Gmail (16 caractères)
"""

import os
import json
import smtplib
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import firebase_admin
from firebase_admin import credentials, auth, firestore


# ── Initialisation Firebase ───────────────────────────────────────
def init_firebase():
    cred_json = os.environ["FIREBASE_CREDENTIALS_JSON"]
    cred_dict = json.loads(cred_json)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)
    return firestore.client()


# ── Dates utiles (heure de Paris, DST géré correctement) ──────────
def date_key_paris(offset_days: int = 0) -> str:
    now_paris = datetime.now(ZoneInfo("Europe/Paris")) - timedelta(days=offset_days)
    return now_paris.strftime("%Y-%m-%d")


# ── Messages de rappel (ton Zero Excuse) ──────────────────────────
MESSAGES = [
    "Il est déjà tard et vous n'avez toujours pas transmis votre poids. "
    "La méthode n'accepte aucun retard — c'est votre sérieux qui est la clé de la réussite.",

    "Vous n'avez pas encore pesé aujourd'hui. C'est sûrement un oubli — "
    "pensez à le faire avant ce soir.",

    "Zero Excuse : une saisie par jour, et vous voyez votre progrès noir sur blanc. "
    "Il ne manque que la vôtre aujourd'hui.",
]


def build_email(to_email: str) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "⏰ Zero Excuse — Vous n'avez pas encore pesé aujourd'hui"
    msg["From"] = os.environ["GMAIL_ADDRESS"]
    msg["To"] = to_email

    body_text = random.choice(MESSAGES)

    html = f"""
    <div style="font-family: -apple-system, Arial, sans-serif; max-width: 480px; margin: 0 auto;">
      <div style="background:#2C3E50; padding: 24px; border-radius: 16px 16px 0 0;">
        <h1 style="color:#fff; font-size: 20px; letter-spacing: 2px; margin:0; text-align:center;">
          ZERO EXCUSE
        </h1>
      </div>
      <div style="background:#fff; padding: 28px 24px; border-radius: 0 0 16px 16px; box-shadow: 0 8px 24px rgba(0,0,0,.08);">
        <p style="font-size: 15px; color:#2C3E50; line-height:1.6; margin:0 0 20px;">
          {body_text}
        </p>
        <a href="https://monappliminceur-1f6ea.web.app/"
           style="display:block; text-align:center; background:#1E88E5; color:#fff;
                  text-decoration:none; padding:14px; border-radius:12px;
                  font-weight:900; letter-spacing:1px; text-transform:uppercase;
                  font-size:14px;">
          Me peser maintenant
        </a>
      </div>
    </div>
    """

    msg.attach(MIMEText(body_text, "plain"))
    msg.attach(MIMEText(html, "html"))
    return msg


def send_email(to_email: str):
    msg = build_email(to_email)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"])
        server.send_message(msg)


# ── Script principal ──────────────────────────────────────────────
def main():
    db = init_firebase()
    today = date_key_paris(0)
    yesterday = date_key_paris(1)
    day_before_yesterday = date_key_paris(2)

    envoyes = 0
    ignores = 0
    erreurs = 0

    for user_record in auth.list_users().iterate_all():
        uid = user_record.uid
        email = user_record.email
        if not email:
            continue

        user_doc = db.collection("users").document(uid).get()
        user_data = user_doc.to_dict() if user_doc.exists else {}

        # Ne pas relancer un utilisateur en pause
        if user_data.get("pauseActive"):
            ignores += 1
            continue

        weights_ref = db.collection("users").document(uid).collection("weights")

        # Déjà pesé aujourd'hui -> rien à faire
        if weights_ref.document(today).get().exists:
            ignores += 1
            continue

        # Zero Excuse ne relance pas les utilisateurs décrochés depuis 3 jours ou plus
        # (l'app Flutter elle-même arrête ses rappels après le "DERNIER RAPPEL" à J+3).
        # On envoie seulement si l'utilisateur a encore pesé hier OU avant-hier.
        pese_recemment = (
            weights_ref.document(yesterday).get().exists
            or weights_ref.document(day_before_yesterday).get().exists
        )
        if not pese_recemment:
            ignores += 1
            continue

        try:
            send_email(email)
            envoyes += 1
            print(f"Rappel envoyé à {email}")
        except Exception as e:
            erreurs += 1
            print(f"Erreur d'envoi à {email} : {e}")

    print(f"\nTerminé — {envoyes} email(s) envoyé(s), {ignores} ignoré(s), {erreurs} erreur(s).")


if __name__ == "__main__":
    main()
