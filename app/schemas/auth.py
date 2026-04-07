from pydantic import BaseModel, EmailStr

class SignUpModel(BaseModel):
    username: str
    email: EmailStr
    password: str  # input only, DB stores password_hash

class SignInModel(BaseModel):
    email: EmailStr
    password: str
