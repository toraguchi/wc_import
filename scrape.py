import csv
import time
from playwright.sync_api import sync_playwright
import gspread
import os

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
        page.goto(LOGIN_URL)
        page.fill("input[name='login_id']", account_id)
        page.fill("input[name='password']", account_pass)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")

        # CSVダウンロード画面へ
        page.goto(CSV_URL)
        page.wait_for_load_state("networkidle")

        # ダウンロード
        with page.expect_download() as dl_info:
            page.click("a[href*='export']")
        download = dl_info.value
        download.save_as(filename)

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
    ws = sh.sheet1

    # シート全削除
    ws.clear()

    # CSV全文をアップ
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

    # GSSへ
    SHEET_ID = "1zfnTMt8RKAojSBZ51M3M2s73vTneFP8eyyVEYRtxlwM"
    upload_to_gss("merged.csv", SHEET_ID)
