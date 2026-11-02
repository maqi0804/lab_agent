from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.equipment import Equipment
from app.models.lab import Lab
from app.models.user import User


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = {"comment": "预约信息表"}

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), comment="预约人", nullable=False
    )
    lab_id: Mapped[int] = mapped_column(
        ForeignKey("labs.id"), comment="实验室", nullable=False
    )
    equipment_id: Mapped[int] = mapped_column(
        ForeignKey("equipments.id"), comment="设备，空表示预约实验室", nullable=True
    )
    date: Mapped[str] = mapped_column(String(20), comment="预约日期", nullable=False)
    start_time: Mapped[str] = mapped_column(
        String(20), comment="使用开始时间", nullable=False
    )
    end_time: Mapped[str] = mapped_column(
        String(20), comment="使用结束时间", nullable=False
    )
    remark: Mapped[str | None] = mapped_column(
        String(255), comment="预约备注", nullable=True
    )
    status: Mapped[int] = mapped_column(
        default=0, comment="预约状态:0-待审核,1-审核通过,2-审核未通过,3-已取消"
    )

    user: Mapped[User] = relationship()
    lab: Mapped[Lab] = relationship()
    equipment: Mapped[Equipment] = relationship()
