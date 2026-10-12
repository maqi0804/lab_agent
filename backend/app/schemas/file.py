from pydantic import BaseModel


class fileResponse(BaseModel):
    original_name: str
    disk_name: str
    size: int
    url: str
