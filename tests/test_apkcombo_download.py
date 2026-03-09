import unittest

from apkcombo_download import (
    classify_variant_file_type,
    extract_xid_from_html,
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


if __name__ == "__main__":
    unittest.main()
