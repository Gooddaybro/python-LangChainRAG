import json
from datetime import datetime

from clothing_rag_demo.config_data import CHAT_HISTORY_DIR

# 负责保存和读取聊天历史
DEFAULT_SESSION_ID = "default"
DEFAULT_HISTORY_LIMIT = 3


def get_history_file_path(session_id=DEFAULT_SESSION_ID):
    """根据会话 ID 找到对应的历史文件路径。"""
    safe_session_id = session_id.strip() or DEFAULT_SESSION_ID

    # 会话 ID 最终会变成文件名，所以先禁止路径分隔符，避免写到 chat_history 目录外面。
    if "/" in safe_session_id or "\\" in safe_session_id:
        raise ValueError("session_id 不能包含路径分隔符。")

    return CHAT_HISTORY_DIR / f"{safe_session_id}.jsonl"


def load_chat_history(session_id=DEFAULT_SESSION_ID, limit=DEFAULT_HISTORY_LIMIT):
    """读取最近 limit 轮聊天历史。"""
    history_file_path = get_history_file_path(session_id)

    if not history_file_path.exists():
        return []

    with history_file_path.open("r", encoding="utf-8") as file:
        lines = [line.strip() for line in file if line.strip()]

    # JSONL 文件一行是一轮问答；只取最后 limit 行，避免把过长历史全部塞给大模型。
    recent_lines = lines[-limit:]
    chat_history = []

    for line in recent_lines:
        chat_history.append(json.loads(line))

    return chat_history


def append_chat_turn(user_query, assistant_answer, session_id=DEFAULT_SESSION_ID):
    """追加保存一轮用户问题和 AI 回答。"""
    CHAT_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    history_file_path = get_history_file_path(session_id)

    chat_turn = {
        "user_query": user_query,
        "assistant_answer": assistant_answer,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # 使用追加写入，避免每次保存都重写整个历史文件。
    with history_file_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(chat_turn, ensure_ascii=False) + "\n")

    return chat_turn


def clear_chat_history(session_id=DEFAULT_SESSION_ID):
    """清空当前会话的聊天历史。"""
    history_file_path = get_history_file_path(session_id)

    if history_file_path.exists():
        history_file_path.unlink()


def main():
    """最小测试：保存两轮服装问答，再读取最近三轮历史。"""
    test_session_id = "demo_test"
    clear_chat_history(test_session_id)

    append_chat_turn(
        user_query="我身高168，体重65kg，想买一件日常穿的T恤，推荐什么尺码和颜色？洗的时候需要注意什么？",
        assistant_answer="建议选择 L 码；颜色可选黑白灰、米色、藏蓝；洗涤时水温不超过30℃，深浅色分开洗。",
        session_id=test_session_id,
    )
    append_chat_turn(
        user_query="那如果我想宽松一点呢？",
        assistant_answer="如果想宽松一点，可以在 L 码基础上加大一码，考虑 XL。",
        session_id=test_session_id,
    )

    chat_history = load_chat_history(test_session_id, limit=3)

    print(f"已读取 {len(chat_history)} 轮历史：")
    for index, chat_turn in enumerate(chat_history, start=1):
        print(f"{index}. 用户：{chat_turn['user_query']}")
        print(f"   助手：{chat_turn['assistant_answer']}")
        print(f"   时间：{chat_turn['created_at']}")


if __name__ == "__main__":
    main()
