import secrets
from typing import Optional, Dict
from fastapi import HTTPException, Security, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from server.config import STATIC_TOKENS, ADMIN_SECRET_KEY

# In-memory dynamic registry for token -> user_id mapping
# Can be populated at runtime via admin API or static configuration
DYNAMIC_TOKENS: Dict[str, str] = dict(STATIC_TOKENS)

# Security scheme for Swagger UI
security_bearer = HTTPBearer(auto_error=False)


def register_token(token: str, user_id: str) -> None:
    """Register or update a user token."""
    DYNAMIC_TOKENS[token] = user_id


def generate_user_token(user_id: str) -> str:
    """Generate a secure new token for a user."""
    token = f"antigravity_{secrets.token_urlsafe(24)}"
    DYNAMIC_TOKENS[token] = user_id
    return token


import hashlib

def verify_token(token: str) -> Optional[str]:
    """
    Verify token and return associated user_id.
    - If pre-configured in DYNAMIC_TOKENS, returns assigned username.
    - If dynamic key provided by any user (min 6 characters), automatically
      creates an isolated, collision-free user session.
    """
    if not token or len(token.strip()) < 6:
        return None

    token = token.strip()
    if token in DYNAMIC_TOKENS:
        return DYNAMIC_TOKENS[token]

    # Dynamically derive a stable, isolated user session from the secret key
    derived_user = f"user_{hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]}"
    DYNAMIC_TOKENS[token] = derived_user
    return derived_user


async def get_token_from_request(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
) -> Optional[str]:
    """
    Extract token from:
    1. HTTP Authorization Bearer header
    2. Custom headers ('x-api-key', 'api-key', 'x-auth-token')
    3. URL query parameters ('token' or 'api_key')
    """
    # 1. Bearer header
    if auth_header and auth_header.credentials:
        return auth_header.credentials.strip()

    auth = request.headers.get("Authorization") or request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    elif auth.strip():
        return auth.strip()

    # 2. Custom headers for Claude, webhooks, or custom clients
    for h in ("x-api-key", "api-key", "x-auth-token"):
        v = request.headers.get(h)
        if v and v.strip():
            return v.strip()

    # 3. Query param (for web clients like SSE where headers can't be easily set)
    query_token = request.query_params.get("token") or request.query_params.get("api_key")
    if query_token:
        return query_token.strip()

    return None


async def get_current_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
) -> str:
    """FastAPI dependency to authenticate requests and return the user_id."""
    token = await get_token_from_request(request, auth_header)
    if token:
        user_id = verify_token(token)
        if user_id:
            return user_id

    # 4. Fallback for Web Actions without custom headers:
    # Automatically route to the currently active local IDE bridge session for action/tool endpoints!
    path = request.url.path
    if path.startswith("/api/action/") or path.startswith("/api/tools/") or path.startswith("/mcp"):
        import time
        from server.relay import relay_manager
        now = time.time()
        active_users = [uid for uid, t in relay_manager.client_heartbeats.items() if (now - t) < 180.0]
        if active_users:
            return max(active_users, key=lambda u: relay_manager.client_heartbeats.get(u, 0))

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication credentials and no active local IDE companion detected. Start 'python bridge.py' or provide 'Authorization: Bearer <token>'."
    )


async def verify_admin_key(request: Request) -> bool:
    """Verify admin secret key for administrative actions."""
    auth_header = request.headers.get("X-Admin-Secret")
    query_secret = request.query_params.get("admin_secret")
    secret = auth_header or query_secret

    if not secret or secret != ADMIN_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing admin secret key."
        )
    return True
