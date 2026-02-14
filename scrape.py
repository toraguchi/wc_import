import csv
import time
from playwright.sync_api import sync_playwright
import gspread

LOGIN_URL = "https://hikkoshi-kanri.zba.jp/"
CSV_URL = "https://hikkoshi-kanri.zba.jp/checkbox/company/users/searched/50/1"
ACCOUNTS = [
    ("hks-hk-twins", "InitialPassword@123"),
    ("hks-good-face-group", "InitialPassword@123")
]

def download_csv(account_id, account_pass, filename):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # ログイン
        page.goto(LOGIN_URL, wait_until="domcontentloaded")

        # デバッグ用スクリーンショット（ログインページ到達確認）
        page.screenshot(path=f"debug_before_login_{account_id}.png")
        print(f"📷 debug_before_login_{account_id}.png saved")

        # 要素が出現するまで待ってから入力
        page.wait_for_selector("input[name='login_id']", timeout=60000)
        page.fill("input[name='login_id']", account_id)
        page.fill("input[name='password']", account_pass)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        # ログイン後のスクリーンショット（ログイン成否確認）
        page.screenshot(path=f"debug_after_login_{account_id}.png")
        print(f"📷 debug_after_login_{account_id}.png saved")

        # CSVダウンロード画面
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
    # 2アカウント分ダウンロード
    download_csv(ACCOUNTS[0][0], ACCOUNTS[0][1], "a.csv")
    time.sleep(3)
    download_csv(ACCOUNTS[1][0], ACCOUNTS[1][1], "b.csv")

    # 結合
    merge_csv(["a.csv", "b.csv"], "merged.csv")

    # GSSへ反映（ID固定）
    SHEET_ID = "1zfnTMt8RKAojSBZ51M3M2s73vTneFP8eyyVEYRtxlwM"
    upload_to_gss("merged.csv", SHEET_ID)
