import os
import re
import json
import urllib.request
import urllib.error
from datetime import datetime

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
MODEL = "gemini-1.5-flash"

PROMPT = """
あなたはWebリサーチアシスタントです。今日の最新情報を検索し、
ニュースダッシュボード用のJavaScriptオブジェクトを生成してください。

以下の6カテゴリについて過去24時間以内の最新情報を収集し、
const NEWS_DATA = { から }; までのJavaScriptオブジェクトのみを出力してください。
余計な解説・前置き・コードブロック記号(```)は絶対に含めないでください。

【収集カテゴリ】
1. domestic（国内ニュース）- 政治・経済・社会・気象・SNS話題
   hero（1本）+ items（4〜5本）
2. world（世界情勢）- 国際政治・地政学・海外市場・SNS拡散ニュース
   hero（1本）+ items（4〜5本）
3. aitrend（2ch/5ch AIトレンド）- 5ch・X・Redditで話題のAI
   スレッド形式5本（num,board,title,preview,detail,replies,views,hot）
4. imagegen（画像生成AI）- Midjourney・NovelAI・FLUX等の最新動向
   カード形式5本（gradient,emoji,tool,title,desc,detail,tags）
5. tech（テクノロジー）- 半導体・スマホ・EV・量子・サイバー
   hero（1本）+ items（4〜5本）
6. agent（AIエージェント活用）- Claude Code・GPT等の最新事例
   hero（1本）+ items（4〜5本）

【各itemの必須フィールド】
- hero/items（domestic,world,tech,agent）: emoji,tag,title,desc,detail,source,time
- itemsのcolor: var(--accent),var(--red),var(--gold),var(--blue),var(--purple)
- agentは"#00e5ff"、techは"#ff8c44"を使用
- detailはHTML段落形式（<p>タグ）で500文字程度

【出力形式】必ずこの形式で出力してください：
const NEWS_DATA = {
  domestic: { hero: {...}, items: [...] },
  world: { hero: {...}, items: [...] },
  aitrend: [...],
  imagegen: [...],
  tech: { hero: {...}, items: [...] },
  agent: { hero: {...}, items: [...] }
};
"""

def call_gemini(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_API_KEY}"
    data = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 8192, "temperature": 0.7}
    }).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    return result["candidates"][0]["content"]["parts"][0]["text"]

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
    print("Gemini APIを呼び出し中...")
    result = call_gemini(PROMPT)
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
