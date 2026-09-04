"""Ferramentas locais do administrador; senha nunca é ecoada."""

from getpass import getpass

from argon2 import PasswordHasher


def main() -> None:
    password = getpass("Admin password: ")
    confirmation = getpass("Confirm password: ")
    if password != confirmation or len(password) < 12:
        raise SystemExit("Passwords must match and contain at least 12 characters")
    print(PasswordHasher().hash(password))


if __name__ == "__main__":
    main()
