import asyncio
import os
from fastapi import FastAPI
from camoufox.async_api import AsyncCamoufox as Camoufox
from browserforge.fingerprints import Screen
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ArchCamoufox")

app = FastAPI()
GLOBAL_PAGE = None

@app.get("/")
async def root():
    return {"status": "online", "service": "Arch-Agent WhatsApp Automation"}

@app.get("/status")
async def get_status():
    global GLOBAL_PAGE
    page_status = "not_initialized"
    if GLOBAL_PAGE:
        try:
            url = GLOBAL_PAGE.url
            page_status = f"active: {url}"
        except Exception as e:
            page_status = f"error: {str(e)}"
    return {
        "status": "online",
        "whatsapp_page": page_status
    }

@app.get("/screenshot")
async def take_screenshot():
    global GLOBAL_PAGE
    if not GLOBAL_PAGE:
        return {"error": "Browser not initialized"}
    path = "whatsapp_manual_screenshot.png"
    await GLOBAL_PAGE.screenshot(path=path)
    return {"status": "screenshot_saved", "path": path}

async def run_your_agentic_brain(sender_name: str, text: str):
    """
    Hook your custom Agentic AI logic here.
    """
    logger.info(f"🧠 Agent processing input from {sender_name}: '{text}'")
    
    # Run your custom model/logic processing loops here...
    response = f"Arch-Agent online. Read: '{text}'"
    
    await send_whatsapp_reply(response)

async def send_whatsapp_reply(message_text: str):
    global GLOBAL_PAGE
    if GLOBAL_PAGE is None: return
    try:
        input_selector = 'div[contenteditable="true"][@data-tab="10"]'
        await GLOBAL_PAGE.wait_for_selector(input_selector, timeout=5000)
        await GLOBAL_PAGE.click(input_selector)
        await GLOBAL_PAGE.fill(input_selector, message_text)
        await GLOBAL_PAGE.keyboard.press("Enter")
        logger.info("Reply sent!")
    except Exception as e:
        logger.error(f"DOM Injection Error: {str(e)}")

async def monitor_whatsapp_dom(page):
    logger.info("DOM Monitor listening...")
    while True:
        try:
            unread_chats = await page.query_selector_all('span[aria-label*="unread"]')
            if unread_chats:
                for chat in unread_chats:
                    await chat.click()
                    await asyncio.sleep(0.5)
                    
                    sender_element = await page.query_selector('header >> span[dir="auto"]')
                    sender_name = await sender_element.inner_text() if sender_element else "Unknown"
                    
                    message_elements = await page.query_selector_all('div.message-in span.selectable-text')
                    if message_elements:
                        last_message_text = await message_elements[-1].inner_text()
                        asyncio.create_task(run_your_agentic_brain(sender_name, last_message_text))
                        
            await asyncio.sleep(2)
        except Exception as e:
            await asyncio.sleep(2)

@app.on_event("startup")
async def start_headless_browser():
    global GLOBAL_PAGE
    
    # 🔧 FIX FOR ARCH LINUX: Force a full HD frame buffer size 
    # This prevents layout breaking in virtual display modes.
    browser_manager = Camoufox(
        headless="virtual",
        screen=Screen(min_width=1920, min_height=1080, max_width=1920, max_height=1080),
        user_data_dir=os.path.expanduser("~/.camoufox_whatsapp_profile"),
        persistent_context=True
    )
    
    logger.info("Launching stealth session via Camoufox...")
    context = await browser_manager.start()
    GLOBAL_PAGE = await context.new_page()
    
    await GLOBAL_PAGE.goto("https://web.whatsapp.com")
    
    await asyncio.sleep(5)
    qr_present = await GLOBAL_PAGE.query_selector('canvas[aria-label="Scan me!"]')
    if qr_present:
        logger.warning("Saving login QR Code to 'whatsapp_qr.png'...")
        await GLOBAL_PAGE.screenshot(path="whatsapp_qr.png")
    
    asyncio.create_task(monitor_whatsapp_dom(GLOBAL_PAGE))
