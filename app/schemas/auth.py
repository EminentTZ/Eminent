from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(BaseModel):
    """Self-service: any signed-in user changing their own password."""
    current_password: str
    new_password: str = Field(min_length=6)


class ResetPasswordRequest(BaseModel):
    """Admin override: set someone else's password without knowing the old one."""
    new_password: str = Field(min_length=6)
