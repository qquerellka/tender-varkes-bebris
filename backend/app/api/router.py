from fastapi import APIRouter

from app.api.routes import auth, catalog, debug, events, profile, search, user_actions

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(catalog.router, prefix="/catalog", tags=["catalog"])
api_router.include_router(events.router, prefix="/events", tags=["events"])
api_router.include_router(profile.router, prefix="/profile", tags=["profile"])
api_router.include_router(user_actions.router, prefix="/actions", tags=["actions"])
api_router.include_router(debug.router, prefix="/debug", tags=["debug"])
