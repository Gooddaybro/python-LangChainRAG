import os
# 引入 LangChain 社区版对阿里通义千问的封装
from langchain_community.chat_models.tongyi import ChatTongyi
# 引入 LangChain 的标准消息体
from langchain_core.messages import HumanMessage, SystemMessage


# 2. 实例化 Chat 模型 (注意：这里用的是 ChatTongyi，对应图里的聊天模型)
# 如果你想换成 OpenAI，只需要把这里改成 ChatOpenAI() 即可，下面代码一行不用改！这就叫统一接口！
chat_model = ChatTongyi(
    model="qwen-turbo",  # 指定模型版本
    temperature=0.7  # 发散度：0表示严谨不废话，1表示天马行空
)

# 3. 编排“剧本”（构建 Message 列表）
messages = [
    # 设定 AI 的底层角色（SystemMessage）
    SystemMessage(content="你是一个暴躁但技术极强的顶级程序员，说话喜欢一针见血，不用客气。"),

    # 模拟用户的提问（HumanMessage）
    HumanMessage(content="我在学 Python 里的 LangChain，但觉得好难，各种概念，我该放弃吗？")
]

print("正在向通义千问发送剧本，等待大佬回复...\n")
print("=" * 50)

# 4. 执行调用 (invoke 是 LangChain 的标准执行方法)
response = chat_model.invoke(messages)

# 5. 输出结果 (返回的是一个 AIMessage 对象，它的 content 属性才是真正的文本)
print(response.content)
print("=" * 50)