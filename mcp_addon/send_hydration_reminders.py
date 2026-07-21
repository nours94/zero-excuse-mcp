#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
# send_hydration_reminders.py
#
# Envoie une notification push "pense à boire de l'eau" aux heures fixes
# 10h, 14h, 18h (heure de Paris). Prévu pour être lancé toutes les heures
# via cron — le script ne fait rien si l'heure locale de Paris ne
# correspond à aucun des créneaux ci-dessous, donc pas de risque de spam
# même en cas de double déclenchement.
#
# Utilise zoneinfo (heure de Paris) plutôt qu'un cron UTC fixe, pour ne
# pas avoir à gérer manuellement le changement heure été/hiver.
#
# Ne touche qu'au push (FCM) : c'est le seul canal qui déclenche un son
# natif sur le téléphone, même site fermé. Les utilisateurs sans
# `fcmToken` (notifications jamais activées) ne sont pas notifiés par ce
# script — c'est une limite connue, pas un bug.
#
# Variables d'environnement nécessaires :
#   FIREBASE_SERVICE_ACCOUNT_JSON   → même compte de service que
#                                       send_coach_reports.py
# ══════════════════════════════════════════════════════════════════════

import json
import os
from zoneinfo import ZoneInfo
from datetime import datetime

import firebase_admin
from firebase_admin import credentials, firestore, messaging

HEURES_RAPPEL = {10, 14, 18}  # heure de Paris, à ajuster ici si besoin

if not firebase_admin._apps:
    cred_json = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
    cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()


def envoyer_rappels_hydratation():
    heure_paris = datetime.now(ZoneInfo("Europe/Paris")).hour
    if heure_paris not in HEURES_RAPPEL:
        print(f"Heure actuelle à Paris : {heure_paris}h — hors créneau, rien à envoyer.")
        return

    users_ref = db.collection("users")
    docs = list(users_ref.stream())
    envoyes = 0

    for doc in docs:
        data = doc.to_dict() or {}
        token = data.get("fcmToken")
        if not token:
            continue
        try:
            messaging.send(
                messaging.Message(
                    token=token,
                    notification=messaging.Notification(
                        title="💧 Pense à t'hydrater",
                        body="Un petit verre d'eau, c'est le moment !",
                    ),
                    webpush=messaging.WebpushConfig(
                        fcm_options=messaging.WebpushFCMOptions(
                            link="https://monappliminceur-1f6ea.web.app/"
                        ),
                        notification=messaging.WebpushNotification(icon="/splash.png"),
                    ),
                )
            )
            envoyes += 1
        except Exception as e:
            print(f"⚠️ Échec push hydratation pour {doc.id} : {e}")

    print(f"✓ Rappel hydratation {heure_paris}h : {envoyes}/{len(docs)} utilisateur(s) notifié(s).")


if __name__ == "__main__":
    envoyer_rappels_hydratation()
