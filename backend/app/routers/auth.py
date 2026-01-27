"""
Authentication endpoints: signup, login, profile.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from core.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from core.database.crud import (
    create_user,
    get_user_by_email,
    get_user_by_id,
)
from core.database.models import User
from core.database.session import get_db
from core.database.crud import create_audit_log

router = APIRouter(prefix="/auth", tags=["Authentication"])


# Request/Response models
class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class SignupResponse(BaseModel):
    user_id: str
    email: str
    name: Optional[str]
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    name: Optional[str]


class UserProfile(BaseModel):
    id: str
    email: str
    name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: str

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignupRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new user account.
    """
    # Check if user already exists
    existing = await get_user_by_email(db, request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Validate password
    if len(request.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters"
        )
    
    # Check password byte length (bcrypt limit is 72 bytes)
    password_bytes = request.password.encode('utf-8')
    if len(password_bytes) > 72:
        # Password will be automatically truncated to 72 bytes
        # This is handled in get_password_hash()
        # We accept it but the user should be aware
        pass
    
    # Create user
    try:
        password_hash = get_password_hash(request.password)
    except Exception as e:
        # Handle password hashing errors (e.g., bcrypt 72-byte limit)
        error_msg = str(e)
        if "72 bytes" in error_msg.lower() or "truncate" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password is too long. Please use a password with 72 characters or less."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to hash password: {error_msg}"
        )
    
    user = await create_user(
        db=db,
        email=request.email,
        password_hash=password_hash,
        name=request.name
    )
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user.id, "email": user.email}
    )
    
    # Log signup
    await create_audit_log(
        db=db,
        user_id=user.id,
        action="signup",
        resource=f"user:{user.id}",
        details={"email": user.email}
    )
    
    return SignupResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        access_token=access_token,
        token_type="bearer"
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Login with email and password. Returns JWT access token.
    """
    # Get user
    user = await get_user_by_email(db, request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user.id, "email": user.email}
    )
    
    # Log login
    await create_audit_log(
        db=db,
        user_id=user.id,
        action="login",
        resource=f"user:{user.id}",
        details={"email": user.email}
    )
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        email=user.email,
        name=user.name
    )


@router.get("/me", response_model=UserProfile)
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's profile.
    Requires authentication.
    """
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at.isoformat()
    )


@router.put("/me", response_model=UserProfile)
async def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update current user's profile.
    Requires authentication.
    """
    if request.name is not None:
        current_user.name = request.name
    
    await db.commit()
    await db.refresh(current_user)
    
    # Log update
    await create_audit_log(
        db=db,
        user_id=current_user.id,
        action="update_profile",
        resource=f"user:{current_user.id}",
        details={"name": request.name}
    )
    
    return UserProfile(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at.isoformat()
    )
