from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class RegisterRequest(BaseModel):
    email: EmailStr | None = None
    phone: str | None = Field(default=None, pattern=r"^\+[1-9]\d{7,14}$")
    full_name: str = Field(min_length=1, max_length=120, strip_whitespace=True)
    password: str = Field(min_length=12, max_length=128)

    @model_validator(mode="after")
    def require_contact(self) -> "RegisterRequest":
        if self.email is None and self.phone is None:
            raise ValueError("Provide an email address or mobile number")
        if self.email is not None:
            self.email = self.email.lower()
        return self


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=320, strip_whitespace=True)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str | None
    phone: str | None
    full_name: str
    role: str


class MessageResponse(BaseModel):
    message: str
