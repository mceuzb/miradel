from aiogram import Router

from . import groups, tasks

router = Router(name="teacher")
router.include_router(groups.router)
router.include_router(tasks.router)
