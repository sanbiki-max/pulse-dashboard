import os
import re
import json
import time
import urllib.request
from datetime import datetime

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """
あなたはWebリサーチアシスタントです。Web検索を使って今日の最新情報を収集し、
ニュースダッシュボード用のJavaScriptオブジェクトを生成してください。

以下の6カテゴリについて最新情報を収集し、
const NEWS_DATA = { から }; までのJavaScriptオブジェクトのみを出力してください。
余計な解説・前置き・コードブロック記号（```など）は絶対に含めないでください。
必ず const NEWS_DATA = { で始まり }; で終わること。

【収集カテゴリ】
1. domestic（国内ニュース）: hero1本 + items4本
   - 政治・経済・社会・気象・SNS話題
2. world（世界情勢）: hero1本 + items4本
   - 国際政治・地政学・海外市場
3. aitrend（AIトレンド）: スレッド形式5本
   - フィールド: num, board, title, preview, detail, replies, views, hot
   - 5ch・X・Redditで話題のAI関連スレ風
4. imagegen（画像生成AI）: カード形式5本
   - フィールド: gradient, emoji, tool, title, desc, detail, tags
   - Midjourney・NovelAI・FLUX等の最新動向
5. tech（テクノロジー）: hero1本 + items4本
   - 半導体・スマホ・EV・量子
6. agent（AIエージェント活用）: hero1本 + items4本
   - Claude Code・GPT等の実用事例

【hero/itemsの必須フィールド】
emoji, tag, title, desc, detail, source, time

【itemsのcolor】
var(--accent), var(--red), var(--gold), var(--blue), var(--purple)
agentカテゴリは "#00e5ff"、techカテゴリは "#ff8c44"

【detailフィールド】
<p>タグのHTML形式で300〜500文字程度の詳細解説

【出力形式（この形式のみ、他は何も出力しない）】
const NEWS_DATA = {
  domestic: { hero: {...}, items: [...] },
  world: { hero: {...}, items: [...] },
  aitrend: [...],
  imagegen: [...],
  tech: { hero: {...}, items: [...] },
  agent: { hero: {...}, items: [...] }
};
"""

def get_user_prompt():
    today = datetime.now().strftime('%Y年%m月%d日')
    return f"""
今日は{today}です。

【重要】以下のルールを必ず守ってください：
- 「{today}」または直近24時間以内に発生・報道されたニュースのみ使用すること
- それより古い記事は絶対に使わないこと
- 各カテゴリの検索クエリに必ず「{today}」または「2026年6月」を含めること
- 検索結果の日付を必ず確認し、古いニュースは除外すること
- 見つからない場合は直近の最新ニュースを使うこと（古くても今週以内）

各カテゴリについて実際にWeb検索して最新情報を取得してから生成してください。
必ず const NEWS_DATA = {{ で始まり }}; で終わる形式のみ出力してください。
"""

WEB_SEARCH_TOOL = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 10
}


def api_call(messages):
    """Anthropic APIを1回呼び出す"""
    url = "https://api.anthropic.com/v1/messages"
    payload = {
        "model": MODEL,
        "max_tokens": 8192,
        "system": SYSTEM_PROMPT,
        "messages": messages,
        "tools": [WEB_SEARCH_TOOL]
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        }
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def call_claude_with_retry(max_retries=3):
    """
    Web検索ツールを使うClaudeはagentic loopが必要。
    stop_reason が "end_turn" になるまでやり取りを繰り返す。
    """
    for attempt in range(max_retries):
        try:
            user_prompt = get_user_prompt()
            messages = [{"role": "user", "content": user_prompt}]
            loop_count = 0

            while True:
                loop_count += 1
                print(f"   APIコール #{loop_count}...")
                result = api_call(messages)

                stop_reason = result.get("stop_reason")
                content = result.get("content", [])

                print(f"   stop_reason: {stop_reason}, ブロック数: {len(content)}")
                for block in content:
                    print(f"   ブロックtype: {block.get('type')}")

                # assistantのメッセージを会話履歴に追加
                messages.append({"role": "assistant", "content": content})

                # 終了条件
                if stop_reason == "end_turn":
                    text_parts = [
                        block.get("text", "")
                        for block in content
                        if block.get("type") == "text"
                    ]
                    final_text = "\n".join(text_parts)
                    print(f"   最終テキスト長: {len(final_text)}文字")
                    return final_text

                # ツール使用中 → tool_resultを返して続行
                if stop_reason == "tool_use":
                    tool_results = []
                    for block in content:
                        if block.get("type") == "tool_use":
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.get("id"),
                                "content": "検索結果はClaudeのサーバーサイドで処理されます。"
                            })
                    if tool_results:
                        messages.append({"role": "user", "content": tool_results})
                    continue

                # それ以外のstop_reason（max_tokens等）
                print(f"   想定外のstop_reason: {stop_reason}")
                text_parts = [
                    block.get("text", "")
                    for block in content
                    if block.get("type") == "text"
                ]
                return "\n".join(text_parts)

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            print(f"試行{attempt+1} HTTPエラー {e.code}: {body[:500]}")
        except Exception as e:
            print(f"試行{attempt+1}失敗: {e}")

        wait = 60 * (attempt + 1)
        if attempt < max_retries - 1:
            print(f"→ {wait}秒待機して再試行...")
            time.sleep(wait)

    raise Exception("最大リトライ回数に達しました")


def extract_news_data(text):
    """テキストからconst NEWS_DATA = {...};を抽出してクリーニング"""
    text = text.strip()

    # コードブロック記号を除去
    if text.startswith("```"):
        text = re.sub(r'^```[a-z]*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    text = text.strip()

    # const NEWS_DATA = {...}; を探して抽出
    if not text.startswith("const NEWS_DATA"):
        match = re.search(r'(const NEWS_DATA\s*=\s*\{[\s\S]*)', text)
        if match:
            text = match.group(1)
        else:
            print(f"⚠️ テキスト全体:\n{text[:1000]}")
            raise ValueError("NEWS_DATAが見つかりませんでした。")

    # 末尾の ; を確認・補完
    if not text.rstrip().endswith(";"):
        text = text.rstrip() + ";"

    return text


def update_html(news_data_js):
    """index.htmlのNEWS_DATAを更新する"""
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()

    pattern = r'const NEWS_DATA\s*=\s*\{[\s\S]*?\};'
    new_html = re.sub(pattern, news_data_js, html, count=1)

    if new_html == html:
        raise ValueError("index.html内のNEWS_DATAが見つかりませんでした。")

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(new_html)

    print("✅ index.html を更新しました")


def main():
    print(f"🚀 ニュース更新開始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   モデル: {MODEL}")
    print(f"   対象日付: {datetime.now().strftime('%Y年%m月%d日')}")

    print("📡 Claude API（Web検索）を呼び出し中...")
    raw_result = call_claude_with_retry()

    print("🔍 NEWS_DATAを抽出中...")
    news_data_js = extract_news_data(raw_result)

    print(f"   抽出結果プレビュー: {news_data_js[:200]}...")

    update_html(news_data_js)
    print(f"🎉 完了! {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
