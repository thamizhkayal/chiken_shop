import argparse
from getpass import getpass

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.identity import Role, StaffProfile, User


def create_privileged_user(role_name: str, email: str, full_name: str) -> None:
    if role_name not in {"staff", "admin"}:
        raise ValueError("Only staff and admin accounts can be bootstrapped")
    password = getpass("Password (12+ characters): ")
    confirmation = getpass("Confirm password: ")
    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters")
    if password != confirmation:
        raise ValueError("Passwords do not match")

    with SessionLocal() as db:
        role = db.scalar(select(Role).where(Role.name == role_name))
        if role is None:
            raise RuntimeError("Roles are not initialized; run Alembic migrations first")
        existing = db.scalar(select(User.id).where(User.email == email.lower()))
        if existing is not None:
            raise ValueError("An account with that email already exists")

        user = User(
            role_id=role.id,
            email=email.lower(),
            full_name=full_name.strip(),
            password_hash=hash_password(password),
        )
        db.add(user)
        db.flush()
        db.add(StaffProfile(user_id=user.id, display_name=full_name.strip()))
        db.commit()
        print(f"Created {role_name} account for {email.lower()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision a shop staff or administrator account.")
    parser.add_argument("--role", choices=("staff", "admin"), required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    create_privileged_user(args.role, args.email, args.name)


if __name__ == "__main__":
    main()
