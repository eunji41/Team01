# app.py
# 실행 방법:
# py -m pip install -r requirements.txt
# py -m streamlit run app.py

import os
import re
import time
import urllib.robotparser as robotparser
from collections import Counter
from urllib.parse import quote_plus, urljoin, urlparse, urlencode, parse_qs, urlunparse

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from wordcloud import WordCloud


# ============================================================
# Java / KoNLPy 설정
# ============================================================

JAVA_HOME_PATH = r"C:\Program Files\Java\jdk-25.0.2"
JVM_DLL_PATH = r"C:\Program Files\Java\jdk-25.0.2\bin\server\jvm.dll"

os.environ["JAVA_HOME"] = JAVA_HOME_PATH
os.environ["PATH"] = (
    JAVA_HOME_PATH + r"\bin;"
    + JAVA_HOME_PATH + r"\bin\server;"
    + os.environ.get("PATH", "")
)

try:
    import jpype
    from konlpy import jvm as konlpy_jvm
    from konlpy.tag import Okt

    KONLPY_IMPORT_ERROR = None

except Exception as e:
    jpype = None
    konlpy_jvm = None
    Okt = None
    KONLPY_IMPORT_ERROR = e


# ============================================================
# 기본 설정
# ============================================================

USER_AGENT = "ReviewCrawlerProject/1.0"
DEFAULT_SLEEP = 2.0
TIMEOUT = 10
MAX_PAGES = 10

BASE_REVIEW_COLUMNS = ["브랜드명", "제품명", "리뷰 내용", "평점", "날짜"]
REQUIRED_REVIEW_COLUMNS = ["브랜드명", "제품명", "리뷰 내용", "평점", "날짜", "수집 방식"]

BRAND_CONFIG = {
    "다이소": {
        "base_url": "https://prdm.daisomall.co.kr",
        "search_url": "https://prdm.daisomall.co.kr/search?keyword={query}",
        "product_link_keywords": ["SCR_PDP", "pdNo=", "goods", "product"],
        "review_card_selectors": [
            "li.review_item",
            "div.review_item",
            "div.review_cont",
            "div.review_area",
            "div[class*='review']",
            "li[class*='review']",
        ],
    }
}


# ============================================================
# 불용어 / 감성사전
# ============================================================

STOPWORDS = {
    "그리고", "그래서", "하지만", "정말", "너무", "많이", "조금", "약간",
    "진짜", "완전", "그냥", "계속", "사용", "제품", "구매", "리뷰",
    "배송", "오늘", "이번", "때문", "느낌", "정도", "부분", "하나",
    "있다", "없다", "같다", "이다", "하다", "되다", "보다", "저는",
    "제가", "이거", "그거", "거의", "일단", "다시", "처음"
}

POSITIVE_WORDS = {
    "좋다", "만족", "추천", "촉촉", "부드럽다", "가볍다", "깔끔",
    "예쁘다", "편하다", "괜찮다", "훌륭", "저렴", "빠르다", "산뜻",
    "재구매", "효과", "흡수", "순하다", "유용", "최고", "마음",
    "좋아하다", "시원하다", "깨끗하다", "자연스럽다", "강하다",
    "부담없다", "넉넉하다", "편리하다", "감사", "만족스럽다",
    "좋아요", "좋음", "추천해요", "괜찮아요", "만족해요"
}

NEGATIVE_WORDS = {
    "나쁘다", "별로", "실망", "불만", "건조", "무겁다", "끈적",
    "비싸다", "자극", "아프다", "부족", "늦다", "냄새", "트러블",
    "최악", "불편", "후회", "약하다", "깨지다", "문제", "답답하다",
    "따갑다", "밀리다", "번들거리다", "아쉽다", "어둡다", "불량",
    "별로예요", "별로에요", "실망이에요"
}

DEFAULT_PRODUCT_KEYWORDS = [
    "리들샷", "reedle", "샷", "vt", "브이티", "올리브영", "올영",
    "다이소", "에센스", "토너", "세럼", "앰플", "크림", "패드",
    "마스크", "선크림", "쿠션", "스킨", "로션", "화장품"
]

DEFAULT_REVIEW_KEYWORDS = [
    "사용", "써", "써봤", "써봄", "써보", "발라", "발림", "흡수",
    "흡수력", "효과", "후기", "리뷰", "구매", "재구매", "만족",
    "실망", "별로", "추천", "비추천", "피부", "트러블", "자극",
    "따갑", "따가", "순하", "건조", "촉촉", "민감", "끈적",
    "번들", "향", "냄새", "개선", "좋아요", "괜찮아요", "좋음",
    "가성비", "가격", "용량"
]

OFFTOPIC_KEYWORDS = [
    "언니", "오빠", "예뻐", "예쁘", "잘생", "귀여", "목소리", "편집",
    "영상", "구독", "좋아요누르고", "재밌", "웃겨", "춤", "노래",
    "사랑해요", "팬", "화이팅"
]


# ============================================================
# 공통 함수
# ============================================================

def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def clean_review_text(text) -> str:
    if pd.isna(text):
        return ""

    text = str(text)
    text = re.sub(r"[^가-힣a-zA-Z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def get_domain_root(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def check_robots_allowed(url: str) -> tuple:
    root_url = get_domain_root(url)
    robots_url = urljoin(root_url, "/robots.txt")

    rp = robotparser.RobotFileParser()
    rp.set_url(robots_url)

    try:
        rp.read()
        allowed = rp.can_fetch(USER_AGENT, url)
        delay = rp.crawl_delay(USER_AGENT)

        if delay is None:
            delay = DEFAULT_SLEEP

        if not allowed:
            return False, delay, f"robots.txt 정책상 접근이 허용되지 않습니다: {url}"

        return True, delay, "robots.txt 확인 완료"

    except Exception as e:
        return False, DEFAULT_SLEEP, f"robots.txt 확인 실패: {e}"


def safe_get_html(url: str) -> str:
    allowed, delay, message = check_robots_allowed(url)

    if not allowed:
        raise PermissionError(message)

    time.sleep(max(delay, DEFAULT_SLEEP))

    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }

    response = requests.get(url, headers=headers, timeout=TIMEOUT)
    response.raise_for_status()

    if response.encoding is None:
        response.encoding = "utf-8"

    return response.text


def get_html_with_selenium(url: str, wait_sec: float = 3.0) -> str:
    allowed, delay, message = check_robots_allowed(url)

    if not allowed:
        raise PermissionError(message)

    time.sleep(max(delay, DEFAULT_SLEEP))

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,2500")
    options.add_argument(f"user-agent={USER_AGENT}")

    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)
        time.sleep(wait_sec)
        return driver.page_source

    finally:
        driver.quit()


def append_page_param(url: str, page: int) -> str:
    parsed = urlparse(url)
    query_dict = parse_qs(parsed.query)

    query_dict["page"] = [str(page)]
    query_dict["pageIdx"] = [str(page)]

    new_query = urlencode(query_dict, doseq=True)

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment,
        )
    )


def convert_df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


def is_valid_url(url: str) -> bool:
    if not url:
        return False

    parsed = urlparse(url)
    return parsed.scheme in ["http", "https"] and bool(parsed.netloc)


def get_file_product_name(raw_df: pd.DataFrame, product_name: str) -> str:
    file_product_name = product_name.strip() if product_name else ""

    if not file_product_name and not raw_df.empty and "제품명" in raw_df.columns:
        file_product_name = str(raw_df["제품명"].iloc[0]).strip()

    if not file_product_name:
        file_product_name = "reviews"

    return re.sub(r'[\\/:*?"<>|]', "_", file_product_name)


def normalize_review_dataframe(
    df: pd.DataFrame,
    brand: str,
    product_name: str,
    source_method: str
) -> pd.DataFrame:
    df = df.copy()

    for col in BASE_REVIEW_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df["브랜드명"] = brand

    if product_name.strip():
        df["제품명"] = product_name.strip()

    df["수집 방식"] = source_method

    df = df[REQUIRED_REVIEW_COLUMNS]
    df = df.dropna(subset=["리뷰 내용"])
    df["리뷰 내용"] = df["리뷰 내용"].astype(str).str.strip()
    df = df[df["리뷰 내용"] != ""]
    df = df.drop_duplicates(subset=["브랜드명", "제품명", "리뷰 내용"])

    return df.reset_index(drop=True)


# ============================================================
# CSV 파일 업로드 함수
# ============================================================

def load_review_csv(uploaded_file, brand: str, product_name: str) -> pd.DataFrame:
    try:
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
    except UnicodeDecodeError:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, encoding="cp949")

    df.columns = df.columns.str.strip()

    missing = [col for col in BASE_REVIEW_COLUMNS if col not in df.columns]

    if missing:
        raise ValueError(f"CSV 파일에 필수 컬럼이 없습니다: {missing}")

    return normalize_review_dataframe(
        df=df,
        brand=brand,
        product_name=product_name,
        source_method="CSV 파일 업로드"
    )


# ============================================================
# 유튜브 댓글 수집 함수
# ============================================================

def extract_video_id(youtube_url: str) -> str:
    parsed = urlparse(youtube_url)

    if parsed.netloc in ["youtu.be"]:
        return parsed.path.lstrip("/")

    if "youtube.com" in parsed.netloc:
        query = parse_qs(parsed.query)

        if "v" in query:
            return query["v"][0]

        path_parts = parsed.path.strip("/").split("/")

        if len(path_parts) >= 2 and path_parts[0] in ["shorts", "embed"]:
            return path_parts[1]

    return ""


def build_keyword_list(product_name: str, extra_keywords_text: str) -> list:
    keywords = []

    if product_name:
        keywords.append(product_name.strip())

        split_tokens = re.split(r"[\s,/]+", product_name.strip())

        for token in split_tokens:
            token = token.strip()

            if len(token) >= 2:
                keywords.append(token)

    if extra_keywords_text:
        extra_tokens = [x.strip() for x in extra_keywords_text.split(",")]

        for token in extra_tokens:
            if token:
                keywords.append(token)

    return list(dict.fromkeys(keywords))


def is_product_review_comment(
    comment: str,
    product_keywords: list,
    review_keywords: list,
    offtopic_keywords: list,
    strict_mode: bool = True
) -> bool:
    if not comment:
        return False

    text = clean_review_text(comment).lower()

    if len(text) < 5:
        return False

    product_hit = any(keyword.lower() in text for keyword in product_keywords if keyword)
    review_hit = any(keyword.lower() in text for keyword in review_keywords if keyword)
    offtopic_hit = any(keyword.lower() in text for keyword in offtopic_keywords if keyword)

    if not (product_hit or review_hit):
        return False

    if offtopic_hit and not review_hit:
        return False

    if strict_mode and not review_hit:
        return False

    return True


def fetch_youtube_comments(
    api_key: str,
    youtube_url: str,
    brand: str,
    product_name: str,
    comment_count: int = 30,
    extra_keywords_text: str = "",
    strict_mode: bool = True
) -> tuple:
    video_id = extract_video_id(youtube_url)

    if not video_id:
        raise ValueError("유효한 유튜브 영상 URL에서 videoId를 찾지 못했습니다.")

    if not api_key.strip():
        raise ValueError("YouTube Data API Key를 입력해 주세요.")

    user_keywords = build_keyword_list(product_name, extra_keywords_text)
    product_keywords = list(dict.fromkeys(DEFAULT_PRODUCT_KEYWORDS + user_keywords))
    review_keywords = DEFAULT_REVIEW_KEYWORDS
    offtopic_keywords = OFFTOPIC_KEYWORDS

    base_url = "https://www.googleapis.com/youtube/v3/commentThreads"
    next_page_token = None
    raw_comments = []

    target_raw_count = max(comment_count * 4, 100)
    max_api_pages = 10

    for _ in range(max_api_pages):
        params = {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": 100,
            "order": "relevance",
            "textFormat": "plainText",
            "key": api_key,
        }

        if next_page_token:
            params["pageToken"] = next_page_token

        response = requests.get(base_url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            top_comment = snippet.get("topLevelComment", {})
            comment_snippet = top_comment.get("snippet", {})

            comment_text = (
                comment_snippet.get("textOriginal", "")
                or comment_snippet.get("textDisplay", "")
            )

            published_at = comment_snippet.get("publishedAt", "")

            raw_comments.append(
                {
                    "브랜드명": brand,
                    "제품명": product_name,
                    "리뷰 내용": clean_text(comment_text),
                    "평점": "",
                    "날짜": published_at[:10] if published_at else "",
                    "수집 방식": "유튜브 URL 업로드",
                }
            )

        if len(raw_comments) >= target_raw_count:
            break

        next_page_token = data.get("nextPageToken")

        if not next_page_token:
            break

        time.sleep(0.2)

    raw_df = pd.DataFrame(raw_comments, columns=REQUIRED_REVIEW_COLUMNS)
    raw_df = raw_df.drop_duplicates(subset=["리뷰 내용"]).reset_index(drop=True)

    if raw_df.empty:
        return raw_df, raw_df

    filtered_df = raw_df[
        raw_df["리뷰 내용"].apply(
            lambda x: is_product_review_comment(
                comment=x,
                product_keywords=product_keywords,
                review_keywords=review_keywords,
                offtopic_keywords=offtopic_keywords,
                strict_mode=strict_mode
            )
        )
    ].copy()

    filtered_df = filtered_df.drop_duplicates(subset=["리뷰 내용"]).reset_index(drop=True)
    filtered_df = filtered_df.head(comment_count)

    return raw_df, filtered_df


# ============================================================
# 웹 크롤링 함수
# ============================================================

def find_first_product_url(brand: str, product_name: str) -> str:
    if brand != "다이소":
        raise PermissionError(
            "현재 웹 크롤링은 다이소몰만 지원합니다. "
            "올리브영은 CSV 파일 업로드 또는 유튜브 URL 업로드 방식을 사용하세요."
        )

    config = BRAND_CONFIG[brand]
    query = quote_plus(product_name)
    search_url = config["search_url"].format(query=query)
    base_url = config["base_url"]

    try:
        html = safe_get_html(search_url)
    except Exception:
        html = get_html_with_selenium(search_url)

    soup = BeautifulSoup(html, "html.parser")
    product_urls = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag.get("href", "")
        full_url = urljoin(base_url, href)

        if any(keyword in full_url for keyword in config["product_link_keywords"]):
            product_urls.append(full_url)

    for tag in soup.find_all(attrs={"onclick": True}):
        onclick_text = tag.get("onclick", "")
        urls = re.findall(r"https?://[^\s'\"]+", onclick_text)

        for found_url in urls:
            if any(keyword in found_url for keyword in config["product_link_keywords"]):
                product_urls.append(found_url)

    product_urls = list(dict.fromkeys(product_urls))

    if not product_urls:
        raise ValueError(
            "제품명 자동 검색으로 상품 상세 URL을 찾지 못했습니다. "
            "다이소몰 상품 상세 URL을 직접 입력해 주세요."
        )

    return product_urls[0]


def extract_date(text: str) -> str:
    patterns = [
        r"20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2}",
        r"20\d{2}년\s*\d{1,2}월\s*\d{1,2}일",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            return clean_text(match.group())

    return ""


def extract_rating(text: str) -> str:
    patterns = [
        r"평점\s*([0-5](?:\.\d)?)",
        r"별점\s*([0-5](?:\.\d)?)",
        r"([0-5](?:\.\d)?)\s*점",
        r"([0-5](?:\.\d)?)/5",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            return match.group(1)

    return ""


def remove_noise_from_review(text: str) -> str:
    text = re.sub(r"20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2}", " ", text)
    text = re.sub(r"20\d{2}년\s*\d{1,2}월\s*\d{1,2}일", " ", text)
    text = re.sub(r"평점\s*[0-5](?:\.\d)?", " ", text)
    text = re.sub(r"별점\s*[0-5](?:\.\d)?", " ", text)
    text = re.sub(r"[0-5](?:\.\d)?\s*점", " ", text)

    return clean_text(text)


def parse_reviews_from_html(html: str, brand: str, product_name: str) -> list:
    config = BRAND_CONFIG[brand]
    soup = BeautifulSoup(html, "html.parser")

    review_cards = []

    for selector in config["review_card_selectors"]:
        cards = soup.select(selector)

        if cards:
            review_cards = cards
            break

    if not review_cards:
        review_cards = soup.find_all(
            lambda tag:
            tag.name in ["li", "div", "article"]
            and tag.get("class")
            and "review" in " ".join(tag.get("class")).lower()
        )

    reviews = []

    for card in review_cards:
        raw_text = clean_text(card.get_text(" ", strip=True))

        if len(raw_text) < 10:
            continue

        date = extract_date(raw_text)
        rating = extract_rating(raw_text)
        review_content = remove_noise_from_review(raw_text)

        if len(review_content) < 5:
            continue

        reviews.append(
            {
                "브랜드명": brand,
                "제품명": product_name,
                "리뷰 내용": review_content,
                "평점": rating,
                "날짜": date,
                "수집 방식": "웹 크롤링",
            }
        )

    return reviews
def deduplicate_reviews(reviews: list) -> list:
    unique_reviews = []
    seen = set()

    for review in reviews:
        key = review.get("리뷰 내용", "")

        if key and key not in seen:
            seen.add(key)
            unique_reviews.append(review)

    return unique_reviews


def crawl_reviews_with_requests(
    brand: str,
    product_name: str,
    review_count: int,
    product_url: str
) -> list:
    collected_reviews = []

    for page in range(1, MAX_PAGES + 1):
        if len(collected_reviews) >= review_count:
            break

        page_url = product_url if page == 1 else append_page_param(product_url, page)

        try:
            html = safe_get_html(page_url)
            page_reviews = parse_reviews_from_html(html, brand, product_name)

            before_count = len(collected_reviews)
            collected_reviews.extend(page_reviews)
            collected_reviews = deduplicate_reviews(collected_reviews)

            if len(collected_reviews) == before_count and page > 1:
                break

        except PermissionError:
            raise

        except Exception:
            break

    return collected_reviews[:review_count]


def click_review_tab_if_exists(driver) -> None:
    possible_texts = ["리뷰", "상품후기", "후기"]

    for text in possible_texts:
        elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{text}')]")

        for element in elements:
            try:
                driver.execute_script("arguments[0].click();", element)
                time.sleep(2)
                return

            except Exception:
                continue


def click_next_review_page_if_exists(driver) -> bool:
    next_selectors = [
        "a.next",
        "button.next",
        "a[class*='next']",
        "button[class*='next']",
    ]

    for selector in next_selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)

        for element in elements:
            try:
                driver.execute_script("arguments[0].click();", element)
                time.sleep(2)
                return True

            except Exception:
                continue

    for text in ["다음", ">"]:
        elements = driver.find_elements(By.XPATH, f"//*[contains(text(), '{text}')]")

        for element in elements:
            try:
                driver.execute_script("arguments[0].click();", element)
                time.sleep(2)
                return True

            except Exception:
                continue

    return False


def crawl_reviews_with_selenium(
    brand: str,
    product_name: str,
    review_count: int,
    product_url: str
) -> list:
    allowed, delay, message = check_robots_allowed(product_url)

    if not allowed:
        raise PermissionError(message)

    time.sleep(max(delay, DEFAULT_SLEEP))

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,2500")
    options.add_argument(f"user-agent={USER_AGENT}")

    driver = webdriver.Chrome(options=options)
    collected_reviews = []

    try:
        driver.get(product_url)
        time.sleep(3)

        click_review_tab_if_exists(driver)

        for _ in range(MAX_PAGES):
            if len(collected_reviews) >= review_count:
                break

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

            html = driver.page_source
            page_reviews = parse_reviews_from_html(html, brand, product_name)

            before_count = len(collected_reviews)
            collected_reviews.extend(page_reviews)
            collected_reviews = deduplicate_reviews(collected_reviews)

            if len(collected_reviews) >= review_count:
                break

            moved = click_next_review_page_if_exists(driver)

            if not moved and len(collected_reviews) == before_count:
                break

        return collected_reviews[:review_count]

    finally:
        driver.quit()


def crawl_web_reviews(
    brand: str,
    product_name: str,
    review_count: int,
    product_url_input: str = ""
) -> pd.DataFrame:
    if brand != "다이소":
        raise PermissionError(
            "현재 웹 크롤링은 다이소몰만 지원합니다. "
            "올리브영은 CSV 파일 업로드 또는 유튜브 URL 업로드 방식을 사용하세요."
        )

    product_url_input = product_url_input.strip()

    if product_url_input:
        if not is_valid_url(product_url_input):
            raise ValueError("상품 상세 URL 형식이 올바르지 않습니다. https:// 로 시작하는 URL을 입력하세요.")

        product_url = product_url_input

    else:
        product_url = find_first_product_url(brand, product_name)

    reviews = []

    try:
        reviews = crawl_reviews_with_requests(
            brand=brand,
            product_name=product_name,
            review_count=review_count,
            product_url=product_url,
        )

    except PermissionError:
        raise

    except Exception:
        reviews = []

    if len(reviews) < review_count:
        try:
            selenium_reviews = crawl_reviews_with_selenium(
                brand=brand,
                product_name=product_name,
                review_count=review_count,
                product_url=product_url,
            )

            reviews.extend(selenium_reviews)
            reviews = deduplicate_reviews(reviews)

        except PermissionError:
            raise

        except Exception:
            pass

    raw_df = pd.DataFrame(
        reviews[:review_count],
        columns=REQUIRED_REVIEW_COLUMNS
    )

    raw_df = normalize_review_dataframe(
        df=raw_df,
        brand=brand,
        product_name=product_name,
        source_method="웹 크롤링"
    )

    return raw_df


# ============================================================
# 전처리 함수
# ============================================================

def init_okt():
    if Okt is None:
        raise ImportError(
            f"konlpy 또는 JPype1을 불러오지 못했습니다. 오류 내용: {KONLPY_IMPORT_ERROR}"
        )

    if jpype is None or konlpy_jvm is None:
        raise ImportError("JPype 또는 KoNLPy JVM 모듈을 사용할 수 없습니다.")

    if not os.path.exists(JVM_DLL_PATH):
        raise FileNotFoundError(
            f"jvm.dll 파일을 찾지 못했습니다. 현재 설정된 경로: {JVM_DLL_PATH}"
        )

    try:
        if not jpype.isJVMStarted():
            konlpy_jvm.init_jvm(jvmpath=JVM_DLL_PATH)

        return Okt()

    except Exception as e:
        raise RuntimeError(
            "Okt 초기화 중 오류가 발생했습니다. "
            f"현재 JAVA_HOME: {os.environ.get('JAVA_HOME')}, "
            f"현재 JVM_DLL_PATH: {JVM_DLL_PATH}, "
            f"오류 내용: {e}"
        )


def simple_tokenize(text: str) -> list:
    if not text:
        return []
    return text.split()


def extract_nouns_adjectives(text: str, okt) -> list:
    if not text:
        return []

    try:
        pos_result = okt.pos(text, stem=True)

        words = [
            word for word, tag in pos_result
            if tag in ["Noun", "Adjective"]
        ]

        return words

    except Exception:
        return []


def remove_stopwords(tokens: list) -> list:
    return [
        token for token in tokens
        if token not in STOPWORDS and len(token) > 1
    ]


def preprocess_reviews(df: pd.DataFrame, use_simple_if_okt_error: bool = True) -> pd.DataFrame:
    processed_df = df.copy()

    if "리뷰 내용" not in processed_df.columns:
        raise ValueError("'리뷰 내용' 컬럼이 없습니다.")

    processed_df = processed_df.dropna(subset=["리뷰 내용"])
    processed_df = processed_df.drop_duplicates(subset=["브랜드명", "제품명", "리뷰 내용"])

    processed_df["전처리 전 리뷰"] = processed_df["리뷰 내용"]
    processed_df["정제 리뷰"] = processed_df["리뷰 내용"].apply(clean_review_text)
    processed_df = processed_df[processed_df["정제 리뷰"].str.len() > 0]

    okt_error_message = ""

    try:
        okt = init_okt()

        processed_df["형태소"] = processed_df["정제 리뷰"].apply(
            lambda x: extract_nouns_adjectives(x, okt)
        )

        processed_df["분석 방식"] = "Okt"

    except Exception as e:
        okt_error_message = str(e)

        if not use_simple_if_okt_error:
            raise

        processed_df["형태소"] = processed_df["정제 리뷰"].apply(simple_tokenize)
        processed_df["분석 방식"] = "간단 토큰화"

    processed_df["전처리 결과"] = processed_df["형태소"].apply(remove_stopwords)

    processed_df["전처리 결과 문자열"] = processed_df["전처리 결과"].apply(
        lambda tokens: " ".join(tokens)
    )

    processed_df.attrs["okt_error_message"] = okt_error_message

    return processed_df.reset_index(drop=True)


def get_word_frequency(processed_df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    all_tokens = []

    for tokens in processed_df["전처리 결과"]:
        if isinstance(tokens, list):
            all_tokens.extend(tokens)

    counter = Counter(all_tokens)

    return pd.DataFrame(
        counter.most_common(top_n),
        columns=["단어", "빈도"]
    )


# ============================================================
# 감성분석 함수
# ============================================================

def calculate_sentiment_score(tokens: list) -> int:
    if not isinstance(tokens, list):
        return 0

    positive_count = sum(1 for token in tokens if token in POSITIVE_WORDS)
    negative_count = sum(1 for token in tokens if token in NEGATIVE_WORDS)

    return positive_count - negative_count


def classify_sentiment(score: int) -> str:
    if score > 0:
        return "긍정"

    elif score < 0:
        return "부정"

    else:
        return "중립"


def analyze_sentiment(processed_df: pd.DataFrame) -> pd.DataFrame:
    result_df = processed_df.copy()

    result_df["감성 점수"] = result_df["전처리 결과"].apply(calculate_sentiment_score)
    result_df["감성 분류"] = result_df["감성 점수"].apply(classify_sentiment)

    return result_df


def calculate_brand_positive_ratio(sentiment_df: pd.DataFrame) -> pd.DataFrame:
    if sentiment_df.empty:
        return pd.DataFrame(columns=["브랜드명", "전체 리뷰 수", "긍정 리뷰 수", "긍정 비율"])

    summary = sentiment_df.groupby("브랜드명").agg(
        전체_리뷰_수=("감성 분류", "count"),
        긍정_리뷰_수=("감성 분류", lambda x: (x == "긍정").sum())
    ).reset_index()

    summary["긍정 비율"] = (
        summary["긍정_리뷰_수"] / summary["전체_리뷰_수"] * 100
    ).round(2)

    summary = summary.rename(
        columns={
            "전체_리뷰_수": "전체 리뷰 수",
            "긍정_리뷰_수": "긍정 리뷰 수"
        }
    )

    return summary


def calculate_product_avg_sentiment(sentiment_df: pd.DataFrame) -> pd.DataFrame:
    if sentiment_df.empty:
        return pd.DataFrame(columns=["브랜드명", "제품명", "평균 감성 점수"])

    summary = sentiment_df.groupby(["브랜드명", "제품명"]).agg(
        평균_감성_점수=("감성 점수", "mean")
    ).reset_index()

    summary["평균_감성_점수"] = summary["평균_감성_점수"].round(2)

    summary = summary.rename(
        columns={"평균_감성_점수": "평균 감성 점수"}
    )

    return summary


def get_top_keywords_from_tokens(sentiment_df: pd.DataFrame, top_n: int = 5) -> str:
    all_tokens = []

    for tokens in sentiment_df["전처리 결과"]:
        if isinstance(tokens, list):
            all_tokens.extend(tokens)

    counter = Counter(all_tokens)
    keywords = [word for word, count in counter.most_common(top_n)]

    return ", ".join(keywords)


def create_analysis_summary_row(sentiment_df: pd.DataFrame) -> pd.DataFrame:
    if sentiment_df.empty:
        return pd.DataFrame()

    rows = []

    group_cols = ["브랜드명", "제품명", "수집 방식"]

    for (brand, product, method), group_df in sentiment_df.groupby(group_cols):
        total_count = len(group_df)
        positive_count = (group_df["감성 분류"] == "긍정").sum()
        negative_count = (group_df["감성 분류"] == "부정").sum()
        neutral_count = (group_df["감성 분류"] == "중립").sum()

        positive_ratio = round(positive_count / total_count * 100, 2) if total_count else 0
        negative_ratio = round(negative_count / total_count * 100, 2) if total_count else 0
        neutral_ratio = round(neutral_count / total_count * 100, 2) if total_count else 0
        avg_score = round(group_df["감성 점수"].mean(), 2) if total_count else 0
        top_keywords = get_top_keywords_from_tokens(group_df, top_n=5)

        rows.append(
            {
                "분석 번호": "",
                "분석 시간": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                "브랜드명": brand,
                "제품명": product,
                "수집 방식": method,
                "분석 리뷰 수": total_count,
                "긍정 수": positive_count,
                "부정 수": negative_count,
                "중립 수": neutral_count,
                "긍정 비율(%)": positive_ratio,
                "부정 비율(%)": negative_ratio,
                "중립 비율(%)": neutral_ratio,
                "평균 감성 점수": avg_score,
                "상위 키워드": top_keywords,
            }
        )

    summary_df = pd.DataFrame(rows)

    return summary_df


def add_current_analysis_to_summary(summary_df: pd.DataFrame) -> pd.DataFrame:
    current_summary = create_analysis_summary_row(summary_df)

    if current_summary.empty:
        return st.session_state.analysis_history_df

    history_df = st.session_state.analysis_history_df.copy()

    if history_df.empty:
        combined_df = current_summary.copy()
    else:
        combined_df = pd.concat([history_df, current_summary], ignore_index=True)

    combined_df["분석 번호"] = range(1, len(combined_df) + 1)

    return combined_df.reset_index(drop=True)


# ============================================================
# 시각화 함수
# ============================================================

def get_korean_font_path():
    font_candidates = [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/gulim.ttc",
        "/System/Library/Fonts/AppleGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]

    for font_path in font_candidates:
        if os.path.exists(font_path):
            return font_path

    return None


def setup_korean_font():
    font_path = get_korean_font_path()

    if font_path:
        font_name = fm.FontProperties(fname=font_path).get_name()
        plt.rcParams["font.family"] = font_name

    else:
        plt.rcParams["font.family"] = "DejaVu Sans"

    plt.rcParams["axes.unicode_minus"] = False

    return font_path


def get_brand_word_counters(processed_df: pd.DataFrame) -> dict:
    brand_counters = {}

    if processed_df.empty:
        return brand_counters

    for brand_name, group_df in processed_df.groupby("브랜드명"):
        words = []

        for tokens in group_df["전처리 결과"]:
            if isinstance(tokens, list):
                words.extend(tokens)

        brand_counters[brand_name] = Counter(words)

    return brand_counters


def counter_to_dataframe(counter: Counter, top_n: int = 20) -> pd.DataFrame:
    return pd.DataFrame(
        counter.most_common(top_n),
        columns=["단어", "빈도"]
    )


def plot_word_frequency_bar(word_freq_df: pd.DataFrame, brand_name: str):
    fig, ax = plt.subplots(figsize=(10, 5))

    if word_freq_df.empty:
        ax.text(0.5, 0.5, "표시할 단어가 없습니다.", ha="center", va="center")
        ax.axis("off")
        return fig

    ax.bar(word_freq_df["단어"], word_freq_df["빈도"])
    ax.set_title(f"{brand_name} 상위 단어 빈도")
    ax.set_xlabel("단어")
    ax.set_ylabel("빈도")

    for label in ax.get_xticklabels():
        label.set_rotation(45)
        label.set_ha("right")

    fig.tight_layout()

    return fig


def plot_brand_wordcloud(counter: Counter, brand_name: str, font_path: str):
    fig, ax = plt.subplots(figsize=(10, 6))

    if not counter:
        ax.text(0.5, 0.5, "표시할 단어가 없습니다.", ha="center", va="center")
        ax.axis("off")
        return fig

    if font_path is None:
        ax.text(
            0.5,
            0.5,
            "한글 폰트 파일을 찾지 못했습니다.",
            ha="center",
            va="center"
        )
        ax.axis("off")
        return fig

    wordcloud = WordCloud(
        font_path=font_path,
        width=800,
        height=400,
        background_color="white"
    ).generate_from_frequencies(counter)

    ax.imshow(wordcloud, interpolation="bilinear")
    ax.set_title(f"{brand_name} 워드클라우드")
    ax.axis("off")

    fig.tight_layout()

    return fig


def calculate_sentiment_ratio(sentiment_df: pd.DataFrame) -> pd.DataFrame:
    if sentiment_df.empty:
        return pd.DataFrame(columns=["브랜드명", "감성 분류", "개수", "비율"])

    ratio_df = sentiment_df.groupby(["브랜드명", "감성 분류"]).size().reset_index(name="개수")

    ratio_df["비율"] = ratio_df.groupby("브랜드명")["개수"].transform(
        lambda x: (x / x.sum() * 100).round(2)
    )

    return ratio_df


def plot_sentiment_ratio_bar(ratio_df: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(10, 5))

    if ratio_df.empty:
        ax.text(0.5, 0.5, "표시할 감성 비율 데이터가 없습니다.", ha="center", va="center")
        ax.axis("off")
        return fig

    pivot_df = ratio_df.pivot(
        index="브랜드명",
        columns="감성 분류",
        values="비율"
    ).fillna(0)

    for col in ["긍정", "부정", "중립"]:
        if col not in pivot_df.columns:
            pivot_df[col] = 0

    pivot_df = pivot_df[["긍정", "부정", "중립"]]
    pivot_df.plot(kind="bar", ax=ax)

    ax.set_title("브랜드별 긍정/부정/중립 비율")
    ax.set_xlabel("브랜드")
    ax.set_ylabel("비율(%)")
    ax.legend(title="감성 분류")

    for label in ax.get_xticklabels():
        label.set_rotation(0)

    fig.tight_layout()

    return fig


# ============================================================
# Streamlit 화면
# ============================================================

st.set_page_config(
    page_title="다이소 vs 올리브영 리뷰 분석",
    layout="wide"
)

st.title("다이소 vs 올리브영 리뷰 분석 프로그램")

st.caption(
    "수집 방식을 선택하여 리뷰 데이터를 수집한 뒤 "
    "전처리, 감성분석, 시각화, 분석 결과 누적표를 확인합니다."
)


with st.expander("Java / KoNLPy 환경 확인", expanded=False):
    st.write("현재 JAVA_HOME:", os.environ.get("JAVA_HOME"))
    st.write("현재 JVM_DLL_PATH:", JVM_DLL_PATH)
    st.write("jvm.dll 존재 여부:", os.path.exists(JVM_DLL_PATH))

    if jpype is not None:
        try:
            st.write("JPype JVM 시작 여부:", jpype.isJVMStarted())

        except Exception as e:
            st.write("JPype 상태 확인 오류:", e)

    else:
        st.write("JPype import 실패:", KONLPY_IMPORT_ERROR)


# ============================================================
# session_state 초기화
# ============================================================

if "raw_df" not in st.session_state:
    st.session_state.raw_df = pd.DataFrame()

if "processed_df" not in st.session_state:
    st.session_state.processed_df = pd.DataFrame()

if "sentiment_df" not in st.session_state:
    st.session_state.sentiment_df = pd.DataFrame()

if "youtube_raw_df" not in st.session_state:
    st.session_state.youtube_raw_df = pd.DataFrame()

if "analysis_history_df" not in st.session_state:
    st.session_state.analysis_history_df = pd.DataFrame()

if "selection_key" not in st.session_state:
    st.session_state.selection_key = ""


# ============================================================
# 입력 영역
# ============================================================

brand = st.selectbox(
    "1. 브랜드 선택",
    ["다이소", "올리브영"]
)

collection_method = st.selectbox(
    "2. 수집 방식 선택",
    ["웹 크롤링", "CSV 파일 업로드", "유튜브 URL 업로드"]
)

current_selection_key = f"{brand}_{collection_method}"

if st.session_state.selection_key != current_selection_key:
    st.session_state.selection_key = current_selection_key
    st.session_state.raw_df = pd.DataFrame()
    st.session_state.processed_df = pd.DataFrame()
    st.session_state.sentiment_df = pd.DataFrame()
    st.session_state.youtube_raw_df = pd.DataFrame()

product_name = ""


# ============================================================
# 수집 방식 1: 웹 크롤링
# ============================================================

if collection_method == "웹 크롤링":
    st.subheader("웹 크롤링 방식")

    if brand == "올리브영":
        st.warning(
            "현재 웹 크롤링은 다이소몰만 지원합니다. "
            "올리브영은 CSV 파일 업로드 또는 유튜브 URL 업로드 방식을 사용하세요."
        )

    product_name = st.text_input(
        "3. 제품명 입력",
        placeholder="예: VT 리들샷 300 앰플"
    )

    product_url_input = st.text_input(
        "4. 상품 상세 URL 입력 선택",
        placeholder="자동 검색이 안 될 경우 상품 상세 URL을 직접 붙여넣으세요"
    )

    review_count = st.slider(
        "5. 리뷰 개수 선택",
        min_value=10,
        max_value=100,
        value=20,
        step=10
    )

    run_button = st.button(
        "6. 웹 크롤링 실행",
        disabled=(brand == "올리브영")
    )

    if run_button:
        if not product_name.strip():
            st.warning("제품명을 입력해 주세요.")

        else:
            try:
                with st.spinner(f"{brand} 리뷰를 수집하고 있습니다."):
                    raw_df = crawl_web_reviews(
                        brand=brand,
                        product_name=product_name.strip(),
                        review_count=review_count,
                        product_url_input=product_url_input.strip()
                    )

                st.session_state.raw_df = raw_df
                st.session_state.processed_df = pd.DataFrame()
                st.session_state.sentiment_df = pd.DataFrame()

                if raw_df.empty:
                    st.warning("수집된 리뷰가 없습니다. 상품 URL 직접 입력 또는 CSV 업로드 방식을 사용해 보세요.")

                else:
                    st.success(f"{brand} 리뷰 {len(raw_df)}개를 수집했습니다.")

            except ValueError as e:
                st.error(str(e))
                st.info("자동 검색이 실패하면 상품 상세 URL을 직접 입력하세요.")

            except PermissionError as e:
                st.error(str(e))
                st.info("robots.txt 또는 사이트 정책상 자동 수집이 제한된 경우입니다.")

            except requests.exceptions.RequestException as e:
                st.error(f"요청 중 오류가 발생했습니다: {e}")

            except Exception as e:
                st.error(f"크롤링 중 예외가 발생했습니다: {e}")


# ============================================================
# 수집 방식 2: CSV 파일 업로드
# ============================================================

elif collection_method == "CSV 파일 업로드":
    st.subheader("CSV 파일 업로드 방식")

    st.markdown(
        """
        CSV 파일은 아래 컬럼명을 포함해야 합니다.

        `브랜드명, 제품명, 리뷰 내용, 평점, 날짜`

        단, `브랜드명`과 `제품명`은 화면에서 선택/입력한 값으로 다시 정리됩니다.
        """
    )

    product_name = st.text_input(
        "3. 제품명 입력",
        placeholder="예: VT 리들샷 300"
    )

    uploaded_file = st.file_uploader(
        "4. 리뷰 CSV 파일 업로드",
        type=["csv"]
    )

    if uploaded_file is not None:
        if not product_name.strip():
            st.warning("제품명을 입력해 주세요.")

        else:
            try:
                raw_df = load_review_csv(
                    uploaded_file=uploaded_file,
                    brand=brand,
                    product_name=product_name.strip()
                )

                st.session_state.raw_df = raw_df
                st.session_state.processed_df = pd.DataFrame()
                st.session_state.sentiment_df = pd.DataFrame()

                st.success(f"{brand} CSV 데이터 {len(raw_df)}개를 불러왔습니다.")

            except Exception as e:
                st.error(f"CSV 파일을 불러오는 중 오류가 발생했습니다: {e}")

    with st.expander("CSV 예시 보기"):
        example_df = pd.DataFrame(
            {
                "브랜드명": [brand, brand, brand],
                "제품명": ["VT 리들샷 300", "VT 리들샷 300", "VT 리들샷 300"],
                "리뷰 내용": [
                    "흡수가 빠르고 사용감이 좋아요",
                    "조금 자극이 있어서 아쉬웠어요",
                    "가격 대비 무난하고 촉촉합니다"
                ],
                "평점": [5, 3, 4],
                "날짜": ["2026-05-01", "2026-05-02", "2026-05-03"]
            }
        )

        st.dataframe(example_df, use_container_width=True)

        st.download_button(
            label="CSV 예시 파일 다운로드",
            data=convert_df_to_csv_bytes(example_df),
            file_name=f"{brand}_review_example.csv",
            mime="text/csv"
        )


# ============================================================
# 수집 방식 3: 유튜브 URL 업로드
# ============================================================

else:
    st.subheader("유튜브 URL 업로드 방식")

    st.info(
        "유튜브 영상 댓글을 수집한 뒤 제품 관련 또는 후기 관련 키워드가 포함된 댓글만 남깁니다. "
        "'언니 너무 예뻐요', '영상 잘 봤어요' 같은 댓글은 제외되도록 설계했습니다."
    )

    product_name = st.text_input(
        "3. 제품명 입력",
        placeholder="예: VT 리들샷 300"
    )

    youtube_url = st.text_input(
        "4. 유튜브 영상 URL 입력",
        placeholder="예: https://www.youtube.com/watch?v=2jw-ii-yRtc"
    )

    youtube_api_key = st.text_input(
        "5. YouTube Data API Key 입력",
        type="password",
        placeholder="Google Cloud에서 발급한 API Key"
    )

    comment_count = st.slider(
        "6. 최종 분석에 사용할 댓글 개수 선택",
        min_value=10,
        max_value=100,
        value=30,
        step=10
    )

    extra_keywords_text = st.text_input(
        "7. 추가 제품 키워드 입력",
        placeholder="예: PDRN, 에센스, 민감성, 앰플"
    )

    strict_mode = st.checkbox(
        "후기성 키워드가 있는 댓글만 남기기",
        value=True
    )

    run_button = st.button("8. 유튜브 댓글 수집 실행")

    if run_button:
        if not product_name.strip():
            st.warning("제품명을 입력해 주세요.")

        elif not youtube_url.strip():
            st.warning("유튜브 영상 URL을 입력해 주세요.")

        elif not youtube_api_key.strip():
            st.warning("YouTube Data API Key를 입력해 주세요.")

        else:
            try:
                with st.spinner("유튜브 댓글을 수집하고 필터링하고 있습니다."):
                    youtube_raw_df, filtered_df = fetch_youtube_comments(
                        api_key=youtube_api_key.strip(),
                        youtube_url=youtube_url.strip(),
                        brand=brand,
                        product_name=product_name.strip(),
                        comment_count=comment_count,
                        extra_keywords_text=extra_keywords_text.strip(),
                        strict_mode=strict_mode
                    )

                st.session_state.youtube_raw_df = youtube_raw_df
                st.session_state.raw_df = filtered_df
                st.session_state.processed_df = pd.DataFrame()
                st.session_state.sentiment_df = pd.DataFrame()

                st.success(
                    f"원본 댓글 {len(youtube_raw_df)}개 수집 완료 / "
                    f"제품·후기 관련 댓글 {len(filtered_df)}개 필터링 완료"
                )

                if filtered_df.empty:
                    st.warning("필터링 후 남은 댓글이 없습니다. 추가 키워드를 넣거나 엄격 필터를 해제해 보세요.")

            except requests.exceptions.RequestException as e:
                st.error(f"YouTube API 요청 중 오류가 발생했습니다: {e}")

            except Exception as e:
                st.error(f"유튜브 댓글 수집 중 오류가 발생했습니다: {e}")

    with st.expander("유튜브 댓글 필터링 기준 설명"):
        st.write("제외하려는 댓글 예시")
        st.write("- 언니 너무 예뻐요")
        st.write("- 영상 잘 봤어요")
        st.write("- 편집 너무 좋아요")
        st.write("")
        st.write("남기려는 댓글 예시")
        st.write("- 리들샷 써봤는데 자극은 있지만 효과는 좋아요")
        st.write("- 피부가 민감한 편인데 따갑긴 해도 괜찮았어요")
        st.write("- 재구매 의사는 있는데 가격은 조금 아쉬워요")

    if not st.session_state.youtube_raw_df.empty:
        with st.expander("유튜브 원본 댓글 보기"):
            st.dataframe(st.session_state.youtube_raw_df.head(50), use_container_width=True)


# ============================================================
# 원본 데이터 출력
# ============================================================

raw_df = st.session_state.raw_df
file_product_name = get_file_product_name(raw_df, product_name)

if not raw_df.empty:
    st.subheader("수집 데이터 출력")
    st.write(f"총 분석 대상 개수: {len(raw_df)}개")

    with st.expander("원본 수집 데이터 보기", expanded=True):
        st.dataframe(raw_df.head(20), use_container_width=True)

    raw_csv_bytes = convert_df_to_csv_bytes(raw_df)

    st.download_button(
        label="원본 리뷰/댓글 CSV 저장",
        data=raw_csv_bytes,
        file_name=f"{brand}_{file_product_name}_raw_reviews.csv",
        mime="text/csv"
    )

    st.subheader("데이터 전처리 및 감성분석")

    use_simple_if_okt_error = st.checkbox(
        "Okt 오류 시 간단 토큰화로 대체",
        value=True
    )

    preprocess_button = st.button("전처리 및 감성분석 실행")

    if preprocess_button:
        try:
            with st.spinner("전처리와 감성분석을 실행하고 있습니다."):
                processed_df = preprocess_reviews(
                    raw_df,
                    use_simple_if_okt_error=use_simple_if_okt_error
                )

                sentiment_df = analyze_sentiment(processed_df)

            st.session_state.processed_df = processed_df
            st.session_state.sentiment_df = sentiment_df

            okt_error_message = processed_df.attrs.get("okt_error_message", "")

            if okt_error_message:
                st.warning(
                    "Okt 실행에 실패하여 간단 토큰화로 대체했습니다. "
                    "과제에서 Okt 사용이 필수라면 Java/Jpype 환경을 다시 확인해야 합니다."
                )

                with st.expander("Okt 오류 내용 보기"):
                    st.write(okt_error_message)

            else:
                st.success("Okt 형태소 분석 기반 전처리 및 감성분석이 완료되었습니다.")

        except ImportError as e:
            st.error("konlpy 또는 Okt 형태소 분석기를 사용할 수 없습니다.")
            st.info(str(e))
            st.code(
                """
py -m pip install --upgrade JPype1 konlpy
py -m streamlit run app.py
                """,
                language="powershell"
            )

        except Exception as e:
            st.error(f"전처리 또는 감성분석 중 오류가 발생했습니다: {e}")


# ============================================================
# 전처리 결과 출력
# ============================================================

processed_df = st.session_state.processed_df

if not processed_df.empty:
    st.subheader("전처리 결과")

    st.write(f"전처리 후 개수: {len(processed_df)}개")

    with st.expander("전처리 전/후 비교 DataFrame 보기", expanded=True):
        compare_df = processed_df[
            [
                "브랜드명",
                "제품명",
                "수집 방식",
                "전처리 전 리뷰",
                "정제 리뷰",
                "전처리 결과 문자열",
                "분석 방식"
            ]
        ]

        st.dataframe(compare_df.head(20), use_container_width=True)

    with st.expander("전체 전처리 단어 빈도 보기"):
        word_freq_df = get_word_frequency(processed_df)
        st.dataframe(word_freq_df, use_container_width=True)

    processed_csv_bytes = convert_df_to_csv_bytes(processed_df)

    st.download_button(
        label="전처리 결과 CSV 저장",
        data=processed_csv_bytes,
        file_name=f"{brand}_{file_product_name}_processed_reviews.csv",
        mime="text/csv"
    )


# ============================================================
# 감성분석 결과 출력
# ============================================================

sentiment_df = st.session_state.sentiment_df

if not sentiment_df.empty:
    st.subheader("감성분석 결과")

    with st.expander("감성분석 전체 결과 보기", expanded=True):
        sentiment_view_df = sentiment_df[
            [
                "브랜드명",
                "제품명",
                "수집 방식",
                "전처리 전 리뷰",
                "전처리 결과 문자열",
                "감성 점수",
                "감성 분류",
                "분석 방식"
            ]
        ]

        st.dataframe(sentiment_view_df.head(20), use_container_width=True)

    brand_ratio_df = calculate_brand_positive_ratio(sentiment_df)

    with st.expander("브랜드별 긍정 비율 보기"):
        st.dataframe(brand_ratio_df, use_container_width=True)

    product_score_df = calculate_product_avg_sentiment(sentiment_df)

    with st.expander("제품별 평균 감성 점수 보기"):
        st.dataframe(product_score_df, use_container_width=True)

    # ========================================================
    # 분석 결과 누적표
    # ========================================================

    st.subheader("분석 결과 누적표")

    col_add, col_reset = st.columns(2)

    with col_add:
        if st.button("현재 분석 결과를 누적표에 추가"):
            st.session_state.analysis_history_df = add_current_analysis_to_summary(sentiment_df)
            st.success("현재 분석 결과가 누적표에 추가되었습니다.")

    with col_reset:
        if st.button("누적표 초기화"):
            st.session_state.analysis_history_df = pd.DataFrame()
            st.success("누적표가 초기화되었습니다.")

    if not st.session_state.analysis_history_df.empty:
        with st.expander("누적 분석 결과 표 보기", expanded=True):
            st.dataframe(st.session_state.analysis_history_df, use_container_width=True)

        st.download_button(
            label="누적 분석 결과 CSV 저장",
            data=convert_df_to_csv_bytes(st.session_state.analysis_history_df),
            file_name="analysis_summary_history.csv",
            mime="text/csv"
        )

    else:
        st.info("아직 누적된 분석 결과가 없습니다. 감성분석 후 '현재 분석 결과를 누적표에 추가' 버튼을 누르세요.")

    st.subheader("긍정 / 부정 / 중립 리뷰 필터")

    sentiment_filter = st.selectbox(
        "감성 분류 선택",
        ["전체", "긍정", "부정", "중립"]
    )

    if sentiment_filter == "전체":
        filtered_df = sentiment_df

    else:
        filtered_df = sentiment_df[sentiment_df["감성 분류"] == sentiment_filter]

    with st.expander("필터링된 리뷰 보기", expanded=True):
        filtered_view_df = filtered_df[
            [
                "브랜드명",
                "제품명",
                "수집 방식",
                "전처리 전 리뷰",
                "감성 점수",
                "감성 분류"
            ]
        ]

        st.dataframe(filtered_view_df.head(50), use_container_width=True)

    sentiment_csv_bytes = convert_df_to_csv_bytes(sentiment_df)

    st.download_button(
        label="감성분석 결과 CSV 저장",
        data=sentiment_csv_bytes,
        file_name=f"{brand}_{file_product_name}_sentiment_reviews.csv",
        mime="text/csv"
    )

    # ========================================================
    # 시각화
    # 제품별 평균 감성점수 그래프는 제거함
    # ========================================================

    st.subheader("시각화 결과")

    font_path = setup_korean_font()

    if font_path is None:
        st.warning("한글 폰트를 찾지 못했습니다. 그래프나 워드클라우드의 한글이 깨질 수 있습니다.")

    top_n = st.slider(
        "상위 단어 개수 선택",
        min_value=5,
        max_value=30,
        value=20,
        step=5
    )

    brand_counters = get_brand_word_counters(processed_df)

    with st.expander("상위 단어 빈도 분석 및 막대그래프", expanded=True):
        if not brand_counters:
            st.warning("단어 빈도 분석에 사용할 데이터가 없습니다.")

        else:
            for brand_name, counter in brand_counters.items():
                st.markdown(f"#### {brand_name}")

                word_freq_df = counter_to_dataframe(counter, top_n=top_n)

                st.dataframe(word_freq_df, use_container_width=True)

                fig = plot_word_frequency_bar(word_freq_df, brand_name)
                st.pyplot(fig)
                plt.close(fig)

    with st.expander("워드클라우드", expanded=True):
        if not brand_counters:
            st.warning("워드클라우드에 사용할 데이터가 없습니다.")

        else:
            for brand_name, counter in brand_counters.items():
                st.markdown(f"#### {brand_name}")

                fig = plot_brand_wordcloud(counter, brand_name, font_path)
                st.pyplot(fig)
                plt.close(fig)

    with st.expander("감성 비율 그래프", expanded=True):
        ratio_df = calculate_sentiment_ratio(sentiment_df)

        st.dataframe(ratio_df, use_container_width=True)

        fig = plot_sentiment_ratio_bar(ratio_df)
        st.pyplot(fig)
        plt.close(fig)

    st.info(
        "현재 감성분석은 간단한 감성사전 기반 방식입니다. "
        "문맥, 반어, 부정 표현을 완벽하게 반영하지 못할 수 있습니다."
    )