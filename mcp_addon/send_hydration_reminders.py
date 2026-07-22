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

HEURES_RAPPEL = [10, 14, 18]  # heure de Paris
FENETRE_TOLERANCE_H = 2  # accepte l'envoi jusqu'à 2h après le créneau visé,
                          # car GitHub Actions peut retarder ou sauter des
                          # exécutions planifiées sur un dépôt peu actif

if not firebase_admin._apps:
    cred_json = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
    cred = credentials.Certificate(cred_json)
    firebase_admin.initialize_app(cred)

db = firestore.client()
CONTROL_DOC = db.collection("control").document("hydration_reminders")


def creneau_a_envoyer(heure_actuelle):
    """Retourne le créneau (10/14/18) à envoyer maintenant, ou None.
    Un créneau est dû si l'heure actuelle est dans [créneau, créneau + tolérance)
    ET qu'il n'a pas déjà été envoyé aujourd'hui."""
    aujourdhui = datetime.now(ZoneInfo("Europe/Paris")).date().isoformat()
    control_data = CONTROL_DOC.get().to_dict() or {}

    for creneau in HEURES_RAPPEL:
        deja_envoye = control_data.get(str(creneau)) == aujourdhui
        dans_la_fenetre = creneau <= heure_actuelle < creneau + FENETRE_TOLERANCE_H
        if dans_la_fenetre and not deja_envoye:
            return creneau, aujourdhui
    return None, aujourdhui


def envoyer_rappels_hydratation():
    heure_paris = datetime.now(ZoneInfo("Europe/Paris")).hour
    creneau, aujourdhui = creneau_a_envoyer(heure_paris)

    if creneau is None:
        print(f"Heure actuelle à Paris : {heure_paris}h — rien à envoyer (hors fenêtre ou déjà fait aujourd'hui).")
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

    print(f"✓ Rappel hydratation {creneau}h : {envoyes}/{len(docs)} utilisateur(s) notifié(s).")
    CONTROL_DOC.set({str(creneau): aujourdhui}, merge=True)


if __name__ == "__main__":
    envoyer_rappels_hydratation()
