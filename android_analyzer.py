"""Analyze an Android app package and generate a manifest-based Markdown report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import zipfile
from datetime import datetime

from dependency_bootstrap import DependencyBootstrapError, DependencySpec, ensure_dependencies
from workspace_manager import (
    WorkspaceLimitError,
    create_package_workspace,
    ensure_workspace_capacity,
    resolve_workspace_root,
)

SCRIPT_DIR = Path(__file__).parent.resolve()
APK = None
etree = None


def ensure_analysis_dependencies():
    """Load analysis dependencies only when they are actually needed."""

    global APK, etree
    if APK is not None and etree is not None:
        return

    ensure_dependencies(
        [
            DependencySpec("androguard"),
            DependencySpec("lxml"),
        ]
    )

    try:
        from loguru import logger as _loguru_logger

        _loguru_logger.disable("androguard")
    except ImportError:
        pass

    from androguard.core.apk import APK as apk_class
    from lxml import etree as etree_module

    APK = apk_class
    etree = etree_module


def download_apk(package_name, downloads_dir):
    """Download the latest package artifact into the managed downloads directory."""

    from apkcombo_download import download_package

    print("=" * 60)
    print("Phase 1: Download package")
    print("=" * 60)
    downloaded_path = download_package(package_name=package_name, output_dir=str(downloads_dir))
    return Path(downloaded_path)


def extract_apk_from_xapk(xapk_path, extracted_root):
    """Extract the base APK from an XAPK package."""

    print(f"\nProcessing XAPK: {xapk_path.name}")
    if not zipfile.is_zipfile(xapk_path):
        print("Error: the XAPK file is not a valid ZIP archive.")
        return None

    extract_dir = extracted_root / xapk_path.stem
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(xapk_path, "r") as archive:
        names = archive.namelist()
        print(f"    Archive entries: {len(names)}")

        xapk_manifest = None
        if "manifest.json" in names:
            with archive.open("manifest.json") as manifest_file:
                try:
                    xapk_manifest = json.loads(manifest_file.read())
                    print(f"    Package name: {xapk_manifest.get('package_name', '')}")
                    print(f"    Version: {xapk_manifest.get('version_name', '')}")
                except json.JSONDecodeError:
                    xapk_manifest = None

        apk_files = [name for name in names if name.endswith(".apk")]
        print(f"    APK entries: {apk_files}")

        target_apk = None
        if xapk_manifest:
            package_apk = f"{xapk_manifest.get('package_name', '')}.apk"
            if package_apk in apk_files:
                target_apk = package_apk
        if not target_apk and "base.apk" in apk_files:
            target_apk = "base.apk"
        if not target_apk and apk_files:
            target_apk = max(apk_files, key=lambda item: archive.getinfo(item).file_size)

        if not target_apk:
            print("Error: no APK payload was found in the XAPK package.")
            return None

        print(f"    Extracting: {target_apk}")
        archive.extract(target_apk, extract_dir)
        extracted_path = extract_dir / target_apk
        print(f"    Extracted to: {extracted_path}")
        return extracted_path


def parse_apk(apk_path, reports_dir):
    """Parse the APK manifest and export a copy of the XML."""

    ensure_analysis_dependencies()

    try:
        apk = APK(str(apk_path))
    except Exception as exc:
        print(f"Error: could not parse APK: {exc}")
        return None, None, None

    xml_root = apk.get_android_manifest_xml()
    manifest_xml = etree.tostring(xml_root, pretty_print=True, encoding="unicode")
    manifest_file = reports_dir / f"{apk_path.stem}_manifest.xml"
    manifest_file.write_text(manifest_xml, encoding="utf-8")
    print(f"    Manifest exported: {manifest_file}")

    android_ns = "http://schemas.android.com/apk/res/android"
    info = {
        "package": apk.get_package() or "",
        "version_code": apk.get_androidversion_code() or "",
        "version_name": apk.get_androidversion_name() or "",
        "min_sdk": apk.get_min_sdk_version() or "",
        "target_sdk": apk.get_target_sdk_version() or "",
        "compile_sdk": xml_root.get(
            f"{{{android_ns}}}compileSdkVersion",
            xml_root.get("compileSdkVersion", ""),
        ),
        "application_name": "",
        "permissions": apk.get_permissions() or [],
        "activities": apk.get_activities() or [],
        "services": apk.get_services() or [],
        "receivers": apk.get_receivers() or [],
        "providers": apk.get_providers() or [],
        "meta_data": [],
    }

    app_element = xml_root.find("application")
    if app_element is not None:
        info["application_name"] = app_element.get(f"{{{android_ns}}}name", "")

    for meta_data in xml_root.iter("meta-data"):
        name = meta_data.get(f"{{{android_ns}}}name", "")
        value = meta_data.get(f"{{{android_ns}}}value", "") or meta_data.get(
            f"{{{android_ns}}}resource", ""
        )
        if name:
            info["meta_data"].append({"name": name, "value": value})

    return info, manifest_xml, manifest_file


def analyze_strategies(manifest_text, info):
    """Detect background, messaging, and scheduling strategies."""

    strategies = {}

    has_sync = "android.content.SyncAdapter" in manifest_text
    sync_services = [service for service in info["services"] if "sync" in service.lower()]
    strategies["sync_adapter"] = {
        "name": "Sync adapter",
        "detected": has_sync,
        "details": sync_services if has_sync else [],
        "description": "Uses Android sync adapters to keep background jobs active.",
    }

    has_contact_directory = any(
        meta_data["name"] == "android.content.ContactDirectory" for meta_data in info["meta_data"]
    )
    strategies["contact_directory"] = {
        "name": "Contact directory provider",
        "detected": has_contact_directory,
        "details": [],
        "description": "Registers a contact directory provider that can keep the app visible to system lookups.",
    }

    has_boot_permission = "android.permission.RECEIVE_BOOT_COMPLETED" in info["permissions"]
    boot_receivers = [receiver for receiver in info["receivers"] if "boot" in receiver.lower()]
    strategies["boot_completed"] = {
        "name": "Boot completed receiver",
        "detected": has_boot_permission,
        "details": boot_receivers,
        "description": "Starts work again after device reboot.",
    }

    has_fcm = any("FirebaseMessaging" in service for service in info["services"])
    has_fcm = has_fcm or any(
        "FirebaseMessagingRegistrar" in meta_data["name"] for meta_data in info["meta_data"]
    )
    has_fcm = has_fcm or "com.google.firebase.messaging" in manifest_text
    fcm_components = [
        service for service in info["services"] if "firebase" in service.lower() and "messag" in service.lower()
    ]
    has_firebase_any = any("firebase" in service.lower() for service in info["services"]) or any(
        "firebase" in provider.lower() for provider in info["providers"]
    )
    strategies["fcm"] = {
        "name": "Firebase Cloud Messaging",
        "detected": has_fcm,
        "details": fcm_components,
        "has_firebase_any": has_firebase_any,
        "description": "Uses FCM for server-driven push delivery.",
    }

    has_full_screen_intent = "android.permission.USE_FULL_SCREEN_INTENT" in info["permissions"]
    strategies["full_screen_intent"] = {
        "name": "Full-screen intent",
        "detected": has_full_screen_intent,
        "details": [],
        "description": "Can surface urgent full-screen notifications such as calls or alarms.",
    }

    has_overlay = "android.permission.SYSTEM_ALERT_WINDOW" in info["permissions"]
    strategies["system_alert_window"] = {
        "name": "System alert window",
        "detected": has_overlay,
        "details": [],
        "description": "Can draw on top of other apps with overlay windows.",
    }

    has_foreground_service = "android.permission.FOREGROUND_SERVICE" in info["permissions"]
    foreground_permissions = [
        permission
        for permission in info["permissions"]
        if permission.startswith("android.permission.FOREGROUND_SERVICE_")
    ]
    strategies["foreground_service"] = {
        "name": "Foreground service",
        "detected": has_foreground_service,
        "details": foreground_permissions,
        "description": "Keeps long-running work alive with a visible notification.",
    }

    has_exact_alarm = (
        "android.permission.SCHEDULE_EXACT_ALARM" in info["permissions"]
        or "android.permission.USE_EXACT_ALARM" in info["permissions"]
    )
    exact_alarm_permissions = [
        permission
        for permission in info["permissions"]
        if "EXACT_ALARM" in permission or "SET_ALARM" in permission
    ]
    strategies["exact_alarm"] = {
        "name": "Exact alarm",
        "detected": has_exact_alarm,
        "details": exact_alarm_permissions,
        "description": "Schedules exact wake-ups for reminders or timing-sensitive jobs.",
    }

    has_workmanager = any("androidx.work" in service for service in info["services"])
    workmanager_components = [service for service in info["services"] if "androidx.work" in service]
    strategies["workmanager"] = {
        "name": "WorkManager / JobScheduler",
        "detected": has_workmanager,
        "details": workmanager_components,
        "description": "Uses system-managed background scheduling and retries.",
    }

    return strategies


def detect_ad_sdks(info, manifest_text):
    """Detect common advertising SDKs from manifest signals."""

    known_sdks = {
        "Google AdMob": ["com.google.android.gms.ads"],
        "AppLovin / MAX": ["com.applovin"],
        "IronSource / LevelPlay": ["com.ironsource", "LevelPlay"],
        "Unity Ads": ["com.unity3d.ads", "com.unity3d.services"],
        "Chartboost": ["com.chartboost"],
        "Mintegral (Mbridge)": ["com.mbridge"],
        "ByteDance / Pangle": ["com.bytedance.sdk.openadsdk"],
        "BigoAds": ["sg.bigo.ads"],
        "BidMachine": ["io.bidmachine"],
        "Vungle / Liftoff": ["com.vungle", "vungle"],
        "Meta / Facebook Audience": ["com.facebook.ads"],
        "InMobi": ["com.inmobi"],
        "Mopub": ["com.mopub"],
        "AdColony": ["com.adcolony"],
        "Tapjoy": ["com.tapjoy"],
        "PubMatic": ["com.pubmatic"],
        "Digital Turbine": ["com.digitalturbine"],
        "Yandex Ads": ["com.yandex.mobile.ads"],
        "Amazon Ads": ["com.amazon.device.ads"],
        "Criteo": ["com.criteo"],
        "Smaato": ["com.smaato"],
        "Fyber": ["com.fyber"],
        "Pangle": ["com.pangle"],
    }

    detected = {}
    all_components = " ".join(
        info["activities"] + info["services"] + info["receivers"] + info["providers"]
    )

    for sdk_name, identifiers in known_sdks.items():
        for identifier in identifiers:
            if identifier.lower() not in manifest_text.lower() and identifier.lower() not in all_components.lower():
                continue
            if sdk_name == "Google AdMob":
                app_id = ""
                for meta_data in info["meta_data"]:
                    if meta_data["name"] == "com.google.android.gms.ads.APPLICATION_ID":
                        app_id = meta_data["value"]
                        break
                detected[sdk_name] = app_id
            else:
                detected[sdk_name] = ""
            break

    return detected


def detect_third_party_services(info, manifest_text):
    """Detect common non-advertising third-party services."""

    known_services = {
        "Firebase Analytics": ["com.google.firebase.analytics", "AppMeasurement"],
        "Firebase Installations": ["FirebaseInstallationsRegistrar"],
        "Firebase Crashlytics": ["com.google.firebase.crashlytics"],
        "Firebase Remote Config": ["com.google.firebase.remoteconfig"],
        "Firebase Performance": ["com.google.firebase.perf"],
        "Google Sign-In": ["com.google.android.gms.auth.api.signin"],
        "Google Play Services": ["com.google.android.gms"],
        "Google Cast": ["com.google.android.gms.cast"],
        "Facebook SDK": ["com.facebook"],
        "Adjust SDK": ["com.adjust"],
        "AppsFlyer": ["com.appsflyer"],
        "Branch.io": ["io.branch"],
        "Singular": ["com.singular"],
        "Kochava": ["com.kochava"],
        "Sentry": ["io.sentry"],
        "Bugsnag": ["com.bugsnag"],
        "Picasso": ["com.squareup.picasso"],
        "Glide": ["com.bumptech.glide"],
        "OkHttp": ["com.squareup.okhttp", "okhttp3"],
        "Retrofit": ["retrofit2"],
        "ExoPlayer": ["com.google.android.exoplayer", "androidx.media3"],
        "Room Database": ["androidx.room"],
        "WorkManager": ["androidx.work"],
    }

    detected = []
    lowered_manifest = manifest_text.lower()
    for service_name, identifiers in known_services.items():
        if any(identifier.lower() in lowered_manifest for identifier in identifiers):
            detected.append(service_name)
    return detected


def generate_report(info, strategies, ad_sdks, third_party, output_path):
    """Generate a Markdown report from manifest analysis results."""

    sensitive_permissions = {
        "ACCESS_FINE_LOCATION",
        "ACCESS_COARSE_LOCATION",
        "READ_CONTACTS",
        "WRITE_CONTACTS",
        "READ_PHONE_STATE",
        "CALL_PHONE",
        "CAMERA",
        "RECORD_AUDIO",
        "READ_SMS",
        "SEND_SMS",
        "READ_EXTERNAL_STORAGE",
        "WRITE_EXTERNAL_STORAGE",
        "READ_CALENDAR",
        "WRITE_CALENDAR",
        "BODY_SENSORS",
    }

    lines = [
        "# Android App Analysis Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "---",
        "",
        "## 1. Basic Information",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| **Package** | `{info['package']}` |",
        f"| **Version** | {info['version_name']} (versionCode: {info['version_code']}) |",
        f"| **compileSdk** | {info['compile_sdk']} |",
        f"| **targetSdk** | {info['target_sdk']} |",
        f"| **minSdk** | {info['min_sdk']} |",
        f"| **Application** | `{info['application_name']}` |",
        "",
        "## 2. Background, Messaging, and Scheduling Signals",
        "",
        "| Strategy | Status | Details |",
        "|---|---|---|",
    ]

    for key, strategy in strategies.items():
        status = "**Detected**" if strategy["detected"] else "Not found"
        details = ""
        if strategy["details"]:
            if len(strategy["details"]) <= 3:
                details = ", ".join(f"`{detail}`" for detail in strategy["details"])
            else:
                details = f"{len(strategy['details'])} components"
        if key == "fcm" and not strategy["detected"] and strategy.get("has_firebase_any"):
            details = "Firebase components found, but no FCM signal"
        lines.append(f"| {strategy['name']} | {status} | {details} |")

    lines.extend(["", "### Detected Strategy Details", ""])
    for strategy in strategies.values():
        if not strategy["detected"]:
            continue
        lines.append(f"#### {strategy['name']}")
        lines.append("")
        lines.append(f"- **Description:** {strategy['description']}")
        if strategy["details"]:
            lines.append("- **Related components:**")
            for detail in strategy["details"]:
                lines.append(f"  - `{detail}`")
        lines.append("")

    lines.append("## 3. Advertising SDKs")
    lines.append("")
    if ad_sdks:
        lines.append(f"Detected **{len(ad_sdks)}** advertising SDKs:")
        lines.append("")
        lines.append("| SDK | Notes |")
        lines.append("|---|---|")
        for sdk_name, extra in sorted(ad_sdks.items()):
            note = f"App ID: `{extra}`" if extra else ""
            lines.append(f"| {sdk_name} | {note} |")
    else:
        lines.append("No common advertising SDKs were detected.")
    lines.append("")

    lines.append("## 4. Third-Party Services")
    lines.append("")
    if third_party:
        for service_name in sorted(third_party):
            lines.append(f"- {service_name}")
    else:
        lines.append("No common third-party services were detected.")
    lines.append("")

    lines.append("## 5. Permissions")
    lines.append("")
    lines.append(f"Detected **{len(info['permissions'])}** permissions:")
    lines.append("")

    system_permissions = [permission for permission in info["permissions"] if permission.startswith("android.permission.")]
    custom_permissions = [permission for permission in info["permissions"] if not permission.startswith("android.permission.")]

    if system_permissions:
        lines.append(f"### System Permissions ({len(system_permissions)})")
        lines.append("")
        for permission in sorted(system_permissions):
            short_name = permission.replace("android.permission.", "")
            suffix = " [sensitive]" if short_name in sensitive_permissions else ""
            lines.append(f"- `{permission}`{suffix}")
        lines.append("")

    if custom_permissions:
        lines.append(f"### Custom or Third-Party Permissions ({len(custom_permissions)})")
        lines.append("")
        for permission in sorted(custom_permissions):
            lines.append(f"- `{permission}`")
        lines.append("")

    lines.extend(
        [
            "## 6. Component Counts",
            "",
            "| Component | Count |",
            "|---|---|",
            f"| Activity | {len(info['activities'])} |",
            f"| Service | {len(info['services'])} |",
            f"| Receiver | {len(info['receivers'])} |",
            f"| Provider | {len(info['providers'])} |",
            "",
        ]
    )

    report_content = "\n".join(lines)
    output_path.write_text(report_content, encoding="utf-8")
    return report_content


def write_run_metadata(workspace, source_target, info, apk_path, report_path, manifest_path):
    """Persist a small metadata file for later cleanup or inspection."""

    metadata = {
        "source_target": source_target,
        "workspace": str(workspace.package_dir),
        "package": info.get("package", ""),
        "version_name": info.get("version_name", ""),
        "version_code": info.get("version_code", ""),
        "apk_path": str(apk_path),
        "report_path": str(report_path),
        "manifest_path": str(manifest_path),
        "generated_at": datetime.now().isoformat(),
    }
    metadata_path = workspace.package_dir / "run.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata_path


def analyze_apk(apk_path, workspace, source_target):
    """Run the full manifest analysis workflow for a single APK."""

    print(f"\n{'=' * 60}")
    print("Phase 2: Parse manifest")
    print(f"{'=' * 60}")

    info, manifest_text, manifest_file = parse_apk(apk_path, workspace.reports_dir)
    if not info:
        return False

    print(f"\n{'=' * 60}")
    print("Phase 3: Analyze manifest")
    print(f"{'=' * 60}")
    print(f"    Package: {info['package']}")
    print(f"    Version: {info['version_name']} ({info['version_code']})")
    print(
        f"    SDK: min={info['min_sdk']} target={info['target_sdk']} compile={info['compile_sdk']}"
    )
    print(f"    Permissions: {len(info['permissions'])}")
    print(
        "    Components: "
        f"{len(info['activities'])} Activity, "
        f"{len(info['services'])} Service, "
        f"{len(info['receivers'])} Receiver, "
        f"{len(info['providers'])} Provider"
    )

    strategies = analyze_strategies(manifest_text, info)
    detected_count = sum(1 for strategy in strategies.values() if strategy["detected"])
    print(f"\n    Detected strategies: {detected_count}/{len(strategies)}")
    for strategy in strategies.values():
        marker = "[+]" if strategy["detected"] else "[-]"
        print(f"      {marker} {strategy['name']}")

    ad_sdks = detect_ad_sdks(info, manifest_text)
    print(f"\n    Advertising SDKs: {len(ad_sdks)}")
    for sdk_name in sorted(ad_sdks):
        print(f"      [AD] {sdk_name}")

    third_party = detect_third_party_services(info, manifest_text)
    print(f"\n    Third-party services: {len(third_party)}")

    print(f"\n{'=' * 60}")
    print("Phase 4: Generate report")
    print(f"{'=' * 60}")

    report_name = f"{info['package']}_analysis.md" if info["package"] else "analysis_report.md"
    report_path = workspace.reports_dir / report_name
    generate_report(info, strategies, ad_sdks, third_party, report_path)
    metadata_path = write_run_metadata(
        workspace=workspace,
        source_target=source_target,
        info=info,
        apk_path=apk_path,
        report_path=report_path,
        manifest_path=manifest_file,
    )

    print(f"    Report saved: {report_path}")
    print(f"    Run metadata: {metadata_path}")
    print(f"\n{'=' * 60}")
    print("Analysis complete")
    print(f"{'=' * 60}")
    print(f"  Workspace: {workspace.package_dir}")
    print(f"  APK: {apk_path}")
    print(f"  Report: {report_path}")
    print(f"  Manifest: {manifest_file}")

    return True


def resolve_local_target(target, workspace_root):
    """Resolve a local APK/XAPK target path and pick a workspace name for it."""

    target_path = Path(target)
    for candidate in (target_path, workspace_root / target, SCRIPT_DIR / target):
        if candidate.exists() and candidate.suffix.lower() in (".apk", ".xapk"):
            return candidate.resolve()
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Android APK/XAPK packages with a managed workspace cache.",
    )
    parser.add_argument(
        "target",
        help="Application package name (for example com.whatsapp) or a local APK/XAPK path",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        help="Workspace root directory (default: .cache/android-app-analyzer under the repository)",
    )
    parser.add_argument(
        "--skip-download",
        "-s",
        action="store_true",
        help="Skip network download and reuse an artifact already present in the managed downloads directory",
    )
    args = parser.parse_args()

    try:
        workspace_root = resolve_workspace_root(
            repo_root=SCRIPT_DIR,
            output_root=Path(args.output) if args.output else None,
        )
        warning = ensure_workspace_capacity(workspace_root)
        if warning:
            print(f"Warning: {warning}")

        resolved_local_path = resolve_local_target(args.target, workspace_root)
        workspace_name = resolved_local_path.stem if resolved_local_path else args.target
        workspace = create_package_workspace(workspace_root, workspace_name)
        print(f"Workspace: {workspace.package_dir}")

        if resolved_local_path:
            apk_path = resolved_local_path
            print(f"Analyzing local file: {apk_path}")
        elif args.skip_download:
            candidates = list(workspace.downloads_dir.glob("*.apk")) + list(
                workspace.downloads_dir.glob("*.xapk")
            )
            if not candidates:
                print("Error: no cached APK/XAPK file was found in the managed downloads directory.")
                sys.exit(1)
            candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
            apk_path = candidates[0]
            print(f"Reusing cached artifact: {apk_path}")
        else:
            apk_path = download_apk(args.target, workspace.downloads_dir)

        if apk_path.suffix.lower() == ".xapk":
            extracted = extract_apk_from_xapk(apk_path, workspace.extracted_dir)
            if not extracted:
                print("Error: could not extract a base APK from the XAPK package.")
                sys.exit(1)
            apk_path = extracted

        success = analyze_apk(apk_path, workspace, source_target=args.target)
        if not success:
            sys.exit(1)
    except DependencyBootstrapError as exc:
        print(exc)
        sys.exit(1)
    except WorkspaceLimitError as exc:
        print(f"Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
