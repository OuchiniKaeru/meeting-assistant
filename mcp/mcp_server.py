from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI, Response
from pydantic import Field
import json

# MCP サーバーのインスタンスを作成
mcp = FastMCP(name="Term Dictionary as Tools")

# 専門用語辞書
@mcp.tool(description="Explanation of technical terms included in the recognition results.")
def explain_japanese_terms(
    term: str = Field(..., description="説明したい専門用語（例：MCP）")
) -> str:
    """Explanation of technical terms."""
    terms = {
        "mcp": "Model Context Protocol。AIエージェントが外部のサービスやデータと標準化された方法でやり取りするためのプロトコル",
        "nlweb": "Natural Language Web。NLWeb は、あらゆるウェブサイトをAI搭載アプリ化できるオープンプロジェクトで、自然言語でサイトの内容を操作・検索できるインターフェースを簡単に導入できます",
    }
    # 正規化（空白削除 + 小文字化）
    normalized_term = term.replace(" ", "").lower()

    explanation = terms.get(normalized_term, "その用語の説明は見つかりませんでした。")
    print(f"{term} の説明: {explanation}")

    # ヘッダ付きの結果を作成
    result_with_header = f"【ツールの利用結果】専門用語辞書\n用語: {term}\n説明: {explanation}"
    
    return json.dumps(result_with_header, ensure_ascii=False)

# FastAPI アプリケーションを作成し、MCP の SSE エンドポイントをマウント
app = FastAPI()
app.mount("/", mcp.sse_app())

# サーバーを起動するには、以下のコマンドを実行してください:
# uvicorn mcp_server:app --host 127.0.0.1 --port 8000
