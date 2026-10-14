import os
from typing import Dict
from dotenv import load_dotenv

load_dotenv()

PORT = int(os.getenv("PORT", "8000"))
HOST = os.getenv("HOST", "0.0.0.0")
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "t")

ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "default-admin-secret-change-me")

# Default token-to-user mapping from env: "tok1:user1,tok2:user2"
AUTH_TOKENS_RAW = os.getenv("AUTH_TOKENS", "")


def parse_auth_tokens(raw: str) -> Dict[str, str]:
    tokens: Dict[str, str] = {}
    if not raw.strip():
        return tokens
    for item in raw.split(","):
        item = item.strip()
        if ":" in item:
            token, user_id = item.split(":", 1)
            tokens[token.strip()] = user_id.strip()
    return tokens


STATIC_TOKENS = parse_auth_tokens(AUTH_TOKENS_RAW)

# Relay timeout in seconds (how long MCP tool call waits for local IDE client response)
RELAY_TASK_TIMEOUT = int(os.getenv("RELAY_TASK_TIMEOUT", "30"))

# Upstash Redis / Vercel KV settings (for multi-instance serverless Vercel persistence)
UPSTASH_REDIS_REST_URL = os.getenv("UPSTASH_REDIS_REST_URL") or os.getenv("KV_REST_API_URL", "")
UPSTASH_REDIS_REST_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN") or os.getenv("KV_REST_API_TOKEN", "")

