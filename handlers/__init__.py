from aiogram import Router

from . import admin, chat_events, media


def setup_routers() -> Router:
    router = Router(name="root")
    router.include_router(admin.router)
    router.include_router(chat_events.router)
    router.include_router(media.router)
    return router
