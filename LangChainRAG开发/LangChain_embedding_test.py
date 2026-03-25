import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
# 【核心跨越】：引入 LangChain 社区版封装的阿里 Embedding 接口
from langchain_community.embeddings import DashScopeEmbeddings

def main():
    print("正在初始化 LangChain 的阿里嵌入模型大炮...\n")
    # 2. 实例化模型（这里体现了 LangChain 的威力，接口极其简洁）
    # 阿里官方默认模型通常是 text-embedding-v1 或 v2
    embeddings = DashScopeEmbeddings(model="text-embedding-v1")

    # ==========================================
    # 场景 A：单独翻译一句用户的提问 (embed_query)
    # ==========================================
    query = "Java中怎么解决缓存穿透？"
    print(f"用户提问：【{query}】")
    # 调用 embed_query 方法
    query_vector = embeddings.embed_query(query)
    print(f"✅ 提问已转化为向量！维度大小：{len(query_vector)} 维 (代表它在1500多个维度上的坐标)\n")

    # ==========================================
    # 场景 B：批量翻译知识库里的文档 (embed_documents)
    # ==========================================
    knowledge_base = [
        "使用布隆过滤器或者缓存空对象可以有效解决Redis缓存穿透问题。",
        "今天食堂的红烧排骨做咸了，建议多喝水。",
        "Spring Boot 中可以使用 @Async 注解实现异步调用。"
    ]
    print("正在批量将知识库文本转化为向量矩阵...")
    # 调用 embed_documents 方法（注意传的是个列表）
    doc_vectors = embeddings.embed_documents(knowledge_base)
    print(f"✅ 知识库转化完成！共转化了 {len(doc_vectors)} 篇文章。\n")

    # ==========================================
    # 场景 C：见证奇迹的时刻 —— 算分匹配
    # ==========================================
    print("-" * 50)
    print("开始进行语义向量匹配计算：")
    # 将一维数组转为二维，供 sklearn 计算
    q_vec_2d = np.array([query_vector])

    for i, doc_vec in enumerate(doc_vectors):
        d_vec_2d = np.array([doc_vec])
        # 计算余弦相似度
        score = cosine_similarity(q_vec_2d, d_vec_2d)[0][0]

        # 设定一个阈值，分数高打印绿色，分数低打印红色（这里只是模拟）
        status = "🟢 高度相关" if score > 0.6 else "🔴 毫不相干"
        print(f"[{status}] 得分: {score:.4f} | 内容: {knowledge_base[i]}")
    print("-" * 50)


if __name__ == '__main__':
    main()