from aiogram import Router

from . import referral, tasks

router = Router(name="student")
router.include_router(tasks.router)
router.include_router(referral.router)
