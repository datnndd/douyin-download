# -*- coding: utf-8 -*-
"""
src/web/api/settings.py
GET and POST endpoints for managing persistent configuration in config.yaml.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from src.web.core.config import ConfigManager
from src.web.core.schemas import SettingsModel

logger = logging.getLogger("DouyinWeb.Api.Settings")
router = APIRouter(tags=["Settings"])


def get_config_manager() -> ConfigManager:
    return ConfigManager.get_instance()


@router.get(
    "/settings",
    response_model=SettingsModel,
    summary="Get Configuration Settings",
)
async def get_settings_endpoint() -> SettingsModel:
    """Retrieves current application settings loaded from config.yaml."""
    manager = get_config_manager()
    return manager.get_settings()


@router.post(
    "/settings",
    response_model=SettingsModel,
    summary="Update Configuration Settings",
)
async def update_settings_endpoint(payload: Dict[str, Any]) -> SettingsModel:
    """
    Updates application settings, synchronizes cookie representations,
    persists changes to config.yaml preserving comments, and updates headers.
    """
    manager = get_config_manager()
    try:
        current = manager.get_settings()
        current_data = current.model_dump()
        current_data.update({k: v for k, v in payload.items() if v is not None})
        new_settings = SettingsModel(**current_data)
        updated = manager.update_settings(new_settings)
        return updated
    except Exception as e:
        logger.error(f"Failed to update settings: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid settings payload: {str(e)}")
