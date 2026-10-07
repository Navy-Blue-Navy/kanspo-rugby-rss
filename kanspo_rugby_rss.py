import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime, parsedate_to_datetime
from urllib.parse import urljoin
import hashlib
import re


URL = "https://kanspo.jp/archives/category/rugby"
OUTPUT = Path(__file__).parent / "kanspo_rugby.xml"

JST = timezone(timedelta(hours=9))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/154.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
}


# --------------------------------------------------
# 既存RSS
# --------------------------------------------------

old_items = {}

if OUTPUT.exists():
    try:
        tree = ET.parse(OUTPUT)

        for item in tree.getroot().findall("./channel/item"):

            guid = item.findtext("guid", "")

            if guid:
                old_items[guid] = {
                    "title": item.findtext("title", ""),
                    "link": item.findtext("link", ""),
                    "description": item.findtext("description", ""),
                    "pubDate": item.findtext("pubDate", ""),
                    "guid": guid,
                }

    except Exception:
        old_items = {}


# --------------------------------------------------
# ページ取得
# --------------------------------------------------

response = requests.get(
    URL,
    headers=HEADERS,
    timeout=30
)

print("HTTP:", response.status_code)

response.raise_for_status()
response.encoding = response.apparent_encoding

soup = BeautifulSoup(
    response.text,
    "html.parser"
)


# --------------------------------------------------
# 記事取得
# --------------------------------------------------

current_items = []
seen_urls = set()

date_pattern = re.compile(
    r"20\d{2}年\d{1,2}月\d{1,2}日"
)


# h4が記事タイトル
for heading in soup.find_all(
    ["h2", "h3", "h4"]
):

    a = heading.find(
        "a",
        href=True
    )

    if not a:
        continue

    title = " ".join(
        a.stripped_strings
    ).strip()

    # ラグビー記事だけ
    if (
        "【ラグビー】" not in title
        and "〖ラグビー〗" not in title
    ):
        continue

    article_url = urljoin(
        URL,
        a["href"]
    )

    if article_url in seen_urls:
        continue

    # --------------------------------------------------
    # 記事カード内の日付を探す
    # --------------------------------------------------

    parent = heading
    date_text = None

    for _ in range(6):

        if parent is None:
            break

        text = " ".join(
            parent.stripped_strings
        )

        match = date_pattern.search(text)

        if match:
            date_text = match.group(0)
            break

        parent = parent.parent


    if not date_text:

        print(
            "日付取得失敗:",
            title
        )

        continue


    # --------------------------------------------------
    # 日付変換
    # --------------------------------------------------

    match = re.match(
        r"(\d{4})年(\d{1,2})月(\d{1,2})日",
        date_text
    )

    if not match:
        continue

    year = int(match.group(1))
    month = int(match.group(2))
    day = int(match.group(3))

    dt = datetime(
        year,
        month,
        day,
        12,
        0,
        0,
        tzinfo=JST
    )

    pub_date = format_datetime(dt)


    # --------------------------------------------------
    # GUID
    # --------------------------------------------------

    guid = hashlib.sha256(
        article_url.encode("utf-8")
    ).hexdigest()


    current_items.append(
        {
            "title": title,
            "link": article_url,
            "description": "カンスポ ラグビー",
            "pubDate": pub_date,
            "guid": guid,
        }
    )

    seen_urls.add(article_url)


# --------------------------------------------------
# 既存RSSと統合
# --------------------------------------------------

all_items = []
seen_guids = set()


for item in current_items:

    if item["guid"] not in seen_guids:

        all_items.append(item)
        seen_guids.add(item["guid"])


for guid, item in old_items.items():

    if guid not in seen_guids:

        all_items.append(item)
        seen_guids.add(guid)


# --------------------------------------------------
# 新しい順
# --------------------------------------------------

def get_date(item):

    try:
        return parsedate_to_datetime(
            item["pubDate"]
        )

    except Exception:
        return datetime.min.replace(
            tzinfo=timezone.utc
        )


all_items.sort(
    key=get_date,
    reverse=True
)

all_items = all_items[:300]


# --------------------------------------------------
# RSS作成
# --------------------------------------------------

rss = ET.Element(
    "rss",
    version="2.0"
)

channel = ET.SubElement(
    rss,
    "channel"
)

ET.SubElement(
    channel,
    "title"
).text = "カンスポ ラグビー"

ET.SubElement(
    channel,
    "link"
).text = URL

ET.SubElement(
    channel,
    "description"
).text = (
    "関大スポーツ編集局（カンスポ）のラグビー新着記事"
)

ET.SubElement(
    channel,
    "language"
).text = "ja"


for item in all_items:

    element = ET.SubElement(
        channel,
        "item"
    )

    ET.SubElement(
        element,
        "title"
    ).text = item["title"]

    ET.SubElement(
        element,
        "link"
    ).text = item["link"]

    ET.SubElement(
        element,
        "description"
    ).text = item["description"]

    ET.SubElement(
        element,
        "pubDate"
    ).text = item["pubDate"]

    guid_element = ET.SubElement(
        element,
        "guid"
    )

    guid_element.set(
        "isPermaLink",
        "false"
    )

    guid_element.text = item["guid"]


# --------------------------------------------------
# 保存
# --------------------------------------------------

tree = ET.ElementTree(rss)

ET.indent(
    tree,
    space="  "
)

tree.write(
    OUTPUT,
    encoding="utf-8",
    xml_declaration=True
)


# --------------------------------------------------
# 結果表示
# --------------------------------------------------

print()
print("RSS作成成功")
print(
    "今回取得:",
    len(current_items),
    "件"
)
print(
    "RSS保存件数:",
    len(all_items),
    "件"
)
print(
    "保存先:",
    OUTPUT
)

print()
print("取得記事:")

for i, item in enumerate(
    current_items,
    start=1
):

    print()
    print(
        f"[{i}] {item['title']}"
    )
    print(
        "    ",
        item["pubDate"]
    )
    print(
        "    ",
        item["link"]
    )