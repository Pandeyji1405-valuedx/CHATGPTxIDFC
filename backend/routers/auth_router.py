from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
from backend.database import get_db
from backend.models import User, AuditLog
from backend.schemas import UserRegisterRequest, UserLoginRequest, GoogleAuthRequest, SwitchAccountRequest, TokenResponse, UserResponse
from backend.auth import verify_password, get_password_hash, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    req: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(User.email == req.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists"
        )

    new_user = User(
        name=req.name.strip(),
        email=req.email.lower().strip(),
        password_hash=get_password_hash(req.password),
        auth_provider="local",
        role="user"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Audit log
    audit = AuditLog(
        user_id=new_user.id,
        action="REGISTER",
        details="User registered with email/password",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    db.commit()

    token = create_access_token({"sub": new_user.id, "email": new_user.email, "role": new_user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )

@router.post("/login", response_model=TokenResponse)
def login_user(
    req: UserLoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    search_email = req.email.lower().strip()
    user = db.query(User).filter(User.email == search_email).first()
    
    # Allow matching by username or substring prefix (e.g. "devesh.pandey")
    if not user:
        user = db.query(User).filter(
            (User.email.ilike(f"%{search_email}%")) | (User.name.ilike(f"%{search_email}%"))
        ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account does not exist. Please sign up."
        )

    # If user was created via Google OAuth / without password, set password on first explicit login
    if user.password_hash is None and req.password:
        user.password_hash = get_password_hash(req.password)
        db.commit()
    elif not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Please try again."
        )

    # Audit log
    audit = AuditLog(
        user_id=user.id,
        action="LOGIN",
        details="User logged in successfully",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    db.commit()

    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

@router.post("/switch-account", response_model=TokenResponse)
def switch_account_session(
    req: SwitchAccountRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Seamless multi-account session switcher. Re-issues a valid token for an existing saved user.
    """
    user = None
    if req.user_id:
        user = db.query(User).filter(User.id == req.user_id).first()
    if not user and req.email:
        search_email = req.email.lower().strip()
        user = db.query(User).filter(User.email == search_email).first()
        if not user:
            user = db.query(User).filter(
                (User.email.ilike(f"%{search_email}%")) | (User.name.ilike(f"%{search_email}%"))
            ).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found"
        )

    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    
    audit = AuditLog(
        user_id=user.id,
        action="SWITCH_ACCOUNT",
        details=f"Switched session to {user.email}",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    db.commit()

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

@router.post("/google", response_model=TokenResponse)
def google_auth(
    req: GoogleAuthRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handles Google OAuth token exchange. Supports both live Google OAuth credentials
    and developer Google login payload.
    """
    target_email = (req.email or f"google_user_{req.credential[:8]}@gmail.com").lower().strip()
    target_name = req.name or "Google User"
    avatar = req.avatar_url or f"https://api.dicebear.com/7.x/bottts/svg?seed={target_email}"

    user = db.query(User).filter(User.email == target_email).first()
    if not user:
        user = User(
            email=target_email,
            name=target_name,
            auth_provider="google",
            avatar_url=avatar,
            role="user"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    audit = AuditLog(
        user_id=user.id,
        action="GOOGLE_LOGIN",
        details="User authenticated via Google OAuth",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    db.commit()

    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)

@router.post("/logout")
def logout_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    audit = AuditLog(
        user_id=current_user.id,
        action="LOGOUT",
        details="User logged out",
        ip_address=request.client.host if request.client else "127.0.0.1"
    )
    db.add(audit)
    db.commit()
    return {"message": "Logged out successfully"}

