import smtplib, ssl, json, urllib.request, os
from datetime import date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL_USER         = "parth.zanwar01@gmail.com"
GMAIL_APP_PASSWORD = "yrbwvhwtnvutttit"
RECIPIENTS         = ["parth.zanwar01@gmail.com", "2812032093@txt.att.net"]
ANTHROPIC_API_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
BUDGET             = 200.0   # dollars available to invest

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

# Global market context queries — broad headlines Claude uses for macro context
GLOBAL_QUERIES = [
    "S&P 500 market today",
    "Federal Reserve interest rates",
    "inflation economy",
    "stock market earnings",
]


# ── Fetch real-time quote ─────────────────────────────────────────────────────
def fetch_quote(symbol):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        meta    = data["chart"]["result"][0]["meta"]
        price   = meta.get("regularMarketPrice", 0)
        prev    = meta.get("chartPreviousClose") or meta.get("previousClose") or price
        chg_pct = ((price - prev) / prev * 100) if prev else 0
        return price, chg_pct
    except Exception:
        return 0, 0


# ── Fetch news headlines from Yahoo Finance ───────────────────────────────────
def fetch_news(query, count=3):
    url = (f"https://query1.finance.yahoo.com/v1/finance/search"
           f"?q={urllib.request.quote(query)}&newsCount={count}&quotesCount=0")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return [item["title"] for item in data.get("news", [])[:count]]
    except Exception:
        return []


# ── Fetch global macro headlines ──────────────────────────────────────────────
def fetch_global_headlines():
    headlines = []
    for q in GLOBAL_QUERIES:
        headlines.extend(fetch_news(q, count=2))
    # De-duplicate while preserving order
    seen, unique = set(), []
    for h in headlines:
        if h not in seen:
            seen.add(h)
            unique.append(h)
    return unique[:8]


# ── Ask Claude to analyze news and give a verdict ────────────────────────────
def claude_analyze(symbol, name, stock_headlines, global_headlines):
    """Returns (score, reason, verdict) where score ∈ {-1, 0, 1}."""
    if not ANTHROPIC_API_KEY:
        return 0, "No API key.", "NEUTRAL"

    global_block = "\n".join(f"- {h}" for h in global_headlines) if global_headlines else "- None available"
    stock_block  = "\n".join(f"- {h}" for h in stock_headlines)  if stock_headlines  else "- No recent news"

    prompt = (
        f"You are a sharp stock market analyst. Today is {date.today().strftime('%B %d, %Y')}.\n\n"
        f"GLOBAL MARKET HEADLINES RIGHT NOW:\n{global_block}\n\n"
        f"HEADLINES SPECIFIC TO {name} ({symbol}):\n{stock_block}\n\n"
        f"Given all of the above, will {symbol} most likely go UP or DOWN in today's trading session?\n\n"
        f"Reply in this exact format (two lines only):\n"
        f"VERDICT: BULLISH or BEARISH or NEUTRAL\n"
        f"REASON: One concise sentence explaining your call."
    )

    payload = json.dumps({
        "model":      "claude-haiku-4-5-20251001",
        "max_tokens": 120,
        "messages":   [{"role": "user", "content": prompt}]
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key":         ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type":      "application/json",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
        text = result["content"][0]["text"].strip()

        verdict, reason = "NEUTRAL", text
        for line in text.split("\n"):
            line = line.strip()
            if line.upper().startswith("VERDICT:"):
                verdict = line.split(":", 1)[1].strip().upper()
            elif line.upper().startswith("REASON:"):
                reason = line.split(":", 1)[1].strip()

        score = 1 if "BULLISH" in verdict else (-1 if "BEARISH" in verdict else 0)
        return score, reason, verdict

    except Exception as e:
        print(f"  Claude error for {symbol}: {e}")
        return 0, "Analysis unavailable.", "NEUTRAL"


# ── Rank stocks by blended momentum + AI sentiment ───────────────────────────
def get_top_picks(watchlist, global_headlines, n=3):
    results = []
    for symbol, name in watchlist:
        print(f"  Analysing {symbol}…")
        price, chg_pct = fetch_quote(symbol)
        if price == 0:
            continue
        stock_headlines          = fetch_news(symbol, count=3)
        ai_score, reason, verdict = claude_analyze(symbol, name, stock_headlines, global_headlines)
        combined                 = (chg_pct * 0.7) + (ai_score * 3.0)
        top_headline             = stock_headlines[0] if stock_headlines else "No recent news"
        shares_affordable        = int(BUDGET // price) if price > 0 else 0
        results.append((symbol, name, price, chg_pct,
                        top_headline, ai_score, reason, verdict,
                        combined, shares_affordable))

    results.sort(key=lambda x: x[8], reverse=True)
    return results[:n]


# ── Build the email / SMS body ────────────────────────────────────────────────
def build_message():
    today = date.today().strftime("%A, %B %d, %Y")

    print("Fetching global market headlines…")
    global_headlines = fetch_global_headlines()

    print("Analysing dividend picks…")
    div_picks  = get_top_picks(DIVIDEND_STOCKS, global_headlines)

    print("Analysing tech / AI picks…")
    tech_picks = get_top_picks(TECH_AI_STOCKS, global_headlines)

    def fmt(pick):
        symbol, name, price, chg, headline, _, reason, verdict, _, shares = pick
        sign  = "+" if chg >= 0 else ""
        arrow = "UP ↑" if verdict == "BULLISH" else ("DOWN ↓" if verdict == "BEARISH" else "FLAT →")
        budget_note = (f"  Budget: ${BUDGET:.0f} buys ~{shares} share{'s' if shares != 1 else ''} "
                       f"@ ${price:.2f}" if shares > 0 else f"  Budget: ${price:.2f}/share (>{BUDGET:.0f})")
        return (
            f"• {symbol} ({name})\n"
            f"  ${price:.2f}  {sign}{chg:.2f}% today  |  Claude: {verdict} ({arrow})\n"
            f"  Why: {reason}\n"
            f"  News: {headline}\n"
            f"{budget_note}"
        )

    global_summary = "\n".join(f"  • {h}" for h in global_headlines[:4])

    body = (
        f"Good morning Parth!  Morning Stock Picks — {today}\n"
        f"Budget: ${BUDGET:.0f}  |  AI: Claude (Anthropic)\n\n"
        f"{'='*46}\n"
        f"  TODAY'S GLOBAL MARKET CONTEXT\n"
        f"{'='*46}\n"
        f"{global_summary}\n\n"
        f"{'='*46}\n"
        f"  DIVIDEND PICKS  (Top 3)\n"
        f"{'='*46}\n"
        + "\n\n".join(fmt(p) for p in div_picks) +
        f"\n\n{'='*46}\n"
        f"  TECH / AI PICKS  (Top 3)\n"
        f"{'='*46}\n"
        + "\n\n".join(fmt(p) for p in tech_picks) +
        f"\n\nMarkets open 9:30 AM ET  |  Data: Yahoo Finance\n"
        f"— Your Claude Stock Alert"
    )

    subject = f"📈 Morning Picks — {today}  |  ${BUDGET:.0f} Budget"
    return subject, body


# ── Send via Gmail SMTP (+ AT&T SMS gateway) ─────────────────────────────────
def send_alert(subject, body):
    msg            = MIMEMultipart()
    msg["From"]    = GMAIL_USER
    msg["To"]      = ", ".join(RECIPIENTS)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, RECIPIENTS, msg.as_string())
    print(f"✓ Alert sent: {subject}")


if __name__ == "__main__":
    subject, body = build_message()
    print(body)
    send_alert(subject, body)
