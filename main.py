#!/usr/bin/env python3
"""
📚 Telegram Book PDF Direct Sender Bot v4
- Maximum sources se direct PDF Telegram mein bheje
- Gutenberg + Archive.org + OpenLibrary + Feedbooks
- Koi website nahi kholni!

Install:
    pip install python-telegram-bot requests beautifulsoup4

Run:
    export TELEGRAM_BOT_TOKEN="your_token"
    python main.py
"""

import os, io, logging, urllib.parse, requests, re
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)

# ── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
MAX_SIZE_MB = 45

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
}


# ═══════════════════════════════════════════════════════════════════════════════
#  SOURCE 1 — Project Gutenberg (Best for classics)
# ═══════════════════════════════════════════════════════════════════════════════
def search_gutenberg(query: str) -> list[dict]:
    results = []
    try:
        url = f"https://gutendex.com/books/?search={urllib.parse.quote_plus(query)}"
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return results
        for book in r.json().get("results", [])[:8]:
            fmt    = book.get("formats", {})
            dl_url = fmt.get("application/pdf") or fmt.get("application/epub+zip")
            if not dl_url:
                continue
            ext = "pdf" if "pdf" in dl_url else "epub"
            authors = ", ".join(a["name"] for a in book.get("authors", []))
            results.append({
                "title":  book.get("title", "Unknown"),
                "author": authors or "Unknown",
                "source": "📗 Gutenberg",
                "dl_url": dl_url,
                "ext":    ext,
            })
    except Exception as e:
        logger.warning(f"Gutenberg: {e}")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  SOURCE 2 — Open Library + Archive.org
# ═══════════════════════════════════════════════════════════════════════════════
def search_openlibrary(query: str) -> list[dict]:
    results = []
    try:
        url = (
            f"https://openlibrary.org/search.json"
            f"?q={urllib.parse.quote_plus(query)}"
            f"&fields=key,title,author_name,ia&limit=8&has_fulltext=true"
        )
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return results
        for doc in r.json().get("docs", []):
            ia_list = doc.get("ia", [])
            if not ia_list:
                continue
            ia_id   = ia_list[0]
            dl_url  = f"https://archive.org/download/{ia_id}/{ia_id}.pdf"
            authors = ", ".join(doc.get("author_name", ["Unknown"]))
            results.append({
                "title":  doc.get("title", "Unknown"),
                "author": authors,
                "source": "🏛️ Archive.org",
                "dl_url": dl_url,
                "ext":    "pdf",
            })
    except Exception as e:
        logger.warning(f"OpenLibrary: {e}")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  SOURCE 3 — Feedbooks (Free public domain EPUB/PDF)
# ═══════════════════════════════════════════════════════════════════════════════
def search_feedbooks(query: str) -> list[dict]:
    results = []
    try:
        url = f"https://www.feedbooks.com/catalog/search.atom?query={urllib.parse.quote_plus(query)}"
        r   = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "xml")
        for entry in soup.find_all("entry")[:6]:
            title  = entry.find("title")
            author = entry.find("author")
            links  = entry.find_all("link")
            dl_url = None
            ext    = "epub"
            for lnk in links:
                href = lnk.get("href", "")
                typ  = lnk.get("type", "")
                if "pdf" in typ or href.endswith(".pdf"):
                    dl_url = href; ext = "pdf"; break
                if "epub" in typ or href.endswith(".epub"):
                    dl_url = href; ext = "epub"
            if not dl_url:
                continue
            results.append({
                "title":  title.text.strip() if title else "Unknown",
                "author": author.find("name").text.strip() if author and author.find("name") else "Unknown",
                "source": "📘 Feedbooks",
                "dl_url": dl_url,
                "ext":    ext,
            })
    except Exception as e:
        logger.warning(f"Feedbooks: {e}")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  SOURCE 4 — Standard Ebooks (Beautiful free classics)
# ═══════════════════════════════════════════════════════════════════════════════
def search_standardebooks(query: str) -> list[dict]:
    results = []
    try:
        url = f"https://standardebooks.org/ebooks?query={urllib.parse.quote_plus(query)}"
        r   = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return results
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select("li[typeof='schema:Book']")[:5]:
            title_el  = item.select_one("[property='schema:name']")
            author_el = item.select_one("[property='schema:author'] span")
            link_el   = item.select_one("a[href]")
            if not (title_el and link_el):
                continue
            book_path = link_el["href"]
            # Build epub download URL
            slug    = book_path.strip("/").split("/")[-1]
            dl_url  = f"https://standardebooks.org{book_path}/downloads/{slug}.epub"
            results.append({
                "title":  title_el.text.strip(),
                "author": author_el.text.strip() if author_el else "Unknown",
                "source": "⭐ Standard Ebooks",
                "dl_url": dl_url,
                "ext":    "epub",
            })
    except Exception as e:
        logger.warning(f"StandardEbooks: {e}")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  SOURCE 5 — ManyBooks.net
# ═══════════════════════════════════════════════════════════════════════════════
def search_manybooks(query: str) -> list[dict]:
    results = []
    try:
        url  = f"https://manybooks.net/search-book?search={urllib.parse.quote_plus(query)}"
        r    = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(r.text, "html.parser")
        for card in soup.select(".book-teaser")[:5]:
            title_el  = card.select_one("h3 a") or card.select_one("a")
            author_el = card.select_one(".author")
            if not title_el:
                continue
            book_url = "https://manybooks.net" + title_el.get("href", "")
            # Get download page
            try:
                br   = requests.get(book_url, headers=HEADERS, timeout=10)
                bsoup = BeautifulSoup(br.text, "html.parser")
                dl    = bsoup.select_one("a[href*='.pdf']") or bsoup.select_one("a[href*='.epub']")
                if dl:
                    dl_url = dl["href"]
                    if not dl_url.startswith("http"):
                        dl_url = "https://manybooks.net" + dl_url
                    ext = "pdf" if ".pdf" in dl_url else "epub"
                    results.append({
                        "title":  title_el.text.strip(),
                        "author": author_el.text.strip() if author_el else "Unknown",
                        "source": "📙 ManyBooks",
                        "dl_url": dl_url,
                        "ext":    ext,
                    })
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"ManyBooks: {e}")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  DOWNLOAD FILE
# ═══════════════════════════════════════════════════════════════════════════════
def check_size(url: str) -> float | None:
    try:
        r = requests.head(url, headers=HEADERS, timeout=8, allow_redirects=True)
        cl = r.headers.get("Content-Length")
        return round(int(cl) / 1024 / 1024, 1) if cl else None
    except Exception:
        return None


def download_file(url: str) -> tuple[bytes | None, str]:
    """Returns (bytes, error_reason)"""
    try:
        r = requests.get(url, headers=HEADERS, timeout=60, stream=True, allow_redirects=True)
        if r.status_code != 200:
            return None, f"Server ne refuse kiya (status {r.status_code})"

        data = bytearray()
        for chunk in r.iter_content(131072):
            data.extend(chunk)
            if len(data) > MAX_SIZE_MB * 1024 * 1024:
                return None, f"File bahut badi hai ({MAX_SIZE_MB}MB se zyada)"

        raw = bytes(data)
        if len(raw) < 500:
            return None, "File empty ya invalid hai"

        # Validate format
        is_pdf  = raw[:4] == b"%PDF"
        is_epub = raw[:2] == b"PK"
        if not (is_pdf or is_epub):
            return None, "Valid PDF/EPUB nahi mili"

        return raw, ""
    except requests.exceptions.Timeout:
        return None, "Timeout — server ne jawab nahi diya"
    except Exception as e:
        return None, str(e)


# ═══════════════════════════════════════════════════════════════════════════════
#  COMBINED SEARCH
# ═══════════════════════════════════════════════════════════════════════════════
def combined_search(query: str) -> list[dict]:
    all_results = []
    all_results += search_gutenberg(query)
    all_results += search_openlibrary(query)
    all_results += search_feedbooks(query)
    all_results += search_standardebooks(query)
    # ManyBooks slow hota hai, last mein
    if len(all_results) < 5:
        all_results += search_manybooks(query)

    # Deduplicate by title
    seen, unique = set(), []
    for b in all_results:
        key = b["title"].lower()[:35]
        if key not in seen:
            seen.add(key)
            unique.append(b)
    return unique[:12]


# ═══════════════════════════════════════════════════════════════════════════════
#  KEYBOARDS
# ═══════════════════════════════════════════════════════════════════════════════
def results_keyboard(results: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for i, b in enumerate(results):
        icon  = "📄" if b["ext"] == "pdf" else "📱"
        label = b["title"][:40] + ("…" if len(b["title"]) > 40 else "")
        buttons.append([InlineKeyboardButton(f"{icon} {label}", callback_data=f"get:{i}")])
    return InlineKeyboardMarkup(buttons)


def book_keyboard(idx: int, size_mb: float | None, too_large: bool) -> InlineKeyboardMarkup:
    buttons = []
    if not too_large:
        size_txt = f" (~{size_mb}MB)" if size_mb else ""
        buttons.append([InlineKeyboardButton(
            f"⬇️ Telegram में भेजो{size_txt}", callback_data=f"dl:{idx}"
        )])
    buttons.append([InlineKeyboardButton("🔙 वापस", callback_data="back")])
    return InlineKeyboardMarkup(buttons)


# ═══════════════════════════════════════════════════════════════════════════════
#  HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Book PDF Direct Bot में स्वागत है!*\n\n"
        "📚 Book का नाम भेजो\n"
        "⬇️ PDF/EPUB सीधे Telegram में आएगी!\n"
        "🚫 कोई website नहीं खोलनी!\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "*Sources:*\n"
        "📗 Project Gutenberg\n"
        "🏛️ Archive.org\n"
        "📘 Feedbooks\n"
        "⭐ Standard Ebooks\n"
        "📙 ManyBooks\n\n"
        "━━━━━━━━━━━━━━━━\n"
        "*Example search करो:*\n"
        "`Sherlock Holmes`\n"
        "`Pride and Prejudice`\n"
        "`Python programming`\n\n"
        "/popular — Popular books list",
        parse_mode="Markdown"
    )


async def popular_command(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    books = [
        "Sherlock Holmes", "Pride and Prejudice", "Frankenstein",
        "Dracula", "The Art of War", "Alice in Wonderland",
        "Moby Dick", "Romeo and Juliet", "The Count of Monte Cristo",
        "Think and Grow Rich",
    ]
    buttons = [[InlineKeyboardButton(f"📗 {b}", callback_data=f"search:{b}")] for b in books]
    await update.message.reply_text(
        "🔥 *Popular Free Books:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if len(query) < 2:
        return

    await update.message.reply_chat_action("typing")
    msg = await update.message.reply_text(
        f"🔍 *'{query}'* search हो रही है...\n⏳ 3-5 seconds wait करो",
        parse_mode="Markdown"
    )

    results = combined_search(query)
    ctx.user_data["results"] = results
    ctx.user_data["query"]   = query

    if not results:
        await msg.edit_text(
            f"😔 *'{query}'* नहीं मिली।\n\n"
            "💡 Try करो:\n"
            "• English में लिखो\n"
            "• Author name भी लिखो\n"
            "• Shorter title लिखो",
            parse_mode="Markdown"
        )
        return

    lines = [f"✅ *{len(results)} books मिलीं '{query}' के लिए:*\n"]
    for i, b in enumerate(results, 1):
        icon = "📄" if b["ext"] == "pdf" else "📱"
        lines.append(f"{icon} *{i}.* {b['title']}\n    ✍️ _{b['author']}_ | {b['source']}")
    lines.append("\n👇 *Book tap करो — Telegram में file आएगी:*")

    await msg.edit_text(
        "\n".join(lines),
        parse_mode="Markdown",
        reply_markup=results_keyboard(results)
    )


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    # ── Popular search
    if data.startswith("search:"):
        query = data[7:]
        ctx.user_data["query"] = query
        msg = await q.message.reply_text(
            f"🔍 *'{query}'* search हो रही है...",
            parse_mode="Markdown"
        )
        results = combined_search(query)
        ctx.user_data["results"] = results
        if not results:
            await msg.edit_text(f"😔 '{query}' नहीं मिली।")
            return
        lines = [f"✅ *{len(results)} books मिलीं:*\n"]
        for i, b in enumerate(results, 1):
            icon = "📄" if b["ext"] == "pdf" else "📱"
            lines.append(f"{icon} *{i}.* {b['title']}\n    ✍️ _{b['author']}_ | {b['source']}")
        lines.append("\n👇 *Tap करो:*")
        await msg.edit_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=results_keyboard(results)
        )

    # ── Book detail
    elif data.startswith("get:"):
        idx     = int(data[4:])
        results = ctx.user_data.get("results", [])
        if idx >= len(results):
            await q.message.reply_text("⚠️ Expire हो गया। फिर से search करो।")
            return
        book    = results[idx]
        size_mb = check_size(book["dl_url"])
        too_large = bool(size_mb and size_mb > MAX_SIZE_MB)

        size_text = f"📦 Size: ~{size_mb}MB" if size_mb else "📦 Size: checking..."
        status = "⚠️ बहुत बड़ी file है!" if too_large else "✅ Download हो सकती है!"

        await q.message.reply_text(
            f"📖 *{book['title']}*\n"
            f"✍️ {book['author']}\n"
            f"🌐 {book['source']}\n"
            f"📄 Format: {book['ext'].upper()}\n"
            f"{size_text}\n"
            f"{status}",
            parse_mode="Markdown",
            reply_markup=book_keyboard(idx, size_mb, too_large)
        )

    # ── Download & send
    elif data.startswith("dl:"):
        idx     = int(data[3:])
        results = ctx.user_data.get("results", [])
        if idx >= len(results):
            await q.message.reply_text("⚠️ Expire हो गया।")
            return
        book = results[idx]

        msg = await q.message.reply_text(
            f"⬇️ *'{book['title']}'* download हो रही है...\n"
            f"🌐 Source: {book['source']}\n"
            f"⏳ Please wait...",
            parse_mode="Markdown"
        )

        file_bytes, error = download_file(book["dl_url"])

        if file_bytes:
            size_mb  = round(len(file_bytes) / 1024 / 1024, 1)
            raw_name = re.sub(r'[^\w\s-]', '', book['title'])[:50]
            filename = raw_name.replace(" ", "_") + f".{book['ext']}"

            await msg.edit_text(f"📤 Sending... ({size_mb}MB)")

            await q.message.reply_document(
                document=io.BytesIO(file_bytes),
                filename=filename,
                caption=(
                    f"📚 *{book['title']}*\n"
                    f"✍️ {book['author']}\n"
                    f"🌐 {book['source']}\n"
                    f"📦 {size_mb}MB | {book['ext'].upper()}\n\n"
                    f"_Happy Reading! 📖_"
                ),
                parse_mode="Markdown",
            )
            await msg.delete()

        else:
            # Try next source automatically
            await msg.edit_text(
                f"😔 *'{book['title']}'* नहीं मिली इस source से।\n"
                f"❌ Reason: {error}\n\n"
                f"🔄 दूसरी book try करो या नाम से फिर search करो।",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 वापस Results पर", callback_data="back")
                ]])
            )

    # ── Back
    elif data == "back":
        results = ctx.user_data.get("results", [])
        query   = ctx.user_data.get("query", "")
        if not results:
            await q.message.reply_text("🔍 फिर से book का नाम भेजो।")
            return
        lines = [f"📚 *'{query}' के results:*\n"]
        for i, b in enumerate(results, 1):
            icon = "📄" if b["ext"] == "pdf" else "📱"
            lines.append(f"{icon} *{i}.* {b['title']}\n    ✍️ _{b['author']}_ | {b['source']}")
        lines.append("\n👇 *Tap करो:*")
        await q.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=results_keyboard(results)
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ TELEGRAM_BOT_TOKEN set nahi hai!")
        return

    print("📚 Book PDF Direct Bot v4 starting...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("popular", popular_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot chal raha hai!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
