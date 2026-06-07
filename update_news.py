import os
import re
import json
import time
import urllib.request
from datetime import datetime

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-2.0-flash"

PROMPT = """
あなたはWebリサーチアシスタントです。今日の最新情報を収集し、
ニュースダッシュボード用のJavaScriptオブジェクトを生成してください。

以下の6カテゴリについて最新情報を収集し、
const NEWS_DATA = { から }; までのJavaScriptオブジェクトのみを出力してください。
余計な解説・前置き・コードブロック記号は絶対に含めないでください。

【収集カテゴリ】
1. domestic（国内ニュース）hero1本+items4本
2. world（世界情勢）hero1本+items4本
3. aitrend（AIトレンド）スレッド形式5本 num,board,title,preview,detail,replies,views,hot
4. imagegen（画像生成AI）カード形式5本 gradient,emoji,tool,title,desc,detail,tags
5. tech（テクノロジー）hero1本+items4本
6. agent（AIエージェント）hero1本+items4本

hero/itemsの必須フィールド: emoji,tag,title,desc,detail,source,time
itemsのcolor: var(--accent),var(--red),var(--gold),var(--blue),var(--purple)
agentは"#00e5ff"、techは"#ff8c44"
detailは<p>タグのHTML形式で300文字程度

出力形式:
const NEWS_DATA = {
  domestic: { hero: {...}, items: [...] },
  world: { hero: {...}, items: [...] },
  aitrend: [...],
  imagegen: [...],
  tech: { hero: {...}, items: [...] },
  agent: { hero: {...}, items: [...] }
};
"""

def call_gemini_with_retry(prompt, max_retries=5):
    for attempt in range(max_retries):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_API_KEY}"
            data = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"maxOutputTokens": 8192, "temperature": 0.7}
            }).encode("utf-8")
            req = urllib.request.Request(
                url, data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
            return result["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            wait = 60 * (attempt + 1)
            print(f"試行{attempt+1}失敗: {e} → {wait}秒待機")
            if attempt < max_retries - 1:
                time.sleep(wait)
    raise Exception("最大リトライ回数に達しました")

def update_html(news_data_js):
    with open("index.html", "r", encoding="utf-8") as f:
        html = f.read()
    pattern = r'const NEWS_DATA\s*=\s*\{[\s\S]*?\};'
    new_html = re.sub(pattern, news_data_js, html, count=1)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(new_html)
    print("index.html を更新しました")

def main():
    print(f"ニュース更新開始: {datetime.now()}")
    result = call_gemini_with_retry(PROMPT)
    result = result.strip()
    if result.startswith("```"):
        result = re.sub(r'^```[a-z]*\n?', '', result)
        result = re.sub(r'\n?```$', '', result)
    if not result.startswith("const NEWS_DATA"):
        match = re.search(r'const NEWS_DATA\s*=\s*\{[\s\S]*?\};', result)
        if match:
            result = match.group(0)
    update_html(result)
    print("完了!")

if __name__ == "__main__":
    main()
