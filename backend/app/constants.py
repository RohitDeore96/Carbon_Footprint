"""Centralized constants configuration layer for the Carbon Footprint Awareness Platform."""

from typing import Final


class AppConstants:
    """Immutable application-wide constants. Frozen via __slots__ to prevent modification."""

    __slots__ = ()

    FIREBASE_COLLECTION_CARBON_LOGS: Final[str] = "carbon_logs"

    ANONYMOUS_USER_ID: Final[str] = "anonymous"

    RATE_LIMIT_REQUESTS_PER_MINUTE: Final[int] = 60
    RATE_LIMIT_BURST: Final[int] = 10

    CSP_POLICY: Final[str] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' https://carbon-footprint-12.web.app https://*.run.app https://*.googleapis.com https://*.firebaseio.com; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    CORS_ALLOWED_ORIGINS: Final[list[str]] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://carbon-footprint-12.web.app",
    ]
    CORS_ALLOWED_METHODS: Final[list[str]] = ["GET", "POST", "PUT", "DELETE"]
    CORS_ALLOWED_HEADERS: Final[list[str]] = ["Content-Type", "Authorization"]

    HSTS_MAX_AGE: Final[int] = 31536000
    X_FRAME_OPTIONS: Final[str] = "DENY"
    X_CONTENT_TYPE_OPTIONS: Final[str] = "nosniff"
    REFERRER_POLICY: Final[str] = "strict-origin-when-cross-origin"

    TRANSPORT_MODES: Final[tuple[str, ...]] = (
        "car",
        "bus",
        "train",
        "bicycle",
        "walking",
        "flight",
    )
    ENERGY_SOURCES: Final[tuple[str, ...]] = (
        "electricity",
        "natural_gas",
        "solar",
        "wind",
    )
    DIET_TYPES: Final[tuple[str, ...]] = (
        "meat_heavy",
        "average",
        "vegetarian",
        "vegan",
    )
    ACTIVITY_CATEGORIES: Final[tuple[str, ...]] = (
        "transport",
        "energy",
        "food",
        "consumption",
    )
    CARBON_UNITS: Final[tuple[str, ...]] = (
        "kg_co2",
        "g_co2",
        "tonnes_co2",
    )

    EMISSION_FACTORS_TRANSPORT_KG_PER_KM: Final[dict[str, float]] = {
        "car": 0.21,
        "bus": 0.089,
        "train": 0.041,
        "bicycle": 0.0,
        "walking": 0.0,
        "flight": 0.255,
    }
    EMISSION_FACTORS_ENERGY_KG_PER_KWH: Final[dict[str, float]] = {
        "electricity": 0.233,
        "natural_gas": 0.184,
        "solar": 0.0,
        "wind": 0.0,
    }
    EMISSION_FACTORS_DIET_KG_PER_DAY: Final[dict[str, float]] = {
        "meat_heavy": 7.19,
        "average": 5.63,
        "vegetarian": 3.81,
        "vegan": 2.89,
    }
    EMISSION_FACTORS_CONSUMPTION_KG_PER_ITEM: Final[dict[str, float]] = {
        "clothing": 15.0,
        "electronics": 100.0,
        "furniture": 50.0,
        "general": 10.0,
    }

    UNIT_CONVERSION_TO_KG: Final[dict[str, float]] = {
        "kg_co2": 1.0,
        "g_co2": 0.001,
        "tonnes_co2": 1000.0,
    }

    VERTEX_AI_PROJECT_ID: Final[str] = "carbon-footprint-12"
    VERTEX_AI_LOCATION: Final[str] = "us-central1"
    VERTEX_AI_MODEL_NAME: Final[str] = "gemini-2.5-flash"
    VERTEX_AI_TIMEOUT_SECONDS: Final[int] = 30
    VERTEX_AI_MAX_OUTPUT_TOKENS: Final[int] = 1024
    VERTEX_AI_TEMPERATURE: Final[float] = 0.7

    VERTEX_AI_SYSTEM_INSTRUCTION: Final[str] = (
        "You are a Sustainability Coach for the Carbon Footprint Awareness Platform. "
        "Your role is to analyze a user's carbon footprint data and provide encouraging, "
        "actionable advice to help them reduce their environmental impact. "
        "Be specific, practical, and positive. Reference the user's actual data in your analysis. "
        "Always respond in the exact JSON structure requested."
    )

    VERTEX_AI_RESPONSE_KEY_INSIGHT: Final[str] = "insight"
    VERTEX_AI_RESPONSE_KEY_EQUIVALENT: Final[str] = "equivalent_impact"
    VERTEX_AI_RESPONSE_KEY_STEPS: Final[str] = "actionable_steps"
    VERTEX_AI_ACTIONABLE_STEPS_COUNT: Final[int] = 3
