from fastapi import APIRouter

from app.api.v1 import (
    auth,
    bot,
    botbuilder,
    exports,
    industries,
    restaurants,
    reviews,
    stats,
    uploads,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(industries.router)
api_router.include_router(restaurants.router)
api_router.include_router(stats.router)
api_router.include_router(exports.router)
api_router.include_router(botbuilder.router)
api_router.include_router(reviews.router)
api_router.include_router(uploads.router)
api_router.include_router(bot.router)
