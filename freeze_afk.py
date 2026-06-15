#!/usr/bin/env python3
"""
FreezeHost AFK - 自动挂机赚币脚本（支持多实例）
使用 SeleniumBase UC 模式绕过 Cloudflare Turnstile + 广告拦截检测
"""
import os
import random
import time
import platform
import sys

# Linux 服务器上需要虚拟显示器
# if platform.system().lower() == "linux":
#     from pyvirtualdisplay import Display
#     disp = Display(visible=False, size=(1920, 1080))
#     disp.start()
#     os.environ["DISPLAY"] = disp.new_display_var

from seleniumbase import SB
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By

# Discord Token - 从环境变量读取，支持多个（逗号分隔）
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")

# WARP 代理地址（可选，推荐使用）
WARP_PROXY = os.environ.get("WARP_PROXY", "")

# 最大运行时长（分钟），0 = 无限
MAX_RUNTIME = int(os.environ.get("MAX_RUNTIME", "0"))

# 每个 session 赏币时长（秒）
SESSION_DURATION = 1200  # 20 分钟

# 实例编号（从命令行参数或环境变量获取）
INSTANCE_ID = int(os.environ.get("INSTANCE_ID", "0"))
LOG_FILE = os.environ.get("LOG_FILE", "")

# telegram token
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

screenshot_start_path = "screenshots/earn_page_start.png"

def log(msg):
    """带时间戳和实例编号的日志"""
    ts = time.strftime("%H:%M:%S")
    prefix = "[I%d]" % INSTANCE_ID if INSTANCE_ID else ""
    line = "[%s] %s %s" % (ts, prefix, msg)
    print(line, flush=True)
    if LOG_FILE:
        try:
            with open(LOG_FILE, "a") as f:
                f.write(line + "\n")
        except:
            pass

def wait_turnstile(sb, timeout=120):
    start = time.time()
    last_click = 0
    
    # 尝试将 Turnstile 滚动到页面中心
    try:
        sb.execute_script(
            "var el = document.querySelector('#cf-turnstile-container');"
            "if (el) el.scrollIntoView({block: 'center'});"
        )
    except:
        pass

    while time.time() - start < timeout:
        try:
            val = sb.execute_script(
                "return document.querySelector('[name=cf-turnstile-response]')?.value || '';"
            )
            if val and len(str(val)) > 20:
                return str(val)
        except:
            pass
        now = time.time()
        if now - last_click > 5:
            try:
                # 再次滚动确保在可视区域
                sb.execute_script(
                    "var el = document.querySelector('iframe[src*=\"challenges.cloudflare.com\"]') || document.querySelector('.cf-turnstile');"
                    "if (el) el.scrollIntoView({block: 'center'});"
                )
                time.sleep(1)
                sb.uc_gui_click_captcha()
                last_click = now
            except:
                pass
        time.sleep(2)
    return None


def login_via_discord_token(sb, token):
    log("Opening FreezeHost...")
    sb.uc_open_with_reconnect("https://free.freezehost.pro", reconnect_time=5)
    time.sleep(5)

    try:
        sb.click("button#login-btn")
    except:
        sb.execute_script("document.getElementById('login-btn')?.click();")
    time.sleep(3)

    try:
        sb.wait_for_element_visible("button#confirm-login", timeout=5)
        sb.click("button#confirm-login")
        log("Confirmed terms")
    except:
        log("No terms dialog")
    time.sleep(2)

    if "discord.com" in sb.get_current_url():
        log("Inject token...")
        sb.execute_script("""(function(){
            var token = "%s";
            var f = document.createElement("iframe");
            f.style.display = "none";
            document.body.appendChild(f);
            try { f.contentWindow.localStorage.setItem("token", '"'+token+'"'); } catch(e) {}
            try { localStorage.setItem("token", '"'+token+'"'); } catch(e) {}
            document.body.removeChild(f);
        })();""" % token)

        log("Reload...")
        sb.driver.refresh()
        time.sleep(8)

        url = sb.get_current_url()
        if "discord.com/login" in url:
            log("Token invalid!")
            return False

        if "discord.com/oauth2" in url:
            log("Auto-authorize...")
            sb.execute_script("""(function(){
                document.querySelectorAll("button").forEach(function(btn){
                    if(btn.textContent.toLowerCase().includes("authorize")) btn.click();
                });
            })();""")
            time.sleep(5)

        for _ in range(20):
            url = sb.get_current_url()
            if url.startswith("https://free.freezehost.pro"):
                break
            time.sleep(2)

    url = sb.get_current_url()
    log("Login URL: %s" % url)
    return url.startswith("https://free.freezehost.pro")


def adblocker(sb):
    """Bypassing adblocker"""
    log("Bypassing adblocker...")
    try:
        sb.execute_script("""
            if(typeof adblockerDetected !== 'undefined') adblockerDetected = false;
            var msg = document.getElementById('adblocker-message');
            if(msg) msg.style.display = 'none';
        """)
    except:
        pass


def click_start_afk(sb):
    adblocker(sb)
    for attempt in range(3):
        try:
            sb.wait_for_element_visible("#afk-action-trigger", timeout=5)
            element = sb.find_element("#afk-action-trigger")
            
            # Scroll element to the center of the viewport to prevent out-of-bounds errors
            sb.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(1)
            
            actions = ActionChains(sb.driver)
            size = element.size
            w = size.get('width', 100)
            h = size.get('height', 40)
            
            # 计算视口相对边界以防止鼠标移动超出页面范围
            try:
                rect = sb.execute_script("return arguments[0].getBoundingClientRect();", element)
                viewport_w = sb.execute_script("return window.innerWidth || document.documentElement.clientWidth;")
                viewport_h = sb.execute_script("return window.innerHeight || document.documentElement.clientHeight;")
                cx = rect['left'] + rect['width'] / 2
                cy = rect['top'] + rect['height'] / 2
                
                margin = 20
                min_rx = int(margin - cx)
                max_rx = int(viewport_w - margin - cx)
                min_ry = int(margin - cy)
                max_ry = int(viewport_h - margin - cy)
                
                low_rx = max(min_rx, -400)
                high_rx = min(max_rx, 400)
                low_ry = max(min_ry, -300)
                high_ry = min(max_ry, 300)
                
                if low_rx > high_rx:
                    low_rx, high_rx = high_rx, low_rx
                if low_ry > high_ry:
                    low_ry, high_ry = high_ry, low_ry
            except Exception as e:
                log("Failed to calculate precise bounds: %s" % e)
                low_rx, high_rx = -100, 100
                low_ry, high_ry = -100, 100

            # 模拟人类在页面和按钮周围进行无规则移动
            log("Simulating random human-like mouse movements...")
            # 随机移动 4 到 7 次
            for i in range(random.randint(4, 7)):
                # 在按钮周围产生较大的随机偏移量（代表在页面其他部位闲逛）
                rx = random.randint(low_rx, high_rx)
                ry = random.randint(low_ry, high_ry)
                actions.move_to_element_with_offset(element, rx, ry)
                actions.pause(random.uniform(0.15, 0.4))
                
            # 移到按钮上，但稍稍偏离中心
            log("Moving mouse onto the button with minor offset...")
            btn_rx = random.randint(-int(w * 0.3), int(w * 0.3))
            btn_ry = random.randint(-int(h * 0.3), int(h * 0.3))
            actions.move_to_element_with_offset(element, btn_rx, btn_ry)
            actions.pause(random.uniform(0.3, 0.6))
            
            # 精准对齐按钮中心并短暂停顿
            actions.move_to_element(element)
            actions.pause(random.uniform(0.6, 1.2))
            
            # 4. 按住按钮
            log("Holding Start AFK button...")
            actions.click_and_hold(element).perform()
            
            start_hold = time.time()
            success = False
            while time.time() - start_hold < 2.0:  # max hold 2 seconds
                time.sleep(0.05) # check every 50ms
                try:
                    # Accessing properties of disappearing elements will raise
                    # stale element reference or element not interactable exceptions
                    if not element.is_displayed():
                        success = True
                        break
                    _ = element.size
                except Exception as e:
                    err_msg = str(e)
                    if "element not interactable" in err_msg or "has no size and location" in err_msg or "stale" in err_msg:
                        log("Expected visibility exception caught during hold: %s" % err_msg)
                        success = True
                        break
            
            # Release mouse button
            try:
                release_actions = ActionChains(sb.driver)
                release_actions.release().perform()
            except:
                pass
            log("Released Start AFK!")
            
            if success or not sb.is_element_visible("#afk-action-trigger"):
                log("Button #afk-action-trigger is no longer visible/interactable, session started!")
                return True
            raise Exception("Button #afk-action-trigger is still visible after 2s holding")
        except Exception as e:
            err_msg = str(e)
            if "element not interactable" in err_msg or "has no size and location" in err_msg:
                log("Caught expected exception in outer block: %s" % err_msg)
                try:
                    ActionChains(sb.driver).release().perform()
                except:
                    pass
                return True
            log("Attempt %d failed: %s" % (attempt + 1, err_msg[:200]))
    return False


def run_earn_session(sb, session_num, token):
    log("Loading /earn...")
    sb.uc_open_with_reconnect("https://free.freezehost.pro/earn", reconnect_time=6)
    time.sleep(15)

    url = sb.get_current_url()
    if not url.startswith("https://free.freezehost.pro"):
        log("Session expired, re-login...")
        if not login_via_discord_token(sb, token):
            return False
        sb.uc_open_with_reconnect("https://free.freezehost.pro/earn", reconnect_time=6)
        time.sleep(15)

    log("Waiting Turnstile...")
    token_val = wait_turnstile(sb, timeout=120)
    if not token_val:
        log("Turnstile failed!")
        try:
            os.makedirs("screenshots")
            sb.save_screenshot("screenshots/fh_fail_%d_%d.png" % (INSTANCE_ID, session_num))
        except:
            pass
        return False

    log("Turnstile OK! Token: %s..." % token_val[:30])

    if not click_start_afk(sb):
        log("WARNING: Start AFK button click failed!")
        return False

    log("Earning for %ds..." % SESSION_DURATION)
    start = time.time()
    while time.time() - start < SESSION_DURATION:
        try:
            url = sb.get_current_url()
            if not url.startswith("https://free.freezehost.pro"):
                log("Expired during earning")
                break
        except:
            break

        if MAX_RUNTIME > 0 and (time.time() - global_start) > MAX_RUNTIME * 60:
            log("Max runtime reached!")
            return None

        time.sleep(30)

    log("Session #%d done" % session_num)
    return True


def send_tg_message(start_time):
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        return

    end_time = time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        import requests
        import json
        tg_msg = f"""[FreezeHost] AFK finished!
        Start Time: {start_time}
        End Time: {end_time}
        Coins Start: {coins_start}
        Coins End: {coins_end}
        """
    
        requests.post(
            "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": tg_msg}
        )
    except Exception as e:
        log("Failed to send telegram message: %s" % str(e))

def get_coins(sb):
    """获取硬币数"""
    selector = "div.text-right > div.flex > span:last-child"
    sb.wait_for_element(selector, timeout=60)
    try:
        coins = sb.find_element(By.CSS_SELECTOR, selector).text
        return coins
    except Exception as e:
        log("Failed to get coins: %s" % str(e))
        return None

def main():
    global global_start
    global coins_start
    global coins_end

    start_time = time.strftime("%Y-%m-%d %H:%M:%S")

    if not DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN not set!")
        print("Set via: export DISCORD_TOKEN='your_token'")
        return

    # 支持多个 token（逗号分隔），按实例编号选
    tokens = [t.strip() for t in DISCORD_TOKEN.split(",") if t.strip()]
    token = tokens[INSTANCE_ID % len(tokens)]

    log("=" * 50)
    log("FreezeHost AFK - Instance #%d" % INSTANCE_ID)
    log("Token: %s...%s" % (token[:10], token[-5:]))
    log("Proxy: %s" % (WARP_PROXY or "none"))
    log("=" * 50)

    global_start = time.time()

    sb_options = {
        "uc": True,
        "test": True,
        "headed": True,
        "xvfb": True,
        "chromium_arg": "--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--window-size=1280,720",
    }

    if WARP_PROXY:
        sb_options["proxy"] = WARP_PROXY

    with SB(**sb_options) as sb:
        if not login_via_discord_token(sb, token):
            log("Login failed!")
            return
        log("Login OK!")
        # 等待页面刷新
        time.sleep(5)

        coins_start = get_coins(sb)
        log("Coins Start: %s" % coins_start)

        session = 0
        while True:
            if MAX_RUNTIME > 0 and (time.time() - global_start) > MAX_RUNTIME * 60:
                log("Max runtime reached!")
                break

            session += 1
            log("")
            log("=== Session #%d ===" % session)

            result = run_earn_session(sb, session, token)
            if result is None:
                break
            if not result:
                log("Session failed, retrying...")

            time.sleep(5)

        # 循环结束，在关闭浏览器前刷新页面并截取结束图
        sb.refresh()
        coins_end = get_coins(sb)
        log("Coins End: %s" % coins_end)
        
    send_tg_message(start_time)
    log("Done!")


if __name__ == "__main__":
    main()
