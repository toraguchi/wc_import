import csv
import json
import os
import time
from playwright.sync_api import sync_playwright
import gspread
from google.oauth2.service_account import Credentials

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

        # ログイン成功 = URLが変わるまで待つ
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

        # CSVダウンロード画面へ移動
        page.goto(CSV_URL, wait_until="networkidle")
        page.screenshot(path=f"debug_csv_page_{account_id}.png")
        print(f"📷 csv_page saved     | URL: {page.url}")

        # ダウンロード処理
        download_selectors = [
            "button:text('CSV')",
            "button:text('出力')",
            "button:text('ダウンロード')",
            "a[href*='export']",
            "a[href*='csv']",
            "a:text('CSV')",
        ]

        downloaded = False
        for selector in download_selectors:
            try:
                with page.expect_download(timeout=15000) as dl_info:
                    page.click(selector, timeout=5000)
                dl = dl_info.value
                dl.save_as(filename)
                print(f"✅ {filename} downloaded (selector: {selector})")
                downloaded = True
                break
            except Exception as e:
                print(f"  ✗ {selector}: {e}")

        if not downloaded:
            raise Exception("❌ CSVダウンロードリンクが見つかりませんでした")

        browser.close()


def merge_csv(files, output_file):
    """Shift-JIS / UTF-8 どちらでも読み込めるよう対応"""
    merged = []
    header = None
    for f in files:
        for encoding in ["shift_jis", "cp932", "utf-8-sig", "utf-8"]:
            try:
                with open(f, "r", encoding=encoding) as csvfile:
                    rows = list(csv.reader(csvfile))
                print(f"  {f}: encoding={encoding}, {len(rows)}行")
                break
            except (UnicodeDecodeError, Exception):
                continue
        else:
            raise Exception(f"❌ {f} のエンコーディングを判定できませんでした")

        if header is None:
            header = rows[0]
            merged.append(header)
        merged.extend(rows[1:])

    with open(output_file, "w", encoding="utf-8", newline="") as out:
        csv.writer(out).writerows(merged)
    print(f"✅ merged.csv 作成完了: {len(merged)}行")


def upload_to_gss(csv_file, sheet_id):
    # ★ GCP_SA_KEY_JSON 環境変数からサービスアカウント情報を直接読み込む
    sa_json = os.environ.get("GCP_SA_KEY_JSON")
    if not sa_json:
        raise Exception("❌ 環境変数 GCP_SA_KEY_JSON が設定されていません")

    sa_info = json.loads(sa_json)
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(sa_info, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet("row")
    ws.clear()
    with open(csv_file, "r", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    ws.append_rows(rows)
    print(f"✅ GSSへ反映完了: {len(rows)}行")


if __name__ == "__main__":
    download_csv(ACCOUNTS[0][0], ACCOUNTS[0][1], "a.csv")
    time.sleep(3)
    download_csv(ACCOUNTS[1][0], ACCOUNTS[1][1], "b.csv")

    merge_csv(["a.csv", "b.csv"], "merged.csv")

    SHEET_ID = "1zfnTMt8RKAojSBZ51M3M2s73vTneFP8eyyVEYRtxlwM"
    upload_to_gss("merged.csv", SHEET_ID)
