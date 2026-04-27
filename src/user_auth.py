from dotenv import load_dotenv
import os
import streamlit as st
import bcrypt
from src.logger import logger
from src.database import (
    get_user,
    insert_user,
    update_password,
    get_setting,
)

# loads variables from .env into environment
load_dotenv()

admin_user = os.getenv("ADMIN_USER")
admin_password = os.getenv("ADMIN_PASSWORD")


class UserAuthService:
    """
    Service class responsible for user authentication and authorization.

    Provides functionality for:
        - User registration
        - User login verification
        - Password management
        - Admin initialization
        - Role checking
        - System configuration checks
    """

    def __init__(self):
        """
        Initializes the database connection and ensures schema setup.
        """
        self._add_admin()

    def _add_admin(self):
        """
        Creates the default admin user if it does not already exist.
        """
        if not get_user(admin_user):
            insert_user(
                admin_user,
                self._hash(admin_password),
                "admin.abhishek@spa.com",
                is_admin=1,
            )
            logger.info("Admin account Added.")

    @staticmethod
    def _hash(password: str) -> str:
        """
        Hashes a plain text password using bcrypt.

        Args:
            - password(str): Raw password string
        Returns:
            - str: Hashed password
        """
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    @staticmethod
    def _verify(password: str, hashed: str) -> bool:
        """
        Verifies a plain text password against a hashed password.

        Args:
            - password(str): Plain text password
            - hashed(str): Stored hashed password
        Returns:
            - bool: True if password matches, False otherwise
        """
        return bcrypt.checkpw(password.encode(), hashed.encode())

    def register_user(self, username: str, password: str, email: str) -> bool:
        """
        Registers a new user in the system.

        Args:
            - username(str): Desired username
            - password(str): Raw password
            - email(str): User email address
        Returns:
            - bool: True if registration succeeds, False otherwise
        """
        if not username or not password:
            return False
        if username.lower() == admin_user.lower():
            return False

        new_user = insert_user(username.strip(), self._hash(password), email.strip())
        logger.info(
            f"Register '{username}': {'Done' if new_user else 'failed (exists)'}"
        )
        return new_user

    def login_user(self, username: str, password: str) -> bool:
        """
        Authenticates a user using username and password.

        Args:
            - username(str): Username.
            - password(str): Plain text password
        Returns:
            - bool: True if authentication succeeds, False otherwise
        """
        row = get_user(username.strip())
        if not row:
            logger.warning(f"Login failed (not found): {username}")
            return False
        user = self._verify(password, row["password_hash"])
        logger.info(f"Login '{username}': {'Done' if user else 'wrong password'}")
        return user

    def change_password(
        self, username: str, current_password: str, new_password: str
    ) -> bool:
        """
        Changes a user's password after verifying current credentials.

        Args:
            - username(str): Username
            - current_password(str): Current password
            - new_password(str): New password
        Returns:
            - bool: True if password update succeeds, False otherwise
        """
        if not self.login_user(username, current_password):
            return False
        update_password(username, self._hash(new_password))
        logger.info(f"Password changed: {username}")
        return True

    @staticmethod
    def registration_allowed() -> bool:
        """
        Checks whether new user registration is allowed by system settings.

        Returns:
            - bool: True if registration is enabled, False otherwise
        """
        return get_setting("allow_registration", "1") == "1"

    @staticmethod
    def is_admin(username: str) -> bool:
        """
        Checks whether a given user has admin privileges.

        Args:
            - username(str): Username to check
        Returns:
            - bool: True if user is admin, False otherwise
        """
        row = get_user(username)
        return bool(row and row["is_admin"])


@st.cache_resource(show_spinner=False)
def get_auth_service() -> UserAuthService:
    return UserAuthService()
