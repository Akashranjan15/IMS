import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

JWT_SECRET = os.getenv("IMS_JWT_SECRET", "change-me-super-secret")
JWT_ALGORITHM = os.getenv("IMS_JWT_ALGORITHM", "HS256")

bearer_scheme = HTTPBearer(auto_error=True)


def create_access_token(subject: str = "ims-operator", expires_minutes: int = 60 * 24) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=expires_minutes)).timestamp())}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def require_jwt(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired JWT") from exc
    return payload

