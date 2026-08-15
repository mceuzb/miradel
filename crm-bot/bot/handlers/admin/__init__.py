from aiogram import Router

from . import approval, broadcast, channels, contests, groups, modules, teacher_students

router = Router(name="admin")
router.include_router(approval.router)
router.include_router(teacher_students.router)
router.include_router(modules.router)
router.include_router(groups.router)
router.include_router(channels.router)
router.include_router(contests.router)
router.include_router(broadcast.router)
