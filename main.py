#!/usr/bin/env python3
"""
🤖 Telegram-Only Gyan Book World
- Searches across multiple open-source book websites
- Sends PDF directly in Telegram chat (no external links)
- Everything stays inside Telegram
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# ── SEARCHERS ─────────────────────────────────────────────────────────────────

def search_gutenberg(query: str) -> list[dict]:
    """Search Project Gutenberg."""
    results = []
    try:
        url = f"https://gutendex.com/books/?search={urllib.parse.quote_plus(query)}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        for book in data.get("results", [])[:5]:
            pdf_url = book.get("formats", {}).get("application/pdf")
            if pdf_url:
                results.append({
                    "title": book.get("title", "Unknown"),
                    "author": ", ".join(a["name"] for a in book.get("authors", [])),
                    "source": "Project Gutenberg",
                    "pdf_url": pdf_url,
                    "file_size": "~1-100MB"
                })
    except Exception as e:
        logger.warning(f"Gutenberg search failed: {e}")
    return results


def get_archive_pdf_url(identifier: str) -> str | None:
    """Get actual PDF download URL from Archive.org item metadata."""
    try:
        meta_url = f"https://archive.org/metadata/{identifier}"
        r = requests.get(meta_url, headers=HEADERS, timeout=10)
        data = r.json()
        files = data.get("files", [])
        # Prefer smaller PDFs first
        pdf_files = [f for f in files if f.get("name", "").lower().endswith(".pdf")]
        if not pdf_files:
            return None
        # Sort by size ascending, pick smallest
        def safe_size(f):
            try:
                return int(f.get("size", 999999999))
            except Exception:
                return 999999999
        pdf_files.sort(key=safe_size)
        best = pdf_files[0]["name"]
        return f"https://archive.org/download/{identifier}/{urllib.parse.quote(best)}"
    except Exception as e:
        logger.warning(f"Archive metadata failed for {identifier}: {e}")
    return None


def search_archive(query: str) -> list[dict]:
    """Search Archive.org."""
    results = []
    try:
        url = (
            f"https://archive.org/advancedsearch.php"
            f"?q={urllib.parse.quote_plus(query)}+AND+mediatype:texts"
            f"&fl[]=identifier,title,creator,size&sort[]=downloads+desc&rows=8&output=json"
        )
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        for doc in data.get("response", {}).get("docs", [])[:8]:
            identifier = doc.get("identifier", "")
            title = doc.get("title", "Unknown")[:100]
            creator = doc.get("creator", "Unknown")
            pdf_url = get_archive_pdf_url(identifier)
            if not pdf_url:
                continue
            results.append({
                "title": title,
                "author": creator if isinstance(creator, str) else ", ".join(creator) if creator else "Unknown",
                "source": "Archive.org",
                "pdf_url": pdf_url,
                "file_size": "~1-100MB"
            })
            if len(results) >= 5:
                break
    except Exception as e:
        logger.warning(f"Archive search failed: {e}")
    return results


def search_pdfdrive(query: str) -> list[dict]:
    """Search PDF Drive."""
    results = []
    try:
        url = f"https://www.pdfdrive.com/search?q={urllib.parse.quote_plus(query)}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for item in soup.select(".files-new .file-left, .file-right")[:5]:
            title_el = item.find("h2") or item.find("a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            if href:
                page_url = f"https://www.pdfdrive.com{href}" if href.startswith("/") else href
                pdf_url = extract_pdfdrive_direct(page_url)
                if pdf_url:
                    results.append({
                        "title": title[:80],
                        "author": "PDF Drive",
                        "source": "PDF Drive",
                        "pdf_url": pdf_url,
                        "file_size": "~1-100MB"
                    })
    except Exception as e:
        logger.warning(f"PDF Drive search failed: {e}")
    return results


def extract_pdfdrive_direct(page_url: str) -> str | None:
    """Extract direct PDF download link from PDF Drive page."""
    try:
        r = requests.get(page_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        download_btn = soup.find("a", id="download-button") or soup.find("a", string=re.compile(r"download", re.I))
        if download_btn and download_btn.get("href"):
            return "https://www.pdfdrive.com" + download_btn["href"]
    except Exception:
        pass
    return None


def search_manybooks(query: str) -> list[dict]:
    """Search ManyBooks.net."""
    results = []
    try:
        url = f"https://manybooks.net/search-book?search={urllib.parse.quote_plus(query)}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for book in soup.select(".book-row")[:5]:
            title_el = book.select_one(".book-title a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            book_url = "https://manybooks.net" + title_el["href"]
            pdf_url = extract_manybooks_pdf(book_url)
            if pdf_url:
                results.append({
                    "title": title[:80],
                    "author": "ManyBooks",
                    "source": "ManyBooks.net",
                    "pdf_url": pdf_url,
                    "file_size": "~1-100MB"
                })
    except Exception as e:
        logger.warning(f"ManyBooks search failed: {e}")
    return results


def extract_manybooks_pdf(book_url: str) -> str | None:
    try:
        r = requests.get(book_url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for link in soup.find_all("a"):
            href = link.get("href", "")
            if href and href.endswith(".pdf") and "/download/" in href:
                return "https://manybooks.net" + href
    except Exception:
        pass
    return None


# ─── COMBINED SEARCH ──────────────────────────────────────────────────────────

def combined_search(query: str) -> list[dict]:
    """Search all sources and return unique PDF results. Falls back to Google filetype:pdf if needed."""
    all_results = []
    all_results += search_gutenberg(query)
    all_results += search_archive(query)
    all_results += search_pdfdrive(query)
    all_results += search_manybooks(query)

    # Deduplicate
    unique = []
    seen_urls = set()
    for res in all_results:
        if res["pdf_url"] and res["pdf_url"] not in seen_urls:
            seen_urls.add(res["pdf_url"])
            unique.append(res)

    # Fallback: if less than 3 results, try Google filetype:pdf search
    if len(unique) < 3:
        logger.info(f"Only {len(unique)} results found, trying Google filetype:pdf fallback...")
        google_results = search_google_filetype_pdf(query)
        for res in google_results:
            if res["pdf_url"] not in seen_urls:
                seen_urls.add(res["pdf_url"])
                unique.append(res)

    return unique[:10]


# ─── GOOGLE FILETYPE FALLBACK ────────────────────────────────────────────────

def search_google_filetype_pdf(query: str) -> list[dict]:
    """
    Fallback: Google search with filetype:pdf "query".
    Scrapes top direct .pdf links from search results.
    """
    results = []
    try:
        search_query = f'filetype:pdf "{query}"'
        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(search_query)}&num=10"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        seen = set()
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            # Google wraps URLs in /url?q=...
            if href.startswith("/url?q="):
                href = urllib.parse.unquote(href[7:].split("&")[0])
            if href.lower().endswith(".pdf") and href.startswith("http") and href not in seen:
                seen.add(href)
                # Try to get a readable title from link text or URL
                link_text = a_tag.get_text(strip=True)
                title = link_text if link_text and len(link_text) > 5 else href.split("/")[-1].replace(".pdf", "").replace("-", " ").replace("_", " ")
                results.append({
                    "title": title[:80],
                    "author": "Google Search",
                    "source": "Web (Google)",
                    "pdf_url": href,
                    "file_size": "Unknown"
                })
            if len(results) >= 5:
                break
    except Exception as e:
        logger.warning(f"Google filetype search failed: {e}")
    return results


# ─── PDF DOWNLOADER ───────────────────────────────────────────────────────────

def download_pdf(url: str, max_mb: int = 15) -> bytes | None:
    """Download PDF if valid and under size limit."""
    if not url:
        return None
    try:
        r = requests.get(
            url, headers=HEADERS, timeout=30,
            stream=True, allow_redirects=True
        )
        if r.status_code != 200:
            logger.warning(f"PDF download HTTP {r.status_code} for {url}")
            return None

        ct = r.headers.get("Content-Type", "").lower()
        final_url = r.url.lower()

        # Accept if content-type is PDF or URL ends with .pdf
        is_pdf_ct = "pdf" in ct or "octet-stream" in ct
        is_pdf_url = final_url.endswith(".pdf")
        if not is_pdf_ct and not is_pdf_url:
            logger.warning(f"Non-PDF content-type '{ct}' for {url}")
            return None

        # Check size from header
        size = int(r.headers.get("Content-Length", 0))
        if size > max_mb * 1024 * 1024:
            logger.warning(f"PDF too large ({size} bytes) for {url}")
            return None

        data = b""
        for chunk in r.iter_content(chunk_size=8192):
            data += chunk
            if len(data) > max_mb * 1024 * 1024:
                logger.warning(f"PDF exceeded {max_mb}MB while downloading {url}")
                return None

        # Verify PDF magic number
        if data[:4] == b"%PDF":
            return data
        else:
            logger.warning(f"No PDF magic number in response from {url}")
    except Exception as e:
        logger.warning(f"PDF download failed for {url}: {e}")
    return None


# ─── KEYBOARD ─────────────────────────────────────────────────────────────────

def build_results_keyboard(results: list[dict]) -> InlineKeyboardMarkup:
    """Build inline keyboard from search results."""
    buttons = []
    for i, book in enumerate(results[:8]):
        label = f"📘 {book['title'][:30]}"
        if len(book['title']) > 30:
            label += "..."
        # Use short index only — max 64 bytes limit on callback_data
        buttons.append([InlineKeyboardButton(label, callback_data=f"book:{i}")])
    return InlineKeyboardMarkup(buttons)


def build_book_keyboard(book_idx: int) -> InlineKeyboardMarkup:
    """Keyboard for single book."""
    buttons = [
        [InlineKeyboardButton("⬇️ Download PDF (Telegram)", callback_data=f"dl:{book_idx}")],
        [InlineKeyboardButton("🔙 Back to Results", callback_data="back")],
    ]
    return InlineKeyboardMarkup(buttons)


# ─── COMMANDS ─────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🔍 *Telegram Gyan Book World*\n\n"
        "I search *multiple open-source websites* for PDF books and send them directly in this chat.\n\n"
        "📌 *How to use:*\n"
        "Send me a book title or author name.\n"
        "Example: `Sherlock Holmes`\n\n"
        "Commands:\n"
        "/start – Welcome\n"
        "/help – How it works\n"
        "/popular – Popular books"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📖 *How This Bot Works*\n\n"
        "1️⃣ You send a book title or author.\n"
        "2️⃣ I search across:\n"
        "   • Project Gutenberg\n"
        "   • Archive.org\n"
        "   • PDF Drive\n"
        "   • ManyBooks.net\n"
        "3️⃣ Results appear as inline buttons.\n"
        "4️⃣ Tap a book → tap *Download PDF (Telegram)*.\n"
        "5️⃣ The PDF file is sent *directly in this chat* — no external links.\n\n"
        "⚠️ *Note:* Max file size is 15MB."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def popular_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    popular = [
        "Sherlock Holmes Arthur Conan Doyle",
        "Pride and Prejudice Jane Austen",
        "Moby Dick Herman Melville",
        "Alice in Wonderland Lewis Carroll",
        "The Art of War Sun Tzu",
        "Python programming tutorial",
        "Clean Code Robert Martin",
    ]
    buttons = [
        [InlineKeyboardButton(
            f"📗 {q.split()[0]} {q.split()[1] if len(q.split()) > 1 else ''}",
            callback_data=f"search:{q}"
        )]
        for q in popular
    ]
    await update.message.reply_text(
        "🔥 *Popular Free Books — Tap to Search:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


# ─── MESSAGE HANDLER ──────────────────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.message.text.strip()
    if not query:
        return

    msg = await update.message.reply_text(
        f"🔍 Searching *{query}* across open-source sites...\n_If not found, will try Google filetype:pdf fallback_ 🌐",
        parse_mode="Markdown"
    )
    results = combined_search(query)
    context.user_data["last_results"] = results
    context.user_data["last_query"] = query

    if not results:
        await msg.edit_text(
            f"😔 No downloadable PDFs found for *{query}* inside Telegram.\nTry a different book.",
            parse_mode="Markdown",
        )
        return

    lines = [f"📚 Found *{len(results)}* PDFs for `{query}`:\n"]
    for i, b in enumerate(results, 1):
        lines.append(f"*{i}.* {b['title']}\n    _{b['author']}_ — {b['source']}")

    await msg.edit_text(
        "\n".join(lines) + "\n\n👇 *Tap a book to download inside Telegram:*",
        parse_mode="Markdown",
        reply_markup=build_results_keyboard(results),
    )


# ─── CALLBACK HANDLER ─────────────────────────────────────────────────────────

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    await q.answer()
    data = q.data

    if data.startswith("search:"):
        query = data[7:]
        await q.message.reply_text(f"🔍 Searching for *{query}*...", parse_mode="Markdown")
        results = combined_search(query)
        context.user_data["last_results"] = results
        context.user_data["last_query"] = query
        if not results:
            await q.message.reply_text(
                f"😔 No PDFs found for *{query}*.",
                parse_mode="Markdown",
            )
            return
        lines = [f"📚 Found *{len(results)}* PDFs for `{query}`:\n"]
        for i, b in enumerate(results, 1):
            lines.append(f"*{i}.* {b['title']}\n    _{b['author']}_ — {b['source']}")
        await q.message.reply_text(
            "\n".join(lines) + "\n\n👇 *Tap a book:*",
            parse_mode="Markdown",
            reply_markup=build_results_keyboard(results),
        )

    elif data.startswith("book:"):
        idx = int(data.split(":")[1])
        results = context.user_data.get("last_results", [])
        try:
            book = results[idx]
        except (IndexError, ValueError):
            await q.message.reply_text("⚠️ Result expired. Search again.")
            return
        text = (
            f"📖 *{book['title']}*\n"
            f"✍️ Author: {book['author']}\n"
            f"📦 Source: {book['source']}\n"
            f"📄 Size: {book.get('file_size', 'Unknown')}\n\n"
        )
        if book.get("pdf_url"):
            text += "✅ *PDF available inside Telegram — tap Download below.*"
        else:
            text += "⚠️ No PDF found."
        await q.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=build_book_keyboard(idx),
        )

    elif data.startswith("dl:"):
        idx = int(data.split(":")[1])
        results = context.user_data.get("last_results", [])
        try:
            book = results[idx]
            pdf_url = book["pdf_url"]
        except (IndexError, KeyError):
            await q.message.reply_text("⚠️ Result expired. Search again.")
            return
        msg = await q.message.reply_text("⬇️ Downloading PDF inside Telegram... ⏳")
        pdf_bytes = download_pdf(pdf_url)
        if pdf_bytes:
            filename = pdf_url.split("/")[-1] or "book.pdf"
            await q.message.reply_document(
                document=io.BytesIO(pdf_bytes),
                filename=filename,
                caption="📄 Here's your PDF — downloaded inside Telegram ✅",
            )
            await msg.delete()
        else:
            await msg.edit_text(
                "⚠️ PDF download failed.\n\n"
                "Possible reasons:\n"
                "• File size >15MB\n"
                "• Source site blocked the request\n"
                "• File moved or deleted\n\n"
                "💡 Try another book from the list.",
            )

    elif data == "back":
        results = context.user_data.get("last_results", [])
        query = context.user_data.get("last_query", "")
        if not results or not query:
            await q.message.reply_text("🔍 Please search again.")
            return
        lines = [f"📚 Results for `{query}`:\n"]
        for i, b in enumerate(results, 1):
            lines.append(f"*{i}.* {b['title']}\n    _{b['author']}_ — {b['source']}")
        await q.message.reply_text(
            "\n".join(lines) + "\n\n👇 *Tap a book:*",
            parse_mode="Markdown",
            reply_markup=build_results_keyboard(results),
        )


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Set TELEGRAM_BOT_TOKEN first!")
        print("   export TELEGRAM_BOT_TOKEN='your_token_here'")
        return

    print("🤖 Telegram Gyan Book World starting...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("popular", popular_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Bot running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
