from openai import OpenAI
import os

# client = OpenAI(
#     # 如果没有配置环境变量，请用阿里云百炼API Key替换：api_key="sk-xxx"
#     api_key=os.getenv("sk-615cbae70174467abd27e64df63ff27c"),
#     base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
# )


# 调用本地模型
# client = OpenAI(
#     # ← 直接粘贴你的 Key，确保无空格、无多余字符
#     base_url="http://localhost:11434/v1",
# )
# messages = [{"role": "user", "content": "我是计算机技术的双非研究生在ai裁员这么厉害的今天给我一些建议好吗？"}]
# completion = client.chat.completions.create(
#     model="qwen3-vl:4b",  # 您可以按需更换为其它深度思考模型
#     messages=messages,
#     extra_body={"enable_thinking": True},
#     stream=True
# )


# 调用远程模型
client = OpenAI(
    # ← 直接粘贴你的 Key，确保无空格、无多余字符
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1/",
)
# 方式1：最推荐，清晰
messages = [
    {"role": "system",    "content": "你是一个Python专家。"},
    {"role": "assistant", "content": "我是一个Python编程专家。请问有什么可以帮助您的吗？"},
    {"role": "user",      "content": "我是计算机技术的双非研究生在ai裁员这么厉害的今天给我一些建议好吗？语言简练一点"}
]



completion = client.chat.completions.create(
    model="qwen3-max",  # 您可以按需更换为其它深度思考模型
    messages=messages,
    extra_body={"enable_thinking": True},
    stream=True
)

is_answering = False  # 是否进入回复阶段
print("\n" + "=" * 20 + "思考过程" + "=" * 20)
for chunk in completion:
    delta = chunk.choices[0].delta
    if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
        if not is_answering:
            print(delta.reasoning_content, end="", flush=True)
    if hasattr(delta, "content") and delta.content:
        if not is_answering:
            print("\n" + "=" * 20 + "完整回复" + "=" * 20)
            is_answering = True
        print(delta.content, end="", flush=True)
