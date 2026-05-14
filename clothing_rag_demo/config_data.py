from pathlib import Path

# 应该只放配置，不放业务逻辑。
# 定义项目里的“路径配置”和“默认要加载哪些知识文件”。

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DISPLAY_NAME = "AI Clothing Shopping Assistant System"
PROJECT_API_TITLE = f"{PROJECT_DISPLAY_NAME} API"
DATA_DIR = BASE_DIR / "data"
CHAT_HISTORY_DIR = BASE_DIR / "chat_history"
VECTOR_DB_DIR = BASE_DIR / "chroma_db"
FILE_HASH_RECORD_PATH = BASE_DIR / "knowledge_file_hashes.json"
VECTOR_COLLECTION_NAME = "clothing_knowledge_base"
EMBEDDING_MODEL_NAME = "text-embedding-v1"
CHAT_MODEL_NAME = "qwen-turbo"
CHAT_TEMPERATURE = 0.1
DEFAULT_TOP_K = 4
SIZE_KNOWLEDGE_FILE = "尺码推荐.txt"
COLOR_KNOWLEDGE_FILE = "颜色选择.txt"
CARE_KNOWLEDGE_FILE = "洗涤养护.txt"
DEFAULT_TEST_QUERY = (
    "我身高168，体重65kg，想买一件日常穿的T恤，"
    "推荐什么尺码和颜色？洗的时候需要注意什么？"
)

KNOWLEDGE_FILES = [
    "尺码推荐.txt",
    "洗涤养护.txt",
    "颜色选择.txt",
]
