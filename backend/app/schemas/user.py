from pydantic import BaseModel, ConfigDict


class UserResponse(BaseModel):
    id: int
    username: str
    name: str
    role: str
    status: int
    email: str | None = None
    phone: str | None = None

    model_config = ConfigDict(from_attributes=True)  # 将对象JSON序列化
