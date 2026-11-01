# alveria-browser — Stealth Browser Ringan untuk STB ARM64

> Engine: **obscura 0.2.6** (Rust + V8) + lapisan stealth ala Camoufox.
> RSS **32–78 MB** (vs Chromium 250 MB, Camoufox 300 MB). Dibuat untuk STB 1.8 GB RAM.
> Lokasi: `/mnt/hdd/browser/alveria/` · CLI: `alveria-browser` (symlink ke `/usr/local/bin`)

## Kenapa

STB OOM saat menjalankan Chromium/Camoufox untuk halaman berat (Stripe, SPA React).
obscura ringan tapi punya 3 bug nyata + tidak punya WebGL. `alveria-browser` menambal semua itu.

## Struktur

```
/mnt/hdd/browser/alveria/
├── alveria_browser.py     # engine wrapper + stealth layer (≈600 baris)
├── bin/
│   ├── obscura-core       # 81 MB, binary asli obscura stealth
│   ├── obscura-worker     # 77 MB
│   └── alveria-browser    # launcher bash
├── profiles/              # definisi profil (di kode)
├── storage/<profil>/      # cookie/localStorage persisten per profil
└── logs/core-<profil>.log
```

## CLI

```bash
alveria-browser profiles                          # list 6 profil
alveria-browser fetch <url> --eval "EXPR" --wait 15 --profile 1
alveria-browser shot  <url> out.png --wait 20 --profile 4
alveria-browser serve --port 9222 --profile 1     # foreground CDP
```

## Profil Bawaan

| # | Nama | Platform | Cores | RAM | Screen | TZ |
|---|---|---|---|---|---|---|
| 1 | win10-intel-hd | Win32 | 8 | 8 GB | 1920×1080 | Jakarta |
| 2 | win10-nvidia | Win32 | 16 | 16 GB | 1920×1080 | Jakarta |
| 3 | win11-amd | Win32 | 12 | 8 GB | 2560×1440 | Singapore |
| 4 | macbook-pro-m3 | MacIntel | 10 | 16 GB | 1512×982 @2x | Jakarta |
| 5 | macbook-air-m2 | MacIntel | 8 | 8 GB | 1440×900 @2x | Jakarta |
| 6 | win10-lowend | Win32 | 4 | 4 GB | 1366×768 | Jakarta |
| 7 | linux-ubuntu-iris | Linux x86_64 | 8 | 16 GB | 1920×1080 | Jakarta |

Semua nilai (UA, platform, cores, deviceMemory, WebGL, screen, timezone, locale, platform fonts, speech voices) **konsisten satu sama lain** — ini kunci lolos deteksi.

## Fitur Unggulan V0.3 (Hardened Edition)

1. **Anti-Fingerprint Level Camoufox (Tanpa Overhead)**:
   - **AudioContext noise injection**: Patch AudioBuffer & AnalyserNode agar hash audio acak deterministik per sesi.
   - **Font enumeration protection**: document.fonts.check() memfilter font asing non-platform.
   - **Battery & Network Information**: navigator.getBattery() realistis (88-98% battery, charging) & 4G connection.
   - **SpeechSynthesis voices**: window.speechSynthesis.getVoices() menyajikan suara bawaan OS asli (David/Zira di Win, Samantha/Alex di Mac).
   - **WebGL Unmasked Vendor/Renderer**: Lengkap dengan parameter GL asli & shader precision.
   - **Zero Leaks**: WebRTC stripped candidate & navigator.webdriver purged dari seluruh prototype chain.

2. **Human Simulation Engine**:
   - **br.human_move(page, x, y)**: Gerakan kursor mouse melengkung natural berbasis **Cubic Bezier curves** (Fitts's Law).
   - **br.human_click(page, selector)**: Klik dengan offset acak dalam bounding box elemen, jeda mousedown-mouseup 70-150ms.
   - **br.human_type(page, selector, text)**: Mengetik dengan distribusi jeda Gaussian (45-80 WPM), hesitation pause pada tanda baca, dan simulasi salah ketik (typo) 2% dengan backspace otomatis.
   - **br.human_scroll(page, delta_y)**: Scroll bertahap dengan akselerasi kurva sinus (ease-in-out).

3. **Tooling & Anti-Bot Automation**:
   - **br.extract_turnstile_token(page, timeout=45)**: Harvester otomatis untuk Cloudflare Turnstile token (turnstile.getResponse() atau response hidden input).
   - **block_trackers=True**: Memblokir puluhan domain tracker & analytics berat (Google Analytics, Clarity, Hotjar, Sentry, TikTok/FB pixel) di layer routing untuk menghemat RAM STB.
   - **br.smart_wait(page)**: Deteksi kestabilan DOM tanpa blocking sleep statis.

## Python API

```python
import sys; sys.path.insert(0, "/mnt/hdd/browser/alveria")
from alveria_browser import Alveria

with Alveria(profile=1, proxy="http://user:pass@host:port") as br:
    page = br.page()
    page.goto("https://target.com/", wait_until="domcontentloaded", timeout=90000)
    br.wait_settle(page, 15)                     # SPA butuh 15-20s

    # polling pendek — JANGAN evaluate async panjang (bug obscura 4.2)
    tok = br.poll_js(page, "() => document.querySelector('input[name=x]')?.value || null", timeout=40)
    print(tok, f"rss={br.rss_mb()}MB")
```

## Hasil Verifikasi Nyata

### bot.sannysoft.com (profile 1)

```
User Agent (Old)              Mozilla/5.0 (Windows NT 10.0; Win64; x64) ... Chrome/145.0.0.0 Safari/537.36
WebDriver (New)               missing (passed)          ← fixed
WebDriver Advanced            passed
Chrome (New)                  present (passed)
Permissions (New)             default
Plugins Length (Old)          5
Plugins is of type PluginArray passed
Languages (Old)               en-US,en
WebGL Vendor                  Google Inc. (Intel)
WebGL Renderer                ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)
PHANTOM_UA / _PROPERTIES / _ETSL / _LANGUAGE / _WEBSOCKET / _OVERFLOW   semua ok
```

**Sebelum patch:** `WebDriver (New): present (failed)` + WebGL = `err` (null).
**Sesudah:** semua passed.

### creepjs (profile 1)

```
WebRTC host connection:    blocked
foundation/ip:             unsupported / blocked
sdp capabilities:          blocked
devices (4):               dual m...
lies:                      0
Fonts:                     load (51/51) — "Like Windows 11"
FP ID:                     stable per storage-dir
```

WebRTC local-IP leak tertutup, tidak ada "lie" terdeteksi.

### RSS terukur

| Skenario | RSS |
|---|---|
| idle httpbin | 32–38 MB |
| bot.sannysoft (full detector) | 76–78 MB |
| creepjs (worker berat) | 157 MB |

## Lapisan Stealth yang Diterapkan

| Lapisan | Mekanisme |
|---|---|
| UA / platform / vendor | `--user-agent` engine + `defineProperty` JS |
| hardwareConcurrency / deviceMemory | JS override per profil |
| WebGL vendor+renderer | **stub WebGL** (obscura tidak punya GL backend) |
| Canvas noise | LCG deterministik per sesi, patch `getImageData` + `toDataURL` |
| `navigator.webdriver` | dihapus dari **seluruh prototype chain** (bukan di-define ulang) |
| Plugins / mimeTypes | 5 plugin PDF palsu, `PluginArray` asli |
| `window.chrome` | stub `runtime` + `loadTimes` + `csi` + `app` |
| Timezone / locale | engine (`OBSCURA_TIMEZONE`) + context Playwright |
| WebRTC leak | strip `iceServers`, host candidate blocked |
| Screen | width/height/avail/colorDepth konsisten dgn profil |
| TLS + tracker block | build `-stealth` obscura |

## Bug Obscura yang Ditangani

| # | Bug | Workaround di alveria |
|---|---|---|
| 1 | `Target.getTargetInfo` → `targetId: "browser"` | tidak dipakai; selalu `new_context()` + `new_page()` |
| 2 | `evaluate()` async panjang → `Execution context was destroyed` | semua helper pakai `poll_js()` (polling pendek) |
| 3 | `contexts[0].pages` kosong saat connect | selalu buat context+page sendiri |
| 4 | `getContext('webgl')` → `null` | stub WebGL lengkap dgn parameter realistis |
| 5 | `navigator.webdriver` own-property | hapus dari seluruh prototype chain |
| 6 | React/Remix hydration timeout 3s | `OBSCURA_MODULE_BUDGET_MS=60000` |

## Benchmark: alveria vs obscura-ori vs Chromium vs Camoufox

STB 1.8 GB RAM, `--workers 1`, cold start tiap run. Nav = `goto(domcontentloaded)`.

### `platform.liner.com` (SPA React/Remix, ~1600 char body)

| Engine | start | nav | total | RSS |
|---|---|---|---|---|
| **alveria** (5 run avg) | **0.08 s** | **6.1–13.3 s** | **17–25 s** | **100–104 MB** |
| obscura-ori (5 run avg) | 0.08 s | 7.5–13.9 s | 19–25 s | 97–102 MB |
| Chromium 145 | 14.1 s | 2.9 s | 29.0 s | **556 MB** |
| Camoufox 156 | 7.4 s | 7.5 s | 29.9 s | **866 MB** |

### `example.com` (halaman ringan)

| Engine | start | nav | total | RSS |
|---|---|---|---|---|
| **alveria** | **0.08 s** | 2.4 s | **13.6 s** | **33 MB** |
| obscura-ori | 0.08–1.0 s | 1.1 s | 12.3 s | 31 MB |
| Chromium 145 | 16.1 s | 1.1 s | 33.4 s | 478 MB |
| Camoufox 156 | 15.7 s | 2.2 s | 37.0 s | 781 MB |

### Kesimpulan

- **alveria vs obscura-ori: praktis sama** (±2 MB RSS, selisih waktu di dalam noise jaringan).
  Overhead stealth layer terukur **≈0 ms** — `fp_eval_ms` = 0–1 ms di kedua engine
  (50× baca `navigator.*` berturut-turut).
- **Kedua-duanya ~30× lebih cepat start** dari Chromium/Camoufox (0.08 s vs 14–16 s).
- **RSS 5× lebih kecil** dari Chromium (33–104 MB vs 478–556 MB) dan **8× lebih kecil** dari Camoufox.
- Nav obscura **lebih lambat** dari Chromium di halaman berat (tanpa GPU accel) tapi menang total
  di startup + memori → **lebih baik untuk farming berurutan banyak sesi**.

### Kenapa alveria tetap dipakai (walau kecepatan sama)

| Aspek | obscura-ori | alveria |
|---|---|---|
| WebGL | `null` ❌ | stub realistis ✅ |
| `navigator.webdriver` | `present (failed)` ❌ | `missing (passed)` ✅ |
| Canvas noise | tidak ada | LCG deterministik ✅ |
| Profil konsisten | manual via env | 6 profil siap pakai ✅ |
| WebRTC leak | default | blocked ✅ |
| Bug workaround | harus tulis sendiri | built-in ✅ |

**Biaya: 0 ms. Manfaat: lolos bot.sannysoft penuh.**

## Pitfalls

1. **Jangan pakai `page.evaluate` dengan promise >10s** — context dibunuh. Pakai `br.poll_js()`.
2. **Jangan `def(navigator,'webdriver',undefined)`** — itu justru membuat own-property yang terdeteksi. Cukup `delete`.
3. **WebGL stub bukan GL nyata** — kalau target melakukan render WebGL nyata (Three.js, WebGPU) hasilnya kosong. Untuk target seperti itu pakai Chromium/Camoufox.
4. **Cold start 20–40 s** di STB. Timeout < 90 s akan gagal.
5. **`--workers 1`** — naikkan hanya bila RAM bebas > 500 MB.
6. **Storage per profil** ada di `storage/<nama>/`; hapus folder itu untuk reset identitas.
7. **glibc ≥ 2.35** wajib (Debian 12 = 2.36 ✅).
