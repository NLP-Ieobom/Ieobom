import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RefreshRequest, SignupRequest, TokenResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(db: Session, user: User) -> TokenResponse:
    token_row = RefreshToken(
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=int(os.environ["REFRESH_TOKEN_EXPIRE_DAYS"])),
    )
    db.add(token_row)
    db.flush()  # refresh token에 넣을 jti(token_row.id)가 먼저 있어야 한다
    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id, token_row.id),
    )


def _get_valid_refresh_token_row(db: Session, raw_token: str) -> RefreshToken:
    try:
        decoded = decode_token(raw_token)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid refresh token")
    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="invalid refresh token")

    try:
        jti = uuid.UUID(decoded.get("jti", ""))
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid refresh token")

    token_row = db.get(RefreshToken, jti)
    if token_row is None or token_row.revoked_at is not None:
        raise HTTPException(status_code=401, detail="invalid refresh token")
    return token_row


@router.post("/signup", response_model=TokenResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if db.query(User).filter(User.email == payload.email).first() is not None:
        raise HTTPException(status_code=409, detail="email already registered")

    # 관리자는 여기로 못 만든다. role은 항상 student로 시작한다.
    user = User(email=payload.email, password_hash=hash_password(payload.password), role=UserRole.STUDENT.value)
    db.add(user)
    db.flush()  # refresh token의 user_id로 쓰려면 먼저 id가 있어야 한다

    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == payload.email).first()
    # 이메일이 없는 경우와 비밀번호가 틀린 경우를 구분하지 않는다. 가입 여부를 노출하지 않으려는 것.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid email or password")

    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    token_row = _get_valid_refresh_token_row(db, payload.refresh_token)
    user = db.get(User, token_row.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid refresh token")

    # 한 번 쓴 refresh token은 재사용 못 하게 바로 무효화한다 (rotation)
    token_row.revoked_at = datetime.now(timezone.utc)
    tokens = _issue_tokens(db, user)
    db.commit()
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: RefreshRequest, db: Session = Depends(get_db)) -> None:
    # 로그아웃은 멱등하게: 이미 무효한 토큰을 보내도 조용히 끝낸다.
    try:
        token_row = _get_valid_refresh_token_row(db, payload.refresh_token)
    except HTTPException:
        return
    token_row.revoked_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/me", response_model=UserResponse)
def read_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        created_at=current_user.created_at,
    )
