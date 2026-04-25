import jwt
import os
from dotenv import load_dotenv
from src.config.config import ALGORITHM, TOKEN_DAYS
from datetime import datetime, timedelta, timezone

load_dotenv()

SPA_SECRET_KEY = os.environ.get("SPA_SECRET_KEY")


def create_token(username: str) -> str:
    payload = {
        "sub": username, 
        # Expiration time
        "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS),
        # Issued at
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SPA_SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str | None) -> str | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, SPA_SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
