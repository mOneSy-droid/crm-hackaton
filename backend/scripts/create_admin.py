"""Admin foydalanuvchi yaratadi.

    .venv\\Scripts\\python.exe scripts\\create_admin.py admin MahfiyParol123

Parol argument sifatida berilgani uchun terminal tarixida qoladi —
yaratgandan keyin saytda o'zgartirib qo'ying.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.security import hash_password  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models import User, UserRole  # noqa: E402


async def main(username: str, password: str) -> int:
    if len(password) < 8:
        print("Parol kamida 8 belgidan iborat bo'lsin")
        return 1

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with SessionLocal() as db:
        existing = await db.scalar(select(User).where(User.username == username))
        if existing is not None:
            existing.password_hash = hash_password(password)
            existing.role = UserRole.ADMIN
            existing.is_active = True
            await db.commit()
            print(f"Mavjud '{username}' admin qilindi va paroli yangilandi")
            return 0

        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                role=UserRole.ADMIN,
                full_name="Administrator",
            )
        )
        await db.commit()
        print(f"Admin yaratildi: {username}")
    await engine.dispose()
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Ishlatilishi: python scripts/create_admin.py <login> <parol>")
        sys.exit(1)
    sys.exit(asyncio.run(main(sys.argv[1], sys.argv[2])))
