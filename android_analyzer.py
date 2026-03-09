"""Analyze an Android app package and generate a manifest-based Markdown report."""

import argparse
import json
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from dependency_bootstrap import DependencyBootstrapError, DependencySpec, ensure_dependencies

try:
    ensure_dependencies(
        [
            DependencySpec("androguard"),
            DependencySpec("lxml"),
        ]
    )
except DependencyBootstrapError as exc:
    print(exc)
    sys.exit(1)

# 抑制 androguard 的 debug/info 日志 (它用 loguru)
try:
    from loguru import logger as _loguru_logger
    _loguru_logger.disable("androguard")
except ImportError:
    pass

from androguard.core.apk import APK
from lxml import etree

# ============================================================
# 配置
# ============================================================

SCRIPT_DIR = Path(__file__).parent.resolve()
DOWNLOADER_PATH = SCRIPT_DIR / "apkcombo_download.py"


# ============================================================
# APK 下载
# ============================================================

def download_apk(package_name, output_dir):
    """调用 apkcombo_download.py 下载 APK/XAPK"""
    if not DOWNLOADER_PATH.exists():
        print(f"错误: 找不到下载脚本 {DOWNLOADER_PATH}")
        return None

    print("=" * 60)
    print(f"阶段 1: 下载 APK")
    print("=" * 60)

    cmd = [
        sys.executable, str(DOWNLOADER_PATH),
        package_name,
        "--output", str(output_dir),
    ]
    result = subprocess.run(cmd, cwd=str(SCRIPT_DIR))

    if result.returncode != 0:
        print("下载失败")
        return None

    # 查找刚下载的文件
    candidates = []
    for f in output_dir.iterdir():
        if f.suffix in (".apk", ".xapk"):
            candidates.append(f)

    if not candidates:
        print("错误: 未找到下载的文件")
        return None

    # 按修改时间取最新的
    candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    downloaded = candidates[0]
    print(f"\n下载文件: {downloaded.name} ({downloaded.stat().st_size / 1024 / 1024:.1f} MB)")
    return downloaded


# ============================================================
# XAPK 处理
# ============================================================

def extract_apk_from_xapk(xapk_path, output_dir):
    """从 XAPK 文件中提取 base APK"""
    print(f"\n处理 XAPK: {xapk_path.name}")

    if not zipfile.is_zipfile(xapk_path):
        print("错误: XAPK 文件无效 (不是有效的 ZIP)")
        return None

    extract_dir = output_dir / f"{xapk_path.stem}_extracted"
    extract_dir.mkdir(exist_ok=True)

    with zipfile.ZipFile(xapk_path, "r") as zf:
        names = zf.namelist()
        print(f"    XAPK 内容: {len(names)} 个文件")

        # 读取 manifest.json (XAPK 元数据)
        xapk_manifest = None
        if "manifest.json" in names:
            with zf.open("manifest.json") as mf:
                try:
                    xapk_manifest = json.loads(mf.read())
                    pkg = xapk_manifest.get("package_name", "")
                    ver = xapk_manifest.get("version_name", "")
                    print(f"    包名: {pkg}")
                    print(f"    版本: {ver}")
                except json.JSONDecodeError:
                    pass

        # 查找 base APK: 优先 "{package_name}.apk", 然后 "base.apk", 再找任意 .apk
        apk_files = [n for n in names if n.endswith(".apk")]
        print(f"    包含 APK: {apk_files}")

        target_apk = None
        if xapk_manifest:
            pkg_apk = xapk_manifest.get("package_name", "") + ".apk"
            if pkg_apk in apk_files:
                target_apk = pkg_apk
        if not target_apk and "base.apk" in apk_files:
            target_apk = "base.apk"
        if not target_apk:
            # 按大小选最大的 (通常是 base)
            sizes = [(n, zf.getinfo(n).file_size) for n in apk_files]
            sizes.sort(key=lambda x: x[1], reverse=True)
            if sizes:
                target_apk = sizes[0][0]

        if not target_apk:
            print("错误: XAPK 中未找到 APK 文件")
            return None

        print(f"    提取: {target_apk}")
        zf.extract(target_apk, extract_dir)
        extracted_path = extract_dir / target_apk
        print(f"    提取完成: {extracted_path}")
        return extracted_path


# ============================================================
# Manifest 解析 (使用 androguard, 纯 Python, 跨平台)
# ============================================================

def parse_apk(apk_path, output_dir):
    """使用 androguard 解析 APK, 提取 Manifest 信息"""
    try:
        apk = APK(str(apk_path))
    except Exception as e:
        print(f"错误: 无法解析 APK: {e}")
        return None, None

    # 导出 Manifest XML 文本 (供后续文本匹配和存档)
    xml_root = apk.get_android_manifest_xml()
    manifest_xml = etree.tostring(xml_root, pretty_print=True, encoding="unicode")
    manifest_file = output_dir / f"{apk_path.stem}_manifest.xml"
    manifest_file.write_text(manifest_xml, encoding="utf-8")
    print(f"    Manifest 已导出: {manifest_file.name}")

    # 提取结构化信息
    ns = "http://schemas.android.com/apk/res/android"
    info = {
        "package": apk.get_package() or "",
        "version_code": apk.get_androidversion_code() or "",
        "version_name": apk.get_androidversion_name() or "",
        "min_sdk": apk.get_min_sdk_version() or "",
        "target_sdk": apk.get_target_sdk_version() or "",
        "compile_sdk": xml_root.get(f"{{{ns}}}compileSdkVersion",
                                     xml_root.get("compileSdkVersion", "")),
        "application_name": "",
        "permissions": apk.get_permissions() or [],
        "activities": apk.get_activities() or [],
        "services": apk.get_services() or [],
        "receivers": apk.get_receivers() or [],
        "providers": apk.get_providers() or [],
        "meta_data": [],
        "intent_filters": [],
    }

    # Application class name
    app_el = xml_root.find("application")
    if app_el is not None:
        info["application_name"] = app_el.get(f"{{{ns}}}name", "")

    # 提取 meta-data (lxml API)
    for md in xml_root.iter("meta-data"):
        name = md.get(f"{{{ns}}}name", "")
        value = md.get(f"{{{ns}}}value", "") or md.get(f"{{{ns}}}resource", "")
        if name:
            info["meta_data"].append({"name": name, "value": value})

    return info, manifest_xml


# ============================================================
# 策略分析
# ============================================================

def analyze_strategies(manifest_text, info):
    """分析各种保活/推送/权限策略"""
    strategies = {}

    # ----- 1. 账号保活 (SyncAdapter) -----
    has_sync = "android.content.SyncAdapter" in manifest_text
    sync_services = [s for s in info["services"] if "sync" in s.lower()]
    strategies["sync_adapter"] = {
        "name": "账号保活 (SyncAdapter)",
        "detected": has_sync,
        "details": sync_services if has_sync else [],
        "description": "通过 SyncAdapter 注册账号同步服务，利用系统同步机制实现后台保活",
    }

    # ----- 2. 联系人保活 (ContactDirectory) -----
    has_contact = any(
        md["name"] == "android.content.ContactDirectory" for md in info["meta_data"]
    )
    strategies["contact_directory"] = {
        "name": "联系人保活 (ContactDirectory)",
        "detected": has_contact,
        "details": [],
        "description": "通过 ContactDirectory 注册联系人提供者，利用通讯录访问实现后台保活",
    }

    # ----- 3. 开机启动 (BOOT_COMPLETED) -----
    has_boot_perm = "android.permission.RECEIVE_BOOT_COMPLETED" in info["permissions"]
    boot_receivers = []
    # 查找监听 BOOT_COMPLETED 的 receiver
    for m in re.finditer(
        r'E: receiver.*?android:name\([^)]+\)="([^"]+)".*?'
        r'(?=E: receiver|E: service|E: activity|E: provider|\Z)',
        manifest_text, re.DOTALL,
    ):
        block = m.group(0)
        if "BOOT_COMPLETED" in block:
            boot_receivers.append(m.group(1))
    strategies["boot_completed"] = {
        "name": "开机启动 (BOOT_COMPLETED)",
        "detected": has_boot_perm,
        "details": boot_receivers,
        "description": "监听 BOOT_COMPLETED 广播, 设备开机后自动启动",
    }

    # ----- 4. FCM 推送 -----
    has_fcm = any("FirebaseMessaging" in s for s in info["services"])
    has_fcm = has_fcm or any("FirebaseMessagingRegistrar" in md["name"] for md in info["meta_data"])
    has_fcm = has_fcm or "com.google.firebase.messaging" in manifest_text
    fcm_components = [s for s in info["services"] if "firebase" in s.lower() and "messag" in s.lower()]
    # Firebase Analytics 不算 FCM
    has_firebase_analytics = any("firebase" in s.lower() and "analytics" in s.lower() for s in info["services"])
    has_firebase_any = any("firebase" in s.lower() for s in info["services"]) or \
                       any("firebase" in p.lower() for p in info["providers"])
    strategies["fcm"] = {
        "name": "FCM 推送 (Firebase Cloud Messaging)",
        "detected": has_fcm,
        "details": fcm_components,
        "has_firebase_analytics": has_firebase_analytics,
        "has_firebase_any": has_firebase_any,
        "description": "通过 Google FCM 实现服务器主动推送, 是最主流的推送保活方案",
    }

    # ----- 5. Full Screen Intent -----
    has_fsi = "android.permission.USE_FULL_SCREEN_INTENT" in info["permissions"]
    strategies["full_screen_intent"] = {
        "name": "全屏 Intent (USE_FULL_SCREEN_INTENT)",
        "detected": has_fsi,
        "details": [],
        "description": "允许在锁屏上显示全屏通知 (类似闹钟/来电), Android 14+ 需运行时授权",
    }

    # ----- 6. 悬浮窗 (SYSTEM_ALERT_WINDOW) -----
    has_overlay = "android.permission.SYSTEM_ALERT_WINDOW" in info["permissions"]
    strategies["system_alert_window"] = {
        "name": "悬浮窗 (SYSTEM_ALERT_WINDOW)",
        "detected": has_overlay,
        "details": [],
        "description": "允许在其他应用上方绘制悬浮窗口, 可用于悬浮工具/广告展示",
    }

    # ----- 7. 前台服务 -----
    has_fg = "android.permission.FOREGROUND_SERVICE" in info["permissions"]
    fg_types = [p for p in info["permissions"] if p.startswith("android.permission.FOREGROUND_SERVICE_")]
    strategies["foreground_service"] = {
        "name": "前台服务 (FOREGROUND_SERVICE)",
        "detected": has_fg,
        "details": fg_types,
        "description": "通过前台服务保持进程存活, 需在通知栏显示持续通知",
    }

    # ----- 8. 精确闹钟 -----
    has_exact = "android.permission.SCHEDULE_EXACT_ALARM" in info["permissions"] or \
                "android.permission.USE_EXACT_ALARM" in info["permissions"]
    alarm_perms = [p for p in info["permissions"] if "EXACT_ALARM" in p or "SET_ALARM" in p]
    strategies["exact_alarm"] = {
        "name": "精确闹钟 (EXACT_ALARM)",
        "detected": has_exact,
        "details": alarm_perms,
        "description": "使用精确定时唤醒, 可实现定时任务/提醒, Android 12+ 需授权",
    }

    # ----- 9. WorkManager / JobScheduler -----
    has_workmanager = any("androidx.work" in s for s in info["services"])
    wm_components = [s for s in info["services"] if "androidx.work" in s]
    strategies["workmanager"] = {
        "name": "WorkManager / JobScheduler",
        "detected": has_workmanager,
        "details": wm_components,
        "description": "通过 WorkManager 调度后台任务, 系统级任务管理, 可延迟/重试执行",
    }

    return strategies


def detect_ad_sdks(info, manifest_text):
    """检测集成的广告 SDK"""
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
        for ident in identifiers:
            if ident.lower() in manifest_text.lower() or ident.lower() in all_components.lower():
                # 提取 AdMob App ID
                if sdk_name == "Google AdMob":
                    for md in info["meta_data"]:
                        if md["name"] == "com.google.android.gms.ads.APPLICATION_ID":
                            detected[sdk_name] = md["value"]
                            break
                    else:
                        detected[sdk_name] = ""
                else:
                    detected[sdk_name] = ""
                break

    return detected


def detect_third_party_services(info, manifest_text):
    """检测第三方服务和 SDK"""
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
    for name, identifiers in known_services.items():
        for ident in identifiers:
            if ident.lower() in manifest_text.lower():
                detected.append(name)
                break

    return detected


# ============================================================
# 报告生成
# ============================================================

def generate_report(info, strategies, ad_sdks, third_party, manifest_text, output_path):
    """生成 Markdown 格式分析报告"""

    lines = []
    lines.append(f"# Android APP 分析报告")
    lines.append(f"")
    lines.append(f"**生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # 基本信息
    lines.append(f"## 1. 基本信息")
    lines.append(f"")
    lines.append(f"| 项目 | 值 |")
    lines.append(f"|---|---|")
    lines.append(f"| **包名** | `{info['package']}` |")
    lines.append(f"| **版本号** | {info['version_name']} (versionCode: {info['version_code']}) |")
    lines.append(f"| **compileSdk** | {info['compile_sdk']} |")
    lines.append(f"| **targetSdk** | {info['target_sdk']} |")
    lines.append(f"| **minSdk** | {info['min_sdk']} |")
    lines.append(f"| **Application** | `{info['application_name']}` |")
    lines.append(f"")

    # 策略分析
    lines.append(f"## 2. 保活/推送/权限策略分析")
    lines.append(f"")
    lines.append(f"| 策略 | 状态 | 详情 |")
    lines.append(f"|---|---|---|")

    for key, s in strategies.items():
        status = "**已检测到**" if s["detected"] else "未发现"
        details = ""
        if s["details"]:
            if isinstance(s["details"], list) and len(s["details"]) <= 3:
                details = ", ".join(f"`{d}`" for d in s["details"])
            elif isinstance(s["details"], list):
                details = f"{len(s['details'])} 个组件"
        if key == "fcm" and not s["detected"]:
            if s.get("has_firebase_any"):
                details = "仅 Firebase Analytics, 无 FCM"
        lines.append(f"| {s['name']} | {status} | {details} |")

    lines.append(f"")

    # 策略详细说明
    lines.append(f"### 策略详情")
    lines.append(f"")
    for key, s in strategies.items():
        if s["detected"]:
            lines.append(f"#### {s['name']}")
            lines.append(f"")
            lines.append(f"- **说明:** {s['description']}")
            if s["details"]:
                lines.append(f"- **相关组件:**")
                for d in s["details"]:
                    lines.append(f"  - `{d}`")
            lines.append(f"")

    # 广告 SDK
    lines.append(f"## 3. 广告 SDK")
    lines.append(f"")
    if ad_sdks:
        lines.append(f"共检测到 **{len(ad_sdks)}** 个广告 SDK:")
        lines.append(f"")
        lines.append(f"| SDK | 备注 |")
        lines.append(f"|---|---|")
        for sdk_name, extra in sorted(ad_sdks.items()):
            note = f"App ID: `{extra}`" if extra else ""
            lines.append(f"| {sdk_name} | {note} |")
    else:
        lines.append(f"未检测到广告 SDK。")
    lines.append(f"")

    # 第三方服务
    lines.append(f"## 4. 第三方服务/SDK")
    lines.append(f"")
    if third_party:
        for svc in sorted(third_party):
            lines.append(f"- {svc}")
    else:
        lines.append(f"未检测到常见第三方服务。")
    lines.append(f"")

    # 权限列表
    lines.append(f"## 5. 完整权限列表")
    lines.append(f"")
    lines.append(f"共 **{len(info['permissions'])}** 个权限:")
    lines.append(f"")
    # 分类: 系统权限 vs 自定义权限
    system_perms = [p for p in info["permissions"] if p.startswith("android.permission.")]
    custom_perms = [p for p in info["permissions"] if not p.startswith("android.permission.")]

    if system_perms:
        lines.append(f"### 系统权限 ({len(system_perms)})")
        lines.append(f"")
        for p in sorted(system_perms):
            # 标记敏感权限
            sensitive = ""
            dangerous = [
                "ACCESS_FINE_LOCATION", "ACCESS_COARSE_LOCATION",
                "READ_CONTACTS", "WRITE_CONTACTS",
                "READ_PHONE_STATE", "CALL_PHONE",
                "CAMERA", "RECORD_AUDIO",
                "READ_SMS", "SEND_SMS",
                "READ_EXTERNAL_STORAGE", "WRITE_EXTERNAL_STORAGE",
                "READ_CALENDAR", "WRITE_CALENDAR",
                "BODY_SENSORS",
            ]
            perm_short = p.replace("android.permission.", "")
            if perm_short in dangerous:
                sensitive = " ⚠️ 敏感"
            lines.append(f"- `{p}`{sensitive}")
        lines.append(f"")

    if custom_perms:
        lines.append(f"### 自定义/第三方权限 ({len(custom_perms)})")
        lines.append(f"")
        for p in sorted(custom_perms):
            lines.append(f"- `{p}`")
        lines.append(f"")

    # 组件统计
    lines.append(f"## 6. 组件统计")
    lines.append(f"")
    lines.append(f"| 类型 | 数量 |")
    lines.append(f"|---|---|")
    lines.append(f"| Activity | {len(info['activities'])} |")
    lines.append(f"| Service | {len(info['services'])} |")
    lines.append(f"| Receiver | {len(info['receivers'])} |")
    lines.append(f"| Provider | {len(info['providers'])} |")
    lines.append(f"")

    # 写入文件
    report_content = "\n".join(lines)
    output_path.write_text(report_content, encoding="utf-8")
    return report_content


# ============================================================
# 主流程
# ============================================================

def analyze_apk(apk_path, output_dir):
    """对单个 APK 执行完整分析"""
    print(f"\n{'=' * 60}")
    print(f"阶段 2: 解析 Manifest (androguard)")
    print(f"{'=' * 60}")

    info, manifest_text = parse_apk(apk_path, output_dir)
    if not info:
        return False

    print(f"\n{'=' * 60}")
    print(f"阶段 3: 分析 Manifest")
    print(f"{'=' * 60}")

    print(f"    包名: {info['package']}")
    print(f"    版本: {info['version_name']} ({info['version_code']})")
    print(f"    SDK: min={info['min_sdk']} target={info['target_sdk']} compile={info['compile_sdk']}")
    print(f"    权限: {len(info['permissions'])} 个")
    print(f"    组件: {len(info['activities'])} Activity, {len(info['services'])} Service, "
          f"{len(info['receivers'])} Receiver, {len(info['providers'])} Provider")

    # 策略分析
    strategies = analyze_strategies(manifest_text, info)
    detected_count = sum(1 for s in strategies.values() if s["detected"])
    print(f"\n    检测到的策略: {detected_count}/{len(strategies)}")
    for key, s in strategies.items():
        marker = "[+]" if s["detected"] else "[-]"
        print(f"      {marker} {s['name']}")

    # 广告 SDK
    ad_sdks = detect_ad_sdks(info, manifest_text)
    print(f"\n    广告 SDK: {len(ad_sdks)} 个")
    for sdk in sorted(ad_sdks.keys()):
        print(f"      [AD] {sdk}")

    # 第三方服务
    third_party = detect_third_party_services(info, manifest_text)
    print(f"\n    第三方服务: {len(third_party)} 个")

    # 生成报告
    print(f"\n{'=' * 60}")
    print(f"阶段 4: 生成报告")
    print(f"{'=' * 60}")

    report_name = f"{info['package']}_analysis.md" if info["package"] else "analysis_report.md"
    report_path = output_dir / report_name
    manifest_file = output_dir / f"{apk_path.stem}_manifest.xml"
    report_content = generate_report(info, strategies, ad_sdks, third_party, manifest_text, report_path)
    print(f"    报告已保存: {report_path}")

    # 在终端输出报告摘要
    print(f"\n{'=' * 60}")
    print(f"分析完成")
    print(f"{'=' * 60}")
    print(f"  APK:    {apk_path.name}")
    print(f"  包名:   {info['package']}")
    print(f"  版本:   {info['version_name']}")
    print(f"  报告:   {report_path}")
    print(f"  Manifest: {manifest_file}")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Android APP 分析工具 - 下载、解压、Manifest分析、策略检测",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 android_analyzer.py com.whatsapp                    # 下载并分析
  python3 android_analyzer.py com.example.app --skip-download # 分析当前目录已有 APK
  python3 android_analyzer.py ./myapp.apk                     # 直接分析本地文件
  python3 android_analyzer.py com.example.app -o D:\\reports   # 指定输出目录
        """,
    )
    parser.add_argument("target", help="应用包名 (如 com.whatsapp) 或本地 APK/XAPK 文件路径")
    parser.add_argument("--output", "-o", default=".", help="输出目录 (默认当前目录)")
    parser.add_argument("--skip-download", "-s", action="store_true",
                        help="跳过下载, 直接分析当前目录中已有的 APK")
    args = parser.parse_args()

    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    target = args.target
    apk_path = None

    # 判断输入是文件路径还是包名
    target_path = Path(target)
    # 尝试多个位置查找文件: 原始路径、输出目录、脚本目录
    resolved_path = None
    for candidate in [target_path, output_dir / target, SCRIPT_DIR / target]:
        if candidate.exists() and candidate.suffix in (".apk", ".xapk"):
            resolved_path = candidate.resolve()
            break

    if resolved_path:
        # 直接分析本地文件
        apk_path = resolved_path
        print(f"分析本地文件: {apk_path}")
    elif args.skip_download:
        # 在当前目录查找匹配的 APK/XAPK
        package_name = target
        candidates = list(output_dir.glob(f"*{package_name}*.*pk")) + \
                     list(output_dir.glob(f"*{package_name}*.*apk"))
        if candidates:
            candidates.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            apk_path = candidates[0]
            print(f"找到已有文件: {apk_path.name}")
        else:
            print(f"错误: 未找到包含 '{package_name}' 的 APK/XAPK 文件")
            sys.exit(1)
    else:
        # 下载
        package_name = target
        downloaded = download_apk(package_name, output_dir)
        if not downloaded:
            sys.exit(1)
        apk_path = downloaded

    # 如果是 XAPK, 先提取 base APK
    if apk_path.suffix.lower() == ".xapk":
        extracted = extract_apk_from_xapk(apk_path, output_dir)
        if not extracted:
            print("错误: 无法从 XAPK 中提取 APK")
            sys.exit(1)
        apk_path = extracted

    # 执行分析
    success = analyze_apk(apk_path, output_dir)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
