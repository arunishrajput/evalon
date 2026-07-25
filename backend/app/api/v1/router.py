"""Aggregates all /api/v1 sub-routers. Each domain's router is added here as it
is implemented across the build phases."""

from fastapi import APIRouter

from app.api.v1 import admin

api_router = APIRouter()
api_router.include_router(admin.router, tags=["admin"])
