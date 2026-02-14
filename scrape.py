import csv
import os
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

        # ログインページへ移動（Vue.jsの描画を待つためnetworkidle）
        page.goto(LOGIN_URL, wait_until="networkidle")

        # デバッグ用スクリーンショット
        page.screenshot(path=f"debug_before_login_{account_id}.png")
        print(f"📷 debug_before_login_{account_id}.png saved")
        print(f"   URL: {page.url}")
        print(f"   Title: {page.title()}")

        # Vue.jsアプリのためname/id属性なし → autocomplete属性で特定
        page.wait_for_selector("input[autocomplete='username']", timeout=15000)
        page.fill("input[autocomplete='username']", account_id)
        page.fill("input[autocomplete='current-password']", account_pass)

        # submitボタンがなければEnterで送信
        try:
            page.click("button[type='submit']", timeout=3000)
        except Exception:
            page.press("input[autocomplete='current-password']", "Enter")

        page.wait_for_load_state("networkidle")

        # ログイン後スクリーンショット
        page.screenshot(path=f"debug_after_login_{account_id}.png")
        print(f"📷 debug_after_login_{account_id}.png saved")
        print(f"   URL after login: {page.url}")

        # CSVダウンロード画面へ移動
        page.goto(CSV_URL, wait_until="networkidle")

        # ダウンロード処理
        with page.expect_download() as dl_info:
            page.click("a[href*='export']")
        download = dl_info.value
        download.save_as(filename)
        print(f"✅ {filename} downloaded")

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
