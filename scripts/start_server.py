import sys
from pathlib import Path
import uvicorn

# Ensure project root is in sys.path
root_dir = Path(__file__).parent.parent.resolve()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from server.config import PORT, HOST, DEBUG

if __name__ == "__main__":
    print(f"Starting Antigravity MCP Server on {HOST}:{PORT} (debug={DEBUG})...")
    uvicorn.run("server.app:app", host=HOST, port=PORT, reload=DEBUG)
