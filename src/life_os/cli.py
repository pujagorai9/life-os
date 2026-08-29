from __future__ import annotations

import argparse
import json
import os

import uvicorn
from dotenv import load_dotenv

from life_os.agent_catalog import list_agents


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="life-os")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("agents", help="List the public agent catalog")
    serve = subcommands.add_parser("serve", help="Run the Life OS API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()
    if args.command == "agents":
        print(json.dumps([agent.model_dump(mode="json") for agent in list_agents()], indent=2))
    elif args.command == "serve":
        uvicorn.run("life_os.api:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
