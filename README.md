# Clothing RAG Demo

服装知识库问答 MVP，包含两条入口：

- `app_file_uploader.py`：上传并重建本地知识库。
- `app_qa.py`：普通 RAG 问答，可勾选启用导购 Agent。

## Setup

```powershell
pip install -r requirements.txt
$env:DASHSCOPE_API_KEY="your-dashscope-api-key"
```

## Run

先更新知识库：

```powershell
streamlit run clothing_rag_demo/app_file_uploader.py
```

再打开问答页：

```powershell
streamlit run clothing_rag_demo/app_qa.py
```

## Test

```powershell
python -m unittest discover -v
python -m compileall -q clothing_rag_demo tests
```

## Notes

`chat_history/`、`chroma_db/` 和 `_chroma_probe/` 是本地运行产物，不提交到版本库。知识文件仍放在 `clothing_rag_demo/data/`。
