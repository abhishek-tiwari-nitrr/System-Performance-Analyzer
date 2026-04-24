from dotenv import load_dotenv
import os
import bcrypt
from src.logger.logger import Logger
from src.database.database import (
    get_user,
    insert_user,
    update_password,
    init_db,
    get_setting,
)

logger = Logger().setup_logs()

# loads variables from .env into environment
load_dotenv()

admin_user = os.getenv("ADMIN_USER")
admin_password = os.getenv("ADMIN_PASSWORD")


class UserAuthService:
    def __init__(self):
        init_db()

    def _add_admin(self):
        if not get_user(admin_user):
            insert_user(
                admin_user,
                self._hash(admin_password),
                "admin.abhishek@spa.com",
                is_admin=1,
            )
            logger.info("Admin account Added.")

    def _hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def _verify(self, password: str, hashed: str) -> bool:
        return bcrypt.checkpw(password.encode(), hashed.encode())

    def register_user(self, username: str, password: str, email: str) -> bool:
        if not username or not password:
            return False
        if username.lower() == admin_user.lower():
            return False

        new_user = insert_user(username.strip(), self._hash(password), email.strip())
        logger.info(f"Register '{username}': {'ok' if new_user else 'failed (exists)'}")
        return new_user

    def login_user(self, username: str, password: str) -> bool:
        row = get_user(username.strip())
        if not row:
            logger.warning(f"Login failed (not found): {username}")
            return False
        user = self._verify(password, row["password_hash"])
        logger.info(f"Login '{username}': {'ok' if user else 'wrong password'}")
        return user

    def change_password(
        self, username: str, current_password: str, new_password: str
    ) -> bool:
        if not self.login_user(username, current_password):
            return False
        update_password(username, self._hash(new_password))
        logger.info(f"Password changed: {username}")
        return True

    def registration_allowed(self) -> bool:
        return get_setting("allow_registration", "1") == "1"

    def is_admin(self, username: str) -> bool:
        row = get_user(username)
        return bool(row and row["is_admin"])
