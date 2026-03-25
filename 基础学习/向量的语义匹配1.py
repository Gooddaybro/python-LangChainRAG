# import numpy as np
#
# def cosine_similarity(vec1, vec2):
#     vec1 = np.array(vec1)
#     vec2 = np.array(vec2)
#     return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
#
# # 示例（真实项目里这里放 Embedding 结果）
# v1 = [0.1, 0.3, 0.8, 0.2]
# v2 = [0.12, 0.31, 0.79, 0.21]
# score = cosine_similarity(v1, v2)
# print(f"相似度得分: {score:.4f}")   # 输出约 0.999


import numpy as np
from numpy.linalg import norm

# 假设经过 Embedding 模型后，三句话变成了三个数组（向量）
vector_a = np.array([1.2, 0.5, 0.1]) # 句子A："iPhone好用"
vector_b = np.array([1.1, 0.4, 0.2]) # 句子B："苹果手机不错"
vector_c = np.array([0.1, 0.1, 1.5]) # 句子C："红富士好吃"

# 定义余弦相似度函数：(A·B) / (|A|*|B|)
def cosine_sim(a, b):
    return np.dot(a, b) / (norm(a) * norm(b))

# 测试打分
print(f"A和B的相似度 (谈手机): {cosine_sim(vector_a, vector_b):.4f}") # 输出极可能接近 0.99
print(f"A和C的相似度 (跨频道): {cosine_sim(vector_a, vector_c):.4f}") # 输出极可能接近 0.10