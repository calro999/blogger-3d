import os
import random
import requests
import time
import sys
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

CACHE_FILE = "posted_cache.txt"

def load_posted_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_to_cache(item_code):
    with open(CACHE_FILE, "a", encoding="utf-8") as f:
        f.write(f"{item_code}\n")

def fetch_rakuten_item():
    app_id = os.environ.get("RAKUTEN_APP_ID")
    access_key = os.environ.get("RAKUTEN_ACCESS_KEY")
    if not app_id or not access_key:
        raise ValueError("RAKUTEN_APP_ID and RAKUTEN_ACCESS_KEY must be set in environment variables.")

    # 3Dプリンター・フィラメント特化のキーワードリスト
    keywords = [
        "eSUN フィラメント",
        "SUNLU フィラメント",
        "PolyMaker フィラメント",
        "OVERTURE フィラメント",
        "3Dプリンター ノズル 0.4mm",
        "PEIビルドプレート"
    ]
    selected_keyword = random.choice(keywords)
    print(f"Searching Rakuten for keyword: {selected_keyword}")

    url = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260401"
    params = {
        "applicationId": app_id,
        "accessKey": access_key,
        "keyword": selected_keyword,
        "NGKeyword": "乾燥機 ドライヤー ケース ボックス 収納 減速機 3Dプリンター本体",
        "format": "json",
        "hits": 30
    }

    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise RuntimeError(f"Failed to fetch from Rakuten API: {response.status_code} - {response.text}")

    data = response.json()
    items = data.get("Items", [])
    if not items:
        raise RuntimeError(f"No items found for keyword: {selected_keyword}")

    posted_cache = load_posted_cache()
    for item_wrapper in items:
        item = item_wrapper.get("Item", {})
        item_code = item.get("itemCode")
        if item_code and item_code not in posted_cache:
            return item

    raise RuntimeError("All fetched items have already been posted.")

def generate_article_with_llm(item):
    title = item.get("itemName")
    price = item.get("itemPrice")
    url = item.get("affiliateUrl") or item.get("itemUrl")
    
    # 複数画像がある場合は最初の一枚、なければ空文字列
    image_url = ""
    medium_images = item.get("mediumImageUrls", [])
    if medium_images:
        image_url = medium_images[0]
    else:
        small_images = item.get("smallImageUrls", [])
        if small_images:
            image_url = small_images[0]

    # Google Analytics計測ID（G-NFPP76LS9J）を含む計測コード
    ga_tag = """<!-- Global site tag (gtag.js) - Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-NFPP76LS9J"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-NFPP76LS9J');
</script>"""

    prompt = f"""以下の楽天の商品情報を基にして、自動投稿用のHTML記事を生成してください。
【商品名】: {title}
【価格】: {price}円
【商品画像URL】: {image_url}
【アフィリエイトURL】: {url}

以下の要件を【厳格】に遵守してください：
1. 出力はブログの本文となるHTMLコードのみとし、余計な説明、挨拶、前置きや後書き（例：「以下が記事です」「```html」のようなマークダウンブロック）は絶対に含めず、純粋なHTML文字列のみを出力してください。
2. 【最優先・強制】記事の最上部（ヘッダー部分）に、以下のGoogle Analytics計測コード（ID: G-NFPP76LS9J）を必ず【完全な形式】でそのまま挿入してください：
{ga_tag}
3. アイキャッチ画像として、商品画像URL（{image_url}）を直接<img>タグのsrc属性に指定し、Google Analyticsコードの直下に配置してください。
4. 記事構成：
   - キャッチーな見出し（<h2> または <h3> タグを使用）
   - 商品の特性（PLA/PETG/ABS/TPU/シルク等の素材、色、太さ）の簡潔な要約（客観的で魅力が伝わる文章）
   - 【最重要】スライサーソフト（CuraやBambu Studio等）に入力するための「推奨印刷設定表」（HTMLの <table> タグを使用し、ノズル温度、ヒートベッド温度、推奨印刷速度などの項目を綺麗にテーブル化する。データが商品説明にない場合は一般的な素材の推奨値を補完して出力すること）
   - 3Dプリンターユーザー（造形環境）向けの注意点や魅力3ポイント（必ず <ul> と <li> タグを使用）
   - 購買意欲を促す太字の誘導文（<strong> または <b> タグを使用）
   - 最後に装飾されたアフィリエイトリンクのボタン（<a>タグでスタイルし、新しいタブで開く target="_blank" rel="noopener noreferrer" を指定。オレンジ等のボタンデザインになるようインラインスタイルを施すこと。例：background-color: #ff6600; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;）
"""

    system_content = "あなたは3Dプリンターのフィラメントおよびカスタムパーツ専門の技術派コレクター兼紹介ブロガーです。指示された仕様に完全に従い、Google Analytics計測タグを最上部に埋め込み、前置きやHTMLタグブロックのマークダウン表現などを含めない純粋なHTML本文のみを出力します。"

    # 1. GitHub Models API (GITHUB_TOKENを使用) を最優先
    github_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if github_token:
        try:
            print("Attempting to generate article with GitHub Models API...")
            headers = {
                "Authorization": f"Bearer {github_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7
            }
            response = requests.post("https://models.inference.ai.azure.com/chat/completions", headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                result = response.json()["choices"][0]["message"]["content"].strip()
                if "```html" in result:
                    result = result.split("```html", 1)[1]
                if "```" in result:
                    result = result.split("```", 1)[0]
                return result.strip()
            else:
                print(f"GitHub Models API returned status code: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"GitHub Models API failed with exception: {e}")
    else:
        print("GITHUB_TOKEN / GH_TOKEN is not set in environment variables.")

    # 2. Pollinations AI (キー不要、フォールバック)
    pollinations_models = ["openai", "mistral"]
    for model in pollinations_models:
        try:
            print(f"Attempting to generate article with Pollinations AI (model: {model})...")
            response = requests.post(
                "https://text.pollinations.ai/",
                json={
                    "messages": [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": prompt}
                    ],
                    "model": model
                },
                timeout=45
            )
            if response.status_code == 200 and len(response.text.strip()) > 100:
                result = response.text.strip()
                if "```html" in result:
                    result = result.split("```html", 1)[1]
                if "```" in result:
                    result = result.split("```", 1)[0]
                return result.strip()
            else:
                print(f"Pollinations AI ({model}) returned status code: {response.status_code} - {response.text[:200]}")
        except Exception as e:
            print(f"Pollinations AI ({model}) failed with exception: {e}")
            time.sleep(1)

    raise RuntimeError("All LLM generation attempts failed.")

def print_env_debug(name, value):
    if not value:
        print(f"[DEBUG-AUTH] {name} is NOT set or is empty.")
        return
    val_str = str(value)
    length = len(val_str)
    start_chars = val_str[:3] if length >= 3 else val_str
    end_chars = val_str[-3:] if length >= 3 else val_str
    
    # 改行やスペースなどの見えない文字がないか確認できるようにエスケープ表現に変換
    repr_start = repr(start_chars)
    repr_end = repr(end_chars)
    
    print(f"[DEBUG-AUTH] {name}: length={length}, start={repr_start}, end={repr_end}")

def post_to_blogger(title, content):
    refresh_token = os.environ.get("BLOGGER_REFRESH_TOKEN")
    client_id = os.environ.get("BLOGGER_CLIENT_ID")
    client_secret = os.environ.get("BLOGGER_CLIENT_SECRET")
    blog_id = os.environ.get("BLOGGER_BLOG_ID")

    print("=== Environment Variables Debugging ===")
    print_env_debug("BLOGGER_REFRESH_TOKEN", refresh_token)
    print_env_debug("BLOGGER_CLIENT_ID", client_id)
    print_env_debug("BLOGGER_CLIENT_SECRET", client_secret)
    print_env_debug("BLOGGER_BLOG_ID", blog_id)
    print("=======================================")

    # 環境変数の検証
    missing_vars = []
    if not refresh_token: missing_vars.append("BLOGGER_REFRESH_TOKEN")
    if not client_id: missing_vars.append("BLOGGER_CLIENT_ID")
    if not client_secret: missing_vars.append("BLOGGER_CLIENT_SECRET")
    if not blog_id: missing_vars.append("BLOGGER_BLOG_ID")

    if missing_vars:
        raise ValueError(f"Missing required Blogger API variables: {', '.join(missing_vars)}")

    print("Building Blogger API Credentials...")
    creds = Credentials(
        token=None,
        refresh_token=refresh_token.strip() if refresh_token else None,
        client_id=client_id.strip() if client_id else None,
        client_secret=client_secret.strip() if client_secret else None,
        token_uri="https://oauth2.googleapis.com/token",
    )
    
    # トークンのリフレッシュによる明確なエラー検知と詳細ダンプ
    try:
        print("Verifying and refreshing Blogger API OAuth credentials...")
        creds.refresh(Request())
    except RefreshError as refresh_err:
        print("\n=== Blogger API OAuth Refresh Error (RefreshError) ===")
        print(f"Error Type: {type(refresh_err)}")
        print(f"Error Message: {refresh_err}")
        # 生のサーバーからのエラーレスポンスを出力
        if hasattr(refresh_err, 'args') and refresh_err.args:
            print("OAuth Response Payload / Details:")
            for arg in refresh_err.args:
                print(f" - {arg}")
        raise refresh_err
    except Exception as auth_err:
        print("\n=== Blogger API OAuth General Failure ===")
        print(f"Error Type: {type(auth_err)}")
        print(f"Error Message: {auth_err}")
        if hasattr(auth_err, 'response'):
            try:
                print(f"HTTP Response Body: {auth_err.response.text}")
            except Exception:
                pass
        raise auth_err

    service = build("blogger", "v3", credentials=creds)
    
    # 二重の安全策：生成されたコンテンツに Google Analytics 計測 ID が入っていなければ、先頭に強制挿入する
    if "G-NFPP76LS9J" not in content:
        print("Warning: Google Analytics ID (G-NFPP76LS9J) not found in LLM content. Injecting GA tag automatically.")
        ga_tag = """<!-- Global site tag (gtag.js) - Google Analytics -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-NFPP76LS9J"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-NFPP76LS9J');
</script>
"""
        content = ga_tag + "\n" + content

    body = {
        "title": title,
        "content": content
    }
    
    print(f"Posting to Blogger (Blog ID: {blog_id})...")
    post = service.posts().insert(blogId=blog_id, body=body).execute()
    print(f"Successfully posted! Post URL: {post.get('url')}")

def main():
    try:
        # 1. 楽天から商品取得
        item = fetch_rakuten_item()
        item_code = item.get("itemCode")
        title = item.get("itemName")
        print(f"Selected Item: {title} ({item_code})")

        # 2. LLMで記事生成
        content = generate_article_with_llm(item)

        # 3. Bloggerに投稿
        post_to_blogger(title, content)

        # 4. キャッシュに保存
        save_to_cache(item_code)
        print("Process completed successfully.")

    except Exception as e:
        print(f"Error in execution: {e}")
        exit(1)

if __name__ == "__main__":
    main()
