"""
User response schemas.

These Pydantic models define the data shapes returned in API responses.

SECURITY CRITICAL:
  UserResponse intentionally OMITS password_hash.
  Never add password_hash to any response schema.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole


class UserResponse(BaseModel):
    """
    Safe user representation for API responses.

    Excludes all sensitive fields (password_hash).
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime
