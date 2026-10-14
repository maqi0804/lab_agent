from typing import Any

from pydantic import BaseModel


class Response(BaseModel):
    """统一封装的返回格式"""

    code: int
    message: str
    data: Any = None

    @classmethod
    def success(cls, message: str = "请求成功", data: Any = None):
        return cls(code=200, message=message, data=data)

    @classmethod
    def error(cls, code: int = 500, message: str = "请求失败", data: Any = None):
        return cls(code=code, message=message, data=data)


class PageResponse(BaseModel):
    """统一封装的分页返回格式"""

    list: Any = []
    total: int = 0
