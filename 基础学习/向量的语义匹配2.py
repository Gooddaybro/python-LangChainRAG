from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

vec1 = np.array([[0.1, 0.3, 0.8, 0.2]])
vec2 = np.array([[0.12, 0.31, 0.79, 0.21]])
score = cosine_similarity(vec1, vec2)[0][0]
print(score)