from fastapi import Depends

from app.config import Settings, get_settings


async def get_current_settings(
    settings: Settings = Depends(get_settings),
) -> Settings:
    return settings
