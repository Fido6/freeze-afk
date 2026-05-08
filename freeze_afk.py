#!/usr/bin/env python3
"""
FreezeHost AFK - 自动挂机赚币脚本
使用 SeleniumBase UC 模式绕过 Cloudflare Turnstile + 广告拦截检测
"""
import os
import time
import platform

# Linux 服务器上需要虚拟显示器
if platform.system().lower() == "linux":
    from pyvirtualdisplay import Display
    disp = Display(visible=False, size=(1920, 1080))
    disp.start()
    os.environ["DISPLAY"] = disp.new_display_var

from seleniumbase import SB

# Discord Token - 从环境变量读取，或直接填写
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")

# WARP 代理地址（可选，推荐使用）
WARP_PROXY = os.environ.get("WARP_PROXY", "socks5://127.0.0.1:40000")

# 最大运行时长（分钟），0 = 无限
MAX_RUNTIME = int(os.environ.get("MAX_RUNTIME", "0"))

# 每个 session 赏币时长（秒）
SESSION_DURATION = 1200  # 20 分钟


def log(msg):
    """带时间戳的日志"""
    ts = time.strftime("%H:%M:%S")
    print("[%s] %s" % (ts, msg), flush=True)


def wait_turnstile(sb, timeout=120):
    """
    等待 Turnstile 验证通过

    原理：
    1. WARP IP 是 Cloudflare 信任的，challenge 会降级为 managed 类型
    2. SeleniumBase UC 模式自动处理验证框点击
    3. 等待 cf-turnstile-response input 出现值
    """
    start = time.time()
    last_click = 0

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
                sb.uc_gui_click_captcha()
                last_click = now
            except:
                pass
        time.sleep(2)

    return None


def login_via_discord_token(sb):
    """
    通过 Discord Token 登录 FreezeHost

    原理：
    1. 点击 FreezeHost 的 Discord 登录按钮
    2. 在 discord.com 页面注入 token 到 localStorage
    3. 刷新页面后 Discord 自动登录
    4. OAuth 回调返回 FreezeHost
    """
    log("Opening FreezeHost...")
    sb.uc_open_with_reconnect("https://free.freezehost.pro", reconnect_time=5)
    time.sleep(5)

    # 点击登录按钮
    log("Click Login...")
    try:
        sb.click("button#login-btn")
    except:
        sb.execute_script("document.getElementById('login-btn')?.click();")
    time.sleep(3)

    # 确认条款弹窗
    try:
        sb.wait_for_element_visible("button#confirm-login", timeout=5)
        sb.click("button#confirm-login")
        log("Confirmed terms")
    except:
        log("No terms dialog")
    time.sleep(2)

    # 如果跳转到 Discord 登录页
    if "discord.com" in sb.get_current_url():
        log("Inject Discord token...")
        sb.execute_script("""(function(){
            var token = "%s";
            var f = document.createElement("iframe");
            f.style.display = "none";
            document.body.appendChild(f);
            try { f.contentWindow.localStorage.setItem("token", '"'+token+'"'); } catch(e) {}
            try { localStorage.setItem("token", '"'+token+'"'); } catch(e) {}
            document.body.removeChild(f);
        })();""" % DISCORD_TOKEN)

        log("Reload to apply token...")
        sb.driver.refresh()
        time.sleep(8)

        url = sb.get_current_url()
        log("After inject: %s" % url)

        # Token 无效会停在登录页
        if "discord.com/login" in url:
            log("Token invalid!")
            return False

        # 如果还在 OAuth 页面，自动授权
        if "discord.com/oauth2" in url:
            log("Auto-authorize...")
            sb.execute_script("""(function(){
                document.querySelectorAll("button").forEach(function(btn){
                    if(btn.textContent.toLowerCase().includes("authorize")) btn.click();
                });
            })();""")
            time.sleep(5)

        # 等待跳回 FreezeHost（精确检查 URL 开头）
        for _ in range(20):
            url = sb.get_current_url()
            if url.startswith("https://free.freezehost.pro"):
                break
            time.sleep(2)

    url = sb.get_current_url()
    log("Final URL: %s" % url)
    # 必须 URL 以 free.freezehost.pro 开头才算成功
    return url.startswith("https://free.freezehost.pro")


def click_start_afk(sb):
    """
    点击 Start AFK Session 按钮

    关键：需要绕过页面的广告拦截检测！
    页面会检测 adsbygoogle 元素的 offsetHeight，如果为 0 就判定为广告拦截，
    禁用按钮并显示 "Disable AdBlocker First"。

    解决方案：在点击前注入 JS 把 adblockerDetected 设为 false，
    并强制按钮启用。
    """
    log("Bypassing adblocker detection...")
    try:
        sb.execute_script("""
            if(typeof adblockerDetected !== 'undefined') adblockerDetected = false;
            var msg = document.getElementById('adblocker-message');
            if(msg) msg.style.display = 'none';
        """)
    except:
        pass

    # 强制按钮可用
    try:
        sb.execute_script("""
            var btn = document.getElementById('start-afk-btn');
            if(btn){ btn.disabled = false; btn.textContent = 'Start AFK Session'; }
        """)
    except:
        pass

    # 尝试点击按钮（按钮可能因为广告拦截被隐藏）
    for attempt in range(3):
        try:
            sb.wait_for_element_visible("#start-afk-btn", timeout=5)
            sb.click("#start-afk-btn")
            log("Clicked Start AFK Session!")
            time.sleep(3)
            # 检查 WebSocket 是否建立
            ws_state = sb.execute_script(
                "return (typeof ws !== 'undefined' && ws) ? ws.readyState : -1;"
            )
            log("WebSocket state: %s" % ws_state)
            return True
        except Exception as e:
            log("Attempt %d: %s" % (attempt + 1, str(e)[:80]))
            # JS fallback - 直接用 JS 点击（绕过可见性检测）
            try:
                sb.execute_script("""
                    if(typeof adblockerDetected !== 'undefined') adblockerDetected = false;
                    document.getElementById('start-afk-btn')?.click();
                """)
                time.sleep(3)
                ws_state = sb.execute_script(
                    "return (typeof ws !== 'undefined' && ws) ? ws.readyState : -1;"
                )
                log("JS click - WebSocket state: %s" % ws_state)
                if ws_state == 0 or ws_state == 1:
                    return True
            except:
                pass

    return False


def run_earn_session(sb, session_num):
    """
    执行一次挂机赚币 session

    每个 session 最长 20 分钟（1200秒）
    页面 JavaScript 自动处理 WebSocket 连接和挑战响应
    """
    log("Loading /earn page...")
    sb.uc_open_with_reconnect("https://free.freezehost.pro/earn", reconnect_time=6)
    time.sleep(15)

    # 检查是否需要重新登录（精确检查 URL）
    url = sb.get_current_url()
    if not url.startswith("https://free.freezehost.pro"):
        log("Session expired, re-login...")
        if not login_via_discord_token(sb):
            return False
        sb.uc_open_with_reconnect("https://free.freezehost.pro/earn", reconnect_time=6)
        time.sleep(15)

    # 等待 Turnstile 验证
    log("Waiting Turnstile...")
    token = wait_turnstile(sb, timeout=120)

    if token:
        log("Turnstile passed! Token: %s..." % token[:30])

        # 绕过广告拦截 + 点击 Start AFK 按钮
        if not click_start_afk(sb):
            log("WARNING: Start AFK button click failed!")

        log("Session #%d earning for %ds (%d min)..." % (
            session_num, SESSION_DURATION, SESSION_DURATION // 60))

        # 保持页面，页面 JS 自动赚币
        start = time.time()
        while time.time() - start < SESSION_DURATION:
            try:
                url = sb.get_current_url()
                if not url.startswith("https://free.freezehost.pro"):
                    log("Session expired during earning")
                    break
            except:
                break

            # 检查最大运行时长
            if MAX_RUNTIME > 0 and (time.time() - global_start) > MAX_RUNTIME * 60:
                log("Max runtime reached!")
                return None  # None 表示应该退出

            # 定期检查 WebSocket 状态
            elapsed = time.time() - start
            if int(elapsed) % 300 == 0 and elapsed > 0:
                try:
                    ws_state = sb.execute_script(
                        "return (typeof ws !== 'undefined' && ws) ? ws.readyState : -1;"
                    )
                    log("WebSocket state: %s (elapsed: %ds)" % (ws_state, int(elapsed)))
                except:
                    pass

            time.sleep(30)

        log("Session #%d completed!" % session_num)
        return True
    else:
        log("Turnstile failed!")
        try:
            sb.save_screenshot("/tmp/fh_fail_%d.png" % session_num)
        except:
            pass
        return False


def main():
    global global_start

    if not DISCORD_TOKEN:
        print("ERROR: DISCORD_TOKEN not set!")
        print("Set via: export DISCORD_TOKEN='your_token'")
        print("Or set as GitHub Secret: DISCORD_TOKEN")
        return

    log("=" * 50)
    log("FreezeHost AFK - Auto Earn Coins")
    log("=" * 50)
    log("Proxy: %s" % (WARP_PROXY or "none"))
    log("Max runtime: %d min %s" % (MAX_RUNTIME, "(unlimited)" if MAX_RUNTIME == 0 else ""))
    log("Session duration: %ds (%d min)" % (SESSION_DURATION, SESSION_DURATION // 60))
    log("=" * 50)

    global_start = time.time()

    # SeleniumBase UC 配置
    sb_options = {
        "uc": True,           # Undetected Chrome 模式
        "test": True,
        "headed": True,       # 需要 headed 模式（Turnstile 需要）
        "chromium_arg": "--no-sandbox,--disable-dev-shm-usage,--disable-gpu,--window-size=1280,720",
    }

    if WARP_PROXY:
        sb_options["proxy"] = WARP_PROXY

    with SB(**sb_options) as sb:
        # 登录
        if not login_via_discord_token(sb):
            log("Login failed!")
            return
        log("Login successful!")

        # 无限循环挂机
        session = 0
        while True:
            # 检查最大运行时长
            if MAX_RUNTIME > 0 and (time.time() - global_start) > MAX_RUNTIME * 60:
                log("Max runtime reached, exiting!")
                break

            session += 1
            log("")
            log("=== Session #%d ===" % session)

            result = run_earn_session(sb, session)
            if result is None:
                break
            if not result:
                log("Session failed, retrying...")

            time.sleep(5)

    log("Done!")


if __name__ == "__main__":
    main()