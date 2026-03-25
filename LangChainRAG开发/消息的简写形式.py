import os
from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate

# 初始化模型
chat = ChatTongyi(model="qwen-max", temperature=0.7)

# ==================== 方式1：直接用简写元组（最简单） ====================
messages = [
    ("system", "你是一个专业的AI助手，请用中文回答问题。"),
    ("human", "AI下的计算机行业破局？")
]

response = chat.invoke(messages)
print(response.content)