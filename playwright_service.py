from playwright.sync_api import sync_playwright
import pandas as pd
import re
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from openpyxl import Workbook
import uuid
import asyncio

import asyncio
import sys

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

BASE_DIR = Path(__file__).resolve().parent
LOGINS_FILE = BASE_DIR / "data" / "marketlogins.xlsx"

MAX_WORKERS = 1
STAGGER_SEC = 5


# ─────────────────────────────────────────
# 🔹 COMMON LOGIN
# ─────────────────────────────────────────
def login(page, username, password):
    page.goto("https://www.t-mobiledealerordering.com/")

    page.fill("#userid", username)
    page.fill("#password", password)
    page.click("input[name='AgreeTerms']")
    page.click("a[name='login']")

    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(8000)  # <-- VERY IMPORTANT

    text = None
    print(f"[{username}] URL:", page.url)
    print(f"[{username}] Frames:", [f.url for f in page.frames])
    for frame in page.frames:
        try:
            locator = frame.locator("#credithold-tab-msg")
            if locator.count() > 0:
                text = locator.inner_text(timeout=5000)
                break



        except:
            continue

    if not text:
        print("⚠️ Login may not have loaded correctly")

# ─────────────────────────────────────────
# 🔹 ALLOCATION
# ─────────────────────────────────────────


#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=True)
#         page = browser.new_page()
#
#         try:
#             login(page, username, password)
#
#             frame = page.frame_locator("iframe")
#
#             frame.locator("//a[@onclick='show_catalog_view()']").click()
#             page.wait_for_timeout(5000)
#
#             items = frame.locator(".catalauge-item-holder").all()
#
#             devices = []
#
#             for item in items:
#                 try:
#                     name = item.locator(".cat-prd-dsc").inner_text()
#                     sku = item.locator(".cat-prd-id").inner_text()
#
#                     alloc_text = item.locator(".cat-prd-qty").inner_text()
#                     nums = re.findall(r'\d+', alloc_text)
#
#                     available = int(nums[0]) if nums else 0
#                     total = int(nums[1]) if len(nums) > 1 else 0
#
#                     if available > 0:
#                         devices.append({
#                             "Market": market,
#                             "SKU": sku,
#                             "Name": name,
#                             "Available": available,
#                             "Total": total,
#                         })
#                 except:
#                     continue
#
#             return devices
#
#         finally:
#             browser.close()
def scrape_allocation_page(page, row):
    market = row["Market"]
    username = row["Username"]
    password = row["Password"]

    login(page, username, password)

    # ───── 1. CLICK CATALOG ─────
    clicked = False

    for _ in range(15):
        for frame in page.frames:
            try:
                locator = frame.locator("//a[@onclick='show_catalog_view()']")
                if locator.count() > 0:
                    locator.first.click()
                    clicked = True
                    break
            except:
                continue

        if clicked:
            break
        time.sleep(1)

    if not clicked:
        print(f"[{market}] ❌ Catalog button not found")
        return []

    time.sleep(3)

    devices = []

    # ───── 2. GET CATALOG ITEMS ─────
    items = None

    for _ in range(15):
        for frame in page.frames:
            try:
                locator = frame.locator(".catalauge-item-holder")
                if locator.count() > 0:
                    items = locator.all()
                    break
            except:
                continue

        if items:
            break
        time.sleep(1)

    if not items:
        print(f"[{market}] ❌ No catalog items found")
        return []

    for item in items:
        try:
            name = item.locator(".cat-prd-dsc").inner_text()
            sku = item.locator(".cat-prd-id").inner_text()

            alloc_text = item.locator(".cat-prd-qty").inner_text()
            nums = re.findall(r'\d+', alloc_text)

            available = int(nums[0]) if nums else 0
            total = int(nums[1]) if len(nums) > 1 else 0

            if available > 0:
                devices.append({
                    "Market": market,
                    "SKU": sku,
                    "Name": name,
                    "Available": available,
                    "Total": total,
                    "Type": "Catalog"
                })
        except:
            continue

    # ───── 3. CLICK CPO ─────
    cpo_clicked = False

    for _ in range(15):
        for frame in page.frames:
            try:
                locator = frame.locator("a:has-text('CPO')")
                if locator.count() > 0:
                    locator.first.click()
                    cpo_clicked = True
                    break
            except:
                continue

        if cpo_clicked:
            break
        time.sleep(1)

    if not cpo_clicked:
        print(f"[{market}] ❌ CPO tab not found")
        return devices  # return catalog at least

    time.sleep(3)

    # ───── 4. GET CPO ITEMS ─────
    items = None

    for _ in range(15):
        for frame in page.frames:
            try:
                locator = frame.locator(".catalauge-item-holder")
                if locator.count() > 0:
                    items = locator.all()
                    break
            except:
                continue

        if items:
            break
        time.sleep(1)

    if not items:
        print(f"[{market}] ❌ No CPO items found")
        return devices

    for item in items:
        try:
            name = item.locator(".cat-prd-dsc").inner_text()
            sku = item.locator(".cat-prd-id").inner_text()

            alloc_text = item.locator(".cat-prd-qty").inner_text()
            nums = re.findall(r'\d+', alloc_text)

            available = int(nums[0]) if nums else 0
            total = int(nums[1]) if len(nums) > 1 else 0

            if available > 0:
                devices.append({
                    "Market": market,
                    "SKU": sku,
                    "Name": name,
                    "Available": available,
                    "Total": total,
                    "Type": "CPO"
                })
        except:
            continue

    return devices



# ─────────────────────────────────────────
# 🔹 AMOUNTS
# ─────────────────────────────────────────
def scrape_amount(market, username, password):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        try:
            login(page, username, password)

            content = page.content().lower()

            if "runtime error" in content:
                return {"Market": market, "Capacity": "ERROR"}

            if "password expired" in content:
                return {"Market": market, "Capacity": "PASSWORD EXPIRED"}
            print(f"[{market}] URL:", page.url)
            print(f"[{market}] Frames:", [f.url for f in page.frames])
            # Wait for iframes to load
            iframe_found = False

            for _ in range(10):  # try for ~10 seconds
                if len(page.frames) > 1:
                    iframe_found = True
                    break
                time.sleep(1)

            if not iframe_found:
                print(f"[{market}] ⚠️ No iframe found — likely login issue")
                return {"Market": market, "Capacity": "ERROR"}

                text = None

                for _ in range(15):  # retry for ~15 seconds
                    for frame in page.frames:
                        try:
                            locator = frame.locator("#credithold-tab-msg")
                            if locator.count() > 0:
                                text = locator.inner_text(timeout=2000)
                                if text.strip():
                                    break
                        except:
                            continue

                    if text:
                        break

                    time.sleep(1)  # wait and retry
            if not text:
                return {"Market": market, "Capacity": "NOT FOUND"}

            match = re.search(r'\$(\d[\d,\.]*)', text)

            if match:
                return {"Market": market, "Capacity": match.group(0)}

            return {"Market": market, "Capacity": "NOT FOUND"}

        finally:
            browser.close()


# ─────────────────────────────────────────
# 🔹 RUNNERS
# ─────────────────────────────────────────
def run_allocation(selected_markets=None):
    df = pd.read_excel(LOGINS_FILE)
    df.columns = df.columns.str.strip()

    if selected_markets:
        df = df[df["Market"].str.lower().isin([m.lower() for m in selected_markets])]

    rows = [row for _, row in df.iterrows()]
    results_map = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for row in rows:
            page = browser.new_page()
            try:
                devices = scrape_allocation_page(page, row)
                results_map[row["Market"]] = devices
            finally:
                page.close()

        browser.close()

    # Save Excel (same as before)
    output = BASE_DIR / f"data/allocation_{uuid.uuid4().hex}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.append(["Market", "SKU", "Name", "Available", "Total"])

    for market, devices in results_map.items():
        for d in devices:
            ws.append([d["Market"], d["SKU"], d["Name"], d["Available"], d["Total"]])

    wb.save(output)
    return str(output)

def scrape_amount_page(page, row):
    market = row["Market"]
    username = row["Username"]
    password = row["Password"]

    login(page, username, password)

    content = page.content().lower()

    if "runtime error" in content:
        return {"Market": market, "Capacity": "ERROR"}

    if "password expired" in content:
        return {"Market": market, "Capacity": "PASSWORD EXPIRED"}

    iframe_found = False

    for _ in range(10):  # try for ~10 seconds
        if len(page.frames) > 1:
            iframe_found = True
            break
        time.sleep(1)

    if not iframe_found:
        print(f"[{market}] ⚠️ No iframe found — likely login issue")
        return {"Market": market, "Capacity": "ERROR"}
    text = None

    for _ in range(15):  # retry for ~15 seconds
        for frame in page.frames:
            try:
                locator = frame.locator("#credithold-tab-msg")
                if locator.count() > 0:
                    text = locator.inner_text(timeout=2000)
                    if text.strip():
                        break
            except:
                continue

        if text:
            break

        time.sleep(1)  # wait and retry

    if not text:
        print("⚠️ Login may not have loaded correctly")

    match = re.search(r'\$(\d[\d,\.]*)', text)

    if match:
        return {"Market": market, "Capacity": match.group(0)}

    return {"Market": market, "Capacity": "NOT FOUND"}

def run_amounts(selected_markets=None):
    df = pd.read_excel(LOGINS_FILE)
    df.columns = df.columns.str.strip()

    if selected_markets:
        df = df[df["Market"].str.lower().isin([m.lower() for m in selected_markets])]

    rows = [row for _, row in df.iterrows()]
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        for row in rows:
            page = browser.new_page()
            try:
                result = scrape_amount_page(page, row)
                results.append(result)
            finally:
                page.close()

        browser.close()

    output = BASE_DIR / f"data/amounts_{uuid.uuid4().hex}.xlsx"
    pd.DataFrame(results).to_excel(output, index=False)

    return str(output)