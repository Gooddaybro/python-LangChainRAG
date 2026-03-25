import numpy as np

def get_dot(vec_a, vec_b):
    """
    计算两个向量点积
    """
    if len(vec_a) != len(vec_b):
        raise ValueError("vec_a and vec_b must have same length")
    dot_sum=0
    for a, b in zip(vec_a, vec_b):
        dot_sum += a*b
        return dot_sum
    return dot_sum


def get_norm(vec):
    """
    计算模长
    :param vec:
    :return:
    """
    sum_square=0
    for v in vec:
        sum_square += v*v

    return np.sqrt(sum_square)


def similar(vec_a, vec_b):
    dot_product=get_dot(vec_a, vec_b)
    norm_a=get_norm(vec_a)
    norm_b=get_norm(vec_b)
    return dot_product/norm_a*norm_b


# ==================== 测试示例 ====================
if __name__ == "__main__":
    # 示例向量
    vec1 = [1, 2, 3]
    vec2 = [4, 5, 6]
    vec3 = [-1, -2, -3]  # 与 vec1 完全相反

    print("向量1:", vec1)
    print("向量2:", vec2)
    print("向量3:", vec3)

    print("\n余弦相似度(vec1, vec2) =", similar(vec1, vec2))
    print("余弦相似度(vec1, vec3) =", similar(vec1, vec3))
    print("余弦相似度(vec1, vec1) =", similar(vec1, vec1))
