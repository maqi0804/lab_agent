from pydantic import BaseModel, ConfigDict


class LabResponse(BaseModel):
    """实验室信息响应参数"""

    id: int
    name: str
    description: str | None = None
    img: str | None = None
    location: str | None = None
    capacity: int
    open_time: str | None = None
    close_time: str | None = None
    status: int

    model_config = ConfigDict(from_attributes=True)  # 将对象JSON序列化


class LabCreateRequest(BaseModel):
    """实验室信息创建参数"""

    name: str
    description: str | None = None
    img: str | None = None
    location: str | None = None
    capacity: int = 1
    open_time: str | None = None
    close_time: str | None = None
    status: int = 1


class LabUpdateRequest(BaseModel):
    """实验室信息更新参数"""

    name: str | None = None
    description: str | None = None
    img: str | None = None
    location: str | None = None
    capacity: int | None = None
    open_time: str | None = None
    close_time: str | None = None
    status: int | None = None
