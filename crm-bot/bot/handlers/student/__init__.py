from aiogram import Router

from . import tasks

router = Router(name="student")
router.include_router(tasks.router)
