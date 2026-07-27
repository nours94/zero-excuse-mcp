#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
# send_broadcast.py
#
# Se déclenche sur les annonces globales créées depuis le dashboard admin
# (bouton "Envoyer à tous les utilisateurs" → collection `broadcasts`).
# Envoie un push + un email à CHAQUE utilisateur ayant un fcmToken/email.
#
# Prévu pour tourner toutes les 5 minutes (même cron que les rapports
# coach). Marque `notified: true` une fois traité pour ne jamais renvoyer.
#
# Variables d'environnement nécessaires (mêmes que les autres scripts) :
#   FIREBASE_SERVICE_ACCOUNT_JSON, GMAIL_ADDRESS, GMAIL_APP_PASSWORD
# ══════════════════════════════════════════════════════════════════════

import json
import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

import firebase_admin
from firebase_admin import credentials, firestore, messaging

if not firebase_admin._apps:
    cred_json = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
    cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]


def envoyer_email(destinataire, texte):
    msg = MIMEText(
        f"{texte}\n\nVa consulter l'application : https://monappliminceur-1f6ea.web.app/",
        "plain", "utf-8",
    )
    msg["Subject"] = "📢 Nouvelle annonce — Zero Excuse"
    msg["From"] = formataddr(("Zero Excuse", GMAIL_ADDRESS))
    msg["To"] = destinataire
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [destinataire], msg.as_string())


def envoyer_push(fcm_token, preview):
    messaging.send(
        messaging.Message(
            token=fcm_token,
            notification=messaging.Notification(
                title="📢 Nouvelle annonce Zero Excuse",
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


def traiter_annonces_en_attente():
    broadcasts_ref = db.collection("broadcasts").where("notified", "==", False)
    docs = list(broadcasts_ref.stream())

    if not docs:
        print("Aucune annonce en attente.")
        return

    users_docs = list(db.collection("users").stream())

    for broadcast_doc in docs:
        data = broadcast_doc.to_dict()
        texte = data.get("text", "")
        preview = texte.split("\n")[0][:120]

        envoyes_push, envoyes_email = 0, 0
        for user_doc in users_docs:
            u = user_doc.to_dict() or {}
            token = u.get("fcmToken")
            email = u.get("email")

            if token:
                try:
                    envoyer_push(token, preview)
                    envoyes_push += 1
                except Exception as e:
                    print(f"⚠️ Échec push pour {user_doc.id} : {e}")

            if email:
                try:
                    envoyer_email(email, texte)
                    envoyes_email += 1
                except Exception as e:
                    print(f"⚠️ Échec email pour {user_doc.id} ({email}) : {e}")

        broadcast_doc.reference.update({"notified": True})
        print(f"✓ Annonce {broadcast_doc.id} : {envoyes_push} push, {envoyes_email} email(s) sur {len(users_docs)} utilisateur(s).")


if __name__ == "__main__":
    traiter_annonces_en_attente()
