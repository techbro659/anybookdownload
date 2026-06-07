#!/usr/bin/env python3
"""
📚 Telegram Book PDF Finder & Downloader Bot v2
- Searches multiple free sources
- Tries to find direct PDF download links
- Sends PDF file directly in Telegram chat

Requirements:
    pip install python-telegram-bot requests beautifulsoup4

Usage:
    1. Get token from @BotFather
    2. Set TELEGRAM_BOT_TOKEN env variable or paste below
    3. Run: python book_pdf_bot_v2.py
"""

import os
import io
import re
import logging
import urllib.parse
import requests
from bs4 import BeautifulSoup
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ── CONFIG ────────────────────────────────────────────────────────────────────
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# ── FREE SEARCH SOURCES (for inline buttons) ──────────────────────────────────
SOURCES = {
    "📖 PDF Drive":        "https://www.pdfdrive.com/search?q={q}",
    "🏛️ Archive.org":      "https://archive.org/search?query={q}&mediatype=texts",
    "📚 Open Library":     "https://openlibrary.org/search?q={q}&format=ebooks&has_fulltext=true",
    "✨ Gutenberg":         "https://www.gutenberg.org/ebooks/search/?query={q}",
    "📗 ManyBooks":        "https://manybooks.net/search-book?search={q}",
    "⭐ Standard Ebooks":  "https://standardebooks.org/ebooks?query={q}",
    "🔬 Z-Library":        "https://z-lib.id/s/{q}",
    "📕 Bookboon":         "https://bookboon.com/en/textbooks?query={q}",
}


# ── SEARCHERS ─────────────────────────────────────────────────────────────────

def search_gutenberg(query: str) -> list[dict]:
    """Search Project Gutenberg and return books with direct download links."""
    results = []
    try:
        url = f"https://gutendex.com/books/?search={urllib.parse.quote_plus(query)}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        for book in data.get("results", [])[:5]:
            title = book.get("title", "Unknown")
            authors = ", ".join(a["name"] for a in book.get("authors", []))
            formats = book.get("formats", {})
            pdf_url = formats.get("application/pdf") or formats.get("text/html")
            epub_url = formats.get("application/epub+zip")
            results.append({
                "title": title,
                "author": authors,
                "source": "Project Gutenberg",
                "pdf_url": pdf_url,
                "epub_url": epub_url,
                "page_url": f"https://www.gutenberg.org/ebooks/{book.get('id', '')}",
            })
    except Exception as e:
        logger.warning(f"Gutenberg search failed: {e}")
    return results


def search_openlibrary(query: str) -> list[dict]:
    """Search Open Library and return books with availability info."""
    results = []
    try:
        url = f"https://openlibrary.org/search.json?q={urllib.parse.quote_plus(query)}&fields=key,title,author_name,ia,lending_edition_s&limit=5"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        for doc in data.get("docs", [])[:5]:
            ia = doc.get("ia", [])
            ia_id = ia[0] if ia else None
            pdf_url = f"https://archive.org/download/{ia_id}/{ia_id}.pdf" if ia_id else None
            results.append({
                "title": doc.get("title", "Unknown"),
                "author": ", ".join(doc.get("author_name", ["Unknown"])),
                "source": "Open Library / Archive.org",
                "pdf_url": pdf_url,
                "epub_url": f"https://archive.org/download/{ia_id}/{ia_id}_djvu.txt" if ia_id else None,
                "page_url": f"https://openlibrary.org{doc.get('key', '')}",
            })
    except Exception as e:
        logger.warning(f"Open Library search failed: {e}")
    return results


def search_pdfdrive(query: str) -> list[dict]:
    """Search PDF Drive for books."""
    results = []
    try:
        url = f"https://www.pdfdrive.com/search?q={urllib.parse.quote_plus(query)}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select(".file-right")[:5]:
            title_el = item.select_one("h2 a") or item.select_one("a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            page_url = f"https://www.pdfdrive.com{href}" if href.startswith("/") else href
            results.append({
                "title": title,
                "author": "See page",
                "source": "PDF Drive",
                "pdf_url": None,  # requires page visit to get direct link
                "epub_url": None,
                "page_url": page_url,
            })
    except Exception as e:
        logger.warning(f"PDFDrive search failed: {e}")
    return results


def try_download_pdf(url: str, max_mb: int = 15) -> bytes | None:
    """Try to download a PDF from a direct URL. Returns bytes or None."""
    if not url or not url.lower().endswith(".pdf"):
        return None
    try:
        r = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        content_type = r.headers.get("Content-Type", "")
        if "pdf" not in content_type and not url.endswith(".pdf"):
            return None
        size = int(r.headers.get("Content-Length", 0))
        if size > max_mb * 1024 * 1024:
            logger.info(f"PDF too large ({size} bytes), skipping download")
            return None
        data = b""
        for chunk in r.iter_content(chunk_size=65536):
            data += chunk
            if len(data) > max_mb * 1024 * 1024:
                return None
        if data[:4] == b"%PDF":
            return data
    except Exception as e:
        logger.warning(f"PDF download failed: {e}")
    return None


def combined_search(query: str) -> list[dict]:
    """Search all sources and return combined results."""
    results = []
    results += search_gutenberg(query)
    results += search_openlibrary(query)
    results += search_pdfdrive(query)
    return results


# ── KEYBOARD BUILDERS ─────────────────────────────────────────────────────────

def build_results_keyboard(results: list[dict], query: str) -> InlineKeyboardMarkup:
    """Build keyboard from search results."""
    buttons = []
    for i, book in enumerate(results[:8]):
        label = f"📄 {book['title'][:35]}{'...' if len(book['title']) > 35 else ''}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"book:{i}:{query}")])
    # Add search-all-sources row
    encoded = urllib.parse.quote_plus(query)
    buttons.append([
        InlineKeyboardButton("🔗 Search All Sources", callback_data=f"allsrc:{query}"),
    ])
    return InlineKeyboardMarkup(buttons)


def build_book_keyboard(book: dict) -> InlineKeyboardMarkup:
    """Build keyboard for a single book."""
    buttons = []
    if book.get("pdf_url"):
        buttons.append([InlineKeyboardButton("⬇️ Download PDF", callback_data=f"dl:{book['pdf_url']}")])
    if book.get("page_url"):
        buttons.append([InlineKeyboardButton("🌐 Open Book Page", url=book["page_url"])])
    if book.get("epub_url"):
        buttons.append([InlineKeyboardButton("📱 EPUB Version", url=book["epub_url"])])
    buttons.append([InlineKeyboardButton("🔙 Back to Results", callback_data="back")])
    return InlineKeyboardMarkup(buttons)


def build_all_sources_keyboard(query: str) -> InlineKeyboardMarkup:
    """Build keyboard with all search source links."""
    encoded = urllib.parse.quote_plus(query)
    buttons = []
    src_list = list(SOURCES.items())
    for i in range(0, len(src_list), 2):
        row = []
        for name, url_tpl in src_list[i:i+2]:
            row.append(InlineKeyboardButton(name, url=url_tpl.format(q=encoded)))
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


# ── COMMAND HANDLERS ──────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "👋 *Welcome to Book PDF Finder Bot!*\n\n"
        "I search free legal sources and try to send PDFs directly to you! 📬\n\n"
        "📌 *How to use:*\n"
        "Just type any book title or author name!\n\n"
        "*Examples:*\n"
        "• `Sherlock Holmes`\n"
        "• `Python programming`\n"
        "• `Atomic Habits James Clear`\n"
        "• `Pride and Prejudice`\n\n"
        "Commands:\n"
        "/start — Welcome\n"
        "/help — How it works\n"
        "/popular — Popular free books\n"
        "/sources — All search sources"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📖 *How it works:*\n\n"
        "1️⃣ Send me a book title or author name\n"
        "2️⃣ I search Gutenberg, Archive.org, Open Library & more\n"
        "3️⃣ Pick a book from the results\n"
        "4️⃣ Tap *Download PDF* — I'll send the file right here!\n\n"
        "📦 *Direct download works for:*\n"
        "• Project Gutenberg books (free classics)\n"
        "• Archive.org / Open Library books\n\n"
        "🔗 *For other sources* (PDF Drive, Z-Library):\n"
        "I'll give you the direct page link to download.\n\n"
        "⚠️ *Note:* Max PDF size is 15MB for direct sending."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def sources_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["📚 *All Free Book Sources:*\n"]
    for name, url in SOURCES.items():
        base = url.split("?")[0].split("/s/")[0]
        lines.append(f"{name} — {base}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def popular_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    popular = [
        "Sherlock Holmes Arthur Conan Doyle",
        "Pride and Prejudice Jane Austen",
        "Moby Dick Herman Melville",
        "Python programming tutorial",
        "Clean Code Robert Martin",
        "Think and Grow Rich Napoleon Hill",
        "The Art of War Sun Tzu",
        "Frankenstein Mary Shelley",
    ]
    buttons = [[InlineKeyboardButton(f"📗 {q.split(' ')[0:3][0]} {q.split(' ')[1] if len(q.split(' ')) > 1 else ''}", callback_data=f"search:{q}")] for q in popular]
    await update.message.reply_text(
        "🔥 *Popular Free Books — Tap to Search:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ── MESSAGE HANDLER ───────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.message.text.strip()
    if not query:
        return

    msg = await update.message.reply_text(f"🔍 Searching for *{query}*...", parse_mode="Markdown")
    results = combined_search(query)
    context.user_data["last_results"] = results
    context.user_data["last_query"] = query

    if not results:
        await msg.edit_text(
            f"😔 No direct results found for *{query}*.\n\nTry searching on these sites:",
            parse_mode="Markdown",
            reply_markup=build_all_sources_keyboard(query),
        )
        return

    lines = [f"📚 Found *{len(results)}* results for `{query}`:\n"]
    for i, b in enumerate(results[:8], 1):
        dl = "⬇️" if b.get("pdf_url") else "🔗"
        lines.append(f"{dl} *{i}.* {b['title']}\n    _{b['author']}_ — {b['source']}")

    await msg.edit_text(
        "\n".join(lines) + "\n\n👇 *Tap a book to download:*",
        parse_mode="Markdown",
        reply_markup=build_results_keyboard(results, query),
    )


# ── CALLBACK HANDLER ──────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data

    # ── Trigger new search (from /popular)
    if data.startswith("search:"):
        query = data[7:]
        await q.message.reply_text(f"🔍 Searching for *{query}*...", parse_mode="Markdown")
        results = combined_search(query)
        context.user_data["last_results"] = results
        context.user_data["last_query"] = query
        if not results:
            await q.message.reply_text(
                f"😔 No results found for *{query}*.",
                parse_mode="Markdown",
                reply_markup=build_all_sources_keyboard(query),
            )
            return
        lines = [f"📚 Found *{len(results)}* results for `{query}`:\n"]
        for i, b in enumerate(results[:8], 1):
            dl = "⬇️" if b.get("pdf_url") else "🔗"
            lines.append(f"{dl} *{i}.* {b['title']}\n    _{b['author']}_ — {b['source']}")
        await q.message.reply_text(
            "\n".join(lines) + "\n\n👇 *Tap a book to download:*",
            parse_mode="Markdown",
            reply_markup=build_results_keyboard(results, query),
        )

    # ── Show all external sources
    elif data.startswith("allsrc:"):
        query = data[7:]
        await q.message.reply_text(
            f"🔗 *Search for '{query}' on all sources:*",
            parse_mode="Markdown",
            reply_markup=build_all_sources_keyboard(query),
        )

    # ── Show individual book detail
    elif data.startswith("book:"):
        _, idx, query = data.split(":", 2)
        results = context.user_data.get("last_results", [])
        try:
            book = results[int(idx)]
        except (IndexError, ValueError):
            await q.message.reply_text("⚠️ Result expired. Please search again.")
            return
        text = (
            f"📖 *{book['title']}*\n"
            f"✍️ Author: {book['author']}\n"
            f"🌐 Source: {book['source']}\n\n"
            f"{'✅ Direct PDF download available!' if book.get('pdf_url') else '🔗 Visit page to download'}"
        )
        await q.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=build_book_keyboard(book),
        )

    # ── Download PDF directly
    elif data.startswith("dl:"):
        pdf_url = data[3:]
        msg = await q.message.reply_text("⬇️ Downloading PDF... Please wait ⏳")
        pdf_bytes = try_download_pdf(pdf_url)
        if pdf_bytes:
            filename = pdf_url.split("/")[-1] or "book.pdf"
            await q.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename=filename,
                caption="📄 Here is your book PDF! Enjoy reading 📚",
            )
            await msg.delete()
        else:
            await msg.edit_text(
                "⚠️ Could not download PDF directly (file may be too large or unavailable).\n\n"
                "👉 Please open the book page link instead.",
            )

    # ── Back button
    elif data == "back":
        results = context.user_data.get("last_results", [])
        query = context.user_data.get("last_query", "")
        if not results or not query:
            await q.message.reply_text("🔍 Please search again.")
            return
        lines = [f"📚 Results for `{query}`:\n"]
        for i, b in enumerate(results[:8], 1):
            dl = "⬇️" if b.get("pdf_url") else "🔗"
            lines.append(f"{dl} *{i}.* {b['title']}\n    _{b['author']}_ — {b['source']}")
        await q.message.reply_text(
            "\n".join(lines) + "\n\n👇 *Tap a book:*",
            parse_mode="Markdown",
            reply_markup=build_results_keyboard(results, query),
        )


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main() -> None:
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Set your TELEGRAM_BOT_TOKEN first!")
        print("   export TELEGRAM_BOT_TOKEN='your_token_here'")
        return

    print("📚 Book PDF Finder Bot v2 starting...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("sources", sources_command))
    app.add_handler(CommandHandler("popular", popular_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot running! Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
