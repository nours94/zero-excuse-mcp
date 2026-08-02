import os
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from tools.firebase_utils import verifier_plan, trouver_utilisateur_par_api_key
from tools.repas import enregistrer_repas, historique_repas, bilan_calorique_jour
from tools.poids import poids_du_jour, historique_poids
from tools.metabolisme import calculer_metabolisme
from tools.analyse import analyser_progression

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


# ── OUTIL 8 : ANALYSE APPROFONDIE DE LA PROGRESSION ───────────────
@mcp.tool(annotations=READ_ONLY)
def analyser_progression_complete(email: str, jours: int = 21) -> dict:
    """
    Analyse approfondie de la progression : compare le rythme RÉEL de
    perte/prise de poids (mesuré sur l'historique des pesées des X derniers
    jours) au rythme THÉORIQUE calculé depuis le métabolisme de base
    (Harris-Benedict), et projette le nombre de semaines restantes avant
    d'atteindre l'objectif, aux deux rythmes.

    Exclut automatiquement les pesées marquées comme exceptionnelles
    (voyage, maladie, règles, etc.) pour ne pas fausser l'analyse.

    Exemples de déclenchement :
    - "Suis-je dans les temps par rapport à mon objectif ?"
    - "Est-ce que je progresse assez vite ?"
    - "Dans combien de temps vais-je atteindre mon objectif ?"
    - "Compare ma progression réelle à ce que mon métabolisme permettrait"
    """
    return analyser_progression(email=email, jours=jours)


# ══════════════════════════════════════════════════════════════════
# PONT REST — pour l'Action ChatGPT (authentification par clé API)
# ══════════════════════════════════════════════════════════════════
# Ces routes réutilisent exactement les mêmes fonctions que les outils
# MCP ci-dessus, mais identifient l'utilisateur via sa clé API
# personnelle (header Authorization: Bearer <clé>) plutôt que par email.
# Compatible avec un compte ChatGPT gratuit (Actions classiques, pas
# besoin de connecteur MCP ni de compte Plus/Pro).

def _auth_email(request: Request) -> tuple[str | None, JSONResponse | None]:
    """
    Extrait la clé API du header Authorization, retrouve l'utilisateur
    correspondant, et renvoie son email. En cas d'échec, renvoie une
    JSONResponse d'erreur prête à être retournée telle quelle.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None, JSONResponse(
            {"succes": False, "message": "Clé API manquante (header Authorization: Bearer <clé>)."},
            status_code=401,
        )

    api_key = auth_header[7:].strip()
    user = trouver_utilisateur_par_api_key(api_key)
    if not user:
        return None, JSONResponse(
            {"succes": False, "message": "Clé API invalide ou inconnue."},
            status_code=401,
        )

    return user.get("email"), None


@mcp.custom_route("/api/verifier-compte", methods=["GET"])
async def api_verifier_compte(request: Request) -> JSONResponse:
    email, err = _auth_email(request)
    if err:
        return err
    return JSONResponse(verifier_plan(email))


@mcp.custom_route("/api/repas", methods=["POST"])
async def api_sauvegarder_repas(request: Request) -> JSONResponse:
    email, err = _auth_email(request)
    if err:
        return err
    body = await request.json()
    result = enregistrer_repas(
        email=email,
        aliments=body.get("aliments", []),
        calories=body.get("calories", 0),
        proteines=body.get("proteines"),
        glucides=body.get("glucides"),
        lipides=body.get("lipides"),
        repas_type=body.get("repas_type", "repas"),
        notes=body.get("notes", ""),
    )
    return JSONResponse(result)


@mcp.custom_route("/api/historique-repas", methods=["GET"])
async def api_historique_repas(request: Request) -> JSONResponse:
    email, err = _auth_email(request)
    if err:
        return err
    jours = max(1, min(int(request.query_params.get("jours", 7)), 30))
    return JSONResponse(historique_repas(email=email, jours=jours))


@mcp.custom_route("/api/bilan-jour", methods=["GET"])
async def api_bilan_jour(request: Request) -> JSONResponse:
    email, err = _auth_email(request)
    if err:
        return err
    return JSONResponse(bilan_calorique_jour(email=email))


@mcp.custom_route("/api/poids-jour", methods=["GET"])
async def api_poids_jour(request: Request) -> JSONResponse:
    email, err = _auth_email(request)
    if err:
        return err
    return JSONResponse(poids_du_jour(email=email))


@mcp.custom_route("/api/historique-poids", methods=["GET"])
async def api_historique_poids(request: Request) -> JSONResponse:
    email, err = _auth_email(request)
    if err:
        return err
    jours = max(1, min(int(request.query_params.get("jours", 7)), 30))
    return JSONResponse(historique_poids(email=email, jours=jours))


@mcp.custom_route("/api/metabolisme", methods=["GET"])
async def api_metabolisme(request: Request) -> JSONResponse:
    email, err = _auth_email(request)
    if err:
        return err
    return JSONResponse(calculer_metabolisme(email=email))


@mcp.custom_route("/api/progression", methods=["GET"])
async def api_progression(request: Request) -> JSONResponse:
    email, err = _auth_email(request)
    if err:
        return err
    jours = max(1, min(int(request.query_params.get("jours", 21)), 90))
    return JSONResponse(analyser_progression(email=email, jours=jours))


@mcp.custom_route("/openapi.json", methods=["GET"])
async def openapi_schema(request: Request) -> JSONResponse:
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse({
        "openapi": "3.1.0",
        "info": {
            "title": "Zero Excuse — Coach Nutrition",
            "description": "Enregistrement et consultation des repas, poids et métabolisme Zero Excuse.",
            "version": "1.0.0",
        },
        "servers": [{"url": base_url}],
        "components": {
            "securitySchemes": {
                "bearerAuth": {"type": "http", "scheme": "bearer"}
            }
        },
        "security": [{"bearerAuth": []}],
        "paths": {
            "/api/verifier-compte": {
                "get": {
                    "operationId": "verifierCompte",
                    "summary": "Vérifie le compte Zero Excuse associé à la clé API.",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/api/repas": {
                "post": {
                    "operationId": "sauvegarderRepas",
                    "summary": "Enregistre un repas analysé (aliments, calories, macros).",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["aliments", "calories"],
                                    "properties": {
                                        "aliments": {"type": "array", "items": {"type": "string"}},
                                        "calories": {"type": "integer"},
                                        "proteines": {"type": "number", "nullable": True},
                                        "glucides": {"type": "number", "nullable": True},
                                        "lipides": {"type": "number", "nullable": True},
                                        "repas_type": {"type": "string", "default": "repas"},
                                        "notes": {"type": "string", "default": ""},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/api/historique-repas": {
                "get": {
                    "operationId": "historiqueRepas",
                    "summary": "Historique des repas des X derniers jours.",
                    "parameters": [{
                        "name": "jours", "in": "query", "required": False,
                        "schema": {"type": "integer", "default": 7},
                    }],
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/api/bilan-jour": {
                "get": {
                    "operationId": "bilanJour",
                    "summary": "Bilan calorique du jour en cours.",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/api/poids-jour": {
                "get": {
                    "operationId": "poidsJour",
                    "summary": "Poids enregistré aujourd'hui.",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/api/historique-poids": {
                "get": {
                    "operationId": "historiquePoids",
                    "summary": "Historique des pesées des X derniers jours.",
                    "parameters": [{
                        "name": "jours", "in": "query", "required": False,
                        "schema": {"type": "integer", "default": 7},
                    }],
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/api/metabolisme": {
                "get": {
                    "operationId": "metabolisme",
                    "summary": "Métabolisme de base (BMR/TDEE) et objectifs caloriques.",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/api/progression": {
                "get": {
                    "operationId": "progression",
                    "summary": "Analyse de la progression réelle vs théorique.",
                    "parameters": [{
                        "name": "jours", "in": "query", "required": False,
                        "schema": {"type": "integer", "default": 21},
                    }],
                    "responses": {"200": {"description": "OK"}},
                }
            },
        },
    })


# ── DÉMARRAGE ────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    mcp.run(transport="http", host="0.0.0.0", port=port)
