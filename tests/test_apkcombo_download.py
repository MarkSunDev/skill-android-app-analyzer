import unittest

from apkcombo_download import (
    classify_variant_file_type,
    extract_xid_from_html,
    get_download_url,
    parse_variant_links,
    select_variant,
)


DOWNLOAD_PAGE_HTML = """
<html>
  <head></head>
  <body>
    <script>
      var xid = "01a1200x20240308";
      fetchData("/example/" + xid + "/dl");
    </script>
  </body>
</html>
"""


VARIANTS_HTML = """
<div id="download-tab">
  <a
    href="https://apkcombo.com/d?u=aHR0cHM6Ly9kb3dubG9hZC5wdXJlYXBrLmNvbS9iL1hBUEsv"
    class="variant"
    rel="nofollow noreferrer"
  >
    Holy Bible 1.24 XAPK
  </a>
  <a
    href="https://apkcombo.com/d?u=aHR0cHM6Ly9kb3dubG9hZC5wdXJlYXBrLmNvbS9iL0FQSy8="
    class="variant"
    rel="nofollow noreferrer"
  >
    Holy Bible 1.24 APK
  </a>
</div>
"""

DIRECT_DOWNLOAD_PAGE_HTML = """
<html>
  <body>
    <div id="download-tab">
      <a
        href="https://apkcombo.com/d?u=aHR0cHM6Ly9kb3dubG9hZC5wdXJlYXBrLmNvbS9iL1hBUEsv"
        class="variant"
        rel="nofollow noreferrer"
      >
        Holy Bible 1.24 XAPK
      </a>
    </div>
    <script>
      function octs() {
        var endpoint = "https://apkcombo.com/checkin";
      }
    </script>
  </body>
</html>
"""


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"bad status: {self.status_code}")


class DirectVariantSession:
    def get(self, _url, allow_redirects=True):
        _ = allow_redirects
        return FakeResponse(DIRECT_DOWNLOAD_PAGE_HTML)

    def post(self, url, data=None, headers=None):
        _ = data
        _ = headers
        if "checkin" in url:
            return FakeResponse("fp=abc123&ip=1.2.3.4")
        raise AssertionError(f"unexpected POST url: {url}")


class ApkComboDownloadTests(unittest.TestCase):
    def test_extract_xid_from_html(self):
        self.assertEqual(extract_xid_from_html(DOWNLOAD_PAGE_HTML), "01a1200x20240308")

    def test_parse_variant_links_returns_structured_variants(self):
        variants = parse_variant_links(VARIANTS_HTML)

        self.assertEqual(len(variants), 2)
        self.assertEqual(variants[0]["type"], "xapk")
        self.assertIn("Holy Bible 1.24 XAPK", variants[0]["label"])

    def test_classify_variant_file_type_prefers_xapk_hints(self):
        self.assertEqual(
            classify_variant_file_type(
                "Holy Bible 1.24 XAPK",
                "https://download.pureapk.com/b/XAPK/app",
            ),
            "xapk",
        )
        self.assertEqual(
            classify_variant_file_type(
                "Holy Bible 1.24 APK",
                "https://download.pureapk.com/b/APK/app",
            ),
            "apk",
        )

    def test_select_variant_prefers_requested_file_type(self):
        variants = parse_variant_links(VARIANTS_HTML)

        selected = select_variant(variants, preferred_type="apk")

        self.assertEqual(selected["type"], "apk")

    def test_get_download_url_supports_download_pages_with_direct_variant_links(self):
        url, file_type = get_download_url(
            session=DirectVariantSession(),
            download_page_url="https://apkcombo.com/example/download/apk",
            package_name="holy.bible.kjv.kingjamesbible.verse.biblia",
        )

        self.assertEqual(file_type, "xapk")
        self.assertIn("fp=abc123&ip=1.2.3.4", url)
        self.assertIn("package_name=holy.bible.kjv.kingjamesbible.verse.biblia", url)
        self.assertIn("lang=en", url)


if __name__ == "__main__":
    unittest.main()
