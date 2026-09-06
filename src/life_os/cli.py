from __future__ import annotations

import argparse
import html
import json
import os
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import uvicorn
from dotenv import load_dotenv

from life_os.agent_catalog import list_agents


def _connect_oura(timeout: int, open_browser: bool) -> None:
    from life_os.connectors.oura import OuraConnector

    connector = OuraConnector.from_environment()
    redirect = urlsplit(connector.redirect_uri)
    if redirect.scheme != "http" or redirect.hostname not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("OURA_REDIRECT_URI must use local HTTP for this setup flow")
    if not redirect.port:
        raise RuntimeError("OURA_REDIRECT_URI must include a local callback port")

    authorization = connector.begin_authorization()
    result: dict[str, object] = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            request = urlsplit(self.path)
            if request.path != redirect.path:
                self.send_error(404)
                return
            query = parse_qs(request.query)
            returned_state = query.get("state", [""])[0]
            error = query.get("error", [""])[0]
            code = query.get("code", [""])[0]
            try:
                if error:
                    raise RuntimeError(f"Oura authorization was declined: {error}")
                if not secrets.compare_digest(returned_state, authorization.state):
                    raise RuntimeError("Oura authorization state did not match")
                if not code:
                    raise RuntimeError("Oura did not return an authorization code")
                result["status"] = connector.exchange_code(code)
                heading = "Oura connected"
                message = "You can close this tab and return to Life OS."
                status_code = 200
            except Exception as error_value:  # pragma: no cover - browser boundary
                result["error"] = str(error_value)
                heading = "Oura connection failed"
                message = "Return to Life OS and try the connection again."
                status_code = 400
            body = (
                "<!doctype html><html><meta name='viewport' content='width=device-width'>"
                "<body style='font-family:system-ui;padding:3rem;max-width:36rem;margin:auto'>"
                f"<h1>{html.escape(heading)}</h1><p>{html.escape(message)}</p>"
                "</body></html>"
            ).encode()
            self.send_response(status_code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = HTTPServer((redirect.hostname, redirect.port), CallbackHandler)
    server.timeout = timeout
    print("Open this private Oura authorization URL:")
    print(authorization.url)
    if open_browser:
        webbrowser.open(authorization.url)
    server.handle_request()
    server.server_close()
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    if "status" not in result:
        raise TimeoutError("Oura authorization timed out")
    print(json.dumps(result["status"], indent=2))


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="life-os")
    subcommands = parser.add_subparsers(dest="command", required=True)

    subcommands.add_parser("agents", help="List the public agent catalog")
    serve = subcommands.add_parser("serve", help="Run the Life OS API")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    calendar_connect = subcommands.add_parser(
        "calendar-connect", help="Authorize and verify a private Google Calendar connection"
    )
    calendar_connect.add_argument("--credentials", type=Path, required=True)
    calendar_connect.add_argument("--token", type=Path, required=True)
    gmail_connect = subcommands.add_parser(
        "gmail-connect",
        help="Authorize one household Gmail account with read-only access",
    )
    gmail_connect.add_argument("--credentials", type=Path, required=True)
    gmail_connect.add_argument("--account-id", required=True)
    gmail_connect.add_argument("--member-name", required=True)
    gmail_connect.add_argument("--no-browser", action="store_true")
    gmail_connect.add_argument(
        "--accounts-dir", type=Path, default=Path("private/gmail-accounts")
    )
    gmail_connect.add_argument(
        "--registry", type=Path, default=Path("private/gmail-accounts.json")
    )
    oura_connect = subcommands.add_parser(
        "oura-connect", help="Authorize a private, least-privilege Oura connection"
    )
    oura_connect.add_argument("--timeout", type=int, default=300)
    oura_connect.add_argument("--no-browser", action="store_true")
    oura_sync = subcommands.add_parser(
        "oura-sync", help="Import recent Oura daily summaries into private progress data"
    )
    oura_sync.add_argument("--tenant", default="me")
    oura_sync.add_argument("--days", type=int, default=2)
    health_token = subcommands.add_parser(
        "apple-health-token",
        help="Create the private bearer token used by an Apple Health Shortcut",
    )
    health_token.add_argument(
        "--path",
        type=Path,
        default=Path("private/apple-health-ingest-token.txt"),
    )

    args = parser.parse_args()
    if args.command == "agents":
        print(json.dumps([agent.model_dump(mode="json") for agent in list_agents()], indent=2))
    elif args.command == "serve":
        uvicorn.run("life_os.api:app", host=args.host, port=args.port, reload=False)
    elif args.command == "calendar-connect":
        from life_os.connectors.google_calendar import (
            GoogleCalendarConnector,
            redact_token_file,
        )

        connector = GoogleCalendarConnector.authenticate(args.credentials, args.token)
        result = connector.verify()
        result["authorization"] = redact_token_file(args.token)
        print(json.dumps(result, indent=2))
    elif args.command == "gmail-connect":
        from life_os.connectors.google_gmail import (
            GoogleGmailConnector,
            register_gmail_account,
            safe_account_id,
        )

        account_id = safe_account_id(args.account_id)
        token_path = args.accounts_dir / f"{account_id}-token.json"
        connector = GoogleGmailConnector.authenticate(
            args.credentials, token_path, open_browser=not args.no_browser
        )
        profile = connector.profile()
        record = register_gmail_account(
            args.registry,
            account_id=account_id,
            email=profile["email"],
            member_name=args.member_name,
            token_path=token_path,
        )
        print(
            json.dumps(
                {
                    "connected": True,
                    "account_id": record["account_id"],
                    "email": record["email"],
                    "member_name": record["member_name"],
                    "scope": "gmail.readonly",
                },
                indent=2,
            )
        )
    elif args.command == "oura-connect":
        _connect_oura(args.timeout, not args.no_browser)
    elif args.command == "oura-sync":
        from life_os.connectors.oura import OuraConnector
        from life_os.oura_sync import sync_oura_daily
        from life_os.store import LifeOSStore

        if args.days < 1 or args.days > 31:
            raise ValueError("--days must be between 1 and 31")
        end_date = date.today()
        start_date = end_date - timedelta(days=args.days - 1)
        result = sync_oura_daily(
            LifeOSStore(os.getenv("LIFE_OS_DATABASE", "life_os.db")),
            OuraConnector.from_environment(),
            args.tenant,
            start_date,
            end_date,
        )
        print(json.dumps(result, indent=2))
    elif args.command == "apple-health-token":
        args.path.parent.mkdir(parents=True, exist_ok=True)
        if args.path.exists():
            print(f"Apple Health ingestion token already exists at {args.path}")
        else:
            args.path.write_text(secrets.token_urlsafe(36) + "\n")
            args.path.chmod(0o600)
            print(f"Created private Apple Health ingestion token at {args.path}")


if __name__ == "__main__":
    main()
