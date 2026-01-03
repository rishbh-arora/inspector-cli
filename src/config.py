import logging
from pathlib import Path
from envparse import Env
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def load_env():
    schema = Env(
        DB_HOST=str,
        DB_PORT=int,
        DB_USER=str,
        DB_PASSWORD=str,
        DB_NAME=str,        
        OPENAI_API_KEY=str,
        REDIS_HOST=str,
        REDIS_PORT=int,
        REDIS_DB=int,
    )
    schema.read_envfile(".env")
    return schema

TEMP_DIR = "./temp"
IMAGES_TEMP_DIR = TEMP_DIR + "/images"

Path(IMAGES_TEMP_DIR).mkdir(parents=True, exist_ok=True)
print(f"Directories verified: {TEMP_DIR} and {IMAGES_TEMP_DIR}")


env = load_env()
DB_HOST: str = env.str("DB_HOST", default="localhost")
DB_PORT: int = env.int("DB_PORT", default=5432)
DB_USER: str = env.str("DB_USER", default="user")
DB_NAME: str = env.str("DB_NAME", default="inspector")
DB_PASSWORD: str = env.str("DB_PASSWORD", default="password")
DB_URL: str = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
OPENAI_API_KEY: str = env.str("OPENAI_API_KEY")
REDIS_HOST: str = env.str("REDIS_HOST", default="localhost")
REDIS_PORT: int = env.int("REDIS_PORT", default=6379)
REDIS_DB: int = env.int("REDIS_DB", default=0)
INCLUDE_IMAGE_ANALYSIS: bool = env.bool("INCLUDE_IMAGE_ANALYSIS", default=False)