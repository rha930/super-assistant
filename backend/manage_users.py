#!/usr/bin/env python3
"""CLI utility to manage users for the Super Agent application."""

import argparse
import getpass
import sys

from config import AUTH_SECRET_KEY, AUTH_USERS_FILE
from services.auth_service import AuthService


def get_auth_service() -> AuthService:
    return AuthService(users_file=AUTH_USERS_FILE, secret_key=AUTH_SECRET_KEY or "unused")


def cmd_create(args: argparse.Namespace) -> None:
    service = get_auth_service()
    password = getpass.getpass("Password: ")
    if len(password) < 8:
        print("Error: password must be at least 8 characters", file=sys.stderr)
        sys.exit(1)
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Error: passwords do not match", file=sys.stderr)
        sys.exit(1)

    display_name = args.display_name or args.username
    user = service.create_user(args.username, password, display_name)
    if user is None:
        print(f'Error: user "{args.username}" already exists', file=sys.stderr)
        sys.exit(1)
    print(f'Created user: {user["username"]} (id={user["id"]})')


def cmd_list(_args: argparse.Namespace) -> None:
    service = get_auth_service()
    users = service.list_users()
    if not users:
        print("No users found.")
        return
    for u in users:
        print(f'  {u["username"]:20s}  {u.get("display_name", "")}  (id={u["id"]})')


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Super Agent users")
    sub = parser.add_subparsers(dest="command", required=True)

    create_p = sub.add_parser("create", help="Create a new user")
    create_p.add_argument("--username", required=True)
    create_p.add_argument("--display-name", default="")

    sub.add_parser("list", help="List all users")

    args = parser.parse_args()
    if args.command == "create":
        cmd_create(args)
    elif args.command == "list":
        cmd_list(args)


if __name__ == "__main__":
    main()
