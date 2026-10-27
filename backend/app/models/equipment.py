from sqlalchemy import ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.lab import Lab


class Equipment(Base):
    __tablename__ = "equipments"
    __table_args__ = {"comment": "设备信息"}

    lab_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("labs.id"), comment="所属实验室ID", nullable=False
    )
    name: Mapped[str] = mapped_column(String(50), comment="设备名称", nullable=False)
    description: Mapped[str | None] = mapped_column(
        String(500), comment="设备描述", nullable=True
    )
    img: Mapped[str | None] = mapped_column(
        String(100), comment="设备图片", nullable=True
    )
    spec: Mapped[str | None] = mapped_column(
        String(100), comment="型号规格", nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, comment="数量", default=1)
    status: Mapped[int] = mapped_column(
        Integer, comment="设备状态:0-维修,1-正常", default=1
    )

    lab: Mapped[Lab] = relationship()
