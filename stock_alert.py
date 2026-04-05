import smtplib
import ssl
import json
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import urllib.request

GMAIL_USER = "parth.zanwar01@gmail.com"
GMAIL_APP_PASSWORD = "yrbwvhwtnvutttit"
RECIPIENTS = ["parth.zanwar01@gmail.com", "2812032093@txt.att.net"]

DIVIDEND_STOCKS = [
    ("STWD", "Starwood Property Trust"),
    ("O",    "Realty Income"),
    ("CVX",  "Chevron"),
    ("ABBV", "AbbVie"),
    ("ENB",  "Enbridge"),
    ("KO",   "Coca-Cola"),
    ("VZ",   "Verizon"),
    ("MO",   "Altria"),
]

TECH_AI_STOCKS = [
    ("NVDA", "Nvidia"),
    ("MU",   "Micron Technology"),
    ("AMD",  "Advanced Micro Devices"),
    ("MSFT", "Microsoft"),
    ("AVGO", "Broadcom"),
    ("PLTR", "Palantir"),
    ("ARM",  "Arm Holdings"),
    ("TSM",  "TSMC"),
]

POSITIVE_WORDS = {
    "beat", "beats", "record", "surge", "surges", "upgraded", "upgrade", "buy",
    "strong", "growth", "profit", "gains", "bullish", "outperform", "raised",
    "higher", "dividend", "revenue", "partnership", "deal", "wins", "expands",
    "breakout", "rally", "soars", "jumps", "rises", "boosts", "accelerates",
}
NEGATIVE_WORDS = {
    "miss", "misses", "cut", "cuts", "downgrade", "downgrades", "sell", "weak",
    "loss", "decline", "bearish", "underperform", "lowered", "lower", "lawsuit",
    "investigation", "recall", "warning", "concern", "risks", "drops", "falls",
    "plunges", "slump", "disappoints", "layoffs", "charges",
}


def fetch_quote(symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        meta = data["chart"]["result"][0]["meta"]
        price = meta["regularMarketPrice"]
        prev = meta.get("chartPreviousClose") or meta.get("previousClose") or price
        change_pct = ((price - prev) / prev * 100) if prev else 0
        return price, change_pct
    except Exception as e:
        print(f"  [quote error] {symbol}: {e}")
        return None, None


def fetch_news(symbol):
    """Fetch top 3 recent headlines from Yahoo Finance search."""
    try:
        url = (
            f"https://query1.finance.yahoo.com/v1/finance/search"
            f"?q={symbol}&newsCount=3&quotesCount=0&enableFuzzyQuery=false"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        return [item["title"] for item in data.get("news", []) if item.get("title")][:3]
    except Exception as e:
        print(f"  [news error] {symbol}: {e}")
        return []


def sentiment_score(headlines):
    score = 0
    for h in headlines:
        words = set(h.lower().split())
        score += len(words & POSITIVE_WORDS) - len(words & NEGATIVE_WORDS)
    return score


def get_top_picks(watchlist, n=3):
    picks = []
    for symbol, name in watchlist:
        price, change_pct = fetch_quote(symbol)
        if price is None:
            continue
        headlines = fetch_news(symbol)
        sentiment = sentiment_score(headlines)
        combined = (change_pct * 0.7) + (sentiment * 1.5)
        top_headline = headlines[0] if headlines else "No recent news found"
        picks.append((symbol, name, price, change_pct, top_headline, combined))
        print(f"  {symbol}: {change_pct:+.2f}% | sentiment={sentiment} | score={combined:.2f} | news: {top_headline[:60]}")
    picks.sort(key=lambda x: x[5], reverse=True)
    return picks[:n]


def build_message():
    today = date.today().strftime("%A, %B %-d")
    print("Fetching dividend picks...")
    dividend = get_top_picks(DIVIDEND_STOCKS)
    print("Fetching tech/AI picks...")
    tech = get_top_picks(TECH_AI_STOCKS)

    def fmt(p):
        symbol, name, price, change_pct, headline, _ = p
        sign = "+" if change_pct >= 0 else ""
        return (
            f"  {symbol} ({name})"
            f"  ${price:.2f}  {sign}{change_pct:.2f}% today"
            f"\n  >> {headline}"
        )

    lines = [
        f"Morning Stock Picks | {today}",
        "=" * 40,
        "",
        "DIVIDEND PICKS",
        "-" * 20,
        *[fmt(p) for p in dividend],
        "",
        "TECH / AI PICKS",
        "-" * 20,
        *[fmt(p) for p in tech],
        "",
        "Ranked by price momentum + news sentiment.",
        "Data: Yahoo Finance  |  -- Claude Stock Alert",
    ]
    return f"Morning Stock Picks | {today}", "\n".join(lines)


def send_alert(subject, body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_USER
    msg["To"] = ", ".join(RECIPIENTS)
    msg.attach(MIMEText(body, "plain"))
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENTS, msg.as_string())
    print(f"Sent: {subject}")


if __name__ == "__main__":
    subject, body = build_message()
    print("\n" + body + "\n")
    send_alert(subject, body)
    print("Done!")
