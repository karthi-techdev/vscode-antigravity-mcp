import argparse
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.resolve()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from server.auth import generate_user_token


def main():
    parser = argparse.ArgumentParser(description="Generate pairing token for an Antigravity MCP user")
    parser.add_argument("user_id", help="Unique identifier or username for the user (e.g. alice, dev_john)")
    args = parser.parse_args()

    token = generate_user_token(args.user_id)
    print("\n" + "=" * 50)
    print(f"[+] Generated credentials for user: {args.user_id}")
    print(f"[+] Auth Token: {token}")
    print("=" * 50)
    print("\n1. For your server environment (.env or Vercel Environment Variables):")
    print(f'   AUTH_TOKENS="{token}:{args.user_id}"')
    print("\n2. To run the local bridge on this user\'s machine:")
    print(f'   python -m client.agent --key "{token}" --server "https://your-domain.vercel.app"')
    print("\n3. In ChatGPT / Gemini Web MCP configuration:")
    print(f'   URL: https://your-domain.vercel.app/mcp?token={token}')
    print(f'   Header: Authorization: Bearer {token}\n')


if __name__ == "__main__":
    main()
