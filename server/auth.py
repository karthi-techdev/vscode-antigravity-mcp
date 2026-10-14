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


def verify_token(token: str) -> Optional[str]:
    """Verify if token exists and return associated user_id."""
    return DYNAMIC_TOKENS.get(token)


async def get_token_from_request(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
) -> str:
    """
    Extract token from:
    1. HTTP Authorization Bearer header
    2. URL query parameters ('token' or 'api_key')
    """
    # 1. Bearer header
    if auth_header and auth_header.credentials:
        return auth_header.credentials.strip()

    # 2. Query param (for web clients like SSE where headers can't be easily set)
    query_token = request.query_params.get("token") or request.query_params.get("api_key")
    if query_token:
        return query_token.strip()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication credentials. Provide 'Authorization: Bearer <token>' or query param '?token=<token>'."
    )


async def get_current_user(
    request: Request,
    auth_header: Optional[HTTPAuthorizationCredentials] = Security(security_bearer)
) -> str:
    """FastAPI dependency to authenticate requests and return the user_id."""
    token = await get_token_from_request(request, auth_header)
    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token."
        )
    return user_id


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
