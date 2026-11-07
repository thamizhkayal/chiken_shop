from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.identity import Role, User


def get_role(db: Session, role_name: str) -> Role | None:
    return db.scalar(select(Role).where(Role.name == role_name))


def find_by_contact(db: Session, identifier: str) -> User | None:
    return db.scalar(
        select(User)
        .options(joinedload(User.role))
        .where(
            or_(
                func.lower(User.email) == identifier.lower(),
                User.phone == identifier,
            )
        )
    )


def find_by_id(db: Session, user_id: UUID) -> User | None:
    return db.scalar(select(User).options(joinedload(User.role)).where(User.id == user_id))
