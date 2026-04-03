import os
import time
import json
import hashlib
import feedparser
import requests
from anthropic import Anthropic

# ── Ayarlar ──────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "8508147797:AAH1ryzFBV149iEXcv8xKyY3Y-dkGBd_NBI")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "8588450301")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "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")

TWITTER_ACCOUNTS = [
    "SJosephBurns", "DeItaone", "markets", "WSJ", "middleeast",
    "guardian", "DailyLoud", "tashecon", "spectatorindex",
    "crypto", "binance", "NASA", "zerohedge"
]

NITTER_INSTANCES = [
    "nitter.poast.org",
    "nitter.privacydev.net",
    "nitter.1d4.us",
    "nitter.kavin.rocks",
]

CHECK_INTERVAL_MINUTES = 15
SEEN_FILE = "seen_tweets.json"

# ── İstemci ──────────────────────────────────────────────────────────────────
client = Anthropic(api_key=ANTHROPIC_API_KEY)


def load_seen() -> set:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def tweet_id(entry) -> str:
    raw = entry.get("id") or entry.get("link") or entry.get("title", "")
    return hashlib.md5(raw.encode()).hexdigest()


def fetch_tweets(username: str) -> list:
    """Birden fazla Nitter instance dene, biri çalışana kadar."""
    for instance in NITTER_INSTANCES:
        url = f"https://{instance}/{username}/rss"
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                print(f"    ✓ {instance} çalışıyor ({username})")
                tweets = []
                for entry in feed.entries[:5]:
                    tweets.append({
                        "id": tweet_id(entry),
                        "username": username,
                        "title": entry.get("title", ""),
                        "link": entry.get("link", ""),
                    })
                return tweets
        except Exception as e:
            print(f"    ✗ {instance} başarısız: {e}")
            continue
    print(f"  [UYARI] {username} için hiçbir instance çalışmadı")
    return []


def translate_tweet(text: str) -> str:
    """Claude Haiku ile çevir — en ekonomik model."""
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{
                "role": "user",
                "content": (
                    "Aşağıdaki tweet'i Türkçe'ye çevir. "
                    "Sadece çeviriyi yaz, açıklama ekleme. "
                    "Emojileri ve hashtag'leri koru.\n\n"
                    f"{text}"
                )
            }]
        )
        return response.content[0].text.strip()
    except Exception as e:
        print(f"  [HATA] Çeviri başarısız: {e}")
        return text


def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        print(f"  ✅ Telegram'a gönderildi")
    except Exception as e:
        print(f"  [HATA] Telegram: {e}")


def format_message(tweet: dict, translation: str) -> str:
    return (
        f"🐦 <b>@{tweet['username']}</b>\n\n"
        f"🇬🇧 <i>{tweet['title']}</i>\n\n"
        f"🇹🇷 {translation}\n\n"
        f"🔗 {tweet['link']}"
    )


def run():
    print("✅ Bot başlatıldı!")
    print(f"📋 Takip edilen {len(TWITTER_ACCOUNTS)} hesap: {', '.join(TWITTER_ACCOUNTS)}")
    print(f"⏱  Her {CHECK_INTERVAL_MINUTES} dakikada bir kontrol edilecek\n")

    seen = load_seen()

    while True:
        print(f"\n🔍 Kontrol başladı...")
        yeni_tweet_sayisi = 0

        for username in TWITTER_ACCOUNTS:
            tweets = fetch_tweets(username)
            for tweet in reversed(tweets):
                if tweet["id"] in seen:
                    continue

                print(f"  → Yeni tweet: @{username}: {tweet['title'][:60]}...")
                translation = translate_tweet(tweet["title"])
                message = format_message(tweet, translation)
                send_telegram(message)

                seen.add(tweet["id"])
                save_seen(seen)
                yeni_tweet_sayisi += 1
                time.sleep(2)

        print(f"✓ Tamamlandı. {yeni_tweet_sayisi} yeni tweet gönderildi.")
        print(f"💤 {CHECK_INTERVAL_MINUTES} dakika bekleniyor...\n")
        time.sleep(CHECK_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    run()
