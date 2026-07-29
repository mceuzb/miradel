from aiogram import Router

from . import approval, groups, modules

router = Router(name="admin")
router.include_router(approval.router)
router.include_router(modules.router)
router.include_router(groups.router)
