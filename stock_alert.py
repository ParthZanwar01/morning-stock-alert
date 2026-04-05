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
    ("O", "Realty Income"),
    ("CVX", "Chevron"),
    ("ABBV", "AbbVie"),
    ("ENB", "Enbridge"),
    ("KO", "Coca-Cola"),
    ("VZ", "Verizon"),
    ("MO", "Altria"),
]

TECH_AI_STOCKS = [
    ("NVDA", "Nvidia"),
    ("MU", "Micron Technology"),
    ("AMD", "Advanced Micro Devices"),
    ("MSFT", "Microsoft"),
    ("AVGO", "Broadcom"),
    ("PLTR", "Palantir"),
    ("ARM", "Arm Holdings"),
    ("TSM", "TSMC"),
]

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
        print(f"Error fetching {symbol}: {e}")
        return None, None

def get_top_picks(watchlist, n=3):
    picks = []
    for symbol, name in watchlist:
        price, change_pct = fetch_quote(symbol)
        if price is not None:
            picks.append((symbol, name, price, change_pct))
    picks.sort(key=lambda x: x[3], reverse=True)
    return picks[:n]

def build_message():
    today = date.today().strftime("%A, %B %-d")
    dividend = get_top_picks(DIVIDEND_STOCKS)
    tech = get_top_picks(TECH_AI_STOCKS)

    def fmt(p):
        sign = "+" if p[3] >= 0 else ""
        return f"  {p[0]} ({p[1]}) - ${p[2]:.2f} ({sign}{p[3]:.2f}% today)"

    lines = [
        f"Good morning Parth! Stock Picks for {today}",
        "",
        "DIVIDEND PICKS:",
        *[fmt(p) for p in dividend],
        "",
        "TECH / AI PICKS:",
        *[fmt(p) for p in tech],
        "",
        "Markets open 9:30 AM ET. Data via Yahoo Finance.",
        "-- Your Claude Stock Alert",
    ]
    return f"Morning Stock Picks - {today}", "\n".join(lines)

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
    send_alert(subject, body)
    print("Done!")
