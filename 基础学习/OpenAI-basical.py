from openai import OpenAI

client = OpenAI(
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

resource=client.chat.completions.create(
    model="qwen3-max",
    messages=[
        {"role":"system","content":"你是一个python编程专家，并且语言简练，不说废话,回答简单但是精炼"},
        {"role":"assistant","content":"好的，我是一个编程专家，并且不说废话，你要问什么？"},
        {"role":"user","content":"输出1-10的数字，使用python代码"}
    ]
)

print(resource.choices[0].message.content)
