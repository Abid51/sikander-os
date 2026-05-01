"""
Centralized API router and dependency wiring.

Keeps backend `main.py` focused on app lifecycle while this module handles
cross-router composition.
"""

from fastapi import FastAPI

from app.api import (
    routes,
    advanced_routes,
    new_systems_routes,
    admin_routes,
    model_routes,
    advanced_features_routes,
    vision_routes,
    voice_routes,
    tools_routes,
    power_routes,
    ws_hub,
    frontend_routes,
    quantum_routes,
)


def wire_shared_dependencies(brain, sys_ctrl) -> None:
    """
    Wire shared service instances into routers that support dependency injection.
    """
    routes.set_dependencies(brain, sys_ctrl)
    if hasattr(voice_routes, "set_dependencies"):
        voice_routes.set_dependencies(brain, sys_ctrl)


def register_all_routers(app: FastAPI) -> None:
    """Register all API routers in one place."""
    for router in (
        routes.router,
        advanced_routes.router,
        new_systems_routes.router,
        admin_routes.router,
        model_routes.router,
        advanced_features_routes.router,
        vision_routes.router,
        voice_routes.router,
        tools_routes.router,
        power_routes.router,
        ws_hub.router,
        frontend_routes.router,
        quantum_routes.router,
    ):
        app.include_router(router)
