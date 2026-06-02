import logging
import random
import sys
import time
from datetime import date
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

BASE_URL = "https://quotes.toscrape.com"
START_PATH = "/js"
USER_AGENT = "python-automation-scraper/1.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_robots(base_url: str) -> RobotFileParser:
    rp = RobotFileParser()
    robots_url = urljoin(base_url, "/robots.txt")
    rp.set_url(robots_url)
    try:
        rp.read()
        logger.info("robots.txt を読み込みました")
    except Exception as e:
        logger.warning(f"robots.txt の読み込みに失敗しました（全パスを許可として続行）: {e}")
    return rp


def scrape_quotes(base_url: str, start_path: str) -> list[dict]:
    rp = load_robots(base_url)
    quotes: list[dict] = []
    today = date.today().strftime("%Y%m%d")
    screenshot_saved = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page(user_agent=USER_AGENT)

        current_path = start_path
        page_num = 1

        while current_path:
            current_url = urljoin(base_url, current_path)

            if not rp.can_fetch(USER_AGENT, current_url):
                logger.warning(f"robots.txt によりアクセス禁止のためスキップ: {current_url}")
                break

            logger.info(f"ページ {page_num} 取得中: {current_url}")

            try:
                page.goto(current_url, wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_selector(".quote", timeout=10_000)
            except PlaywrightTimeoutError as e:
                logger.error(f"タイムアウトエラー: {e}")
                raise
            except Exception as e:
                logger.error(f"接続エラー: {e}")
                raise

            if not screenshot_saved:
                screenshot_path = f"quotes_{today}.png"
                page.screenshot(path=screenshot_path, full_page=True)
                logger.info(f"スクリーンショットを保存しました → {screenshot_path}")
                screenshot_saved = True

            for el in page.query_selector_all(".quote"):
                text = el.query_selector(".text").inner_text().strip()
                author = el.query_selector(".author").inner_text().strip()
                quotes.append({"text": text, "author": author})

            next_link = page.query_selector("li.next a")
            if next_link:
                current_path = next_link.get_attribute("href")
                page_num += 1
                delay = random.uniform(1, 3)
                logger.info(f"次のページまで {delay:.1f} 秒待機...")
                time.sleep(delay)
            else:
                current_path = None

        browser.close()

    return quotes


def save_markdown(quotes: list[dict], path: str) -> None:
    today = date.today().isoformat()
    lines = [
        f"# Quotes Scraping Results — {today}",
        "",
        f"取得件数: **{len(quotes)} 件**",
        "",
        "---",
        "",
    ]
    for i, q in enumerate(quotes, 1):
        lines.append(f"### {i}. {q['author']}")
        lines.append("")
        lines.append(f"> {q['text']}")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"結果を保存しました → {path}")


def main() -> None:
    logger.info("スクレイピングを開始します")
    try:
        quotes = scrape_quotes(BASE_URL, START_PATH)
    except Exception:
        logger.error("スクレイピングを中断しました")
        sys.exit(1)

    if not quotes:
        logger.error("名言データを取得できませんでした")
        sys.exit(1)

    today = date.today().strftime("%Y%m%d")
    save_markdown(quotes, f"quotes_{today}.md")
    logger.info(f"完了: {len(quotes)} 件のデータを取得しました")


if __name__ == "__main__":
    main()
