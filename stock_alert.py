import smtplib, ssl, json, urllib.request, os
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL_USER        = "parth.zanwar01@gmail.com"
GMAIL_APP_PASSWORD = "yrbwvhwtnvutttit"
RECIPIENTS        = ["parth.zanwar01@gmail.com", "2812032093@txt.att.net"]
GEMINI_API_KEY    = os.environ.get("GEMINI_API_KEY", "")

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


# ── Fetch real-time quote from Yahoo Finance ─────────────────────────────────
def fetch_quote(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        meta = data["chart"]["result"][0]["meta"]
        price    = meta.get("regularMarketPrice", 0)
        prev     = meta.get("chartPreviousClose") or meta.get("previousClose") or price
        chg_pct  = ((price - prev) / prev * 100) if prev else 0
        return price, chg_pct
    except Exception:
        return 0, 0


# ── Fetch recent news headlines from Yahoo Finance ───────────────────────────
def fetch_news(symbol):
    url = (f"https://query1.finance.yahoo.com/v1/finance/search"
           f"?q={symbol}&newsCount=3&quotesCount=0")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return [item["title"] for item in data.get("news", [])[:3]]
    except Exception:
        return []


# ── Ask Google Gemini whether the news is bullish or bearish ─────────────────
def gemini_analyze(symbol, name, headlines):
    """Returns (score, reason, verdict) where score ∈ {-1, 0, 1}."""
    if not headlines or not GEMINI_API_KEY:
        return 0, "No news available.", "NEUTRAL"

    headlines_text = "\n".join(f"- {h}" for h in headlines)
    prompt = (
        f"You are a stock market analyst. Given these recent news headlines for "
        f"{name} ({symbol}), predict whether they would likely push the stock price "
        f"UP or DOWN over the next trading day.\n\n"
        f"Headlines:\n{headlines_text}\n\n"
        f"Respond in this EXACT format (two lines only):\n"
        f"VERDICT: BULLISH or BEARISH or NEUTRAL\n"
        f"REASON: One concise sentence explaining why."
    )

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 80}
    }).encode("utf-8")

    api_url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    req = urllib.request.Request(
        api_url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
        text = result["candidates"][0]["content"]["parts"][0]["text"].strip()

        verdict = "NEUTRAL"
        reason  = text
        for line in text.split("\n"):
            line = line.strip()
            if line.upper().startswith("VERDICT:"):
                verdict = line.split(":", 1)[1].strip().upper()
            elif line.upper().startswith("REASON:"):
                reason = line.split(":", 1)[1].strip()

        score = 1 if "BULLISH" in verdict else (-1 if "BEARISH" in verdict else 0)
        return score, reason, verdict

    except Exception as e:
        print(f"  Gemini error for {symbol}: {e}")
        return 0, "AI analysis unavailable.", "NEUTRAL"


# ── Pick top N stocks by a blended momentum + AI sentiment score ─────────────
def get_top_picks(watchlist, n=3):
    results = []
    for symbol, name in watchlist:
        print(f"  Analysing {symbol}…")
        price, chg_pct = fetch_quote(symbol)
        if price == 0:
            continue
        headlines              = fetch_news(symbol)
        ai_score, reason, verdict = gemini_analyze(symbol, name, headlines)
        # 70% weight on today's price momentum, 30% on AI news sentiment
        combined = (chg_pct * 0.7) + (ai_score * 3.0)
        top_headline = headlines[0] if headlines else "No recent news"
        results.append((symbol, name, price, chg_pct,
                        top_headline, ai_score, reason, verdict, combined))

    results.sort(key=lambda x: x[8], reverse=True)
    return results[:n]


# ── Format the email / SMS body ───────────────────────────────────────────────
def build_message():
    today     = date.today().strftime("%A, %B %d, %Y")
    print("Fetching dividend picks…")
    div_picks  = get_top_picks(DIVIDEND_STOCKS)
    print("Fetching tech/AI picks…")
    tech_picks = get_top_picks(TECH_AI_STOCKS)

    def fmt(pick):
        symbol, name, price, chg, headline, _, reason, verdict, _ = pick
        sign  = "+" if chg >= 0 else ""
        arrow = "UP" if verdict == "BULLISH" else ("DOWN" if verdict == "BEARISH" else "FLAT")
        return (
            f"• {symbol} ({name})\n"
            f"  ${price:.2f}  {sign}{chg:.2f}% today  |  AI: {verdict} ({arrow})\n"
            f"  Why: {reason}\n"
            f"  News: {headline}"
        )

    body = (
        f"Good morning Parth! Morning Stock Picks — {today}\n\n"
        f"{'='*44}\n"
        f"  DIVIDEND PICKS (Top 3)\n"
        f"{'='*44}\n"
        + "\n\n".join(fmt(p) for p in div_picks) +
        f"\n\n{'='*44}\n"
        f"  TECH / AI PICKS (Top 3)\n"
        f"{'='*44}\n"
        + "\n\n".join(fmt(p) for p in tech_picks) +
        f"\n\nMarkets open at 9:30 AM ET.\n"
        f"Data: Yahoo Finance  |  AI: Google Gemini\n"
        f"— Your Claude Stock Alert"
    )

    subject = f"Morning Stock Picks — {today}"
    return subject, body


# ── Send via Gmail SMTP (also hits AT&T SMS gateway) ─────────────────────────
def send_alert(subject, body):
    msg = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(RECIPIENTS)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENTS, msg.as_string())
    print(f"✓ Alert sent: {subject}")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    subject, body = build_message()
    print(body)
    send_alert(subject, body)
