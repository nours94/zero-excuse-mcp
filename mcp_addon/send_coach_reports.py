#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
# send_coach_reports.py
#
# À exécuter périodiquement (ex: toutes les 5-10 min via GitHub Actions,
# ou dans le même processus que ton serveur zero-excuse-mcp sur Render).
#
# Ne nécessite PAS le forfait Blaze : tout passe par le SDK Admin Firebase
# (Firestore + Cloud Messaging), utilisable depuis n'importe quel serveur
# Python avec un compte de service, sans Cloud Functions.
#
# Variables d'environnement nécessaires :
#   FIREBASE_SERVICE_ACCOUNT_JSON   → contenu JSON du compte de service
#                                       (Paramètres → Comptes de service →
#                                        Générer une nouvelle clé privée)
#   GMAIL_ADDRESS                   → l'adresse Gmail expéditrice
#   GMAIL_APP_PASSWORD              → mot de passe d'application Gmail
#                                       (myaccount.google.com/apppasswords)
# ══════════════════════════════════════════════════════════════════════

import json
import os
import smtplib
from email.mime.text import MIMEText

import firebase_admin
from firebase_admin import credentials, firestore, messaging

# ── Initialisation Firebase Admin ────────────────────────────────
if not firebase_admin._apps:
    cred_json = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
    cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()

GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]


def envoyer_email(destinataire, texte_rapport):
    msg = MIMEText(
        f"Ton coach t'a envoyé un nouveau rapport :\n\n{texte_rapport}\n\n"
        f"Va le consulter sur https://monappliminceur-1f6ea.web.app/",
        "plain",
        "utf-8",
    )
    msg["Subject"] = "Nouveau rapport de ton coach — Zero Excuse"
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = destinataire

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [destinataire], msg.as_string())


def envoyer_push(fcm_token, preview):
    try:
        messaging.send(
            messaging.Message(
                token=fcm_token,
                notification=messaging.Notification(
                    title="📋 Nouveau rapport de ton coach",
                    body=preview,
                ),
                webpush=messaging.WebpushConfig(
                    fcm_options=messaging.WebpushFCMOptions(
                        link="https://monappliminceur-1f6ea.web.app/"
                    ),
                    notification=messaging.WebpushNotification(icon="/splash.png"),
                ),
            )
        )
    except Exception as e:
        print(f"⚠️ Échec push : {e}")


def traiter_rapports_en_attente():
    # collection_group interroge coach_messages quel que soit l'utilisateur parent
    messages_ref = db.collection_group("coach_messages").where("notified", "==", False)
    docs = list(messages_ref.stream())

    if not docs:
        print("Aucun nouveau rapport à envoyer.")
        return

    for doc in docs:
        data = doc.to_dict()
        uid = doc.reference.parent.parent.id  # users/{uid}/coach_messages/{msgId}
        texte = data.get("text", "")
        preview = texte.split("\n")[0][:120]

        user_doc = db.collection("users").document(uid).get()
        user_data = user_doc.to_dict() or {}
        email = user_data.get("email")
        fcm_token = user_data.get("fcmToken")

        envoye_email = False
        envoye_push = False

        if email:
            try:
                envoyer_email(email, texte)
                envoye_email = True
            except Exception as e:
                print(f"⚠️ Échec email pour {uid} ({email}) : {e}")

        if fcm_token:
            envoyer_push(fcm_token, preview)
            envoye_push = True

        doc.reference.update({
            "notified": True,
            "notifiedEmail": envoye_email,
            "notifiedPush": envoye_push,
        })
        print(f"✓ Rapport {doc.id} traité pour {uid} (email={envoye_email}, push={envoye_push})")


if __name__ == "__main__":
    traiter_rapports_en_attente()
