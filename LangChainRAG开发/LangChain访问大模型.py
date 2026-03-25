# from langchain_community.llms.tongyi import Tongyi
#
# model = Tongyi(model="qwen-max")
#
# res=model.invoke(input="你是谁能做什么？")
#
# print(res)
from langchain_classic.chains.question_answering.map_reduce_prompt import messages
#
# import os
# from langchain_community.llms import Tongyi   # 更推荐这种导入方式
#
#
# # 实例化模型
# llm = Tongyi(
#     model="qwen-max",        # 常用选项：qwen-max、qwen-plus、qwen-turbo、qwen2.5-72b-instruct 等
#     temperature=0.7,         # 创意度，0~1，数字越大越有创意
#     max_tokens=2048,         # 最大输出长度
#     # streaming=True,        # 如果想流式输出，可以打开
# )
#
# # 调用（最简单的方式）
# response = llm.invoke("帮我讲一个关于程序员的笑话")
# print(response)


# from langchain_community.chat_models import ChatTongyi
# from langchain_core.messages import SystemMessage, HumanMessage
#
# chat = ChatTongyi(model="qwen-max")
#
# messages = [
#     SystemMessage(content="你是一个幽默风趣的AI助手"),
#     HumanMessage(content="给我讲个笑话")
# ]
#
# response = chat.invoke(messages)
# print(response.content)


# # 调用聊天模型
# from langchain_community.chat_models.tongyi import ChatTongyi
# from langchain_core.messages import HumanMessage,AIMessage,SystemMessage
#
# model=ChatTongyi(model="qwen3-max")
# messages=[
#     HumanMessage(content="AI下的计算机行业破局？")
# ]
# res=chat.c
# #res=model.stream(input=messages)
#
# print(res)
# # for chunk in res:
# #     print(chunk,end="",flush=True)
#
#

import os
from langchain_community.chat_models import ChatTongyi
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage


# ====================== 初始化聊天模型 ======================
chat = ChatTongyi(
    model="qwen-max",      # 可以换成 qwen-plus、qwen-turbo、qwen2.5-72b-instruct 等
    temperature=0.7,       # 控制创意度，0~1
    max_tokens=2048,       # 最大输出长度
    # streaming=True,      # 如果要流式输出，打开这行
)

# ====================== 准备消息（支持多轮对话） ======================
messages = [
    SystemMessage(content="你是一个专业的AI助手，请用中文回答问题。"),  # 系统提示
    HumanMessage(content="AI下的计算机行业破局？")                     # 用户问题
]

# ====================== 方式1：普通调用（一次性返回完整答案） ======================
response = chat.invoke(messages)
print("完整回答：")
print(response.content)

# ====================== 方式2：流式输出（像ChatGPT一样一边生成一边打印） ======================
print("\n流式输出：")
for chunk in chat.stream(messages):
    print(chunk.content, end="", flush=True)   # 实时打印，不换行
print()  # 最后换行e)