from fastapi import FastAPI, HTTPException
from app.models.user import User
from app.database import Base, engine
from fastapi.exceptions import RequestValidationError
from app.api import api
from starlette.middleware.cors import CORSMiddleware
from app.common.exceptions import (
    BusinessExcepition,
    bussiness_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    global_exception_handler,
)

Base.metadata.create_all(bind=engine)  # 自动创建数据库和数据库表

app = FastAPI()

# 允许跨域请求
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # 允许的前端源，不要直接写 ["*"]
    allow_credentials=True,  # 允许前端携带 Authorization token
    allow_methods=["*"],  # 允许所有请求方法 GET POST PUT DELETE OPTIONS
    allow_headers=["*"],  # 允许所有请求头（包含Authorization）
)

app.include_router(api)

# 注册自定义异常
app.add_exception_handler(BusinessExcepition, bussiness_exception_handler)
# 注册HTTP异常处理器
app.add_exception_handler(HTTPException, http_exception_handler)
# 注册参数异常处理器
app.add_exception_handler(RequestValidationError, validation_exception_handler)
# 注册全局异常兜底，必须放在最后注册
app.add_exception_handler(Exception, global_exception_handler)


@app.get("/")
def root():
    return {"message": "Hello FastAPI"}
