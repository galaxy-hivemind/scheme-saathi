"""
Application configuration loaded from environment variables with production security validation.
"""
from typing import List, Set, Union
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_SECRET_PATTERNS: Set[str] = {
    "change-me",
    "your-secret",
    "placeholder",
    "password",
    "admin",
    "default",
    "test-secret",
    "dummy-secret",
    "scheme-saathi-jwt-secret",
    "scheme-saathi-super-secret",
}

ALLOWED_JWT_ALGORITHMS: Set[str] = {"HS256", "HS384", "HS512"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_NAME: str = "Scheme Saathi API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    SECRET_KEY: str = ""

    # ── Authentication & JWT ──────────────────────────────────────────────────
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # ── Server ────────────────────────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/scheme_saathi"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Supabase ──────────────────────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # ── Gemini ────────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-pro"

    # ── CORS ──────────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: Union[str, List[str]] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]

    # ── File storage ──────────────────────────────────────────────────────────
    STORAGE_BUCKET: str = "user-documents"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_FILE_TYPES: Union[str, List[str]] = ["pdf", "jpg", "jpeg", "png"]

    # ── Rate limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    AGENT_RATE_LIMIT_PER_MINUTE: int = 20

    # ── Background jobs ───────────────────────────────────────────────────────
    JOBS_ENABLED: bool = True

    @field_validator("ALLOWED_ORIGINS", "ALLOWED_FILE_TYPES", mode="after")
    @classmethod
    def parse_comma_separated_list(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @model_validator(mode="after")
    def validate_production_and_security(self) -> "Settings":
        """
        Enforce strict validation for JWT secrets, algorithms, and debug mode.
        Fails fast if production configuration is unsafe.
        """
        # Validate algorithm restriction
        if self.JWT_ALGORITHM not in ALLOWED_JWT_ALGORITHMS:
            raise ValueError(
                f"Unsupported JWT_ALGORITHM '{self.JWT_ALGORITHM}'. "
                f"Must be one of {sorted(ALLOWED_JWT_ALGORITHMS)}."
            )

        is_production = self.APP_ENV.lower() in ("production", "prod")

        if is_production:
            # 1. DEBUG must be false in production
            if self.DEBUG:
                raise ValueError("DEBUG mode must be disabled (DEBUG=false) in production environment.")

            # 2. JWT_SECRET must be strong, non-empty, and non-placeholder
            if not self.JWT_SECRET:
                raise ValueError("JWT_SECRET must be explicitly configured in production.")

            if len(self.JWT_SECRET) < 32:
                raise ValueError(
                    f"JWT_SECRET must be at least 32 characters long in production (got {len(self.JWT_SECRET)})."
                )

            secret_lower = self.JWT_SECRET.lower()
            for pattern in INSECURE_SECRET_PATTERNS:
                if pattern in secret_lower:
                    raise ValueError(
                        f"JWT_SECRET cannot use insecure placeholder containing '{pattern}' in production."
                    )

            # 3. SECRET_KEY must be strong and non-empty
            if not self.SECRET_KEY:
                raise ValueError("SECRET_KEY must be explicitly configured in production.")

            if len(self.SECRET_KEY) < 32:
                raise ValueError(
                    f"SECRET_KEY must be at least 32 characters long in production (got {len(self.SECRET_KEY)})."
                )

            key_lower = self.SECRET_KEY.lower()
            for pattern in INSECURE_SECRET_PATTERNS:
                if pattern in key_lower:
                    raise ValueError(
                        f"SECRET_KEY cannot use insecure placeholder containing '{pattern}' in production."
                    )
        else:
            # Safe fallbacks for development/testing so setup is straightforward
            if not self.JWT_SECRET:
                self.JWT_SECRET = "dev-scheme-saathi-jwt-secret-key-32-chars-long"
            if not self.SECRET_KEY:
                self.SECRET_KEY = "dev-scheme-saathi-app-secret-key-32-chars-long"

        return self


settings = Settings()
