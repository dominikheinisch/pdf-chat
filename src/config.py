from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: SecretStr
    llm_model: str = "claude-haiku-5-5"
    demo_username: str
    demo_password: SecretStr
    database_url: str
