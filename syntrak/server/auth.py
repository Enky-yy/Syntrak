import os
import secrets
import time
from typing import Any, Dict, Optional
import httpx
import jwt
from fastapi import Header, HTTPException, Request


def _get_jwt_secret() -> str:
    """Retrieve configured JWT secret, or generate a cryptographically secure ephemeral key."""
    secret = (
        os.getenv("SYNTRAK_JWT_SECRET")
        or os.getenv("JWT_SECRET_KEY")
        or os.getenv("JWT_SECRET")
    )
    if secret and secret.strip():
        return secret.strip()
    if os.getenv("PRODUCTION", "").lower() in ("true", "1", "yes"):
        raise RuntimeError("CRITICAL SECURITY ERROR: SYNTRAK_JWT_SECRET or JWT_SECRET_KEY must be set in production mode.")
    if not hasattr(_get_jwt_secret, "_cached_dev_secret"):
        _get_jwt_secret._cached_dev_secret = secrets.token_urlsafe(32)
    return _get_jwt_secret._cached_dev_secret


JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = 86400 * 30  # 30 days
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GUEST_USER_ID = "guest-developer"


async def verify_google_credential(credential: str) -> Dict[str, Any]:
    """Cryptographically verify a Google ID token via Google's tokeninfo service."""
    if not credential or not credential.strip():
        raise HTTPException(status_code=401, detail="Missing Google ID token credential.")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": credential.strip()}
            )
            if resp.status_code == 200:
                payload = resp.json()
                # Verify audience if GOOGLE_CLIENT_ID is configured
                if GOOGLE_CLIENT_ID and payload.get("aud") != GOOGLE_CLIENT_ID:
                    raise HTTPException(status_code=401, detail="Google token client ID mismatch.")

                # Ensure issuer is genuine Google
                iss = payload.get("iss", "")
                if iss not in ("accounts.google.com", "https://accounts.google.com"):
                    raise HTTPException(status_code=401, detail="Invalid Google token issuer.")

                return {
                    "id": f"google_{payload['sub']}",
                    "email": payload.get("email", ""),
                    "name": payload.get("name", "Google User"),
                    "picture": payload.get("picture", "")
                }
            else:
                err_detail = "Failed to verify Google token with identity provider."
                try:
                    err_json = resp.json()
                    if "error_description" in err_json:
                        err_detail = f"Google verification error: {err_json['error_description']}"
                except Exception:
                    pass
                raise HTTPException(status_code=401, detail=err_detail)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Google authentication service error: {str(e)}")


def create_jwt_token(user_data: Dict[str, Any]) -> str:
    """Create a signed JWT session token."""
    now = int(time.time())
    payload = {
        "sub": user_data["id"],
        "email": user_data.get("email", ""),
        "name": user_data.get("name", ""),
        "picture": user_data.get("picture", ""),
        "iat": now,
        "exp": now + JWT_EXPIRATION_SECONDS
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT session token."""
    try:
        payload = jwt.decode(token, _get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return {
            "id": payload["sub"],
            "email": payload.get("email", ""),
            "name": payload.get("name", ""),
            "picture": payload.get("picture", "")
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session token.")


async def get_current_user(
    request: Request,
    authorization: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """FastAPI Dependency: Extract authenticated user from Authorization Bearer or Cookie, falling back to Guest."""
    token = None

    # Check Authorization header
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split("Bearer ", 1)[1].strip()

    # Check cookie fallback
    if not token and "syntrak_token" in request.cookies:
        token = request.cookies.get("syntrak_token")

    if token:
        try:
            return decode_jwt_token(token)
        except HTTPException:
            pass

    # Default to guest developer session
    return {
        "id": GUEST_USER_ID,
        "email": "guest@local.user",
        "name": "Guest Developer",
        "picture": ""
    }
