import csv
import os
import re
import time
from playwright.sync_api import sync_playwright
import gspread

LOGIN_URL = "https://hikkoshi-kanri.zba.jp/"
CSV_URL = "https://hikkoshi-kanri.zba.jp/checkbox/company/users/searched/50/1"

# GitHub Actions Secrets から読み込む
ACCOUNTS = [
    (os.environ["WC_ID_1"], os.environ["WC_PASS_1"]),
    (os.environ["WC_ID_2"], os.environ["WC_PASS_2"]),
]


def download_csv(account_id, account_pass, filename):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # ログインページへ移動
        page.goto(LOGIN_URL, wait_until="networkidle")
        page.screenshot(path=f"debug_before_login_{account_id}.png")
        print(f"📷 before_login saved | URL: {page.url}")

        # Vue.jsフォームに入力
        page.wait_for_selector("input[autocomplete='username']", timeout=15000)
        page.fill("input[autocomplete='username']", account_id)
        page.fill("input[autocomplete='current-password']", account_pass)

        # ログインボタンをクリック（submitボタンがなければEnter）
        try:
            page.click("button[type='submit']", timeout=3000)
        except Exception:
            page.press("input[autocomplete='current-password']", "Enter")

        # ログイン成功 = URLがログインページから変わるまで待つ
        try:
            page.wait_for_url(
                lambda url: url.rstrip("/") != LOGIN_URL.rstrip("/"),
                timeout=15000
            )
        except Exception:
            pass

        page.wait_for_load_state("networkidle")
        page.screenshot(path=f"debug_after_login_{account_id}.png")
        print(f"📷 after_login saved  | URL: {page.url}")

        # ログイン失敗チェック
        if page.url.rstrip("/") == LOGIN_URL.rstrip("/"):
            html = page.content()
            errors = re.findall(r'<[^>]*class="[^"]*error[^"]*"[^>]*>([^<]+)<', html, re.IGNORECASE)
            print(f"⚠️ ログイン失敗の可能性。エラー要素: {errors}")

        # CSVダウンロード画面へ移動
        page.goto(CSV_URL, wait_until="networkidle")
        page.screenshot(path=f"debug_csv_page_{account_id}.png")
        print(f"📷 csv_page saved     | URL: {page.url}")

        # ページ内のリンクを全列挙してCSVエクスポートリンクを特定
        links = page.query_selector_all("a")
        print(f"=== ページ内のリンク ({len(links)}個) ===")
        for link in links:
            href = link.get_attribute("href") or ""
            text = link.inner_text().strip()
            if any(kw in href.lower() or kw in text.lower()
                   for kw in ["export", "csv", "download", "出力", "ダウンロード"]):
                print(f"  ★ 候補: text='{text}', href='{href}'")
            else:
                print(f"    text='{text}', href='{href}'")

        # ダウンロード処理（候補セレクターを優先度順に試みる）
        download_selectors = [
            "a[href*='export']",
            "a[href*='csv']",
            "a[href*='download']",
            "a:text('CSV')",
            "a:text('エクスポート')",
            "a:text('出力')",
            "a:text('ダウンロード')",
            "button:text('CSV')",
            "button:text('出力')",
        ]

        downloaded = False
        for selector in download_selectors:
            try:
                with page.expect_download(timeout=10000) as dl_info:
                    page.click(selector, timeout=5000)
                download = dl_info.value
                download.save_as(filename)
                print(f"✅ {filename} downloaded (selector: {selector})")
                downloaded = True
                break
            except Exception as e:
                print(f"  ✗ {selector}: {e}")

        if not downloaded:
            raise Exception("❌ CSVダウンロードリンクが見つかりませんでした")

        browser.close()


def merge_csv(files, output_file):
    merged = []
    header = None
    for f in files:
        with open(f, "r", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            rows = list(reader)
            if header is None:
                header = rows[0]
                merged.append(header)
            merged.extend(rows[1:])
    with open(output_file, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerows(merged)


def upload_to_gss(csv_file, sheet_id):
    gc = gspread.service_account(filename="service_account.json")
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet("row")
    ws.clear()
    with open(csv_file, "r") as f:
        reader = csv.reader(f)
        ws.append_rows(list(reader))


if __name__ == "__main__":
    download_csv(ACCOUNTS[0][0], ACCOUNTS[0][1], "a.csv")
    time.sleep(3)
    download_csv(ACCOUNTS[1][0], ACCOUNTS[1][1], "b.csv")

    merge_csv(["a.csv", "b.csv"], "merged.csv")

    SHEET_ID = "1zfnTMt8RKAojSBZ51M3M2s73vTneFP8eyyVEYRtxlwM"
    upload_to_gss("merged.csv", SHEET_ID)
