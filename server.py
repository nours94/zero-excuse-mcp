import os
from fastmcp import FastMCP
from tools.firebase_utils import verifier_plan
from tools.repas import enregistrer_repas, historique_repas, bilan_calorique_jour
from tools.poids import poids_du_jour, historique_poids
from tools.metabolisme import calculer_metabolisme

mcp = FastMCP("Zero Excuse — Coach Nutrition")

READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}

WRITE_TOOL = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": False,
}


# ── OUTIL 1 : VÉRIFIER COMPTE ────────────────────────────────────
@mcp.tool(annotations=READ_ONLY)
def verifier_compte(email: str) -> dict:
    """
    Vérifie qu'un utilisateur a bien un compte Zero Excuse et retourne
    son plan (free/premium) et ses données de profil.

    À utiliser en premier dans chaque conversation pour identifier
    l'utilisateur avant d'enregistrer des données.

    Exemple : "Mon email Zero Excuse est olivier@example.com"
    """
    return verifier_plan(email)


# ── OUTIL 2 : ENREGISTRER REPAS ──────────────────────────────────
@mcp.tool(annotations=WRITE_TOOL)
def sauvegarder_repas(
    email: str,
    aliments: list[str],
    calories: int,
    proteines: float | None = None,
    glucides: float | None = None,
    lipides: float | None = None,
    repas_type: str = "repas",
    notes: str = "",
) -> dict:
    """
    Enregistre un repas analysé par ChatGPT dans Firebase Zero Excuse.

    À utiliser APRÈS que l'utilisateur a envoyé une photo de son repas
    et que ChatGPT a identifié les aliments et estimé les calories.

    Exemples de déclenchement :
    - "Enregistre ce repas dans Zero Excuse"
    - "Sauvegarde mon déjeuner"
    - "Ajoute ça à mon journal alimentaire"
    """
    return enregistrer_repas(
        email=email,
        aliments=aliments,
        calories=calories,
        proteines=proteines,
        glucides=glucides,
        lipides=lipides,
        repas_type=repas_type,
        notes=notes,
    )


# ── OUTIL 3 : HISTORIQUE REPAS ───────────────────────────────────
@mcp.tool(annotations=READ_ONLY)
def voir_historique_repas(email: str, jours: int = 7) -> dict:
    """
    Retourne l'historique des repas des X derniers jours enregistrés
    dans Zero Excuse, avec le total calorique par jour.

    Exemples de déclenchement :
    - "Montre-moi mes repas de la semaine"
    - "Quel était mon bilan alimentaire hier ?"
    - "Mes repas des 3 derniers jours"
    """
    jours = max(1, min(jours, 30))
    return historique_repas(email=email, jours=jours)


# ── OUTIL 4 : BILAN DU JOUR ──────────────────────────────────────
@mcp.tool(annotations=READ_ONLY)
def bilan_du_jour(email: str) -> dict:
    """
    Retourne le bilan calorique du jour en cours : calories consommées,
    objectif calorique calculé depuis le profil Zero Excuse (formule
    Harris-Benedict), et calories restantes avant d'atteindre l'objectif.

    Exemples de déclenchement :
    - "Combien de calories me reste-t-il aujourd'hui ?"
    - "Quel est mon bilan calorique du jour ?"
    - "Est-ce que j'ai dépassé mon objectif aujourd'hui ?"
    """
    return bilan_calorique_jour(email=email)


# ── OUTIL 5 : POIDS DU JOUR ───────────────────────────────────────
@mcp.tool(annotations=READ_ONLY)
def voir_poids_jour(email: str) -> dict:
    """
    Retourne le poids enregistré aujourd'hui par l'utilisateur
    (saisi depuis l'app Flutter ou le site web Zero Excuse).

    Exemples de déclenchement :
    - "Quel est mon poids aujourd'hui ?"
    - "Est-ce que je me suis pesé aujourd'hui ?"
    - "Quel poids j'ai entré ce matin ?"
    """
    return poids_du_jour(email=email)


# ── OUTIL 6 : HISTORIQUE POIDS ────────────────────────────────────
@mcp.tool(annotations=READ_ONLY)
def voir_historique_poids(email: str, jours: int = 7) -> dict:
    """
    Retourne l'historique des pesées des X derniers jours, avec
    l'évolution du poids jour par jour et la variation totale sur
    la période.

    Exemples de déclenchement :
    - "Comment évolue mon poids cette semaine ?"
    - "Montre-moi ma courbe de poids"
    - "Combien j'ai perdu ce mois-ci ?"
    """
    return historique_poids(email=email, jours=jours)


# ── OUTIL 7 : MÉTABOLISME DE BASE ─────────────────────────────────
@mcp.tool(annotations=READ_ONLY)
def calculer_metabolisme_base(email: str) -> dict:
    """
    Calcule le métabolisme de base (BMR, formule Harris-Benedict) et
    les indicateurs associés : dépense énergétique totale (TDEE) au
    repos et en jour d'entraînement, apport calorique cible, déficit,
    perte de poids estimée par jour/semaine/mois, besoin d'hydratation
    et morphotype (ecto/méso/endomorphe).

    Se base sur le questionnaire de profil de l'utilisateur (sexe, âge,
    taille, poids, tour de taille, fréquence et intensité sportive).

    Exemples de déclenchement :
    - "Quel est mon métabolisme de base ?"
    - "Combien de calories je brûle par jour ?"
    - "Combien je vais perdre par semaine ?"
    - "Combien d'eau je dois boire ?"
    - "Quel est mon morphotype ?"
    """
    return calculer_metabolisme(email=email)


# ── DÉMARRAGE ────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    mcp.run(transport="http", host="0.0.0.0", port=port)
