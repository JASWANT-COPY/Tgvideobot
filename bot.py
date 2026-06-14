#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║     CLOUD BOT v9.0 — ZERO PHONE DATA                      ║
║     Render.com Deployment Ready                            ║
║     Smart UI + Fast Processing                             ║
╚══════════════════════════════════════════════════════════════╝
"""

import asyncio, re, os, time, json, shutil, signal
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path
from typing import List, Optional, Dict

# Pyrogram
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery
)
from pyrogram.errors import FloodWait
from pyrogram.enums import ParseMode

# yt-dlp
import yt_dlp

# ============================================================
# CONFIG
# ============================================================
import os as environ

API_ID = int(environ.get("API_ID", "0"))
API_HASH = environ.get("API_HASH", "")
BOT_TOKEN = environ.get("BOT_TOKEN", "")
OWNER_ID = int(environ.get("OWNER_ID", "0"))

# Temp directory (Render provides /tmp)
TEMP_DIR = "/tmp/videos"
MAX_FILE_MB = 1900  # 1.9GB (Telegram Premium limit)
MAX_CONCURRENT = 3
FLOOD_DELAY = 2

# ============================================================
# SMART UI CONSTANTS
# ============================================================
EMOJI = {
    "download": "📥",
    "upload": "📤",
    "success": "✅",
    "failed": "❌",
    "processing": "⚙️",
    "wait": "⏳",
    "speed": "⚡",
    "storage": "💾",
    "data": "📊",
    "video": "🎬",
    "time": "⏱",
    "size": "📦",
    "user": "📤",
    "link": "🔗",
    "globe": "🌐",
    "cd": "💿",
    "star": "⭐",
    "fire": "🔥",
    "cloud": "☁️",
    "rocket": "🚀",
    "check": "☑️",
    "cross": "✖️",
    "bar": "▰",
    "empty": "▱",
}

# ============================================================
# GLOBALS
# ============================================================
stats = {
    "processed": 0, "success": 0, "failed": 0,
    "start_time": datetime.now().isoformat(),
    "total_size_mb": 0, "users": set(),
}

# ============================================================
# UTILS
# ============================================================

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def fmt_size(b):
    if not b or b <= 0: return "0 MB"
    mb = b / 1048576
    if mb >= 1000: return f"{mb/1024:.1f} GB"
    if mb >= 1: return f"{mb:.1f} MB"
    return f"{b/1024:.1f} KB"

def fmt_time(s):
    if not s or s <= 0: return "00:00"
    m, sec = divmod(int(s), 60)
    h, m = divmod(m, 60)
    if h > 0: return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"

def extract_urls(text: str) -> List[str]:
    """Extract all URLs from text"""
    if not text: return []
    # Multiple patterns to catch all URL formats
    patterns = [
        r'https?://[^\s<>"\'\)\[\]\n\r]+',
        r'www\.[^\s<>"\'\)\[\]\n\r]+',
    ]
    urls = []
    for pattern in patterns:
        urls.extend(re.findall(pattern, text, re.IGNORECASE))
    
    cleaned = []
    seen = set()
    for url in urls:
        if not url.startswith('http'):
            url = 'https://' + url
        try:
            p = urlparse(url)
            if p.scheme and p.netloc and '.' in p.netloc:
                # Remove tracking params for YouTube
                if 'youtube.com' in p.netloc or 'youtu.be' in p.netloc:
                    url = re.sub(r'[&?](si|feature|list|index|t)=[^&]*', '', url)
                if url not in seen:
                    seen.add(url)
                    cleaned.append(url)
        except:
            pass
    return cleaned

def detect_platform(url: str) -> str:
    """Detect video platform"""
    domain = urlparse(url).netloc.lower()
    if 'youtube.com' in domain or 'youtu.be' in domain:
        return "YouTube"
    if 'instagram.com' in domain:
        return "Instagram"
    if 'facebook.com' in domain or 'fb.watch' in domain:
        return "Facebook"
    if 'twitter.com' in domain or 'x.com' in domain:
        return "Twitter/X"
    if 'tiktok.com' in domain:
        return "TikTok"
    if 'vimeo.com' in domain:
        return "Vimeo"
    if 'rumble.com' in domain or 'rumble.cloud' in domain:
        return "Rumble"
    return "Direct Link"

def progress_bar(percent: int, length: int = 20) -> str:
    """Create visual progress bar"""
    filled = int(length * percent / 100)
    return EMOJI["bar"] * filled + EMOJI["empty"] * (length - filled)

# ============================================================
# CORE: VIDEO DOWNLOADER (Cloud Server)
# ============================================================

async def download_and_send(url: str, msg: Message, client: Client, index: int = 1, total: int = 1) -> bool:
    """
    Download video on CLOUD SERVER and send to user.
    PHONE DATA = ZERO (only Telegram receives the video).
    """
    
    # Create temp dir
    Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)
    
    platform = detect_platform(url)
    
    # Status message with Smart UI
    status_text = (
        f"{EMOJI['download']} **Downloading...** [{index}/{total}]\n"
        f"{EMOJI['link']} `{url[:60]}...`\n"
        f"{EMOJI['globe']} Platform: {platform}\n"
        f"{progress_bar(0)} 0%\n"
        f"{EMOJI['cloud']} Server: Render Cloud\n"
        f"{EMOJI['wait']} Connecting..."
    )
    status_msg = await msg.reply_text(status_text)
    
    try:
        # yt-dlp options for cloud server
        ydl_opts = {
            'outtmpl': f'{TEMP_DIR}/%(id)s.%(ext)s',
            'format': 'best[height<=720]/best[height<=480]/best',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'max_filesize': MAX_FILE_MB * 1024 * 1024,
            'noplaylist': True,
            'playlist_items': '1',
            'retries': 3,
            'fragment_retries': 3,
            'socket_timeout': 60,
            'nocheckcertificate': True,
        }
        
        # Progress hook
        last_update = [0]
        
        def progress_hook(d):
            nonlocal last_update
            if d['status'] == 'downloading':
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                
                if total_bytes > 0:
                    percent = int((downloaded / total_bytes) * 100)
                    speed = d.get('speed', 0)
                    
                    # Update every 10% to avoid flood
                    if percent - last_update[0] >= 10 or percent == 100:
                        last_update[0] = percent
                        
                        bar = progress_bar(percent)
                        text = (
                            f"{EMOJI['download']} **Downloading...** [{index}/{total}]\n"
                            f"{EMOJI['video']} {d.get('filename', '')[:50]}\n"
                            f"{bar} **{percent}%**\n"
                            f"{EMOJI['size']} {fmt_size(downloaded)} / {fmt_size(total_bytes)}\n"
                            f"{EMOJI['speed']} {fmt_size(int(speed))}/s\n"
                            f"{EMOJI['cloud']} Server: Render Cloud"
                        )
                        # Update status message (async)
                        asyncio.create_task(safe_edit(status_msg, text))
        
        ydl_opts['progress_hooks'] = [progress_hook]
        
        # Download on cloud
        loop = asyncio.get_event_loop()
        
        def sync_download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    return None
                if 'entries' in info:
                    entries = [e for e in info['entries'] if e]
                    if not entries:
                        return None
                    info = entries[0]
                
                filepath = ydl.prepare_filename(info)
                # Handle different extensions
                if not os.path.exists(filepath):
                    # Try common extensions
                    for ext in ['.mp4', '.webm', '.mkv', '.mov']:
                        alt = filepath.rsplit('.', 1)[0] + ext
                        if os.path.exists(alt):
                            filepath = alt
                            break
                
                return {
                    'filepath': filepath,
                    'title': info.get('title', 'Video')[:200],
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'filesize': os.path.getsize(filepath) if os.path.exists(filepath) else 0,
                    'thumbnail': info.get('thumbnail', ''),
                }
        
        result = await loop.run_in_executor(None, sync_download)
        
        if not result or not os.path.exists(result.get('filepath', '')):
            await safe_edit(status_msg, f"{EMOJI['cross']} **Download Failed!**\n{EMOJI['link']} {url[:80]}")
            return False
        
        filepath = result['filepath']
        filesize = result['filesize']
        title = result['title']
        duration = result['duration']
        uploader = result['uploader']
        
        # Upload to Telegram
        await safe_edit(status_msg, 
            f"{EMOJI['upload']} **Uploading to Telegram...** [{index}/{total}]\n"
            f"{EMOJI['video']} {title[:80]}\n"
            f"{EMOJI['size']} {fmt_size(filesize)}\n"
            f"{EMOJI['cloud']} Render Cloud → Telegram CDN"
        )
        
        caption = (
            f"{EMOJI['video']} **{title}**\n"
            f"{EMOJI['time']} {fmt_time(duration)} | {EMOJI['size']} {fmt_size(filesize)}\n"
            f"{EMOJI['user']} {uploader} | {EMOJI['globe']} {platform}\n"
            f"{EMOJI['cloud']} Cloud Bot v9.0"
        )
        
        # Send video
        try:
            await client.send_video(
                chat_id=msg.chat.id,
                video=filepath,
                caption=caption,
                supports_streaming=True,
                duration=duration if duration > 0 else None,
                reply_to_message_id=msg.id,
                thumb=None,
            )
        except FloodWait as e:
            log(f"FloodWait: {e.value}s")
            await asyncio.sleep(e.value + 2)
            await client.send_video(
                chat_id=msg.chat.id,
                video=filepath,
                caption=caption,
                supports_streaming=True,
                duration=duration if duration > 0 else None,
                reply_to_message_id=msg.id,
            )
        
        # Delete from cloud
        try:
            os.remove(filepath)
        except:
            pass
        
        await status_msg.delete()
        
        # Update stats
        stats['processed'] += 1
        stats['success'] += 1
        stats['total_size_mb'] += filesize / 1048576
        
        log(f"✅ Sent: {title[:60]} ({fmt_size(filesize)})")
        return True
        
    except Exception as e:
        error_msg = str(e)[:150]
        log(f"❌ Error: {error_msg}")
        
        await safe_edit(status_msg,
            f"{EMOJI['cross']} **Failed!** [{index}/{total}]\n"
            f"{EMOJI['link']} {url[:80]}\n"
            f"Error: `{error_msg[:100]}`"
        )
        
        stats['processed'] += 1
        stats['failed'] += 1
        return False

async def safe_edit(msg, text):
    """Safely edit message"""
    try:
        await msg.edit_text(text)
    except:
        pass

# ============================================================
# BOT CLIENT
# ============================================================

app = Client(
    "CloudVideoBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=10,
    max_concurrent_transmissions=5,
)

# ============================================================
# COMMAND HANDLERS
# ============================================================

@app.on_message(filters.command("start"))
async def start_command(client, msg):
    user = msg.from_user
    stats['users'].add(user.id)
    
    text = f"""
{EMOJI['fire']} **CLOUD VIDEO BOT v9.0** {EMOJI['fire']}

{EMOJI['rocket']} **Zero Data on Your Phone!**

{EMOJI['star']} **Features:**
• {EMOJI['cloud']} Cloud Processing (Render)
• {EMOJI['download']} Auto Download + Upload
• {EMOJI['speed']} Super Fast Delivery
• {EMOJI['link']} Bulk Links Support (25+)
• {EMOJI['globe']} All Platforms Supported
• {EMOJI['size']} Up to 2GB Files
• {EMOJI['data']} Phone Data: **ZERO**

{EMOJI['video']} **How to Use:**
Just send any video link(s)!
Bot cloud pe download karega aur aapko bhej dega.

{EMOJI['star']} **Commands:**
/start - This menu
/help - Detailed guide
/stats - Statistics
/batch - Bulk mode info

{EMOJI['fire']} **Send a link now!**
"""

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{EMOJI['star']} Help", callback_data="help"),
            InlineKeyboardButton(f"{EMOJI['data']} Stats", callback_data="stats"),
        ],
        [
            InlineKeyboardButton(f"{EMOJI['cloud']} How It Works", callback_data="how"),
            InlineKeyboardButton(f"{EMOJI['fire']} Premium", callback_data="premium"),
        ],
    ])
    
    await msg.reply_text(text, reply_markup=kb)

@app.on_message(filters.command("help"))
async def help_command(client, msg):
    text = f"""
{EMOJI['star']} **DETAILED HELP** {EMOJI['star']}

{EMOJI['cloud']} **Architecture:**
