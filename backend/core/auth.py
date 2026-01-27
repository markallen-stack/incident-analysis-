"""
Authentication and authorization utilities.
JWT token generation, validation, and password hashing.
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.crud import get_user_by_email, get_user_by_id
from core.database.session import get_db

# Password hashing
# Configure bcrypt - newer versions of python-bcrypt raise errors for >72 bytes
# We handle truncation manually in get_password_hash() before passing to passlib
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
    Handles bcrypt's 72-byte limit by truncating if necessary.
    Uses the same truncation logic as get_password_hash().
    """
    if not plain_password:
        return False
    
    # Apply same truncation as in get_password_hash()
    # This ensures verification works for passwords that were truncated during hashing
    password_bytes = plain_password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
        plain_password = password_bytes.decode('utf-8', errors='ignore')
        # Verify after decode
        verify_bytes = plain_password.encode('utf-8')
        if len(verify_bytes) > 72:
            plain_password = verify_bytes[:72].decode('utf-8', errors='ignore')
    
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password.
    Bcrypt has a 72-byte limit, so we truncate longer passwords.
    
    The underlying python-bcrypt library raises ValueError for passwords > 72 bytes,
    so we must truncate before hashing.
    """
    if not password:
        raise ValueError("Password cannot be empty")
    
    # Bcrypt can only handle passwords up to 72 bytes (not characters!)
    # Convert to bytes to check actual byte length
    password_bytes = password.encode('utf-8')
    
    # Truncate to 72 bytes if necessary
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
        # Convert back to string
        password = password_bytes.decode('utf-8', errors='ignore')
        # Re-encode to verify it's still <= 72 bytes
        # (decode might create a string that encodes to more bytes in edge cases)
        verify_bytes = password.encode('utf-8')
        if len(verify_bytes) > 72:
            # If still too long, truncate the bytes again
            password = verify_bytes[:72].decode('utf-8', errors='ignore')
    
    # Final check: password must encode to <= 72 bytes
    final_byte_check = password.encode('utf-8')
    if len(final_byte_check) > 72:
        # This should never happen, but if it does, force truncation one more time
        password = final_byte_check[:72].decode('utf-8', errors='ignore')
    
    # Hash the password (guaranteed to be <= 72 bytes when encoded)
    # The underlying bcrypt library will receive a password that's already truncated
    return pwd_context.hash(password)


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
