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

def find_and_fill_login(page, account_id, account_pass):
    """通常のページとiframe両方でログインフォームを探す"""

    # --- name属性で試みる ---
    try:
        page.wait_for_selector("input[name='login_id']", timeout=5000)
        page.fill("input[name='login_id']", account_id)
        page.fill("input[name='password']", account_pass)
        page.click("button[type='submit']")
        print("✅ 通常ページ(name属性)でログイン")
        return
    except Exception:
        pass

    # --- id属性で試みる ---
    try:
        page.wait_for_selector("input#login_id", timeout=5000)
        page.fill("input#login_id", account_id)
        page.fill("input#password", account_pass)
        page.click("button[type='submit']")
        print("✅ 通常ページ(id属性)でログイン")
        return
    except Exception:
        pass

    # --- iframeの中を探す ---
    frames = page.frames
    print(f"フレーム数: {len(frames)}")
    for i, frame in enumerate(frames):
        print(f"  frame[{i}]: url={frame.url}")
        try:
            frame.wait_for_selector("input[name='login_id']", timeout=3000)
            frame.fill("input[name='login_id']", account_id)
            frame.fill("input[name='password']", account_pass)
            frame.click("button[type='submit']")
            print(f"✅ frame[{i}]でログイン")
            return
        except Exception:
            pass

    # --- ページのHTML構造をダンプしてデバッグ ---
    html = page.content()
    inputs = re.findall(r'<input[^>]*>', html, re.IGNORECASE)
    print(f"\n=== ページ内のinput要素 ({len(inputs)}個) ===")
    for inp in inputs:
        print(" ", inp)

    forms = re.findall(r'<form[^>]*>', html, re.IGNORECASE)
    print(f"\n=== form要素 ===")
    for f in forms:
        print(" ", f)

    raise Exception("❌ ログインフォームが見つかりませんでした。上記デバッグ情報を確認してください。")


def download_csv(account_id, account_pass, filename):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # ログインページへ移動
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        time.sleep(2)  # JS描画の余裕を持たせる

        # スクリーンショット（ページ到達確認）
        page.screenshot(path=f"debug_before_login_{account_id}.png")
        print(f"📷 debug_before_login_{account_id}.png saved")
        print(f"   URL: {page.url}")
        print(f"   Title: {page.title()}")

        # ログインフォームを探して入力
        find_and_fill_login(page, account_id, account_pass)

        page.wait_for_load_state("networkidle")

        # ログイン後スクリーンショット
        page.screenshot(path=f"debug_after_login_{account_id}.png")
        print(f"📷 debug_after_login_{account_id}.png saved")
        print(f"   URL after login: {page.url}")

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
    download_csv(ACCOUNTS[0][0], ACCOUNTS[0][1], "a.csv")
    time.sleep(3)
    download_csv(ACCOUNTS[1][0], ACCOUNTS[1][1], "b.csv")

    merge_csv(["a.csv", "b.csv"], "merged.csv")

    SHEET_ID = "1zfnTMt8RKAojSBZ51M3M2s73vTneFP8eyyVEYRtxlwM"
    upload_to_gss("merged.csv", SHEET_ID)
