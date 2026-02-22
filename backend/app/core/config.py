from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "NYC Traffic Intelligence"
    api_prefix: str = "/api"
    database_url: str = "sqlite:///./traffic.db"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "traffic-artifacts"
    jwt_secret: str = "dev-secret"
    jwt_algorithm: str = "HS256"
    upload_max_mb: int = 1024
    allowed_extensions: str = "mp4,mov,mkv"
    fps_sampled: int = 5
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
