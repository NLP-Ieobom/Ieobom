import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

ALGORITHM = os.environ["JWT_ALGORITHM"]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=int(os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"]))
    payload = {"sub": str(user_id), "role": role, "type": "access", "exp": expire}
    return jwt.encode(payload, os.environ["JWT_SECRET_KEY"], algorithm=ALGORITHM)


def create_refresh_token(user_id: uuid.UUID, jti: uuid.UUID) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=int(os.environ["REFRESH_TOKEN_EXPIRE_DAYS"]))
    payload = {"sub": str(user_id), "type": "refresh", "jti": str(jti), "exp": expire}
    return jwt.encode(payload, os.environ["JWT_SECRET_KEY"], algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, os.environ["JWT_SECRET_KEY"], algorithms=[ALGORITHM])
