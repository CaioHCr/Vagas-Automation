import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    CARGOS_ALVO: str
    KEYWORDS_EXECUTIVAS: str
    LOCALIZACAO_FILTRO: str
    EMAIL_USUARIO: str = ""
    EMAIL_SENHA_APP: str = ""

    class Config:
        env_file = ".env"

settings = Settings()
