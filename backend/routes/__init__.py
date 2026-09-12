"""Backend routes package initialization."""
from backend.routes.sessions import router as session_router, set_router_context as set_session_ctx
from backend.routes.attendance import router as attendance_router, set_router_context as set_attendance_ctx
from backend.routes.enrollment import router as enrollment_router, set_router_context as set_enrollment_ctx
from backend.routes.diagnostics import router as diagnostics_router, set_router_context as set_diagnostics_ctx

def init_all_routes(app_context):
    set_session_ctx(app_context)
    set_attendance_ctx(app_context)
    set_enrollment_ctx(app_context)
    set_diagnostics_ctx(app_context)

__all__ = [
    "session_router",
    "attendance_router",
    "enrollment_router",
    "diagnostics_router",
    "init_all_routes"
]
