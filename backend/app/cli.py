"""Management CLI for household user provisioning.

The household is a fixed 2-user model with no open self-registration
endpoint, so accounts are created out-of-band:

    python -m app.cli create-user --username geir --display-name Geir

The command prompts for a password (hidden input) and enforces the same
MIN_PASSWORD_LENGTH policy as the API.
"""
from __future__ import annotations

import argparse
import getpass
import sys

from app.config import get_settings
from app.database import SessionLocal
from app.models import User
from app.security import PasswordPolicyError, hash_password, validate_password_policy


def create_user(username: str, display_name: str, password: str) -> None:
    settings = get_settings()
    try:
        validate_password_policy(password, settings.min_password_length)
    except PasswordPolicyError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).one_or_none()
        if existing is not None:
            print(f"Error: user '{username}' already exists.", file=sys.stderr)
            raise SystemExit(1)

        user = User(username=username, display_name=display_name, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        print(f"Created user '{username}' ({display_name}).")
    finally:
        db.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Life Hub management CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create-user", help="Provision a household user")
    create_parser.add_argument("--username", required=True)
    create_parser.add_argument("--display-name", required=True)

    args = parser.parse_args(argv)

    if args.command == "create-user":
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Error: passwords do not match.", file=sys.stderr)
            raise SystemExit(1)
        create_user(args.username, args.display_name, password)


if __name__ == "__main__":
    main()
