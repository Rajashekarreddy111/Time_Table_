from fastapi import APIRouter, Depends, Request, Response

from models.schemas import (
    AuthUserResponse,
    ChangePasswordRequest,
    ChangeUsernameRequest,
    CoordinatorCreateRequest,
    CoordinatorListResponse,
    CoordinatorPasswordUpdateRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
)
from services.auth import (
    SESSION_HEADER_NAME,
    authenticate_user,
    change_admin_password,
    change_admin_username,
    clear_session,
    create_coordinator,
    create_session_for_user,
    delete_coordinator,
    get_current_user,
    list_coordinators,
    require_roles,
    reset_coordinator_password,
)
from storage.memory_store import store

router = APIRouter(tags=["auth"])


@router.post("/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest, response: Response):
    user = authenticate_user(payload.username, payload.password, payload.role)
    session_id = create_session_for_user(user, response)
    response.headers[SESSION_HEADER_NAME] = session_id
    return LoginResponse(
        user=AuthUserResponse(id=str(user["id"]), username=str(user["username"]), role=str(user["role"])),
        message="Login successful",
        sessionId=session_id,
    )


@router.post("/auth/logout", response_model=MessageResponse)
async def logout(request: Request, response: Response):
    clear_session(response, request)
    return MessageResponse(message="Logged out successfully")


@router.get("/auth/me", response_model=AuthUserResponse)
async def me(user: dict = Depends(get_current_user)):
    return AuthUserResponse(id=str(user["id"]), username=str(user["username"]), role=str(user["role"]))


@router.post("/auth/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    user: dict = Depends(require_roles("admin")),
):
    refreshed_user = change_admin_password(user, payload.currentPassword, payload.newPassword)
    session_id = create_session_for_user(refreshed_user, response)
    response.headers[SESSION_HEADER_NAME] = session_id
    return MessageResponse(message="Password updated successfully")


@router.post("/auth/change-username", response_model=AuthUserResponse)
async def change_username(
    payload: ChangeUsernameRequest,
    response: Response,
    user: dict = Depends(require_roles("admin")),
):
    updated_user = change_admin_username(user, payload.currentPassword, payload.newUsername)
    refreshed_user = store.get_user_by_username(updated_user["username"]) or updated_user
    session_id = create_session_for_user(refreshed_user, response)
    response.headers[SESSION_HEADER_NAME] = session_id
    return AuthUserResponse(**updated_user)


@router.get("/auth/coordinators", response_model=CoordinatorListResponse)
async def coordinators(user: dict = Depends(require_roles("admin"))):
    return CoordinatorListResponse(items=list_coordinators(user))


@router.post("/auth/coordinators", response_model=AuthUserResponse)
async def add_coordinator(
    payload: CoordinatorCreateRequest,
    user: dict = Depends(require_roles("admin")),
):
    created = create_coordinator(payload.username, payload.password, user)
    return AuthUserResponse(**created)


@router.put("/auth/coordinators/{username}/password", response_model=MessageResponse)
async def update_coordinator_password(
    username: str,
    payload: CoordinatorPasswordUpdateRequest,
    user: dict = Depends(require_roles("admin")),
):
    reset_coordinator_password(username, payload.newPassword, user)
    return MessageResponse(message="Coordinator password updated successfully")


@router.delete("/auth/coordinators/{username}", response_model=MessageResponse)
async def remove_coordinator(username: str, user: dict = Depends(require_roles("admin"))):
    delete_coordinator(username, user)
    return MessageResponse(message="Coordinator deleted successfully")
