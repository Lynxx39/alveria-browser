# 🦊 Alveria Browser

> **Ultra-Lightweight (34 MB RSS) Stealth Headless Browser for AI Agents & Automation**  
> *Camoufox-tier fingerprint protection & human simulation built on top of the Obscura Rust+V8 engine.*

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20(x86__64%20%7C%20ARM64%20%7C%20STB)-orange.svg)](https://github.com/Lynxx39/alveria-browser)
[![Python](https://img.shields.io/badge/Python-3.9%2B-green.svg)](https://python.org)
[![Memory Footprint](https://img.shields.io/badge/RAM%20Usage-~34%20MB%20RSS-brightgreen.svg)](#benchmark)

---

## 💡 Why Alveria Browser?

Traditional headless browsers (Chromium, Puppeteer, Camoufox) are **monolithic bloatware**:
* They eat **250 MB – 450 MB RAM per instance**, causing instant Out-Of-Memory (OOM) crashes on low-spec VPS, Docker containers, and ARM STBs.
* They spend massive CPU cycles rendering pixels and painting frames that **no bot or AI agent ever needs to see**.

**Alveria Browser** solves this by pairing **Obscura's Rust + Google V8 engine** with a comprehensive **Camoufox-grade stealth & human simulation layer**:

| Feature | Standard Chromium | Camoufox | Obscura (Vanilla) | **Alveria Browser** |
| :--- | :---: | :---: | :---: | :---: |
| **Idle RAM (RSS)** | ~250 MB | ~300 MB | ~31 MB | **~34 MB** 🚀 |
| **Heavy Page RAM** | 450–550 MB | 700–850 MB | ~97 MB | **~100 MB** 🚀 |
| **Cold Startup Time** | 14.1 s | 7.4 s | 0.08 s | **0.08 s** ⚡ |
| **JavaScript Fidelity** | Full (V8) | Full (SpiderMonkey) | Full (V8) | **Full (Google V8)** |
| **`navigator.webdriver`** | Failed | Passed | Failed ❌ | **Passed (Purged)** ✅ |
| **WebGL Context** | Real GPU | Real GPU | `null` ❌ | **Unmasked Stub** ✅ |
| **Canvas Noise** | None | Randomized | None ❌ | **Deterministic LCG** ✅ |
| **AudioContext Noise** | None | Randomized | None ❌ | **Injected Noise** ✅ |
| **Client Hints Sync** | None | Simulated | None ❌ | **HTTP & JS (`userAgentData`)** ✅ |
| **Font Protection** | Leaked | Protected | Leaked ❌ | **Platform Whitelist** ✅ |
| **Human Simulation** | None | Manual | None ❌ | **Bézier + Gaussian** ✅ |
| **Procedural Random Profiles** | None | Supported | None ❌ | **Dynamic Matched Pools** ✅ |
| **Cross-Origin Challenges (Turnstile/reCAPTCHA)** | Supported | Supported | Not Supported ❌ | **External Token Bridge (`inject_turnstile_token`)** ⚠️ |

---

## ⚡ 1-Line Instant Quickstart

No manual binary compilation or hunting for releases needed. Alveria **auto-detects your architecture (x86_64 or ARM64)** and sets up everything in seconds.

```bash
git clone https://github.com/Lynxx39/alveria-browser.git
cd alveria-browser
chmod +x install.sh
./install.sh
```

*(Or simply run `python3 alveria_browser.py install`)*

---

## 🛡️ Camoufox-Tier Stealth Features

Alveria injects zero-overhead native patches before any script executes on the page:

1. **WebDriver Elimination**: Completely purges `navigator.webdriver` from the **entire prototype chain** (bypasses `'webdriver' in navigator` checks).
2. **WebGL Context Unmasking**: Provides realistic unmasked vendor/renderer stubs (Intel UHD, NVIDIA GTX, AMD Radeon, Apple M-Series Metal) complete with 20+ GL parameters, extensions, and shader precision format.
3. **Canvas Fingerprint Neutralizer**: High-entropy pseudo-random noise (LCG xorshift) injected into `toDataURL` and `getImageData`, ensuring a unique yet consistent canvas hash per session.
4. **AudioContext Noise**: Perturbs `AudioBuffer.prototype.getChannelData` and `AnalyserNode` frequency spectrum to defeat audio fingerprinting (CreepJS / Picasso).
5. **Platform-Consistent Font Whitelisting**: Intercepts `document.fonts.check()` so Windows profiles only answer to Windows fonts, and Mac profiles only answer to Apple typography.
6. **Battery & Network Information**: Realistically mocks `navigator.getBattery()` (88-98% battery level, charging) and `navigator.connection` (4G, 10Mbps, 50ms RTT).
7. **SpeechSynthesis Voices**: Generates native OS voice profiles (Microsoft David/Zira for Win32, Samantha/Alex for Mac).
8. **WebRTC IP Shield**: Blocks internal IP leakage by filtering `RTCPeerConnection` ice servers and stripping host candidates.
9. **Tracker & Analytics Blocker**: Automatically drops connections to resource-heavy telemetry (Google Analytics, Clarity, Hotjar, Sentry, Facebook/TikTok pixels) saving bandwidth and keeping RAM usage minimal.
10. **Client Hints Synchronization**: Bridges both the network layer (`Sec-CH-UA`, `Sec-CH-UA-Platform`, `Sec-CH-UA-Mobile`) and the JavaScript API (`navigator.userAgentData` with `getHighEntropyValues()`), ensuring Cloudflare and enterprise WAFs observe 100% matched signals.
11. **Procedural Profile Generator**: Support for `profile="random"`, `profile="random-chrome"`, or `profile="random-firefox"` generates mathematically coherent identities (screen, GPU model, cores, memory, OS) on the fly, preventing device repetition across large scraping fleets.
12. **Native Code Function Masking**: Every patched prototype method (`getContext`, `toDataURL`, `getImageData`, `getParameter`, `getChannelData`, `fonts.check`) is wrapped in Camoufox-style native function stringification (`function () { [native code] }`), defeating deep prototype inspection and wrapper leaks.
13. **Camoufox-Aligned Firefox Profiles**: Support for native Firefox identities (Profiles 8–10 or `profile="firefox"`). When active, `window.chrome` and `navigator.userAgentData` are purged, `navigator.oscpu`, `navigator.buildID`, and `InstallTrigger` are populated, and `sec-ch-ua` headers are withheld to match real Gecko browser behavior.
14. **Zero-Overhead GeoIP Auto-Matching (`geoip=True`)**: Automatically aligns timezone, locale, languages (`Accept-Language`), and Playwright GPS coordinates directly with the proxy IP using standard library HTTP APIs with thread-safe caching. Completely eliminates proxy-timezone mismatches with 0 KB memory overhead (no heavy MaxMind `.mmdb` databases).

---

## 🎯 Human Simulation Engine

Bypass modern behavioral bot detection (Cloudflare, Akamai, Datadome):

* **`br.human_move(page, x, y)`**: Traverses the viewport using **Cubic Bézier curves** following **Fitts's Law** with natural deceleration near the target.
* **`br.human_click(page, selector)`**: Moves mouse naturally, calculates bounding box with randomized interior coordinates, and pauses with human mousedown/mouseup latency (70–150ms).
* **`br.human_type(page, selector, text)`**: Types with natural Gaussian delay distribution (45–80 WPM), punctuation hesitation pauses, and **simulates human typos (2% rate) with automated Backspace correction**.
* **`br.human_scroll(page, delta_y)`**: Smooth scrolling utilizing a sinusoidal easing curve.
* **`br.drag_slider(page, handle_selector, distance_x)`**: Realistic S-curve slider drag with variable velocity and Y-axis micro-drift for Aliyun and Geetest puzzle captchas.

---

## 🌾 Built for Farming & Micro-VPS Automation

Designed to power synthetic user registration and account lifecycle farming (`farming/` suite):

* **`br.export_to_requests(page)`**: Extracts authenticated cookies and headers into a pre-configured `requests.Session` so workers can transition from browser automation to fast HTTP APIs immediately.
* **`br.get_cookies_dict(page)` & `br.set_cookies(cookies)`**: Seamless cookie persistence and session handoff between worker processes.
* **`br.fill_when_ready(page, selector, text)` & `br.click_when_ready(page, selector)`**: DOM stability polling + human interactions in one line.
* **Resource Saver Mode (`block_images=True`, `block_fonts=True`)**: Drops heavy assets at the CDP layer to keep RAM below ~40 MB during massive parallel account runs.
* **`br.solve_and_inject_turnstile(page)`**: Hybrid Turnstile bridge that solves via background solver/token pool and injects the token into Alveria's DOM.

---

## 💻 Usage

### 1. Python API

```python
from alveria_browser import Alveria

# Profile 1 = Windows 10 Intel HD (coherent UA, cores, RAM, screen & WebGL)
with Alveria(profile=1, block_trackers=True) as br:
    page = br.page()
    page.goto("https://target.com/login", wait_until="domcontentloaded")
    
    # Non-blocking smart hydration wait
    br.smart_wait(page, timeout=15)

    # Human-like typing with auto-backspace on typo
    br.human_type(page, "input[name=email]", "myuser@example.com")
    br.human_type(page, "input[name=password]", "SuperSecretPassword123!")

    # Smooth curve mouse move & click
    br.human_click(page, "button[type=submit]")

    # Inject external Turnstile token if form requires cf-turnstile-response
    # br.inject_turnstile_token(page, token="0.xxxx...")

    print(f"[+] Done! Active RAM: {br.rss_mb()} MB")
```

### 2. Command Line Interface (CLI)

```bash
# List available hardware-coherent device profiles
python3 alveria_browser.py profiles

# Fetch web content with stealth evaluation
python3 alveria_browser.py fetch https://bot.sannysoft.com --wait 10

# Capture screenshot
python3 alveria_browser.py shot https://example.com page.png

# Run as foreground CDP server (ready for Playwright/Puppeteer connect_over_cdp)
python3 alveria_browser.py serve --port 9222 --profile 1
```

---

## 📱 Hardware-Coherent Profiles

Every profile synchronizes User-Agent, platform, hardwareConcurrency, deviceMemory, WebGL vendor/renderer, screen resolution, timezone, fonts, and voices:

| # | Profile Name | OS / Platform | Cores | RAM | Resolution | Timezone |
|---|---|---|---|---|---|---|
| **1** | `win10-intel-hd` | Win32 | 8 | 8 GB | 1920×1080 | Asia/Jakarta |
| **2** | `win10-nvidia` | Win32 | 16 | 16 GB | 1920×1080 | Asia/Jakarta |
| **3** | `win11-amd` | Win32 | 12 | 8 GB | 2560×1440 | Asia/Singapore |
| **4** | `macbook-pro-m3` | MacIntel | 10 | 16 GB | 1512×982 @2x | Asia/Jakarta |
| **5** | `macbook-air-m2` | MacIntel | 8 | 8 GB | 1440×900 @2x | Asia/Jakarta |
| **6** | `win10-lowend` | Win32 | 4 | 4 GB | 1366×768 | Asia/Jakarta |
| **7** | `linux-ubuntu-iris` | Linux x86_64 | 8 | 16 GB | 1920×1080 | Asia/Jakarta |
| **8** | `win10-firefox` | Win32 (Gecko) | 8 | 16 GB | 1920×1080 | Asia/Jakarta |
| **9** | `linux-firefox` | Linux x86_64 (Gecko) | 8 | 16 GB | 1920×1080 | Asia/Jakarta |
| **10** | `mac-firefox` | MacIntel (Gecko) | 8 | 16 GB | 1440×900 @2x | Asia/Jakarta |
| **`random`** | `procedural-random` | Dynamic (Win/Mac/Linux) | 4–16 | 8–16 GB | Matched | Dynamic / GeoIP |
| **`firefox`** | `procedural-firefox` | Dynamic Firefox (Gecko) | 4–16 | 8–16 GB | Matched | Dynamic / GeoIP |

---

## 📊 Benchmark

Measured on a low-spec **ARM64 STB (1.8 GB RAM)** running Debian 12:

```
bot.sannysoft.com:
  WebDriver (New)               missing (passed)
  Chrome (New)                  present (passed)
  Permissions (New)             default (passed)
  Plugins Length                5 (passed)
  WebGL Vendor & Renderer       Google Inc. (Intel) / ANGLE UHD 630 (passed)
  PHANTOM / HEADLESS CHECKS     all passed

creepjs:
  WebRTC host connection        blocked (passed)
  Lies                          0 (passed)
  Fonts matching                Consistent Windows/Mac profile
```

---

## ⚠️ Architecture Note: Cross-Origin Iframes & Turnstile

Obscura's Rust engine implements lightweight in-JS DOM frame simulation (`_IframeDocument`, `_IframeWindow`) rather than independent OS/process browsing contexts. Because interactive widgets like **Cloudflare Turnstile** and **reCAPTCHA** require native cross-origin `postMessage` protocol between independent contexts, they cannot render or solve natively inside the engine.

* **For 95% of automation**: Login flows, web scraping, synthetic user farming, and standard anti-bot evasion (FingerprintJS, CreepJS, Bot Sannysoft) work out-of-the-box at ultra-low memory (~30 MB RSS).
* **For Turnstile-gated forms**: Acquire the token via an external solver API or solver micro-service, then inject it instantly into Alveria's page:
  ```python
  br.inject_turnstile_token(page, token="0.xxxx...")
  ```

---

## 🤝 Credits & Acknowledgements

* Built on top of the incredible **[Obscura](https://github.com/h4ckf0r0day/obscura)** browser engine by [@h4ckf0r0day](https://github.com/h4ckf0r0day).
* Stealth and anti-fingerprinting concepts inspired by **[Camoufox](https://github.com/daijro/camoufox)**.

## 📄 License

Licensed under the [Apache License 2.0](LICENSE).
