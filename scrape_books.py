import logging
import random
import sys
import time
from datetime import date
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://books.toscrape.com/"
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


def fetch(url: str, session: requests.Session) -> BeautifulSoup:
    """ページを取得して BeautifulSoup を返す。接続エラー時は例外を再送出。"""
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        response.encoding = "utf-8"
        return BeautifulSoup(response.text, "html.parser")
    except requests.ConnectionError as e:
        logger.error(f"接続エラー: {e}")
        raise
    except requests.HTTPError as e:
        logger.error(f"HTTP エラー ({response.status_code}): {e}")
        raise
    except requests.RequestException as e:
        logger.error(f"リクエストエラー: {e}")
        raise


def scrape_all_books(base_url: str) -> list[dict]:
    rp = load_robots(base_url)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    books: list[dict] = []
    current_url = base_url
    page = 1

    while current_url:
        if not rp.can_fetch(USER_AGENT, current_url):
            logger.warning(f"robots.txt によりアクセス禁止のためスキップ: {current_url}")
            break

        logger.info(f"ページ {page} 取得中: {current_url}")
        soup = fetch(current_url, session)

        for article in soup.select("article.product_pod"):
            title = article.select_one("h3 a")["title"]
            price = article.select_one("p.price_color").text.strip()
            in_stock = "In stock" in article.select_one("p.availability").text
            books.append({"title": title, "price": price, "in_stock": in_stock})

        next_link = soup.select_one("li.next a")
        if next_link:
            current_url = urljoin(current_url, next_link["href"])
            page += 1
            delay = random.uniform(1, 3)
            logger.info(f"次のページまで {delay:.1f} 秒待機...")
            time.sleep(delay)
        else:
            current_url = None

    return books


def save_markdown(books: list[dict], path: str) -> None:
    today = date.today().isoformat()
    lines = [
        f"# Books Scraping Results — {today}",
        "",
        f"取得件数: **{len(books)} 冊**",
        "",
        "| # | タイトル | 価格 | 在庫状況 |",
        "|--:|---------|-----:|:-------:|",
    ]
    for i, book in enumerate(books, 1):
        stock = "在庫あり" if book["in_stock"] else "在庫なし"
        lines.append(f"| {i} | {book['title']} | {book['price']} | {stock} |")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    logger.info(f"結果を保存しました → {path}")


def main() -> None:
    logger.info("スクレイピングを開始します")
    try:
        books = scrape_all_books(BASE_URL)
    except requests.RequestException:
        logger.error("スクレイピングを中断しました")
        sys.exit(1)

    if not books:
        logger.error("書籍データを取得できませんでした")
        sys.exit(1)

    output = f"books_{date.today().strftime('%Y%m%d')}.md"
    save_markdown(books, output)
    logger.info(f"完了: {len(books)} 冊のデータを取得しました")


if __name__ == "__main__":
    main()
