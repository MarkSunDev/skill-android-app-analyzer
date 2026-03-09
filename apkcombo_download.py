"""Download the latest APK/XAPK package from apkcombo.com by package name."""

import argparse
import base64
import os
import re
import subprocess
import sys
from urllib.parse import urljoin, urlparse, parse_qs, unquote

from dependency_bootstrap import DependencyBootstrapError, DependencySpec, ensure_dependencies

try:
    ensure_dependencies(
        [
            DependencySpec("requests"),
            DependencySpec("beautifulsoup4", "bs4"),
        ]
    )
    import requests
    from bs4 import BeautifulSoup
except DependencyBootstrapError as exc:
    print(exc)
    sys.exit(1)


BASE_URL = "https://apkcombo.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://apkcombo.com/",
}


def get_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def search_app(session, package_name):
    """通过包名搜索应用，返回应用页面 URL 和应用名称"""
    search_url = f"{BASE_URL}/search/{package_name}"
    print(f"[1/5] 搜索应用: {search_url}")

    resp = session.get(search_url, allow_redirects=True)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    title_el = soup.select_one("h1.app_name")
    app_name = title_el.get_text(strip=True) if title_el else package_name

    app_url = resp.url
    print(f"    应用名称: {app_name}")
    print(f"    应用页面: {app_url}")

    return app_url, app_name, soup


def find_download_variants(session, app_url, soup):
    """从应用页面找到可用的下载类型及其下载页 URL"""
    print(f"[2/5] 查找下载选项...")

    variants = []
    download_links = soup.select("a.download_apk_btn, a[href*='/download/']")
    for link in download_links:
        href = link.get("href", "")
        text = link.get_text(strip=True)
        if "/download/" in href:
            full_url = urljoin(app_url, href)
            file_type = "XAPK" if "xapk" in href.lower() or "xapk" in text.lower() else "APK"
            variants.append({"type": file_type, "url": full_url, "text": text})

    if not variants:
        path = urlparse(app_url).path.rstrip("/")
        apk_download_url = f"{BASE_URL}{path}/download/apk"
        variants.append({"type": "APK", "url": apk_download_url, "text": "Download APK"})

    seen = set()
    unique_variants = []
    for v in variants:
        if v["url"] not in seen:
            seen.add(v["url"])
            unique_variants.append(v)
            print(f"    发现: [{v['type']}] {v['text']}")

    return unique_variants


def checkin(session):
    """调用 /checkin 端点获取 fp 和 ip 参数"""
    print(f"[3/5] 获取下载令牌...")
    resp = session.post(f"{BASE_URL}/checkin", headers={"Referer": BASE_URL})
    token_str = resp.text.strip()
    print(f"    令牌: {token_str}")
    return token_str


def decode_base64_url(combo_url):
    """从 /d?u=<base64> URL 中解码出真实下载地址"""
    parsed = urlparse(combo_url)
    params = parse_qs(parsed.query)
    if "u" not in params:
        return combo_url
    encoded = params["u"][0]
    padding = 4 - len(encoded) % 4
    if padding != 4:
        encoded += "=" * padding
    try:
        return base64.b64decode(encoded).decode("utf-8")
    except Exception:
        return combo_url


def get_download_url(session, download_page_url, package_name, token_str):
    """访问下载页面，提取最终的下载链接。返回 (url, file_type)"""
    print(f"[4/5] 解析下载链接...")

    resp = session.get(download_page_url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # 查找下载链接 (按优先级)
    variant_links = (
        soup.select("a.variant") or
        soup.select("a[href*='/d?']") or
        soup.select("a[href*='pureapk'], a[href*='u=aH']")
    )

    if not variant_links:
        print("    错误: 未找到下载链接")
        return None, "apk"

    for link in variant_links:
        href = link.get("href", "")
        if not href:
            continue

        full_url = urljoin(BASE_URL, href)

        # 附加 checkin 令牌
        sep = "&" if "?" in full_url else "?"
        full_url_with_token = f"{full_url}{sep}{token_str}&package_name={package_name}&lang=en"

        # 解码出 download.pureapk.com 的真实 URL
        if "/d?" in full_url and "u=" in full_url:
            real_url = decode_base64_url(full_url_with_token)
        else:
            real_url = full_url_with_token

        text = link.get_text(strip=True)
        print(f"    下载项: {text[:80] if text else 'APK'}")

        # 从 variant 文本和 URL 路径中检测真实文件格式
        text_upper = text.upper() if text else ""
        url_upper = real_url.upper()
        if "XAPK" in text_upper or "/XAPK/" in url_upper or "/APG/" in url_upper:
            file_type = "xapk"
        else:
            file_type = "apk"

        return real_url, file_type

    return None, "apk"


def download_with_curl(url, output_dir, package_name, file_type="apk"):
    """
    使用 curl 下载文件。
    curl 的 TLS 指纹能通过 pureapk.com/winudf.com 的反爬检测，
    而 Python requests 会被识别并重定向到 403 页面。
    """
    print(f"[5/5] 开始下载 (curl)...")

    # 从 URL 参数中提取文件名
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    filename = None
    if "_fn" in params:
        filename = unquote(base64.b64decode(params["_fn"][0] + "==").decode("utf-8", errors="ignore"))

    # 确保文件后缀与实际格式一致
    ext = f".{file_type}"
    if filename:
        # 替换错误的后缀
        if filename.endswith(".apk") and file_type == "xapk":
            filename = filename[:-4] + ".xapk"
        elif filename.endswith(".xapk") and file_type == "apk":
            filename = filename[:-5] + ".apk"
        elif not (filename.endswith(".apk") or filename.endswith(".xapk")):
            filename += ext
    else:
        filename = f"{package_name}{ext}"

    # 清理文件名中的非法字符
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filepath = os.path.join(output_dir, filename)

    print(f"    文件名: {filename}")
    print(f"    保存到: {filepath}")

    # 使用 curl 下载，带进度条
    download_cmd = [
        "curl", "-L",
        "-o", filepath,
        "--progress-bar",
        "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "-H", "Sec-Fetch-Dest: document",
        "-H", "Sec-Fetch-Mode: navigate",
        "-H", "Sec-Fetch-Site: none",
        "-H", "Sec-Fetch-User: ?1",
        "--max-redirs", "10",
        "--fail",
        url,
    ]

    print(f"    下载中...")
    result = subprocess.run(download_cmd, capture_output=False)

    if result.returncode != 0:
        print(f"    curl 下载失败 (exit code: {result.returncode})")
        return None

    file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
    if file_size < 1024:
        # 文件太小，可能是错误页面
        print(f"    警告: 文件仅 {file_size} 字节，可能不是有效的 APK")
        with open(filepath, "r", errors="ignore") as f:
            content = f.read(500)
        if "<html" in content.lower():
            print(f"    错误: 下载到的是 HTML 页面，非 APK 文件")
            os.remove(filepath)
            return None

    print(f"    下载完成: {filepath} ({file_size / 1024 / 1024:.1f} MB)")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="从 apkcombo.com 下载 APK/XAPK")
    parser.add_argument("package_name", help="应用包名，如 com.whatsapp")
    parser.add_argument("--output", "-o", default=".", help="输出目录 (默认当前目录)")
    parser.add_argument("--type", "-t", choices=["apk", "xapk"],
                        help="指定下载类型: apk 或 xapk (默认自动选择最新版本)")
    args = parser.parse_args()

    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    # 检查 curl
    try:
        subprocess.run(["curl", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("错误: 需要 curl，请先安装 curl")
        sys.exit(1)

    session = get_session()

    try:
        # Step 1: 搜索应用
        app_url, app_name, app_soup = search_app(session, args.package_name)

        # Step 2: 查找下载选项
        variants = find_download_variants(session, app_url, app_soup)
        if not variants:
            print("错误: 未找到任何下载选项")
            sys.exit(1)

        # 选择下载类型: 指定了 --type 就按类型筛选，否则直接取第一个(最新版本)
        if args.type:
            preferred_type = args.type.upper()
            selected = None
            for v in variants:
                if v["type"] == preferred_type:
                    selected = v
                    break
            if not selected:
                selected = variants[0]
                print(f"    未找到 {preferred_type} 类型，使用: {selected['type']}")
        else:
            selected = variants[0]

        # Step 3: 获取 checkin 令牌
        token_str = checkin(session)

        # Step 4: 获取最终下载链接
        download_url, file_type = get_download_url(session, selected["url"], args.package_name, token_str)
        if not download_url:
            print("错误: 无法获取下载链接")
            sys.exit(1)

        print(f"    文件格式: {file_type.upper()}")

        # Step 5: 用 curl 下载文件
        filepath = download_with_curl(download_url, output_dir, args.package_name, file_type)
        if filepath:
            print(f"\n完成! 文件已保存至: {filepath}")
        else:
            print("\n下载失败")
            sys.exit(1)

    except requests.exceptions.HTTPError as e:
        print(f"HTTP 错误: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n用户取消下载")
        sys.exit(1)
    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
