"""
Outil : métabolisme
Calculs métaboliques (BMR, TDEE, déficit, perte estimée, hydratation, morphotype)
Port fidèle de metabolic_service.dart (formule Harris-Benedict).
"""

from tools.firebase_utils import get_db, trouver_utilisateur_par_email


def _freq_to_jours(freq: str) -> int:
    return {
        "Jamais": 0,
        "1-2x/semaine": 2,
        "3-4x/semaine": 3,
        "5x+/semaine": 5,
    }.get(freq, 3)


def _kcal_seance(poids: float, intensite: str, duree_min: int) -> float:
    if duree_min <= 0:
        return 0.0
    met = {
        "Legere": 3.5,
        "Moderee": 6.0,
        "Intense": 9.0,
        "Tres intense": 12.0,
    }.get(intensite, 6.0)
    return met * poids * (duree_min / 60)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def calculer_metabolisme(email: str) -> dict:
    """
    Calcule le métabolisme de base (BMR) et les indicateurs associés
    (TDEE, déficit calorique, perte estimée, hydratation, morphotype)
    à partir du profil Zero Excuse de l'utilisateur.

    Utilise les données du questionnaire d'onboarding (diagnosticAnswers) :
    sexe, âge, taille, poids, tour de taille, fréquence et intensité sportive.
    Si ces données n'ont pas été renseignées, des valeurs par défaut
    raisonnables sont utilisées (identique au comportement de l'app Flutter).
    """
    user = trouver_utilisateur_par_email(email)
    if not user:
        return {
            "succes": False,
            "message": "Aucun compte Zero Excuse trouvé avec cet email.",
        }

    uid = user["uid"]
    db = get_db()
    doc = db.collection("users").document(uid).get()
    d = doc.to_dict() if doc.exists else {}
    a = d.get("diagnosticAnswers") or {}

    sexe = str(a.get("sexe") or "Homme")
    age = int(a.get("age") or 30)
    taille = int(a.get("taille") or d.get("heightCm") or 170)
    poids = float(a.get("poids") or 80.0)
    tour_taille = int(a.get("tourTaille") or 85)
    freq_sport = str(a.get("freqSport") or "Jamais")
    intensite = str(a.get("intensite") or "Moderee")
    duree_sport = int(a.get("dureeSport") or 0)
    objectif = float(d.get("goalWeight") or d.get("diagnosticObjectif") or (poids - 5))

    t = float(taille)
    t_m = t / 100

    # ── 1. BMR — Harris-Benedict ──
    if sexe == "Homme":
        bmr = 88.36 + (13.4 * poids) + (4.8 * t) - (5.7 * age)
    else:
        bmr = 447.6 + (9.25 * poids) + (3.1 * t) - (4.3 * age)

    # ── 2. Jours d'entraînement/semaine ──
    nb_jours = _freq_to_jours(freq_sport)

    # ── 3. Calories brûlées par séance ──
    kcal_seance = _kcal_seance(poids, intensite, duree_sport)

    # ── 4. TDEE ──
    tdee_repos = bmr * 1.2
    tdee_entrainement = tdee_repos + kcal_seance

    # ── 5. Apport calorique cible ──
    kcal_min = 1500.0 if sexe == "Homme" else 1200.0
    apport_cible = _clamp(tdee_repos - 500, kcal_min, tdee_repos)

    # ── 6. Déficits effectifs ──
    deficit_repos = _clamp(tdee_repos - apport_cible, 0, 1000)
    deficit_entrainement = _clamp(tdee_entrainement - apport_cible, 0, 1500)

    # ── 7. Perte journalière (1 kg graisse = 7700 kcal) ──
    perte_daily_repos = deficit_repos / 7700
    perte_daily_entrainement = deficit_entrainement / 7700

    # ── 8. Perte hebdomadaire ──
    jours_repos = 7 - nb_jours
    perte_hebdo = (perte_daily_entrainement * nb_jours) + (perte_daily_repos * jours_repos)

    # ── 9. Hydratation ──
    hydratation_base = poids * 0.033
    hydratation_sport = nb_jours * 0.5 / 7
    hydratation_l = _clamp(hydratation_base + hydratation_sport, 1.5, 4.0)

    # ── 10. IMC ──
    imc = poids / (t_m * t_m)

    # ── 11. Morphotype ──
    ic = poids / (t_m ** 3) * 10
    ratio_taille_taille = tour_taille / taille

    if imc < 21.5 and ic < 13.0:
        morphotype = "Ectomorphe"
        morpho_desc = (
            "Silhouette naturellement mince, métabolisme rapide. Le corps brûle "
            "facilement les calories mais stocke peu de muscle. Déficit modéré "
            "recommandé pour préserver la masse musculaire."
        )
    elif 21.5 <= imc <= 25.0 and ratio_taille_taille < 0.5:
        morphotype = "Mésomorphe"
        morpho_desc = (
            "Morphologie athlétique équilibrée. Prise et perte de poids "
            "relativement faciles. Déficit standard avec entraînement mixte optimal."
        )
    else:
        morphotype = "Endomorphe"
        morpho_desc = (
            "Tendance naturelle à stocker les graisses, métabolisme plus lent. "
            "La perte de poids demande plus d'effort et de régularité. "
            "Déficit progressif + activité cardio recommandés."
        )

    return {
        "succes": True,
        "profil": {
            "sexe": sexe,
            "age": age,
            "taille_cm": taille,
            "poids_kg": poids,
            "objectif_kg": objectif,
            "tour_taille_cm": tour_taille,
            "frequence_sport": freq_sport,
            "intensite": intensite,
            "duree_sport_min": duree_sport,
        },
        "bmr_kcal": round(bmr),
        "tdee_repos_kcal": round(tdee_repos),
        "tdee_entrainement_kcal": round(tdee_entrainement),
        "apport_cible_kcal": round(apport_cible),
        "deficit_repos_kcal": round(deficit_repos),
        "deficit_entrainement_kcal": round(deficit_entrainement),
        "perte_estimee_g_jour_repos": round(perte_daily_repos * 1000),
        "perte_estimee_g_jour_entrainement": round(perte_daily_entrainement * 1000),
        "perte_estimee_kg_semaine": round(perte_hebdo, 2),
        "projection_kg_mois": round(perte_hebdo * 4, 1),
        "hydratation_l_jour": round(hydratation_l, 1),
        "imc": round(imc, 1),
        "morphotype": morphotype,
        "morphotype_description": morpho_desc,
        "message": (
            f"Métabolisme de base : {round(bmr)} kcal/jour. "
            f"Apport cible : {round(apport_cible)} kcal/jour. "
            f"Perte estimée : {round(perte_hebdo, 2)} kg/semaine. "
            f"Morphotype : {morphotype}."
        ),
    }
