#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
# send_hydration_evening_alert.py
#
# Vers 20h-21h (heure de Paris), vérifie pour chaque utilisateur si les
# 3 créneaux d'hydratation du jour (10h/14h/18h) ont bien été cochés.
# Si non → email + push de rappel, dans l'esprit du rappel de pesée
# existant (reminder-email.yml).
#
# Lit users/{uid}/hydration_slots/{slotIndex} — le même système à 5
# emplacements rotatifs que côté site (voir app.js, slotIndexPourDate).
#
# Prévu pour tourner toutes les heures via cron ; le script ne fait rien
# hors de la fenêtre 20h-21h59 (tolérance pour les retards GitHub Actions),
# et ne notifie chaque utilisateur qu'une seule fois par jour grâce à
# control/hydration_evening_alert.
#
# Variables d'environnement nécessaires (mêmes que les autres scripts) :
#   FIREBASE_SERVICE_ACCOUNT_JSON, GMAIL_ADDRESS, GMAIL_APP_PASSWORD
# ══════════════════════════════════════════════════════════════════════

import json
import os
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.utils import formataddr
from zoneinfo import ZoneInfo

import firebase_admin
from firebase_admin import credentials, firestore, messaging

HEURE_DEBUT = 20
HEURE_FIN = 22  # exclusif : fenêtre 20h-21h59

if not firebase_admin._apps:
    cred_json = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
    cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()
GMAIL_ADDRESS = os.environ["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
CONTROL_DOC = db.collection("control").document("hydration_evening_alert")


def jours_depuis_epoque(date_key):
    d = datetime.strptime(date_key, "%Y-%m-%d")
    return (d - datetime(1970, 1, 1)).days


def slot_index_pour_date(date_key):
    return jours_depuis_epoque(date_key) % 5


def envoyer_email(destinataire):
    msg = MIMEText(
        "Tu n'as pas encore atteint ton objectif d'hydratation aujourd'hui.\n"
        "Il est encore temps de rattraper avant la fin de la journée !\n\n"
        "Va cocher tes créneaux sur https://monappliminceur-1f6ea.web.app/",
        "plain", "utf-8",
    )
    msg["Subject"] = "💧 Pense à finir ton objectif hydratation — Zero Excuse"
    msg["From"] = formataddr(("Zero Excuse", GMAIL_ADDRESS))
    msg["To"] = destinataire
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [destinataire], msg.as_string())


def envoyer_push(fcm_token):
    messaging.send(
        messaging.Message(
            token=fcm_token,
            notification=messaging.Notification(
                title="💧 Objectif hydratation pas encore atteint",
                body="Il reste du temps pour rattraper aujourd'hui !",
            ),
            webpush=messaging.WebpushConfig(
                fcm_options=messaging.WebpushFCMOptions(
                    link="https://monappliminceur-1f6ea.web.app/"
                ),
                notification=messaging.WebpushNotification(icon="/splash.png"),
            ),
        )
    )


def verifier_et_alerter():
    heure_paris = datetime.now(ZoneInfo("Europe/Paris")).hour
    if not (HEURE_DEBUT <= heure_paris < HEURE_FIN):
        print(f"Heure actuelle à Paris : {heure_paris}h — hors fenêtre (20h-21h59).")
        return

    aujourdhui = datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()
    control_data = CONTROL_DOC.get().to_dict() or {}
    if control_data.get("date_envoi") == aujourdhui:
        print(f"Déjà envoyé aujourd'hui ({aujourdhui}).")
        return

    slot_index = slot_index_pour_date(aujourdhui)
    users_ref = db.collection("users")
    docs = list(users_ref.stream())
    alertes = 0

    for doc in docs:
        data = doc.to_dict() or {}
        uid = doc.id

        slot_snap = db.collection("users").document(uid).collection(
            "hydration_slots"
        ).document(str(slot_index)).get()
        slot_data = slot_snap.to_dict() or {}

        # Objectif atteint (ou jamais commencé aujourd'hui = pas d'alerte forcée
        # si l'utilisateur n'a même pas de diagnostic renseigné)
        objectif_atteint = (
            slot_data.get("date") == aujourdhui
            and slot_data.get("10h") is True
            and slot_data.get("14h") is True
            and slot_data.get("18h") is True
        )
        if objectif_atteint:
            continue

        email = data.get("email")
        fcm_token = data.get("fcmToken")

        if email:
            try:
                envoyer_email(email)
            except Exception as e:
                print(f"⚠️ Échec email hydratation pour {uid} : {e}")
        if fcm_token:
            try:
                envoyer_push(fcm_token)
            except Exception as e:
                print(f"⚠️ Échec push hydratation pour {uid} : {e}")

        alertes += 1

    print(f"✓ Alerte hydratation du soir : {alertes}/{len(docs)} utilisateur(s) notifié(s).")
    CONTROL_DOC.set({"date_envoi": aujourdhui}, merge=True)


if __name__ == "__main__":
    verifier_et_alerter()
