"""Download the latest APK/XAPK package from apkcombo.com by package name."""

from __future__ import annotations

import argparse
import base64
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import parse_qs, unquote, urljoin, urlparse

from dependency_bootstrap import DependencyBootstrapError, DependencySpec, ensure_dependencies
from workspace_manager import (
    WorkspaceLimitError,
    create_package_workspace,
    ensure_workspace_capacity,
    resolve_workspace_root,
)

BASE_URL = "https://apkcombo.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://apkcombo.com/",
}
XID_PATTERN = re.compile(r'var\s+xid\s*=\s*"([^"]+)"')
requests = None
BeautifulSoup = None


def ensure_download_dependencies():
    """Load download dependencies only when they are actually needed."""

    global requests, BeautifulSoup
    if requests is not None and BeautifulSoup is not None:
        return

    ensure_dependencies(
        [
            DependencySpec("requests"),
            DependencySpec("beautifulsoup4", "bs4"),
        ]
    )

    import requests as requests_module
    from bs4 import BeautifulSoup as beautiful_soup_class

    requests = requests_module
    BeautifulSoup = beautiful_soup_class


def get_session():
    ensure_download_dependencies()
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def extract_xid_from_html(html_text):
    """Extract the internal APKCombo xid token from a download page."""

    match = XID_PATTERN.search(html_text)
    if not match:
        return None
    return match.group(1)


def classify_variant_file_type(label, resolved_url):
    """Classify a variant as APK or XAPK from text and URL hints."""

    joined = f"{label or ''} {resolved_url or ''}".upper()
    if "XAPK" in joined or "/XAPK/" in joined or "/APG/" in joined:
        return "xapk"
    return "apk"


def parse_variant_links(html_text):
    """Parse variant entries returned by APKCombo's internal dl endpoint."""

    ensure_download_dependencies()
    soup = BeautifulSoup(html_text, "html.parser")
    variants = []
    for link in soup.select("a.variant"):
        href = link.get("href", "").strip()
        if not href:
            continue
        label = " ".join(link.get_text(" ", strip=True).split())
        full_url = urljoin(BASE_URL, href)
        variants.append(
            {
                "label": label,
                "href": full_url,
                "type": classify_variant_file_type(label, full_url),
            }
        )
    return variants


def select_variant(variants, preferred_type=None):
    """Pick the preferred variant when available, otherwise return the first."""

    if not variants:
        return None
    if preferred_type:
        preferred_type = preferred_type.lower()
        for variant in variants:
            if variant["type"] == preferred_type:
                return variant
    return variants[0]


def search_app(session, package_name):
    """Search apkcombo by package name and return the resolved app page."""

    search_url = f"{BASE_URL}/search/{package_name}"
    print(f"[1/4] Searching app page: {search_url}")

    response = session.get(search_url, allow_redirects=True)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    title_el = soup.select_one("h1.app_name")
    app_name = title_el.get_text(strip=True) if title_el else package_name
    app_url = response.url

    print(f"    App name: {app_name}")
    print(f"    App page: {app_url}")
    return app_url, app_name, soup


def find_download_variants(app_url, soup):
    """Find candidate APK/XAPK download pages from the app page."""

    print("[2/4] Discovering download pages...")
    variants = []
    download_links = soup.select("a.download_apk_btn, a[href*='/download/']")
    for link in download_links:
        href = link.get("href", "")
        text = link.get_text(strip=True)
        if "/download/" not in href:
            continue
        full_url = urljoin(app_url, href)
        file_type = "xapk" if "xapk" in href.lower() or "xapk" in text.lower() else "apk"
        variants.append({"type": file_type, "url": full_url, "text": text})

    if not variants:
        path = urlparse(app_url).path.rstrip("/")
        variants.append(
            {
                "type": "apk",
                "url": f"{BASE_URL}{path}/download/apk",
                "text": "Download APK",
            }
        )

    unique_variants = []
    seen = set()
    for variant in variants:
        if variant["url"] in seen:
            continue
        seen.add(variant["url"])
        unique_variants.append(variant)
        print(f"    Found: [{variant['type'].upper()}] {variant['text']}")

    return unique_variants


def fetch_variant_listing(session, download_page_url, package_name):
    """Resolve APKCombo's internal variant listing HTML for a download page."""

    print("[3/4] Resolving download variants...")
    response = session.get(download_page_url)
    response.raise_for_status()

    xid = extract_xid_from_html(response.text)
    if not xid:
        raise RuntimeError("Could not extract the APKCombo xid token from the download page.")

    variant_url = f"{download_page_url.rstrip('/')}/{xid}/dl"
    variant_response = session.post(
        variant_url,
        data={"package_name": package_name, "version": ""},
        headers={"Referer": download_page_url},
    )
    variant_response.raise_for_status()
    return variant_response.text


def get_download_url(session, download_page_url, package_name, preferred_type=None):
    """Return the selected APK/XAPK download URL and resolved file type."""

    variants_html = fetch_variant_listing(session, download_page_url, package_name)
    variants = parse_variant_links(variants_html)
    if not variants:
        raise RuntimeError("No downloadable APK/XAPK variants were found in the APKCombo response.")

    variant = select_variant(variants, preferred_type=preferred_type)
    if not variant:
        raise RuntimeError("No APK/XAPK variant could be selected.")

    print(f"    Selected variant: {variant['label'] or variant['type'].upper()}")
    return variant["href"], variant["type"]


def build_output_filename(url, package_name, file_type="apk"):
    """Build a best-effort output file name from the variant URL."""

    params = parse_qs(urlparse(url).query)
    filename = None
    if "_fn" in params:
        encoded_name = params["_fn"][0]
        padding = "=" * ((4 - len(encoded_name) % 4) % 4)
        try:
            filename = unquote(
                base64.b64decode(encoded_name + padding).decode("utf-8", errors="ignore")
            )
        except Exception:
            filename = None

    extension = f".{file_type}"
    if filename:
        if filename.endswith(".apk") and file_type == "xapk":
            filename = filename[:-4] + ".xapk"
        elif filename.endswith(".xapk") and file_type == "apk":
            filename = filename[:-5] + ".apk"
        elif not filename.endswith((".apk", ".xapk")):
            filename += extension
    else:
        filename = f"{package_name}{extension}"

    return re.sub(r'[<>:"/\\|?*]', "_", filename)


def download_with_curl(url, output_dir, package_name, file_type="apk"):
    """Download the final artifact with curl for more reliable redirect handling."""

    print("[4/4] Downloading package with curl...")
    filename = build_output_filename(url, package_name, file_type=file_type)
    filepath = os.path.join(output_dir, filename)

    print(f"    File name: {filename}")
    print(f"    Output path: {filepath}")

    command = [
        "curl",
        "-L",
        "-o",
        filepath,
        "--progress-bar",
        "-H",
        f"User-Agent: {HEADERS['User-Agent']}",
        "-H",
        "Sec-Fetch-Dest: document",
        "-H",
        "Sec-Fetch-Mode: navigate",
        "-H",
        "Sec-Fetch-Site: none",
        "-H",
        "Sec-Fetch-User: ?1",
        "--max-redirs",
        "10",
        "--fail",
        url,
    ]

    print("    Downloading...")
    result = subprocess.run(command, capture_output=False)
    if result.returncode != 0:
        print(f"    curl download failed (exit code: {result.returncode})")
        return None

    file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
    if file_size < 1024:
        print(f"    Warning: downloaded file is only {file_size} bytes.")
        with open(filepath, "r", encoding="utf-8", errors="ignore") as file_handle:
            content = file_handle.read(500)
        if "<html" in content.lower():
            print("    Error: received an HTML page instead of an APK/XAPK artifact.")
            os.remove(filepath)
            return None

    print(f"    Download complete: {filepath} ({file_size / 1024 / 1024:.1f} MB)")
    return filepath


def download_package(package_name, output_dir, preferred_type=None):
    """Download a package artifact into the provided directory."""

    session = get_session()
    app_url, _app_name, app_soup = search_app(session, package_name)
    variants = find_download_variants(app_url, app_soup)
    if not variants:
        raise RuntimeError("No APK/XAPK download page was found.")

    download_page = select_variant(variants, preferred_type=preferred_type)
    download_url, file_type = get_download_url(
        session=session,
        download_page_url=download_page["url"],
        package_name=package_name,
        preferred_type=preferred_type,
    )
    print(f"    File type: {file_type.upper()}")

    filepath = download_with_curl(download_url, output_dir, package_name, file_type=file_type)
    if not filepath:
        raise RuntimeError("Download failed.")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Download APK/XAPK packages from apkcombo.com.")
    parser.add_argument("package_name", help="Application package name, for example com.whatsapp")
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Workspace root directory (default: .cache/android-app-analyzer under the repository)",
    )
    parser.add_argument("--type", "-t", choices=["apk", "xapk"], help="Preferred file type: apk or xapk")
    args = parser.parse_args()

    try:
        subprocess.run(["curl", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        print("Error: curl is required but was not found in PATH.")
        sys.exit(1)

    try:
        workspace_root = resolve_workspace_root(
            repo_root=Path(__file__).resolve().parent,
            output_root=Path(args.output) if args.output else None,
        )
        warning = ensure_workspace_capacity(workspace_root)
        if warning:
            print(f"Warning: {warning}")
        workspace = create_package_workspace(workspace_root, args.package_name)

        print(f"Workspace: {workspace.package_dir}")
        filepath = download_package(
            package_name=args.package_name,
            output_dir=str(workspace.downloads_dir),
            preferred_type=args.type,
        )
        print(f"\nDone. File saved to: {filepath}")
    except requests.exceptions.HTTPError as exc:
        print(f"HTTP error: {exc}")
        sys.exit(1)
    except DependencyBootstrapError as exc:
        print(exc)
        sys.exit(1)
    except WorkspaceLimitError as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nDownload cancelled by user.")
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
