import dashscope
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from http import HTTPStatus

# 2. 封装一个“文本转向量”的工程函数
def get_text_embedding(text):
    print(f"正在将【{text}】发送给通义千问大脑进行向量化...")
    resp = dashscope.TextEmbedding.call(
        model=dashscope.TextEmbedding.Models.text_embedding_v1,
        input=text
    )

    if resp.status_code == HTTPStatus.OK:
        # 从阿里的复杂返回结果中，精准提取那个纯数字数组
        return resp.output['embeddings'][0]['embedding']
    else:
        print(f"调用失败：{resp.message}")
        return None

# 3. 核心测试逻辑
if __name__ == '__main__':
    # 场景：假设用户搜了句子A，知识库里有B和C
    text_A = "Java后端开发怎么解决高并发？"
    text_B = "Redis分布式锁在Hmdp项目中的高并发应用实践"
    text_C = "今天中午去食堂吃什么饭比较好？"

    # 把文字变成真实的向量（不再是手写的 0.1, 0.2 了）
    vec_A = get_text_embedding(text_A)
    vec_B = get_text_embedding(text_B)
    vec_C = get_text_embedding(text_C)

    # 确保向量都获取成功了
    if vec_A and vec_B and vec_C:
        # sklearn 要求输入是二维数组，所以套一层 []
        vec_A_2d = np.array([vec_A])
        vec_B_2d = np.array([vec_B])
        vec_C_2d = np.array([vec_C])

        # 核心算分时刻！
        score_AB = cosine_similarity(vec_A_2d, vec_B_2d)[0][0]
        score_AC = cosine_similarity(vec_A_2d, vec_C_2d)[0][0]

        print("\n" + "=" * 40)
        print(f"【{text_A}】 VS 【{text_B}】")
        print(f"✅ 专业领域相似度得分: {score_AB:.4f}")

        print("-" * 40)
        print(f"【{text_A}】 VS 【{text_C}】")
        print(f"❌ 跨频道相似度得分: {score_AC:.4f}")
        print("=" * 40)