from fastapi import APIRouter

from app.api.v1 import activities, admin, auth, redemptions, staff, users, wallet

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(wallet.router)
api_router.include_router(redemptions.router)
api_router.include_router(activities.router)
api_router.include_router(admin.router)
api_router.include_router(staff.router)
