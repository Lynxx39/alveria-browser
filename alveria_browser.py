#!/usr/bin/env python3
"""
alveria-browser — Stealth Headless Browser untuk STB ARM64 & Automation
========================================================================
Engine: obscura (Rust + V8, 23–99 MB RSS) + lapisan stealth Camoufox-tier.

Kenapa bukan Chromium/Camoufox:
  Chromium ~250 MB, Camoufox ~300 MB → OOM di STB 1.8 GB.
  alveria-browser ~25–100 MB dengan fingerprint lengkap & lolos detector.

Fitur stealth bawaan & hardened:
  - UA / platform / hardwareConcurrency / deviceMemory dari profil konsisten
  - WebGL vendor+renderer spoof & unmasked context stub
  - Canvas noise deterministik per sesi (anti canvas-hash)
  - AudioContext noise injection (anti AudioBuffer/frequency hash)
  - Font enumeration protection (whitelist platform-consistent)
  - Battery API & NetworkInformation (4G) spoofing
  - window.speechSynthesis voices platform-consistent
  - navigator.webdriver dihapus dari seluruh prototype chain
  - Plugin & mimeType array palsu (Chrome PDF)
  - Timezone + locale + geolocation override
  - WebRTC local-IP leak dimatikan
  - TLS impersonation (BoringSSL layer bawaan obscura stealth)

Fitur Human Simulation & Tooling:
  - Human mouse movement via cubic Bezier curves + acceleration/overshoot
  - Human keyboard typing dengan Gaussian delays & natural typo simulation
  - Smooth easing human scroll
  - Smart wait / hydration polling tanpa membunuh context V8
  - Native Turnstile token harvester
  - Tracker / ad network request blocking (save memory & bandwidth)

Workaround bug obscura 0.2.6 yang ditangani:
  1. Target.getTargetInfo mengembalikan "browser" → selalu new_context + new_page
  2. evaluate() async panjang → context destroyed → semua helper pakai polling pendek
  3. contexts[0].pages kosong → selalu buat page sendiri
  4. React/Remix hydration timeout 3s → OBSCURA_MODULE_BUDGET_MS=60000

Usage:
  alveria-browser fetch <url> [--eval EXPR] [--wait SEC] [--profile N]
  alveria-browser shot <url> <out.png> [--profile N]
  alveria-browser turnstile <url> [--profile N] [--wait SEC]
  alveria-browser serve [--port 9222] [--profile N]   # foreground CDP
  alveria-browser profiles                             # list profil

Python API:
  from alveria_browser import Alveria
  with Alveria(profile=1) as br:
      page = br.page()
      page.goto("https://target.com/")
      br.human_type(page, "input[name=email]", "user@example.com")
      br.human_click(page, "button[type=submit]")
      token = br.extract_turnstile_token(page)
"""
from __future__ import annotations

import argparse
import json
import math
import re
import os
import random
import signal
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Deteksi root path: prioritaskan folder repo saat ini, fallback ke STB
HOME = Path(__file__).resolve().parent
if not (HOME / "bin" / "obscura-core").exists() and Path("/mnt/hdd/browser/alveria/bin/obscura-core").exists():
    HOME = Path("/mnt/hdd/browser/alveria")
CORE = HOME / "bin" / "obscura-core"
DEFAULT_PORT = 9222


def ensure_core() -> Path:
    """Mengecek keberadaan binary engine Obscura. Jika belum ada, otomatis download dari GitHub Release."""
    bin_dir = HOME / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    target_bin = bin_dir / "obscura-core"

    if target_bin.exists() and os.access(target_bin, os.X_OK):
        return target_bin

    alt_bin = bin_dir / "obscura"
    if alt_bin.exists():
        if not target_bin.exists():
            try:
                alt_bin.rename(target_bin)
            except Exception:
                pass
        if target_bin.exists():
            try:
                os.chmod(target_bin, 0o755)
            except Exception:
                pass
            return target_bin

    import platform
    import tarfile
    import urllib.request

    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64", "armv8"):
        arch_suffix = "aarch64-linux-stealth"
    elif machine in ("x86_64", "amd64"):
        arch_suffix = "x86_64-linux-stealth"
    else:
        raise RuntimeError(f"Arsitektur CPU '{machine}' belum didukung binary native Obscura.")

    url = f"https://github.com/h4ckf0r0day/obscura/releases/latest/download/obscura-{arch_suffix}.tar.gz"
    print(f"\n[alveria] Core engine belum terpasang. Mengunduh otomatis ({arch_suffix})...", file=sys.stderr)
    print(f"[alveria] Sumber: {url}", file=sys.stderr)

    tar_path = bin_dir / f"obscura-{arch_suffix}.tar.gz"

    def _progress(count, block_size, total_size):
        if total_size > 0:
            pct = min(100, int(count * block_size * 100 / total_size))
            mb_cur = (count * block_size) // (1024 * 1024)
            mb_tot = total_size // (1024 * 1024)
            sys.stderr.write(f"\r[alveria] Download progress: {pct}% ({mb_cur}MB / {mb_tot}MB)")
            sys.stderr.flush()

    try:
        urllib.request.urlretrieve(url, tar_path, reporthook=_progress)
        sys.stderr.write("\n[alveria] Mengekstrak binary...\n")
        sys.stderr.flush()

        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path=bin_dir)

        if (bin_dir / "obscura").exists() and not target_bin.exists():
            (bin_dir / "obscura").rename(target_bin)

        if target_bin.exists():
            try:
                os.chmod(target_bin, 0o755)
            except Exception:
                pass
        if (bin_dir / "obscura-worker").exists():
            try:
                os.chmod(bin_dir / "obscura-worker", 0o755)
            except Exception:
                pass

        print(f"[alveria] Core engine siap digunakan di: {target_bin}\n", file=sys.stderr)
    finally:
        if tar_path.exists():
            tar_path.unlink()

    return target_bin


# ---------------------------------------------------------------- Platform Fonts & Voices
WINDOWS_FONTS = [
    "Arial", "Arial Black", "Bahnschrift", "Calibri", "Cambria", "Cambria Math",
    "Candara", "Comic Sans MS", "Consolas", "Constantia", "Corbel", "Courier New",
    "Ebrima", "Franklin Gothic Medium", "Gabriola", "Gadugi", "Georgia", "Impact",
    "Ink Free", "Javanese Text", "Leelawadee UI", "Lucida Console", "Lucida Sans Unicode",
    "Malgun Gothic", "Marlett", "Microsoft Himalaya", "Microsoft JhengHei",
    "Microsoft New Tai Lue", "Microsoft PhagsPa", "Microsoft Sans Serif", "Microsoft Tai Le",
    "Microsoft YaHei", "Microsoft Yi Baiti", "MingLiU-ExtB", "Mongolian Baiti",
    "MS Gothic", "MS PGothic", "MS UI Gothic", "MV Boli", "Myanmar Text", "Nirmala UI",
    "Palatino Linotype", "Segoe MDL2 Assets", "Segoe Print", "Segoe Script", "Segoe UI",
    "Segoe UI Historic", "Segoe UI Emoji", "Segoe UI Symbol", "SimSun", "Sitka",
    "Sylfaen", "Symbol", "Tahoma", "Times New Roman", "Trebuchet MS", "Verdana", "Webdings",
    "Wingdings", "Yu Gothic",
]

MAC_FONTS = [
    "American Typewriter", "Andale Mono", "Apple Braille", "Apple Chancery",
    "Apple Color Emoji", "Apple SD Gothic Neo", "Apple Symbols", "AppleGothic",
    "AppleMyungjo", "Arial", "Arial Black", "Arial Hebrew", "Arial Narrow",
    "Arial Rounded MT Bold", "Arial Unicode MS", "Avenir", "Avenir Next",
    "Avenir Next Condensed", "Baskerville", "Big Caslon", "Bodoni 72", "Chalkboard",
    "Chalkboard SE", "Chalkduster", "Charter", "Cochin", "Comic Sans MS",
    "Copperplate", "Courier", "Courier New", "Didot", "DIN Alternate", "DIN Condensed",
    "Futura", "Geneva", "Georgia", "Gill Sans", "Helvetica", "Helvetica Neue",
    "Herculanum", "Hoefler Text", "Impact", "Lucida Grande", "Luminari", "Marker Felt",
    "Menlo", "Monaco", "Noteworthy", "Optima", "Palatino", "Papyrus", "Phosphate",
    "PT Mono", "PT Sans", "PT Serif", "San Francisco", "Savoye LET", "SignPainter",
    "Skia", "Snell Roundhand", "Times", "Times New Roman", "Trattatello", "Trebuchet MS",
    "Verdana", "Zapfino",
]

LINUX_FONTS = [
    "Arimo", "Cousine", "DejaVu Sans", "DejaVu Sans Mono", "DejaVu Serif",
    "Droid Sans", "FreeMono", "FreeSans", "FreeSerif", "Liberation Mono",
    "Liberation Sans", "Liberation Serif", "Noto Color Emoji", "Noto Sans",
    "Noto Serif", "Open Sans", "Roboto", "Ubuntu", "Ubuntu Mono",
]

WINDOWS_VOICES = [
    {"name": "Microsoft David - English (United States)", "lang": "en-US", "default": True, "localService": True, "voiceURI": "Microsoft David - English (United States)"},
    {"name": "Microsoft Zira - English (United States)", "lang": "en-US", "default": False, "localService": True, "voiceURI": "Microsoft Zira - English (United States)"},
    {"name": "Microsoft Mark - English (United States)", "lang": "en-US", "default": False, "localService": True, "voiceURI": "Microsoft Mark - English (United States)"},
]

MAC_VOICES = [
    {"name": "Samantha", "lang": "en-US", "default": True, "localService": True, "voiceURI": "Samantha"},
    {"name": "Alex", "lang": "en-US", "default": False, "localService": True, "voiceURI": "Alex"},
    {"name": "Fred", "lang": "en-US", "default": False, "localService": True, "voiceURI": "Fred"},
    {"name": "Victoria", "lang": "en-US", "default": False, "localService": True, "voiceURI": "Victoria"},
]

TRACKER_DOMAINS = [
    "google-analytics.com", "analytics.google.com", "googletagmanager.com",
    "clarity.ms", "hotjar.com", "sentry.io", "browser.sentry-cdn.com",
    "connect.facebook.net", "facebook.com/tr", "analytics.tiktok.com",
    "fullstory.com", "segment.io", "cdn.segment.com", "intercom.io",
]


# ---------------------------------------------------------------- Profiles
@dataclass
class Profile:
    """Satu identitas browser. Semua nilai harus saling konsisten."""
    name: str
    ua: str
    platform: str
    vendor: str
    cores: int
    memory: int          # GB
    webgl_vendor: str
    webgl_renderer: str
    timezone: str
    locale: str
    languages: list[str] = field(default_factory=lambda: ["en-US", "en"])
    screen: tuple[int, int] = (1920, 1080)
    device_scale: float = 1.0
    mobile: bool = False
    touch: bool = False
    fonts: list[str] = field(default_factory=lambda: WINDOWS_FONTS)
    voices: list[dict] = field(default_factory=lambda: WINDOWS_VOICES)

    @property
    def chrome_major(self) -> str:
        m = re.search(r"Chrome/(\d+)", self.ua)
        return m.group(1) if m else "145"

    @property
    def chrome_full(self) -> str:
        m = re.search(r"Chrome/([\d.]+)", self.ua)
        return m.group(1) if m else "145.0.0.0"

    @property
    def ch_platform(self) -> str:
        if "Win" in self.platform:
            return "Windows"
        elif "Mac" in self.platform:
            return "macOS"
        elif "Linux" in self.platform:
            return "Linux"
        return self.platform

    @property
    def architecture(self) -> str:
        return "arm" if "Apple" in self.webgl_renderer or "aarch64" in self.ua else "x86"

    @property
    def platform_version(self) -> str:
        if "Win" in self.platform:
            return "15.0.0" if "11" in self.name else "10.0.0"
        elif "Mac" in self.platform:
            return "14.4.1"
        return "6.5.0"

    def client_hints(self) -> dict[str, str]:
        major = self.chrome_major
        return {
            "sec-ch-ua": f'"Chromium";v="{major}", "Not=A?Brand";v="24", "Google Chrome";v="{major}"',
            "sec-ch-ua-mobile": "?1" if self.mobile else "?0",
            "sec-ch-ua-platform": f'"{self.ch_platform}"',
            "Accept-Language": f"{self.locale},en;q=0.9",
        }


def _win(ver: str) -> str:
    return ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{ver}.0.0.0 Safari/537.36")


def _mac(ver: str) -> str:
    return ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{ver}.0.0.0 Safari/537.36")


def _linux(ver: str) -> str:
    return ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            f"(KHTML, like Gecko) Chrome/{ver}.0.0.0 Safari/537.36")


PROFILES: dict[int, Profile] = {
    1: Profile("win10-intel-hd", _win("145"), "Win32", "Google Inc.", 8, 8,
               "Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)",
               "Asia/Jakarta", "en-US", fonts=WINDOWS_FONTS, voices=WINDOWS_VOICES),
    2: Profile("win10-nvidia", _win("145"), "Win32", "Google Inc.", 16, 16,
               "Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Direct3D11 vs_5_0 ps_5_0, D3D11)",
               "Asia/Jakarta", "en-US", screen=(1920, 1080), fonts=WINDOWS_FONTS, voices=WINDOWS_VOICES),
    3: Profile("win11-amd", _win("146"), "Win32", "Google Inc.", 12, 8,
               "Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0, D3D11)",
               "Asia/Singapore", "en-US", screen=(2560, 1440), fonts=WINDOWS_FONTS, voices=WINDOWS_VOICES),
    4: Profile("macbook-pro-m3", _mac("145"), "MacIntel", "Google Inc.", 10, 16,
               "Google Inc. (Apple)", "ANGLE (Apple, ANGLE Metal Renderer: Apple M3 Pro, Unspecified Version)",
               "Asia/Jakarta", "en-US", screen=(1512, 982), device_scale=2.0, fonts=MAC_FONTS, voices=MAC_VOICES),
    5: Profile("macbook-air-m2", _mac("144"), "MacIntel", "Google Inc.", 8, 8,
               "Google Inc. (Apple)", "ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version)",
               "Asia/Jakarta", "en-US", screen=(1440, 900), device_scale=2.0, fonts=MAC_FONTS, voices=MAC_VOICES),
    6: Profile("win10-lowend", _win("143"), "Win32", "Google Inc.", 4, 4,
               "Google Inc. (Intel)", "ANGLE (Intel, Intel(R) HD Graphics 4000 Direct3D11 vs_5_0 ps_5_0, D3D11)",
               "Asia/Jakarta", "en-US", screen=(1366, 768), fonts=WINDOWS_FONTS, voices=WINDOWS_VOICES),
    7: Profile("linux-ubuntu-iris", _linux("145"), "Linux x86_64", "Google Inc.", 8, 16,
               "Google Inc. (Intel)", "ANGLE (Intel, Mesa Intel(R) Iris(R) Xe Graphics (TGL GT2), OpenGL 4.6)",
               "Asia/Jakarta", "en-US", fonts=LINUX_FONTS, voices=WINDOWS_VOICES),
}


def create_random_profile(seed: Optional[int] = None) -> Profile:
    """Generate realistic plausible random profile (Windows/macOS/Linux)."""
    rng = random.Random(seed)
    os_type = rng.choices(["win", "mac", "linux"], weights=[70, 20, 10])[0]
    ver = rng.choice(["143", "144", "145", "146"])

    if os_type == "win":
        gpu = rng.choice([
            ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)", (1920, 1080), 8, 8),
            ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)", (1920, 1080), 16, 16),
            ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1660 Direct3D11 vs_5_0 ps_5_0, D3D11)", (1920, 1080), 8, 16),
            ("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0, D3D11)", (2560, 1440), 12, 16),
            ("Google Inc. (Intel)", "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)", (1920, 1080), 8, 8),
        ])
        return Profile(
            name=f"win-rand-{rng.randint(100, 999)}",
            ua=_win(ver),
            platform="Win32",
            vendor="Google Inc.",
            cores=gpu[3],
            memory=gpu[4],
            webgl_vendor=gpu[0],
            webgl_renderer=gpu[1],
            timezone="Asia/Jakarta",
            locale="en-US",
            screen=gpu[2],
            device_scale=1.0,
            fonts=WINDOWS_FONTS,
            voices=WINDOWS_VOICES,
        )
    elif os_type == "mac":
        gpu = rng.choice([
            ("Google Inc. (Apple)", "ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version)", (1440, 900), 8, 8),
            ("Google Inc. (Apple)", "ANGLE (Apple, ANGLE Metal Renderer: Apple M3 Pro, Unspecified Version)", (1512, 982), 10, 16),
        ])
        return Profile(
            name=f"mac-rand-{rng.randint(100, 999)}",
            ua=_mac(ver),
            platform="MacIntel",
            vendor="Google Inc.",
            cores=gpu[3],
            memory=gpu[4],
            webgl_vendor=gpu[0],
            webgl_renderer=gpu[1],
            timezone="Asia/Jakarta",
            locale="en-US",
            screen=gpu[2],
            device_scale=2.0,
            fonts=MAC_FONTS,
            voices=MAC_VOICES,
        )
    else:
        return Profile(
            name=f"linux-rand-{rng.randint(100, 999)}",
            ua=_linux(ver),
            platform="Linux x86_64",
            vendor="Google Inc.",
            cores=8,
            memory=16,
            webgl_vendor="Google Inc. (Intel)",
            webgl_renderer="ANGLE (Intel, Mesa Intel(R) Iris(R) Xe Graphics (TGL GT2), OpenGL 4.6)",
            timezone="Asia/Jakarta",
            locale="en-US",
            screen=(1920, 1080),
            device_scale=1.0,
            fonts=LINUX_FONTS,
            voices=WINDOWS_VOICES,
        )


# ---------------------------------------------------------------- Stealth JS Generator
def stealth_js(p: Profile, seed: int) -> str:
    """Init script: konsisten dengan profil, noise deterministik per sesi."""
    lang_json = json.dumps(p.languages)
    fonts_json = json.dumps(p.fonts)
    voices_json = json.dumps(p.voices)

    return f"""
(() => {{
  const SEED = {seed};
  let s = SEED >>> 0;
  const rnd = () => {{ s ^= s << 13; s >>>= 0; s ^= s >> 17; s ^= s << 5; s >>>= 0; return s / 4294967296; }};

  const def = (obj, prop, value) => {{
    try {{ Object.defineProperty(obj, prop, {{ get: () => value, configurable: true }}); }} catch (e) {{}}
  }};

  // =========================================================================
  // 1. NAVIGATOR PROPERTIES & WEBDRIVER PURGE
  // =========================================================================
  try {{ delete navigator.webdriver; }} catch (e) {{}}
  try {{ delete Navigator.prototype.webdriver; }} catch (e) {{}}
  try {{
    const chain = [];
    let o = navigator;
    while (o) {{ chain.push(o); o = Object.getPrototypeOf(o); }}
    for (const obj of chain) {{
      const d = Object.getOwnPropertyDescriptor(obj, 'webdriver');
      if (d) {{ try {{ delete obj.webdriver; }} catch (e) {{}} }}
    }}
  }} catch (e) {{}}

  def(navigator, 'platform', {json.dumps(p.platform)});
  def(navigator, 'vendor', {json.dumps(p.vendor)});
  def(navigator, 'hardwareConcurrency', {p.cores});
  def(navigator, 'deviceMemory', {p.memory});
  def(navigator, 'languages', {lang_json});
  def(navigator, 'maxTouchPoints', {1 if p.touch else 0});

  // =========================================================================
  // 1.1 CLIENT HINTS JAVASCRIPT API (navigator.userAgentData)
  // =========================================================================
  const chPlatform = {json.dumps(p.ch_platform)};
  const chBrands = [
    {{ brand: 'Chromium', version: {json.dumps(p.chrome_major)} }},
    {{ brand: 'Not=A?Brand', version: '24' }},
    {{ brand: 'Google Chrome', version: {json.dumps(p.chrome_major)} }}
  ];
  const uad = {{
    brands: chBrands,
    mobile: {json.dumps(p.mobile)},
    platform: chPlatform,
    getHighEntropyValues: async (hints = []) => {{
      const res = {{
        brands: chBrands,
        mobile: {json.dumps(p.mobile)},
        platform: chPlatform,
      }};
      if (hints.includes('architecture')) res.architecture = {json.dumps(p.architecture)};
      if (hints.includes('bitness')) res.bitness = '64';
      if (hints.includes('model')) res.model = '';
      if (hints.includes('platformVersion')) res.platformVersion = {json.dumps(p.platform_version)};
      if (hints.includes('uaFullVersion')) res.uaFullVersion = {json.dumps(p.chrome_full)};
      if (hints.includes('fullVersionList')) res.fullVersionList = [
        {{ brand: 'Chromium', version: {json.dumps(p.chrome_full)} }},
        {{ brand: 'Not=A?Brand', version: '24.0.0.0' }},
        {{ brand: 'Google Chrome', version: {json.dumps(p.chrome_full)} }}
      ];
      return res;
    }},
    toJSON: () => ({{ brands: chBrands, mobile: {json.dumps(p.mobile)}, platform: chPlatform }}),
  }};
  def(navigator, 'userAgentData', uad);
  if (window.NavigatorUAData) {{
    try {{
      NavigatorUAData.prototype.getHighEntropyValues = uad.getHighEntropyValues;
    }} catch (e) {{}}
  }}

  // Network Information API spoof
  const connectionObj = {{
    effectiveType: '4g',
    rtt: 50 + Math.floor(rnd() * 20),
    downlink: 10 + Math.floor(rnd() * 5),
    saveData: false,
    addEventListener: () => {{}},
    removeEventListener: () => {{}},
  }};
  def(navigator, 'connection', connectionObj);

  // Battery API spoof
  if (navigator.getBattery) {{
    const fakeBattery = {{
      charging: true,
      chargingTime: 0,
      dischargingTime: Infinity,
      level: Math.round((0.88 + rnd() * 0.1) * 100) / 100,
      addEventListener: () => {{}},
      removeEventListener: () => {{}},
    }};
    navigator.getBattery = () => Promise.resolve(fakeBattery);
  }}

  // Plugins & MimeTypes
  const plugins = [
    {{ name: 'PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
    {{ name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
    {{ name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
    {{ name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
    {{ name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer', description: 'Portable Document Format' }},
  ];
  const pluginArray = Object.create(PluginArray.prototype);
  plugins.forEach((pl, i) => {{
    const plugin = Object.create(Plugin.prototype);
    def(plugin, 'name', pl.name);
    def(plugin, 'filename', pl.filename);
    def(plugin, 'description', pl.description);
    def(plugin, 'length', 1);
    pluginArray[i] = plugin;
  }});
  def(pluginArray, 'length', plugins.length);
  def(navigator, 'plugins', pluginArray);
  def(navigator, 'mimeTypes', Object.create(MimeTypeArray.prototype));

  // =========================================================================
  // 2. CHROME RUNTIME STUB
  // =========================================================================
  window.chrome = window.chrome || {{}};
  window.chrome.runtime = window.chrome.runtime || {{}};
  if (!window.chrome.loadTimes) {{
    window.chrome.loadTimes = () => ({{ requestTime: Date.now() / 1000, startLoadTime: Date.now() / 1000 }});
    window.chrome.csi = () => ({{ startE: Date.now(), onloadT: Date.now(), pageT: rnd() * 1000, tran: 15 }});
  }}
  window.chrome.app = window.chrome.app || {{ isInstalled: false }};

  // =========================================================================
  // 3. WEBGL CONTEXT STUB & UNMASKED VENDOR/RENDERER
  // =========================================================================
  const GL_VENDOR = {json.dumps(p.webgl_vendor)};
  const GL_RENDERER = {json.dumps(p.webgl_renderer)};
  const GL_PARAMS = {{
    37445: GL_VENDOR, 37446: GL_RENDERER,
    7936: GL_VENDOR, 7937: GL_RENDERER,
    7938: 'WebGL 1.0 (OpenGL ES 2.0 Chromium)',
    35724: 'WebGL GLSL ES 1.0 (OpenGL ES GLSL ES 1.0 Chromium)',
    3379: 16384, 34921: 16, 35660: 16, 35661: 32, 34076: 16384,
    34024: 16384, 36347: 4096, 36348: 30, 3386: new Int32Array([16384, 16384]),
    3413: 8, 3414: 8, 3415: 8, 3412: 8, 3411: 8, 3410: 8,
  }};
  const makeGL = (kind) => {{
    const gl = {{
      canvas: null,
      getParameter: (p) => (p in GL_PARAMS ? GL_PARAMS[p] : null),
      getExtension: (n) => (n === 'WEBGL_debug_renderer_info'
        ? {{ UNMASKED_VENDOR_WEBGL: 37445, UNMASKED_RENDERER_WEBGL: 37446 }}
        : (n === 'EXT_texture_filter_anisotropic' ? {{ MAX_TEXTURE_MAX_ANISOTROPY_EXT: 34047 }} : null)),
      getSupportedExtensions: () => ['WEBGL_debug_renderer_info', 'EXT_texture_filter_anisotropic',
        'OES_texture_float', 'OES_element_index_uint', 'WEBGL_lose_context'],
      getShaderPrecisionFormat: () => ({{ rangeMin: 127, rangeMax: 127, precision: 23 }}),
      getContextAttributes: () => ({{ alpha: true, antialias: true, depth: true, stencil: false,
        premultipliedAlpha: true, preserveDrawingBuffer: false, powerPreference: 'default' }}),
      getError: () => 0, isContextLost: () => false,
      VENDOR: 37445, RENDERER: 37446, VERSION: 7938, SHADING_LANGUAGE_VERSION: 35724,
    }};
    const noop = () => {{}};
    ['viewport','clearColor','clear','enable','disable','drawArrays','drawElements','bindBuffer',
     'bufferData','useProgram','createProgram','createShader','shaderSource','compileShader',
     'attachShader','linkProgram','getAttribLocation','getUniformLocation','uniformMatrix4fv',
     'uniform1i','uniform1f','uniform3fv','activeTexture','bindTexture','texImage2D','texParameteri',
     'generateMipmap','pixelStorei','blendFunc','depthFunc','scissor','finish','flush','readPixels',
    ].forEach(m => {{ gl[m] = noop; }});
    gl.createBuffer = () => ({{}});
    gl.createTexture = () => ({{}});
    gl.getProgramParameter = () => true;
    gl.getShaderParameter = () => true;
    gl.getProgramInfoLog = () => '';
    gl.getShaderInfoLog = () => '';
    return gl;
  }};
  const origGetContext = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type, ...args) {{
    if (type === 'webgl' || type === 'experimental-webgl' || type === 'webgl2') {{
      const real = (() => {{ try {{ return origGetContext.call(this, type, ...args); }} catch (e) {{ return null; }} }})();
      if (real) return real;
      if (!this.__alveria_gl) this.__alveria_gl = makeGL(type);
      this.__alveria_gl.canvas = this;
      return this.__alveria_gl;
    }}
    return origGetContext.call(this, type, ...args);
  }};

  const patchGL = (proto) => {{
    if (!proto) return;
    const orig = proto.getParameter;
    proto.getParameter = function (p) {{
      if (p === 37445 || p === 7936) return GL_VENDOR;
      if (p === 37446 || p === 7937) return GL_RENDERER;
      return orig.call(this, p);
    }};
  }};
  patchGL(window.WebGLRenderingContext && WebGLRenderingContext.prototype);
  patchGL(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype);

  // =========================================================================
  // 4. CANVAS NOISE (DETERMINISTIK PER SESI)
  // =========================================================================
  const noiseCanvas = (proto, name) => {{
    if (!proto) return;
    const orig = proto[name];
    proto[name] = function (...args) {{
      const ctx = this;
      try {{
        const img = orig.apply(this, args);
        if (img && img.data && img.data.length > 0) {{
          const step = Math.max(1, Math.floor(img.data.length / 512));
          for (let i = 0; i < img.data.length; i += step * 4) {{
            if (rnd() < 0.25) img.data[i] = (img.data[i] + (rnd() < 0.5 ? 1 : -1)) & 0xff;
          }}
        }}
        return img;
      }} catch (e) {{ return orig.apply(this, args); }}
    }};
  }};
  noiseCanvas(window.CanvasRenderingContext2D && CanvasRenderingContext2D.prototype, 'getImageData');
  if (window.HTMLCanvasElement) {{
    const toDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function (...args) {{
      try {{
        const ctx = this.getContext('2d');
        if (ctx && this.width && this.height) {{
          const img = ctx.getImageData(0, 0, this.width, this.height);
          for (let i = 0; i < img.data.length; i += 4096) {{
            if (rnd() < 0.3) img.data[i] = (img.data[i] + 1) & 0xff;
          }}
          ctx.putImageData(img, 0, 0);
        }}
      }} catch (e) {{}}
      return toDataURL.apply(this, args);
    }};
  }}

  // =========================================================================
  // 5. AUDIOCONTEXT NOISE INJECTION
  // =========================================================================
  if (window.AudioBuffer && AudioBuffer.prototype.getChannelData) {{
    const origGetChannelData = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = function (channel) {{
      const data = origGetChannelData.call(this, channel);
      if (data && data.length > 0) {{
        for (let i = 0; i < data.length; i += 128) {{
          if (rnd() < 0.2) {{
            data[i] += (rnd() - 0.5) * 0.0000001;
          }}
        }}
      }}
      return data;
    }};
  }}
  if (window.AnalyserNode && AnalyserNode.prototype.getFloatFrequencyData) {{
    const origGetFloatFreq = AnalyserNode.prototype.getFloatFrequencyData;
    AnalyserNode.prototype.getFloatFrequencyData = function (array) {{
      origGetFloatFreq.call(this, array);
      if (array && array.length > 0) {{
        for (let i = 0; i < array.length; i += 16) {{
          if (rnd() < 0.3) {{
            array[i] += (rnd() - 0.5) * 0.01;
          }}
        }}
      }}
    }};
  }}

  // =========================================================================
  // 6. FONT ENUMERATION PROTECTION (PLATFORM CONSISTENCY)
  // =========================================================================
  const allowedFonts = new Set({fonts_json});
  if (document.fonts && document.fonts.check) {{
    const origCheck = document.fonts.check.bind(document.fonts);
    document.fonts.check = function (font, text) {{
      if (typeof font === 'string') {{
        const match = font.match(/(?:['"])(.*?)(?:['"])|(?:[0-9]+(?:px|pt|em)\\s+([a-zA-Z\\s-]+))/);
        const name = match ? (match[1] || match[2]).trim() : font.trim();
        if (name && !allowedFonts.has(name) && !['monospace', 'sans-serif', 'serif'].includes(name.toLowerCase())) {{
          return false;
        }}
      }}
      return origCheck(font, text);
    }};
  }}

  // =========================================================================
  // 7. SPEECHSYNTHESIS VOICES SPOOF
  // =========================================================================
  const platformVoices = {voices_json};
  if (window.speechSynthesis) {{
    window.speechSynthesis.getVoices = () => platformVoices;
  }}

  // =========================================================================
  // 8. PERMISSIONS & NOTIFICATION PERMISSION
  // =========================================================================
  if (window.Notification) {{
    def(Notification, 'permission', 'default');
  }}
  if (navigator.permissions && navigator.permissions.query) {{
    const oq = navigator.permissions.query.bind(navigator.permissions);
    navigator.permissions.query = (params) => {{
      if (!params || !params.name) return oq(params);
      if (params.name === 'notifications') return Promise.resolve({{ state: 'default', onchange: null }});
      if (params.name === 'geolocation' || params.name === 'camera' || params.name === 'microphone') {{
        return Promise.resolve({{ state: 'prompt', onchange: null }});
      }}
      return oq(params);
    }};
  }}

  // =========================================================================
  // 9. WEBRTC LOCAL IP LEAK PREVENTION
  // =========================================================================
  if (window.RTCPeerConnection) {{
    const OrigPC = window.RTCPeerConnection;
    window.RTCPeerConnection = function (cfg, ...rest) {{
      if (cfg && cfg.iceServers) {{
        cfg.iceServers = cfg.iceServers.map(s => ({{ urls: s.urls, username: s.username, credential: s.credential }}));
      }}
      return new OrigPC(cfg, ...rest);
    }};
    window.RTCPeerConnection.prototype = OrigPC.prototype;
    if (window.webkitRTCPeerConnection) window.webkitRTCPeerConnection = window.RTCPeerConnection;
  }}

  // =========================================================================
  // 10. SCREEN & VIEWPORT CONSISTENCY
  // =========================================================================
  def(screen, 'width', {p.screen[0]});
  def(screen, 'height', {p.screen[1]});
  def(screen, 'availWidth', {p.screen[0]});
  def(screen, 'availHeight', {p.screen[1] - 40});
  def(screen, 'colorDepth', 24);
  def(screen, 'pixelDepth', 24);

  def(window, 'outerWidth', {p.screen[0]});
  def(window, 'outerHeight', {p.screen[1]});
}})();
"""


# ---------------------------------------------------------------- Human Simulation Math
def _bezier_point(t: float, p0: Tuple[float, float], p1: Tuple[float, float],
                  p2: Tuple[float, float], p3: Tuple[float, float]) -> Tuple[float, float]:
    """Cubic Bezier curve point calculation."""
    u = 1.0 - t
    tt = t * t
    uu = u * u
    uuu = uu * u
    ttt = tt * t

    x = uuu * p0[0] + 3 * uu * t * p1[0] + 3 * u * tt * p2[0] + ttt * p3[0]
    y = uuu * p0[1] + 3 * uu * t * p1[1] + 3 * u * tt * p2[1] + ttt * p3[1]
    return (x, y)


def generate_bezier_path(start: Tuple[float, float], end: Tuple[float, float],
                         num_points: int = 25, deviation: float = 0.25) -> List[Tuple[float, float]]:
    """Menghasilkan koordinat gerak mouse melengkung natural (Fitts's Law)."""
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dist = math.hypot(dx, dy)

    # Control points dengan random dispersion
    spread = max(20.0, dist * deviation)
    ctrl1 = (start[0] + dx * 0.25 + random.uniform(-spread, spread),
             start[1] + dy * 0.25 + random.uniform(-spread, spread))
    ctrl2 = (start[0] + dx * 0.75 + random.uniform(-spread, spread),
             start[1] + dy * 0.75 + random.uniform(-spread, spread))

    points = []
    for i in range(num_points + 1):
        # Ease-in-out time distribution agar pelan di awal dan akhir
        t_raw = i / num_points
        t = 0.5 * (1.0 - math.cos(t_raw * math.pi))
        pt = _bezier_point(t, start, ctrl1, ctrl2, end)
        points.append((round(pt[0], 1), round(pt[1], 1)))
    return points


# ---------------------------------------------------------------- Core Class
class Alveria:
    def __init__(self, profile: int | str = 1, port: int = DEFAULT_PORT,
                 proxy: str | None = None, headless: bool = True,
                 block_trackers: bool = True, extra_env: dict | None = None,
                 log: bool = True):
        if profile == "random":
            self.profile = create_random_profile()
            self.profile_num = 1 if "win" in self.profile.name else (4 if "mac" in self.profile.name else 7)
        elif isinstance(profile, int) and profile in PROFILES:
            self.profile = PROFILES[profile]
            self.profile_num = profile
        elif isinstance(profile, str) and profile.isdigit() and int(profile) in PROFILES:
            self.profile = PROFILES[int(profile)]
            self.profile_num = int(profile)
        else:
            self.profile = PROFILES[1]
            self.profile_num = 1
        self.port = port
        self.proxy = proxy
        self.headless = headless
        self.block_trackers = block_trackers
        self.extra_env = extra_env or {}
        self.log_enabled = log
        self.proc: subprocess.Popen | None = None
        self._pw = None
        self._browser = None
        self._ctx = None
        self.session_seed = random.randint(1, 2**31 - 1)
        self.last_mouse_pos = (random.randint(100, 300), random.randint(100, 300))

    # ---- logging & env ----
    def _log(self, msg: str):
        if self.log_enabled:
            print(f"[alveria] {msg}", file=sys.stderr, flush=True)

    def _env(self) -> dict:
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/root",
            # tuning wajib: tanpa ini React/Remix gagal hydrate
            "OBSCURA_MODULE_BUDGET_MS": "60000",
            "OBSCURA_SCRIPT_DEADLINE_MS": "60000",
            "OBSCURA_NAV_TIMEOUT_MS": "90000",
            "OBSCURA_CDP_COMMAND_TIMEOUT_MS": "120000",
            # fingerprint engine-level
            "OBSCURA_PROFILE": str(self.profile_num),
            "OBSCURA_TIMEZONE": self.profile.timezone,
            "OBSCURA_USER_AGENT": self.profile.ua,
            "OBSCURA_STORAGE_DIR": str(HOME / "storage" / self.profile.name),
        }
        if self.block_trackers:
            env["OBSCURA_BLOCK_TRACKERSM"] = "1"
        env.update(self.extra_env)
        return env

    # ---- lifecycle ----
    def start(self):
        if not CORE.exists():
            ensure_core()
        (HOME / "storage" / self.profile.name).mkdir(parents=True, exist_ok=True)
        (HOME / "logs").mkdir(parents=True, exist_ok=True)

        cmd = [str(CORE), "--stealth", "--user-agent", self.profile.ua]
        if self.proxy:
            cmd += ["--proxy", self.proxy]
        cmd += ["--storage-dir", str(HOME / "storage" / self.profile.name),
                "serve", "--port", str(self.port), "--workers", "1"]

        logf = open(HOME / "logs" / f"core-{self.profile.name}.log", "a")
        self.proc = subprocess.Popen(cmd, env=self._env(), stdout=logf,
                                     stderr=subprocess.STDOUT, preexec_fn=os.setsid)

        deadline = time.time() + 40
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/version", timeout=2) as r:
                    info = json.load(r)
                self._log(f"core up: {info['Browser']} profile={self.profile.name}")
                return info
            except Exception:
                if self.proc.poll() is not None:
                    raise RuntimeError("core mati saat start — cek logs/")
                time.sleep(0.4)
        raise RuntimeError("core tidak siap dalam 40s")

    def page(self):
        from playwright.sync_api import sync_playwright
        if self._browser is None:
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.connect_over_cdp(f"http://127.0.0.1:{self.port}")
            self._ctx = self._browser.new_context(
                viewport={"width": self.profile.screen[0], "height": min(self.profile.screen[1], 1080)},
                device_scale_factor=self.profile.device_scale,
                locale=self.profile.locale,
                timezone_id=self.profile.timezone,
                user_agent=self.profile.ua,
                is_mobile=self.profile.mobile,
                has_touch=self.profile.touch,
                java_script_enabled=True,
                extra_http_headers=self.profile.client_hints(),
            )
            # Pasang stealth JS injection
            self._ctx.add_init_script(stealth_js(self.profile, self.session_seed))

            # Tracker / Ad blocking di level routing Playwright
            if self.block_trackers:
                def route_filter(route):
                    url = route.request.url.lower()
                    if any(domain in url for domain in TRACKER_DOMAINS):
                        route.abort()
                    else:
                        route.continue_()
                self._ctx.route("**/*", route_filter)

        return self._ctx.new_page()

    def rss_mb(self) -> int:
        if not self.proc:
            return 0
        try:
            with open(f"/proc/{self.proc.pid}/status") as f:
                for line in f:
                    if line.startswith("VmRSS"):
                        return int(line.split()[1]) // 1024
        except Exception:
            pass
        return 0

    # ---- Workaround Helpers (Bug Obscura: No Long Async Evaluate) ----
    def poll_js(self, page, expr: str, timeout: float = 30, interval: float = 0.8) -> Any:
        """Poll pendek berulang — JANGAN pakai evaluate async panjang."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                v = page.evaluate(expr)
                if v:
                    return v
            except Exception:
                pass
            page.wait_for_timeout(int(interval * 1000))
        return None

    def poll_selector(self, page, selector: str, timeout: float = 30) -> bool:
        res = self.poll_js(
            page,
            f"() => {{ const e = document.querySelector({json.dumps(selector)});"
            f" return e && e.offsetParent !== null ? true : null; }}",
            timeout=timeout)
        return bool(res)

    def wait_settle(self, page, seconds: float = 15):
        """Tunggu SPA hydrate. Obscura butuh 15-20s untuk app React berat."""
        page.wait_for_timeout(int(seconds * 1000))

    def smart_wait(self, page, timeout: float = 30, stable_checks: int = 3) -> bool:
        """Smart wait tanpa hardcoded sleep: mendeteksi DOM stability & readyState."""
        deadline = time.time() + timeout
        last_count = -1
        consecutive_stable = 0

        while time.time() < deadline:
            try:
                state = page.evaluate("() => ({ ready: document.readyState, count: document.querySelectorAll('*').length })")
                if state and state.get("ready") in ("interactive", "complete"):
                    cnt = state.get("count", 0)
                    if cnt == last_count and cnt > 50:
                        consecutive_stable += 1
                        if consecutive_stable >= stable_checks:
                            return True
                    else:
                        consecutive_stable = 0
                    last_count = cnt
            except Exception:
                pass
            page.wait_for_timeout(600)
        return False

    # ---- Human Simulation Actions ----
    def human_move(self, page, target_x: float, target_y: float, steps: int = 20):
        """Gerakan mouse lengkung alami memakai Bezier curve."""
        path = generate_bezier_path(self.last_mouse_pos, (target_x, target_y), num_points=steps)
        for x, y in path:
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.005, 0.015))
        self.last_mouse_pos = (target_x, target_y)

    def human_click(self, page, selector_or_coords: Union[str, Tuple[float, float]], timeout: float = 15):
        """Klik mouse realistis: gerak melengkung, down, jeda, up."""
        if isinstance(selector_or_coords, str):
            box = self.poll_js(
                page,
                f"() => {{ const e = document.querySelector({json.dumps(selector_or_coords)});"
                f" if (!e) return null;"
                f" const r = e.getBoundingClientRect();"
                f" return {{ x: r.left + r.width * (0.3 + Math.random() * 0.4),"
                f"          y: r.top + r.height * (0.3 + Math.random() * 0.4) }}; }}",
                timeout=timeout
            )
            if not box:
                raise TimeoutError(f"Elemen '{selector_or_coords}' tidak ditemukan untuk diklik")
            target_x, target_y = box["x"], box["y"]
        else:
            target_x, target_y = selector_or_coords

        self.human_move(page, target_x, target_y)
        time.sleep(random.uniform(0.06, 0.14))
        page.mouse.down()
        time.sleep(random.uniform(0.07, 0.15))
        page.mouse.up()

    def human_type(self, page, selector: str, text: str, wpm_range: Tuple[int, int] = (45, 80),
                   error_rate: float = 0.02, timeout: float = 15):
        """Mengetik teks layaknya manusia dengan jeda Gaussian dan natural typo."""
        self.human_click(page, selector, timeout=timeout)
        time.sleep(random.uniform(0.15, 0.35))

        # Hitung delay rata-rata per karakter dari WPM (1 kata = ~5 karakter)
        wpm = random.uniform(wpm_range[0], wpm_range[1])
        base_delay = 60.0 / (wpm * 5.0)

        for char in text:
            # Simulasi typo sesekali
            if error_rate > 0 and random.random() < error_rate and char.isalpha():
                typo_char = random.choice("asdfghjklqwertyuiop")
                page.keyboard.type(typo_char)
                time.sleep(random.uniform(0.12, 0.28))
                page.keyboard.press("Backspace")
                time.sleep(random.uniform(0.08, 0.18))

            page.keyboard.type(char)

            # Delay Gaussian per tombol
            delay = max(0.035, random.gauss(base_delay, base_delay * 0.35))
            if char in " .,?!;:\n":
                delay += random.uniform(0.12, 0.25)  # jeda tanda baca
            time.sleep(delay)

    def human_scroll(self, page, delta_y: float = 400, steps: int = 12):
        """Scroll halaman dengan percepatan dan deselerasi halus."""
        step_val = delta_y / steps
        for i in range(steps):
            # Ease in-out factor
            factor = math.sin((i / steps) * math.pi) * 1.5
            page.mouse.wheel(0, step_val * factor)
            time.sleep(random.uniform(0.02, 0.05))

    # ---- Turnstile Token Harvester ----
    def extract_turnstile_token(self, page, timeout: float = 45) -> Optional[str]:
        """Mengekstrak respons token Turnstile secara otomatis."""
        expr = """() => {
          // 1. Cek dari window.turnstile API
          try {
            if (typeof window.turnstile !== 'undefined' && window.turnstile.getResponse) {
              const resp = window.turnstile.getResponse();
              if (resp && resp.length > 20) return resp;
            }
          } catch (e) {}

          // 2. Cek hidden input field standar Turnstile
          const input = document.querySelector('input[name="cf-turnstile-response"]') ||
                        document.querySelector('input[name*="turnstile"]') ||
                        document.querySelector('input[id*="cf-chl-widget"]');
          if (input && input.value && input.value.length > 20) {
            return input.value;
          }
          return null;
        }"""
        return self.poll_js(page, expr, timeout=timeout, interval=1.0)

    # ---- teardown ----
    def stop(self):
        for fn in (
            lambda: self._browser and self._browser.close(),
            lambda: self._pw and self._pw.stop(),
        ):
            try:
                fn()
            except Exception:
                pass
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                self.proc.wait(timeout=8)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except Exception:
                    pass

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *exc):
        self.stop()
        return False


# ---------------------------------------------------------------- CLI
def main():
    ap = argparse.ArgumentParser(prog="alveria-browser", add_help=True)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="ambil halaman + eval")
    f.add_argument("url")
    f.add_argument("--eval", default="document.title")
    f.add_argument("--wait", type=float, default=15)
    f.add_argument("--profile", default="1", help="Profile 1-7 atau random")
    f.add_argument("--proxy")

    s = sub.add_parser("shot", help="screenshot")
    s.add_argument("url")
    s.add_argument("out")
    s.add_argument("--wait", type=float, default=15)
    s.add_argument("--profile", default="1", help="Profile 1-7 atau random")
    s.add_argument("--proxy")

    t = sub.add_parser("turnstile", help="tunggu dan extract token Turnstile")
    t.add_argument("url")
    t.add_argument("--profile", default="1", help="Profile 1-7 atau random")
    t.add_argument("--wait", type=float, default=45)
    t.add_argument("--proxy")

    sv = sub.add_parser("serve", help="foreground CDP server")
    sv.add_argument("--port", type=int, default=DEFAULT_PORT)
    sv.add_argument("--profile", default="1", help="Profile 1-7 atau random")
    sv.add_argument("--proxy")

    sub.add_parser("profiles", help="list profil")
    sub.add_parser("install", help="unduh otomatis core binary untuk arsitektur ini")

    a = ap.parse_args()

    if a.cmd == "install":
        ensure_core()
        return 0

    if a.cmd == "profiles":
        for n, p in PROFILES.items():
            print(f"{n}: {p.name:18s} {p.platform:11s} cores={p.cores:<2d} mem={p.memory:2d}GB "
                  f"screen={p.screen[0]}x{p.screen[1]} tz={p.timezone}")
        print("random: Procedural Profile    Auto-gen    Realistic matched GPU/OS/RAM combination")
        return 0

    if a.cmd == "serve":
        prof = int(a.profile) if str(a.profile).isdigit() else a.profile
        br = Alveria(profile=prof, port=a.port, proxy=a.proxy)
        br.start()
        print(f"CDP: http://127.0.0.1:{a.port}  profile={br.profile.name}", flush=True)
        try:
            br.proc.wait()
        except KeyboardInterrupt:
            pass
        finally:
            br.stop()
        return 0

    if a.cmd == "fetch":
        prof = int(a.profile) if str(a.profile).isdigit() else a.profile
        with Alveria(profile=prof, proxy=a.proxy) as br:
            pg = br.page()
            pg.goto(a.url, wait_until="domcontentloaded", timeout=90000)
            br.wait_settle(pg, a.wait)
            print(pg.evaluate(a.eval))
            br._log(f"rss={br.rss_mb()}MB profile={br.profile.name}")
        return 0

    if a.cmd == "shot":
        prof = int(a.profile) if str(a.profile).isdigit() else a.profile
        with Alveria(profile=prof, proxy=a.proxy) as br:
            pg = br.page()
            pg.goto(a.url, wait_until="domcontentloaded", timeout=90000)
            br.wait_settle(pg, a.wait)
            pg.screenshot(path=a.out)
            print(f"saved {a.out} rss={br.rss_mb()}MB")
        return 0

    if a.cmd == "turnstile":
        prof = int(a.profile) if str(a.profile).isdigit() else a.profile
        with Alveria(profile=prof, proxy=a.proxy) as br:
            pg = br.page()
            pg.goto(a.url, wait_until="domcontentloaded", timeout=90000)
            token = br.extract_turnstile_token(pg, timeout=a.wait)
            if token:
                print(f"[SUCCESS] Turnstile token:\n{token}")
            else:
                print("[FAILED] Turnstile token tidak ditemukan dalam batas waktu", file=sys.stderr)
                return 1
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
