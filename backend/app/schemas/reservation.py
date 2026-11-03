from pydantic import BaseModel, ConfigDict


class ReservationCreateRequest(BaseModel):
    date: str
    start_time: str
    end_time: str
    equipment_id: int | None = None
    lab_id: int
    remark: str | None = None


class ReservationResponse(BaseModel):
    id: int
    user_id: int
    user_name: str | None = None
    lab_id: int
    lab_name: str | None = None
    equipment_id: int | None = None
    equipment_name: str | None = None
    type: str | None = None
    date: str
    start_time: str
    end_time: str
    remark: str | None = None
    status: int

    model_config = ConfigDict(from_attributes=True)  # 将ORM模型属性映射到Pydantic模型


class AuditReservationRequest(BaseModel):
    status: int  # 1 |2
