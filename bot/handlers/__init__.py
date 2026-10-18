from aiogram import Router

from bot.handlers import admin, common, user


def setup_routers() -> Router:
    root = Router()
    root.include_router(common.router)
    root.include_router(user.router)
    root.include_router(admin.router)
    return root
