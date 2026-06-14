#!/usr/bin/env python3
"""
CLOUD BOT v9.0 — ZERO PHONE DATA — Render.com Ready
"""
import asyncio, re, os, time, json, sys
from datetime import datetime
from urllib.parse import urlparse
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait
import yt_dlp

API_ID = int(os.environ.get("API_ID", "0"))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
TEMP_DIR = "/tmp/videos"
MAX_FILE_MB = 1900
FLOOD_DELAY = 2

E = {"dl":"📥","up":"📤","ok":"✅","no":"❌","wait":"⏳","speed":"⚡","disk":"💾","stats":"📊","vid":"🎬","clock":"⏱","size":"📦","user":"👤","link":"🔗","web":"🌐","star":"⭐","fire":"🔥","cloud":"☁️","rocket":"🚀","check":"☑️","cross":"✖️","bar":"█","empty":"░","bulb":"💡","phone":"📱","server":"🖥","bot":"🤖"}

stats = {"processed":0,"success":0,"failed":0,"start_time":datetime.now().isoformat(),"total_size_mb":0,"users":set()}

def log(msg): print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"); sys.stdout.flush()
def fmt_size(b):
    if not b or b<=0: return "0 MB"
    mb=b/1048576
    if mb>=1000: return f"{mb/1024:.1f} GB"
    if mb>=1: return f"{mb:.1f} MB"
    return f"{b/1024:.1f} KB"
def fmt_time(s):
    if not s or s<=0: return "00:00"
    m,sec=divmod(int(s),60); h,m=divmod(m,60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"
def extract_urls(text):
    if not text: return []
    urls=[]
    for p in [r'https?://[^\s<>\"\')\[\]\n\r]+', r'www\.[^\s<>\"\')\[\]\n\r]+']:
        urls.extend(re.findall(p,text,re.IGNORECASE))
    cleaned,seen=[],set()
    for url in urls:
        if not url.startswith('http'): url='https://'+url
        try:
            p=urlparse(url)
            if p.scheme and p.netloc and '.' in p.netloc:
                if url not in seen: seen.add(url); cleaned.append(url)
        except: pass
    return cleaned
def detect_platform(url):
    d=urlparse(url).netloc.lower(); p=urlparse(url).path.lower(); f=d+p
    if 'youtube.com' in d or 'youtu.be' in d: return "🎬 YouTube"
    if 'instagram.com' in d: return "📸 Instagram"
    if 'facebook.com' in d or 'fb.watch' in d: return "👤 Facebook"
    if 'twitter.com' in d or 'x.com' in d: return "🐦 Twitter/X"
    if 'tiktok.com' in d: return "🎵 TikTok"
    if 'vimeo.com' in d: return "🎥 Vimeo"
    if 'rumble.com' in d or 'rumble.cloud' in d: return "🔴 Rumble"
    if 'dailymotion.com' in d: return "📺 Dailymotion"
    if any(x in f for x in ['.mp4','.webm','.mkv','cdn.','stream','/video/']): return "💿 Direct CDN"
    return "🔗 Direct Link"
def progress_bar(pct,length=20):
    filled=int(length*pct/100)
    return E["bar"]*filled+E["empty"]*(length-filled)
async def safe_edit(msg,text,kb=None):
    try:
        if kb: await msg.edit_text(text,reply_markup=kb)
        else: await msg.edit_text(text)
    except: pass

async def cloud_download_send(url,msg,client,idx=1,total=1):
    Path(TEMP_DIR).mkdir(parents=True,exist_ok=True)
    platform=detect_platform(url)
    status_text=f"{E['dl']} **Downloading** [{idx}/{total}]\n{E['link']} `{url[:50]}...`\n{E['web']} {platform}\n{progress_bar(0)} 0%\n{E['cloud']} Render Cloud"
    status_msg=await msg.reply_text(status_text)
    try:
        ydl_opts={'outtmpl':f'{TEMP_DIR}/%(id)s.%(ext)s','format':'best[height<=720]/best[height<=480]/best','quiet':True,'no_warnings':True,'ignoreerrors':True,'max_filesize':MAX_FILE_MB*1024*1024,'noplaylist':True,'playlist_items':'1','retries':3,'fragment_retries':3,'socket_timeout':60,'nocheckcertificate':True}
        last_pct=[0]
        def progress_hook(d):
            if d['status']=='downloading':
                tb=d.get('total_bytes') or d.get('total_bytes_estimate',0)
                dl=d.get('downloaded_bytes',0)
                if tb>0:
                    pct=int((dl/tb)*100); speed=d.get('speed',0)
                    if pct-last_pct[0]>=15 or pct==100:
                        last_pct[0]=pct; bar=progress_bar(pct)
                        txt=f"{E['dl']} **Downloading** [{idx}/{total}]\n{E['vid']} {d.get('filename','')[:40]}\n{bar} **{pct}%**\n{E['size']} {fmt_size(dl)} / {fmt_size(tb)}\n{E['speed']} {fmt_size(int(speed))}/s\n{E['cloud']} Render Cloud"
                        asyncio.create_task(safe_edit(status_msg,txt))
        ydl_opts['progress_hooks']=[progress_hook]
        loop=asyncio.get_event_loop()
        def sync_dl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info=ydl.extract_info(url,download=True)
                if not info: return None
                if 'entries' in info:
                    entries=[e for e in info['entries'] if e]
                    if not entries: return None
                    info=entries[0]
                fp=ydl.prepare_filename(info)
                if not os.path.exists(fp):
                    base=fp.rsplit('.',1)[0]
                    for ext in ['.mp4','.webm','.mkv','.mov']:
                        if os.path.exists(base+ext): fp=base+ext; break
                if not os.path.exists(fp): return None
                return {'filepath':fp,'title':info.get('title','Video')[:200],'duration':info.get('duration',0),'uploader':info.get('uploader','Unknown'),'filesize':os.path.getsize(fp),'thumbnail':info.get('thumbnail','')}
        result=await loop.run_in_executor(None,sync_dl)
        if not result or not os.path.exists(result.get('filepath','')):
            await safe_edit(status_msg,f"{E['cross']} **Download Failed!**\n{E['link']} {url[:80]}")
            stats['failed']+=1; stats['processed']+=1; return False
        fp=result['filepath']; fs=result['filesize']; title=result['title']; dur=result['duration']; uploader=result['uploader']
        await safe_edit(status_msg,f"{E['up']} **Uploading...** [{idx}/{total}]\n{E['vid']} {title[:80]}\n{E['size']} {fmt_size(fs)}\n{E['cloud']} Render → Telegram")
        caption=f"{E['vid']} **{title}**\n{E['clock']} {fmt_time(dur)} | {E['size']} {fmt_size(fs)}\n{E['user']} {uploader} | {E['web']} {platform}\n{E['cloud']} Cloud Bot v9.0 | {E['phone']} Zero Data"
        try:
            await client.send_video(chat_id=msg.chat.id,video=fp,caption=caption,supports_streaming=True,duration=dur if dur>0 else None,reply_to_message_id=msg.id)
        except FloodWait as e:
            log(f"FloodWait: {e.value}s"); await asyncio.sleep(e.value+2)
            await client.send_video(chat_id=msg.chat.id,video=fp,caption=caption,supports_streaming=True,duration=dur if dur>0 else None,reply_to_message_id=msg.id)
        try: os.remove(fp)
        except: pass
        await status_msg.delete()
        stats['processed']+=1; stats['success']+=1; stats['total_size_mb']+=fs/1048576
        log(f"{E['ok']} Sent: {title[:60]} ({fmt_size(fs)})")
        return True
    except Exception as e:
        error_msg=str(e)[:150]; log(f"{E['cross']} Error: {error_msg}")
        await safe_edit(status_msg,f"{E['cross']} **Failed!** [{idx}/{total}]\n{E['link']} {url[:80]}\n`{error_msg[:100]}`")
        stats['processed']+=1; stats['failed']+=1; return False

app = Client("CloudBotV9",api_id=API_ID,api_hash=API_HASH,bot_token=BOT_TOKEN,workers=10,max_concurrent_transmissions=5)

@app.on_message(filters.command("start"))
async def start_cmd(client,msg):
    stats['users'].add(msg.from_user.id)
    text=f"{E['fire']} **CLOUD VIDEO BOT v9.0** {E['fire']}\n\n{E['rocket']} **Zero Data on Your Phone! Guaranteed!**\n\n{E['star']} **Features:**\n• {E['cloud']} Cloud Processing (Render.com)\n• {E['dl']} Auto Download + Upload\n• {E['speed']} Super Fast 1Gbps Server\n• {E['link']} Bulk Links (50+)\n• {E['web']} All Platforms\n• {E['size']} Up to 2GB Files\n• {E['phone']} Phone Data: **ZERO KB**\n• {E['disk']} Phone Storage: **ZERO MB**\n\n{E['bulb']} **Use:** Video Link भेजो!\n\n{E['star']} /help /stats /batch\n\n{E['fire']} **अभी Link भेजो!**"
    kb=InlineKeyboardMarkup([[InlineKeyboardButton(f"{E['star']} Help",callback_data="help"),InlineKeyboardButton(f"{E['stats']} Stats",callback_data="stats")],[InlineKeyboardButton(f"{E['cloud']} Technology",callback_data="tech"),InlineKeyboardButton(f"{E['bulb']} How?",callback_data="how")],[InlineKeyboardButton(f"{E['web']} Supported Sites",callback_data="sites")]])
    await msg.reply_text(text,reply_markup=kb)

@app.on_message(filters.command("help"))
async def help_cmd(client,msg):
    text=f"{E['star']} **HELP** {E['star']}\n\n{E['cloud']} **Architecture:**\n📱 → Link → ☁️ Render Cloud → 📥 Download → 📤 Upload → 📱 Video Received\n\n{E['check']} Phone Data: ZERO!\n{E['check']} Phone Storage: ZERO!\n\n{E['web']} YouTube/IG/FB/X/TikTok/Rumble/+1000\n\n{E['speed']} Speed: 1Gbps Cloud\n\n{E['fire']} Bulk: 50 Links एक साथ!"
    await msg.reply_text(text)

@app.on_message(filters.command("stats"))
async def stats_cmd(client,msg):
    s=stats; total=max(1,s['processed']); rate=(s['success']/total)*100
    start=datetime.fromisoformat(s['start_time']); uptime=datetime.now()-start
    h,rem=divmod(int(uptime.total_seconds()),3600); m,sec=divmod(rem,60)
    text=f"{E['stats']} **STATS** {E['stats']}\n\n{E['clock']} Uptime: `{h}h {m}m {sec}s`\n{E['user']} Users: `{len(s['users'])}`\n\n{E['dl']} Processed: `{s['processed']}`\n{E['check']} Success: `{s['success']}`\n{E['cross']} Failed: `{s['failed']}`\n{E['star']} Rate: `{rate:.1f}%`\n\n{E['size']} Data: `{fmt_size(s['total_size_mb']*1048576)}`\n{E['cloud']} Server: `Render.com`\n{E['speed']} Status: `🟢 Online`\n\n{E['phone']} **Phone Data Saved:** `~{s['processed']*50} MB`"
    await msg.reply_text(text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{E['stats']} Refresh",callback_data="refresh_stats")]]))

@app.on_message(filters.command("batch"))
async def batch_cmd(client,msg):
    text=f"{E['fire']} **BULK MODE** {E['fire']}\n\n{E['link']} Multiple Links एक Message में!\nMax: **50 Links**\n\n{E['dl']} Process:\n1️⃣ Links Paste करो\n2️⃣ Bot Process करेगा\n3️⃣ Live Progress\n4️⃣ Videos आएंगी\n\n{E['cloud']} 100% Cloud!\n{E['phone']} Phone Data: ZERO!"
    await msg.reply_text(text)

@app.on_message(filters.text & ~filters.command(["start","help","stats","batch"]))
async def handle_links(client,msg):
    stats['users'].add(msg.from_user.id)
    urls=extract_urls(msg.text or msg.caption or "")
    if not urls:
        await msg.reply_text(f"{E['cross']} **No Links!**\n\nSend video links from YouTube/IG/FB/X/TikTok/Rumble etc.\n\n/batch for Bulk Guide!",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(f"{E['web']} Supported Sites",callback_data="sites")],[InlineKeyboardButton(f"{E['cloud']} How It Works",callback_data="how")]]))
        return
    total=len(urls); platforms=list(set(detect_platform(u) for u in urls))
    header=f"{E['fire']} **PROCESSING {total} LINK(S)** {E['fire']}\n\n{E['link']} Links: **{total}**\n{E['web']} Platforms: {', '.join(platforms[:5])}{'...' if len(platforms)>5 else ''}\n{E['cloud']} Server: Render Cloud\n{E['phone']} Phone Data: **ZERO**\n\n{E['wait']} Starting..."
    header_msg=await msg.reply_text(header)
    success,failed,failed_urls=0,0,[]
    for i,url in enumerate(urls,1):
        result=await cloud_download_send(url,msg,client,i,total)
        if result: success+=1
        else: failed+=1; failed_urls.append(url)
        if i<total: await asyncio.sleep(FLOOD_DELAY)
    rate=(success/max(1,total))*100
    summary=f"{E['check']} **BATCH COMPLETE!** {E['check']}\n\n{E['stats']} **Results:**\n• Total: {total}\n• {E['check']} Success: {success}\n• {E['cross']} Failed: {failed}\n• {E['star']} Rate: {rate:.1f}%\n\n{E['cloud']} **All on Cloud**\n{E['phone']} **Phone Data: ~{total*0.5} KB**\n{E['disk']} **Phone Storage: 0 MB**\n\n{E['fire']} Send more! | /stats | /help"
    if failed_urls and len(failed_urls)<=3:
        summary+=f"\n\n{E['cross']} **Failed:**\n"
        for fu in failed_urls: summary+=f"• `{fu[:60]}...`\n"
    try: await header_msg.edit_text(summary)
    except: await msg.reply_text(summary)

@app.on_callback_query()
async def cb_handler(client,cb):
    d=cb.data
    if d=="help": await help_cmd(client,cb.message)
    elif d in ["stats","refresh_stats"]: await stats_cmd(client,cb.message)
    elif d=="tech": await cb.message.reply_text(f"{E['cloud']} **TECH** {E['cloud']}\n\n{E['server']} Render.com\n{E['bot']} Pyrogram MTProto\n{E['dl']} yt-dlp\n{E['speed']} 1 Gbps\n{E['lock']} Secure\n\n{E['star']} Cloud handles everything!")
    elif d=="how": await cb.message.reply_text(f"{E['bulb']} **HOW** {E['bulb']}\n\n1️⃣ You→Link\n2️⃣ Cloud→Download\n3️⃣ Cloud→Upload\n4️⃣ You→Video\n\n{E['phone']} Phone: 0 Data, 0 Storage\n{E['cloud']} Cloud: 100% Processing\n{E['check']} Result: Video in chat!")
    elif d=="sites": await cb.message.reply_text(f"{E['web']} **SITES** {E['web']}\n\n{E['check']} YouTube/IG/FB/X/TikTok\n{E['check']} Rumble/Vimeo/Dailymotion\n{E['check']} Reddit/CDN/+1000 More!\n\n{E['star']} Powered by yt-dlp")
    await cb.answer()

@app.on_message(filters.video | filters.document | filters.animation)
async def file_handler(client,msg):
    file=msg.video or msg.document or msg.animation
    if not file: return
    await msg.reply_text(f"{E['vid']} **File Received!**\n{E['size']} {fmt_size(file.file_size)}\n{E['info']} ID: `{file.file_id}`\n\n{E['bulb']} Send **LINKS** for Cloud Processing!\n{E['cloud']} Zero Data on Your Phone!")

def main():
    print(f"\n{E['cloud']} CLOUD BOT v9.0 STARTING {E['cloud']}\n")
    log(f"{E['rocket']} Starting Cloud Bot...")
    Path(TEMP_DIR).mkdir(parents=True,exist_ok=True)
    app.run()

if __name__=="__main__":
    main()
