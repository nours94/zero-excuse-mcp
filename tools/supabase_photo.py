"""
Outil : supabase_photo
Télécharge une photo transmise par ChatGPT (via openaiFileIdRefs, lien
valable 5 minutes) et la re-stocke de façon permanente sur Supabase
Storage — le même bucket que les photos prises depuis le site.

N'utilise que la bibliothèque standard (urllib) : aucune dépendance
supplémentaire à installer.
"""

import os
import urllib.request

SUPABASE_URL = "https://qickfdlhgjdrtzxmtvga.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_tgtX28p35SHQMd-ijXZMZQ_88e8ZXQF"
BUCKET = "meal-photos"


def uploader_photo_depuis_chatgpt(download_link: str, uid: str, mime_type: str = "image/jpeg") -> str | None:
    """
    Télécharge l'image depuis le lien temporaire fourni par ChatGPT
    (openaiFileIdRefs), puis la re-uploade sur Supabase Storage.
    Retourne l'URL publique permanente, ou None en cas d'échec
    (une photo ratée ne doit pas empêcher l'enregistrement du repas).
    """
    try:
        with urllib.request.urlopen(download_link, timeout=8) as resp:
            image_bytes = resp.read()
    except Exception:
        return None

    ext = "png" if "png" in mime_type else "jpg"
    path = f"{uid}/chatgpt_{os.urandom(6).hex()}.{ext}"

    upload_url = f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}"
    req = urllib.request.Request(
        upload_url,
        data=image_bytes,
        method="POST",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": mime_type,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            if resp.status not in (200, 201):
                return None
    except Exception:
        return None

    return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"
