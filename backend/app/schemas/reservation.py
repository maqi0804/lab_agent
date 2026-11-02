from pydantic import BaseModel


class ReservationCreateRequest(BaseModel):
    date: str
    start_time: str
    end_time: str
    equipment_id: int | None = None
    lab_id: int
    remark: str | None = None
