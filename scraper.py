"""
ThreadGram Scraper - 用 Playwright 爬取 Threads 圖片
"""
import asyncio
import json
import re
import sys
from pathlib import Path
from datetime import datetime

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("請先安裝 playwright: pip install playwright && playwright install chromium")
    sys.exit(1)


async def scrape_threads(username: str, max_scrolls: int = 30):
    """爬取指定用戶的 Threads 圖片"""

    print(f"🚀 開始爬取 @{username} 的貼文...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        url = f"https://www.threads.net/@{username}"
        print(f"📍 前往 {url}")

        await page.goto(url, wait_until="networkidle")
        await asyncio.sleep(3)  # 等待初始載入

        # 收集所有圖片 URL
        all_images = set()
        last_count = 0
        no_new_count = 0

        for i in range(max_scrolls):
            # 抓取目前頁面的圖片
            images = await page.evaluate('''() => {
                const imgs = document.querySelectorAll('img');
                return Array.from(imgs).map(img => img.src).filter(src =>
                    src.includes('cdninstagram.com') &&
                    !src.includes('s150x150') &&
                    !src.includes('s64x64') &&
                    !src.includes('s32x32')
                );
            }''')

            for img in images:
                all_images.add(img)

            current_count = len(all_images)
            print(f"📸 滾動 {i+1}/{max_scrolls} - 已收集 {current_count} 張圖片", end='\r')

            # 檢查是否有新圖片
            if current_count == last_count:
                no_new_count += 1
                if no_new_count >= 5:
                    print(f"\n✅ 連續 5 次沒有新圖片，停止滾動")
                    break
            else:
                no_new_count = 0

            last_count = current_count

            # 滾動
            await page.evaluate('window.scrollBy(0, 1000)')
            await asyncio.sleep(1.5)

        await browser.close()

    print(f"\n🎉 共收集 {len(all_images)} 張圖片")

    # 分組圖片（根據 URL 中的數字模式）
    posts = group_images(list(all_images))

    # 儲存結果
    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"{username}.json"

    result = {
        "username": username,
        "scraped_at": datetime.now().isoformat(),
        "total_images": len(all_images),
        "total_posts": len(posts),
        "posts": posts
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"💾 已儲存至 {output_file}")
    print(f"📊 共 {len(posts)} 篇貼文")

    return result


def group_images(images: list) -> list:
    """將圖片按貼文分組"""

    # 按 URL 中的數字 ID 分組
    groups = {}

    for url in images:
        # 提取圖片 ID (第一組數字_第二組數字前9位)
        match = re.search(r'/(\d+)_(\d{9})', url)
        if match:
            post_id = match.group(2)  # 用第二組數字前9位作為貼文ID
            if post_id not in groups:
                groups[post_id] = []
            groups[post_id].append(url)
        else:
            # 無法識別的圖片獨立成組
            groups[f"single_{len(groups)}"] = [url]

    # 轉換為列表格式，每張圖片去重（不同尺寸）
    posts = []
    for post_id, urls in groups.items():
        # 去重同一張圖的不同尺寸
        unique_images = dedupe_sizes(urls)
        if unique_images:
            posts.append(unique_images)

    return posts


def dedupe_sizes(urls: list) -> list:
    """去除同一張圖的不同尺寸版本"""

    seen_ids = {}

    for url in urls:
        # 提取完整圖片 ID
        match = re.search(r'/(\d+_\d+_\d+_n)', url)
        if match:
            img_id = match.group(1)
            # 判斷優先級（沒有尺寸標記的優先）
            priority = 0
            if 's150x150' in url: priority = 1
            elif 's320x320' in url: priority = 2
            elif 's640x640' in url: priority = 3
            else: priority = 4

            if img_id not in seen_ids or priority > seen_ids[img_id][1]:
                seen_ids[img_id] = (url, priority)
        else:
            seen_ids[url] = (url, 0)

    return [url for url, _ in seen_ids.values()]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python scraper.py <username> [max_scrolls]")
        print("範例: python scraper.py boooooook__ 50")
        sys.exit(1)

    username = sys.argv[1].replace("@", "")
    max_scrolls = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    asyncio.run(scrape_threads(username, max_scrolls))
