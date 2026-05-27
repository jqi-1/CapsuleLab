from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False

    model_config = {"env_prefix": "CAPSULELAB_"}


settings = Settings()
