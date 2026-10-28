from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    password: str = Field(min_length=8, max_length=200)
    remember_me: bool = False
    organization: str = Field(default="default", min_length=2, max_length=80)


class AuthUser(BaseModel):
    id: UUID
    username: str
    role: Literal["admin", "user"]
    organization_id: UUID
    organization_name: str
    organization_slug: str
    is_demo: bool = False


class LoginResponse(BaseModel):
    expires_in: int
    user: AuthUser


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=8, max_length=200)
