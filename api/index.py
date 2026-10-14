"""
Vercel Serverless Entrypoint for Multi-Tenant MCP Gateway.
Exposes both `app` (for ASGI runtimes) and `handler` (for Mangum / AWS Lambda adapters).
"""
import sys
from pathlib import Path

# Add project root to sys.path so server and client modules can be resolved
root_dir = Path(__file__).parent.parent.resolve()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

try:
    from mangum import Mangum
    from server.app import app
    handler = Mangum(app)
except Exception:
    from server.app import app
    handler = app

__all__ = ["app", "handler"]
