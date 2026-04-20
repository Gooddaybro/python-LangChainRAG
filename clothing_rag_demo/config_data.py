from pathlib import Path

# 应该只放配置，不放业务逻辑。
# 定义项目里的“路径配置”和“默认要加载哪些知识文件”。

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CHAT_HISTORY_DIR = BASE_DIR / "chat_history"
VECTOR_DB_DIR = BASE_DIR / "chroma_db"
FILE_HASH_RECORD_PATH = BASE_DIR / "knowledge_file_hashes.json"

KNOWLEDGE_FILES = [
    "尺码推荐.txt",
    "洗涤养护.txt",
    "颜色选择.txt",
]
