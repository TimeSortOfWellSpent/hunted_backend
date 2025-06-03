from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    aws_access_key_id: str
    aws_secret_access_key: str
    bucket_name: str
    jwt_secret_key: str
    algorithm: str
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()