import uuid

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    username: str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
