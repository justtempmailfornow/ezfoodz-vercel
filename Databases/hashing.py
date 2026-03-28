import bcrypt


def hash_password(password: str) -> str:
    """Hash a password using bcrypt directly (no passlib)."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=4)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False
