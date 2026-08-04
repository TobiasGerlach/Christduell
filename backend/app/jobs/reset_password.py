"""Set a player's password by hand. Run with `make reset-password email=...`.

There is no self-service "forgot password" flow yet (it needs an email
provider), so this is the support path for a small invited beta: the person
asks the organiser, the organiser runs this and tells them the new password,
they log in and change it in the app.
"""

import argparse
import secrets
import sys

from sqlmodel import Session, select

from app.core.security import hash_password
from app.db.session import engine, init_db
from app.models.domain import Player


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument(
        "--password",
        default=None,
        help="New password; a random one is generated (and printed) if omitted.",
    )
    args = parser.parse_args()

    init_db()
    with Session(engine) as session:
        player = session.exec(
            select(Player).where(Player.email == args.email.strip().lower())
        ).first()
        if player is None or player.deleted_at is not None:
            print(f"No active account for {args.email}", file=sys.stderr)
            return 1

        new_password = args.password or secrets.token_urlsafe(9)
        player.password_hash = hash_password(new_password)
        session.add(player)
        session.commit()

    print(f"Password for {player.email} reset.")
    if not args.password:
        print(f"Temporary password: {new_password}")
    print("Ask them to change it in the app under Profil.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
