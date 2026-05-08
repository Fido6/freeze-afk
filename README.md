# FreezeHost AFK - 自动挂机赚币

自动登录 [FreezeHost](https://free.freezehost.pro/earn) 并保持挂机赚币的 Python 脚本。

## 原理

- **SeleniumBase UC 模式**：使用 Undetected Chrome 绕过 Cloudflare 检测
- **WARP 代理**：WARP IP 是 Cloudflare 信任的，Turnstile challenge 会降级为自动通过
- **Discord Token 登录**：注入 token 到 localStorage，自动完成 OAuth 流程
- **绕过广告拦截检测**：页面会检测广告拦截器并禁用赚币按钮，脚本自动绕过
- **点击 Start AFK 按钮**：页面需要手动点击 "Start AFK Session" 按钮才会建立 WebSocket 连接开始赚币
- **浏览器保持挂机**：页面 JS 自动处理 WebSocket 连接和挑战响应，每 60 秒获得 1 币

## 赚币速度

- 每个 session 最长 20 分钟（约 20 币）
- session 结束后自动刷新页面重新过 Turnstile
- 每小时约 60 币

## 本地运行

### 前置要求

1. **Python 3.8+**
2. **SeleniumBase**：`pip install seleniumbase`
3. **pyvirtualdisplay**（Linux 服务器需要）：`pip install pyvirtualdisplay`
4. **Cloudflare WARP**（推荐，用于绕过 Turnstile）

### 安装 WARP（代理模式，非全局）

```bash
# Debian/Ubuntu
curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg | sudo gpg --yes --dearmor -o /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ bookworm main" | sudo tee /etc/apt/sources.list.d/cloudflare-warp.list
sudo apt update && sudo apt install -y cloudflare-warp

# 注册并连接（代理模式，不接管全局流量）
warp-cli registration new
warp-cli mode proxy          # SOCKS5 127.0.0.1:40000
warp-cli connect

# 验证
curl --proxy socks5://127.0.0.1:40000 https://www.cloudflare.com/cdn-cgi/trace
# 应该看到 warp=on
```

### 使用方法

#### 方式一：环境变量

```bash
export DISCORD_TOKEN="your_discord_token_here"
python freeze_afk.py
```

#### 方式二：直接填写

编辑脚本中的 `DISCORD_TOKEN` 变量：

```python
DISCORD_TOKEN = "your_discord_token_here"
```

### 自定义配置

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `DISCORD_TOKEN` | - | Discord Token（必填） |
| `WARP_PROXY` | `socks5://127.0.0.1:40000` | WARP 代理地址，设为空禁用 |
| `MAX_RUNTIME` | `0`（无限） | 最大运行时长（分钟） |

## GitHub Actions 运行

支持在 GitHub Actions 上自动运行，无需自己的服务器。

### 设置步骤

1. **Fork 本仓库**
2. **添加 Secret**：进入仓库 Settings → Secrets and variables → Actions → New repository secret，添加 `DISCORD_TOKEN`
3. **运行方式**：
   - **手动触发**：Actions 页面 → AFK Earn → Run workflow，可设置运行时长（分钟）
   - **定时运行**：默认每 8 小时自动运行一次，每次 5 小时（300 分钟）

### 运行时长说明

- GitHub Actions 最长运行 6 小时
- 默认每次运行 300 分钟（5 小时），约赚 300 币
- 可手动触发时自定义时长

## 获取 Discord Token

1. 打开 Discord 网页版并登录
2. 按 F12 打开开发者工具
3. 在 Console 中输入：`localStorage.token`（去掉引号后的值就是你的 token）

## 工作流程

```
1. 启动 → 打开 FreezeHost
2. 点击 Discord 登录 → 注入 token → 自动 OAuth 回调
3. 进入 /earn 页面
4. 等待 Turnstile 验证通过（WARP IP + UC 模式自动通过）
5. 绕过广告拦截检测 → 点击 Start AFK Session 按钮
6. WebSocket 连接建立 → 页面自动赚币
7. 保持页面 20 分钟（每 60 秒 +1 币）
8. Session 结束 → 刷新页面 → 重新过 Turnstile → 下一轮
9. 循环直到达到最大运行时长
```

## 注意事项

- **必须点击 Start AFK 按钮**：页面不会自动开始赚币，需要点击 "Start AFK Session" 按钮才会建立 WebSocket
- **绕过广告拦截检测**：页面检测到广告拦截会禁用按钮，脚本自动注入 `adblockerDetected = false` 绕过
- **不要手动关闭 Funding Choices 弹窗**：点击或删除弹窗会干扰 Turnstile 渲染
- **必须 headed 模式**：Turnstile 在 headless 模式下不工作
- **Linux 服务器需要 Xvfb**：脚本自动启动虚拟显示器
- **WARP 推荐用代理模式**：避免全局代理影响其他服务

## License

MIT
