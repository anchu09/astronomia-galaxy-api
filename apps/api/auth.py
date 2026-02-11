from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from apps.api.config import Settings, get_settings


def verify_api_key(
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    settings: Annotated[Settings | None, Depends(get_settings)] = None,
) -> None:
    if settings is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "SETTINGS_MISSING", "message": "Failed to load API settings."},
        )

    if not settings.require_api_key:
        return

    if not settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "API_KEY_NOT_CONFIGURED",
                "message": "API key is required but missing.",
            },
        )

    if x_api_key != settings.api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_API_KEY", "message": "Invalid X-API-Key header."},
        )
