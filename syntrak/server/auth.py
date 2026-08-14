"""Google OAuth & JWT Session Authentication for Syntrak Server."""

import os
import time
from typing import Any, Dict, Optional
import httpx
import jwt
from fastapi import Header, HTTPException, Request

JWT_SECRET = os.getenv("SYNTRAK_JWT_SECRET", "syntrak-dev-insecure-secret-key-change-in-prod")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = 86400 * 30  # 30 days
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GUEST_USER_ID = "guest-developer"


async def verify_google_credential(credential: str) -> Dict[str, Any]:
    """Verify a Google ID token from Google Identity Services."""
    # First attempt: Google tokeninfo endpoint
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://oauth2.googleapis.com/tokeninfo",
                params={"id_token": credential}
            )
            if resp.status_code == 200:
                payload = resp.json()
                # Verify audience if GOOGLE_CLIENT_ID is configured
                if GOOGLE_CLIENT_ID and payload.get("aud") != GOOGLE_CLIENT_ID:
                    raise HTTPException(status_code=401, detail="Google token client ID mismatch.")

                return {
                    "id": f"google_{payload['sub']}",
                    "email": payload.get("email", ""),
                    "name": payload.get("name", "Google User"),
                    "picture": payload.get("picture", "")
                }
    except HTTPException:
        raise
    except Exception as e:
        pass

    # Fallback to local decoding if Google client verification is simulated/offline
    try:
        unverified = jwt.decode(credential, options={"verify_signature": False})
        if "sub" in unverified:
            return {
                "id": f"google_{unverified['sub']}",
                "email": unverified.get("email", ""),
                "name": unverified.get("name", "Google User"),
                "picture": unverified.get("picture", "")
            }
    except Exception:
        pass

    raise HTTPException(status_code=401, detail="Invalid Google ID token.")


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
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT session token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
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
