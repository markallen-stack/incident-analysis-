"""
Authentication and authorization utilities.
JWT token generation, validation, and password hashing.
"""

from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from pwdlib import PasswordHash
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.crud import get_user_by_email, get_user_by_id
from core.database.session import get_db

# Password hashing (pwdlib, Argon2id by default via recommended())
password_hasher = PasswordHash.recommended()

# JWT settings
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production-use-env-var")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 7 days default

# HTTP Bearer token
security = HTTPBearer()





def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.
    Uses pwdlib (Argon2id by default via recommended()) and enforces ASCII-only passwords.
    """
    print(f"Verifying password: {plain_password} against hash: {hashed_password}")

    try:
        return password_hasher.verify(plain_password, hashed_password)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """
    Hash a password using pwdlib.
    """
    return password_hasher.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
):
    """
    FastAPI dependency to get the current authenticated user.
    Usage:
        @app.get("/profile")
        async def get_profile(current_user: User = Depends(get_current_user)):
            ...
    """
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: AsyncSession = Depends(get_db)
):
    """
    Optional authentication - returns user if token is valid, None otherwise.
    Useful for endpoints that work with or without authentication.
    """
    if credentials is None:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except HTTPException:
        return None
