"""Aggregates all /api/v1 sub-routers. Each domain's router is added here as it
is implemented across the build phases."""

from fastapi import APIRouter

from app.api.v1 import admin, auth, hackathons

api_router = APIRouter()
api_router.include_router(admin.router, tags=["admin"])
api_router.include_router(auth.router)
api_router.include_router(hackathons.router)
