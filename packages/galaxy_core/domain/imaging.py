"""Domain types for target resolution and catalog image fetching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Band / range as requested by user; maps to a SkyView survey name.
Band = Literal["visible", "optical", "infrared", "ir", "ultraviolet", "uv"]

# SkyView survey identifiers (subset used by our band mapping).
SurveyName = str

# Map band (user-facing) to default SkyView survey. Agent or options can override with catalog=.
BAND_TO_SURVEY: dict[str, SurveyName] = {
    "visible": "DSS",
    "optical": "DSS",
    "infrared": "2MASS-J",
    "ir": "2MASS-J",
    "ultraviolet": "GALEX",
    "uv": "GALEX",
}

# Catálogos/surveys con camino propio (rápido o estable). Cualquier otro se delega a SkyView.
CATALOGS_PRIMARY = ("SDSS", "DSS", "2MASS-J", "GALEX")


def get_capabilities_description() -> str:
    """Texto para que el agente responda preguntas sobre bandas y catálogos disponibles.
    Una sola fuente de verdad: si se añade banda o catálogo, se actualiza aquí y en BAND_TO_SURVEY.
    """
    return (
        "Bandas disponibles: visible (óptico), infrarrojo, ultravioleta (uv). "
        "Catálogos/surveys que usa la aplicación: SDSS (visible, cielo norte), DSS (visible), "
        "2MASS-J (infrarrojo), GALEX (ultravioleta). También se pueden usar otros surveys de SkyView "
        "si se indica el nombre del catálogo. Para imágenes solo hay que indicar galaxia (nombre o coordenadas) "
        "y opcionalmente la banda; si no se indica banda, se usa visible por defecto."
    )


@dataclass(frozen=True)
class ResolvedTarget:
    """Result of resolving a target and fetching an image from a catalog."""

    ra_deg: float
    dec_deg: float
    name: str | None
    survey_used: str
    image_url: str
    size_arcmin: float
