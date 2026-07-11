from pathlib import Path
import os

from dotenv import load_dotenv

# 应该只放配置，不放业务逻辑。
# 定义项目里的“路径配置”和“默认要加载哪些知识文件”。

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
load_dotenv(PROJECT_DIR / ".env")

PROJECT_DISPLAY_NAME = "AI Clothing Shopping Assistant System"
PROJECT_API_TITLE = f"{PROJECT_DISPLAY_NAME} API"
DATA_DIR = BASE_DIR / "data"
PRODUCT_CATALOG_PATH = DATA_DIR / "product_catalog.json"
CHAT_HISTORY_DIR = BASE_DIR / "chat_history"
VECTOR_DB_DIR = BASE_DIR / "chroma_db"
FILE_HASH_RECORD_PATH = BASE_DIR / "knowledge_file_hashes.json"
VECTOR_COLLECTION_NAME = "clothing_knowledge_base"
EMBEDDING_MODEL_NAME = os.getenv("JINA_EMBEDDING_MODEL", "jina-embeddings-v4")
JINA_EMBEDDING_URL = "https://api.jina.ai/v1/embeddings"
JINA_EMBEDDING_TIMEOUT_SECONDS = 30
CHAT_MODEL_NAME = os.getenv("KIMI_CHAT_MODEL", "kimi-k2.5")
KIMI_BASE_URL = "https://api.moonshot.cn/v1"
CHAT_TEMPERATURE = 0.1
ENABLE_LLM_PREFERENCE_MAPPER = os.getenv("ENABLE_LLM_PREFERENCE_MAPPER", "false").lower() == "true"
DEFAULT_TOP_K = 4
RAG_TOP_K = 3
RAG_DISTANCE_THRESHOLD = 0.7
SIZE_KNOWLEDGE_FILE = "尺码推荐.txt"
COLOR_KNOWLEDGE_FILE = "颜色选择.txt"
CARE_KNOWLEDGE_FILE = "洗涤养护.txt"
SCENE_KNOWLEDGE_FILE = "场景穿搭.txt"
MATERIAL_KNOWLEDGE_FILE = "材质知识.txt"
FIT_KNOWLEDGE_FILE = "版型知识.txt"
KNOWLEDGE_FILE_DOMAINS = {
    SIZE_KNOWLEDGE_FILE: "size",
    COLOR_KNOWLEDGE_FILE: "color",
    CARE_KNOWLEDGE_FILE: "care",
    SCENE_KNOWLEDGE_FILE: "scene",
    MATERIAL_KNOWLEDGE_FILE: "material",
    FIT_KNOWLEDGE_FILE: "fit",
}
DEFAULT_TEST_QUERY = (
    "我身高168，体重65kg，想买一件日常穿的T恤，"
    "推荐什么尺码和颜色？洗的时候需要注意什么？"
)

KNOWLEDGE_FILES = [
    "尺码推荐.txt",
    "洗涤养护.txt",
    "颜色选择.txt",
    "场景穿搭.txt",
    "材质知识.txt",
    "版型知识.txt",
]
