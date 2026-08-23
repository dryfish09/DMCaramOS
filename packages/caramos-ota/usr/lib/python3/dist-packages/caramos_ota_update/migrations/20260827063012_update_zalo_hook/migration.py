"""Migration 20260827063012: Install Zalo messaging application for Linux."""

from __future__ import annotations

import os
import pwd
import shutil
import stat
import subprocess
from pathlib import Path

from caramos_ota_update.context import MigrationContext

DESCRIPTION = "Install Zalo messaging application for Linux"

# Cấu hình Zalo
ZALO_APP_NAME = "Zalo"
ZALO_VERSION = "26.5.10"
ZALO_APPIMAGE_URL = f"https://github.com/hthienloc/zalo-for-linux/releases/download/{ZALO_VERSION}/Zalo-{ZALO_VERSION}+ZaDark-26.2-5051532.AppImage"

# Đường dẫn cài đặt
INSTALL_DIR = Path("/usr/local/bin")
APPIMAGE_NAME = f"Zalo-{ZALO_VERSION}.AppImage"
APPIMAGE_PATH = INSTALL_DIR / APPIMAGE_NAME
SYMLINK_PATH = INSTALL_DIR / "Zalo.AppImage"  # Symlink cho tương thích ngược

# Desktop và icon
DESKTOP_FILE = Path("/usr/share/applications/zalo.desktop")
ICON_PATH = Path("/usr/share/pixmaps/zalo.png")
ICON_URL = "https://upload.wikimedia.org/wikipedia/commons/9/91/Icon_of_Zalo.svg"

# Dependencies
REQUIRED_COMMANDS = {"wget", "file"}


def _check_dependencies(context: MigrationContext) -> None:
    """Kiểm tra các lệnh cần thiết."""
    missing = []
    for cmd in REQUIRED_COMMANDS:
        if not shutil.which(cmd):
            missing.append(cmd)
    
    if missing:
        raise RuntimeError(
            f"Missing required commands: {', '.join(missing)}. "
            "Please install: apt install wget file (Debian/Ubuntu)"
        )


def _download_file(url: str, destination: Path, context: MigrationContext) -> None:
    """Tải file với kiểm tra lỗi."""
    if context.dry_run:
        context.log(f"[dry-run] would download {url} to {destination}")
        return

    context.log(f"Downloading {url}...")
    result = subprocess.run(
        ["wget", "-q", "--show-progress", "-O", str(destination), url],
        capture_output=True,
        text=True,
        check=False,
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Failed to download {url}: {result.stderr}")
    
    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError(f"Downloaded file is empty or missing: {destination}")


def _validate_appimage(path: Path, context: MigrationContext) -> None:
    """Kiểm tra tính hợp lệ của AppImage."""
    if context.dry_run:
        context.log(f"[dry-run] would validate {path}")
        return

    if not path.exists():
        raise RuntimeError(f"AppImage not found: {path}")
    
    # Kiểm tra file ELF
    result = subprocess.run(
        ["file", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    
    if result.returncode != 0:
        raise RuntimeError(f"Cannot determine file type: {result.stderr}")
    
    if "ELF" not in result.stdout and "executable" not in result.stdout:
        context.log(f"Warning: file may not be a valid executable: {result.stdout.strip()}")
    
    # Kiểm tra kiến trúc
    if "x86-64" not in result.stdout and "64-bit" not in result.stdout:
        arch = subprocess.check_output(["uname", "-m"], text=True).strip()
        if arch != "x86_64":
            raise RuntimeError(
                f"Zalo only supports x86_64 architecture. Your system: {arch}"
            )


def _install_appimage(context: MigrationContext) -> None:
    """Cài đặt AppImage vào hệ thống."""
    if context.dry_run:
        context.log(f"[dry-run] would install Zalo to {APPIMAGE_PATH}")
        return

    # Tạo thư mục
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    
    # Kiểm tra file cũ
    if APPIMAGE_PATH.exists():
        context.log(f"Existing AppImage found at {APPIMAGE_PATH}, overwriting...")
        APPIMAGE_PATH.unlink()
    
    if SYMLINK_PATH.exists() and SYMLINK_PATH.is_symlink():
        SYMLINK_PATH.unlink()
    
    # Tải và cài đặt
    _download_file(ZALO_APPIMAGE_URL, APPIMAGE_PATH, context)
    APPIMAGE_PATH.chmod(APPIMAGE_PATH.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    
    # Tạo symlink cho tương thích ngược
    SYMLINK_PATH.symlink_to(APPIMAGE_PATH.name)
    
    context.log(f"Installed Zalo AppImage: {APPIMAGE_PATH}")


def _download_icon(context: MigrationContext) -> None:
    """Tải icon Zalo."""
    if context.dry_run:
        context.log(f"[dry-run] would download icon to {ICON_PATH}")
        return

    ICON_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        _download_file(ICON_URL, ICON_PATH, context)
        context.log(f"Downloaded icon: {ICON_PATH}")
    except Exception as e:
        context.log(f"Warning: could not download icon: {e}")
        # Fallback: tạo icon đơn giản nếu có convert
        if shutil.which("convert"):
            try:
                subprocess.run(
                    [
                        "convert", "-size", "128x128",
                        "xc:blue", "-fill", "white",
                        "-draw", "text 20,70 'Z'",
                        str(ICON_PATH)
                    ],
                    check=True,
                    capture_output=True,
                )
                context.log(f"Created fallback icon: {ICON_PATH}")
            except subprocess.CalledProcessError:
                context.log("Warning: could not create fallback icon")


def _create_desktop_file(context: MigrationContext) -> None:
    """Tạo file .desktop cho Zalo."""
    if context.dry_run:
        context.log(f"[dry-run] would create desktop file: {DESKTOP_FILE}")
        return

    # Sử dụng symlink để tương thích ngược
    exec_path = SYMLINK_PATH if SYMLINK_PATH.exists() else APPIMAGE_PATH
    
    desktop_content = f"""[Desktop Entry]
Name=Zalo
Comment=Ứng dụng nhắn tin Zalo cho Linux
Exec={exec_path} --no-sandbox %u
Icon={ICON_PATH}
Terminal=false
Type=Application
Categories=Network;InstantMessaging;
StartupNotify=true
StartupWMClass=Zalo
MimeType=x-scheme-handler/zalo;
"""
    
    DESKTOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    DESKTOP_FILE.write_text(desktop_content, encoding="utf-8")
    DESKTOP_FILE.chmod(0o644)
    
    context.log(f"Created desktop file: {DESKTOP_FILE}")


def _update_desktop_database(context: MigrationContext) -> None:
    """Cập nhật database desktop applications."""
    if context.dry_run:
        context.log("[dry-run] would update desktop database")
        return

    if not shutil.which("update-desktop-database"):
        context.log("Warning: update-desktop-database not found, skipping")
        return
    
    try:
        subprocess.run(
            ["update-desktop-database", "/usr/share/applications"],
            check=False,
            capture_output=True,
        )
        context.log("Updated desktop database")
    except Exception as e:
        context.log(f"Warning: could not update desktop database: {e}")


def _get_desktop_users() -> list[tuple[str, int, Path]]:
    """Lấy danh sách người dùng desktop."""
    users = []
    for user_info in pwd.getpwall():
        if user_info.pw_uid < 1000 or user_info.pw_dir in ("", "/nonexistent"):
            continue
        home = Path(user_info.pw_dir)
        if not home.is_dir():
            continue
        users.append((user_info.pw_name, user_info.pw_uid, home))
    return sorted(users, key=lambda item: item[1])


def _get_user_environment(username: str, uid: int, home: Path) -> dict[str, str]:
    """Tạo environment cho user."""
    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "USER": username,
        "LOGNAME": username,
        "DISPLAY": os.environ.get("DISPLAY", ":0"),
    })
    
    # XDG Runtime
    runtime_dir = Path(f"/run/user/{uid}")
    if runtime_dir.is_dir() and (runtime_dir / "bus").exists():
        env["XDG_RUNTIME_DIR"] = str(runtime_dir)
        env["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime_dir}/bus"
    
    # Xauthority
    xauth_path = home / ".Xauthority"
    if xauth_path.exists():
        env["XAUTHORITY"] = str(xauth_path)
    
    return env


def _run_as_user(username: str, env: dict[str, str], args: list[str]) -> subprocess.CompletedProcess:
    """Chạy lệnh với quyền user."""
    command = ["runuser", "-u", username, "--"]
    
    if "DBUS_SESSION_BUS_ADDRESS" not in env:
        command.extend(["dbus-run-session", "--"])
    
    command.extend(args)
    
    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _create_user_desktop_entry(username: str, uid: int, home: Path, context: MigrationContext) -> None:
    """Tạo desktop entry cho user (nếu chưa có)."""
    if context.dry_run:
        context.log(f"[dry-run] would create desktop entry for user {username}")
        return

    user_desktop_dir = home / ".local/share/applications"
    user_desktop_file = user_desktop_dir / "zalo.desktop"
    
    # Chỉ tạo nếu chưa tồn tại
    if user_desktop_file.exists():
        return
    
    user_desktop_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy từ hệ thống
    if DESKTOP_FILE.exists():
        shutil.copy2(DESKTOP_FILE, user_desktop_file)
        user_desktop_file.chmod(0o644)
        context.log(f"Created desktop entry for user {username}: {user_desktop_file}")
    
    # Update desktop database cho user
    env = _get_user_environment(username, uid, home)
    if shutil.which("update-desktop-database"):
        subprocess.run(
            ["update-desktop-database", str(user_desktop_dir)],
            check=False,
            capture_output=True,
            env=env,
        )


def _register_mime_types(context: MigrationContext) -> None:
    """Đăng ký MIME type cho Zalo."""
    if context.dry_run:
        context.log("[dry-run] would register Zalo MIME types")
        return

    mime_file = Path("/usr/share/mime/packages/zalo.xml")
    mime_content = """<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="x-scheme-handler/zalo">
    <comment>Zalo URL</comment>
  </mime-type>
</mime-info>
"""
    
    mime_file.parent.mkdir(parents=True, exist_ok=True)
    mime_file.write_text(mime_content, encoding="utf-8")
    mime_file.chmod(0o644)
    
    if shutil.which("update-mime-database"):
        subprocess.run(
            ["update-mime-database", "/usr/share/mime"],
            check=False,
            capture_output=True,
        )


def _uninstall_old_version(context: MigrationContext) -> None:
    """Gỡ cài đặt phiên bản cũ nếu có."""
    if context.dry_run:
        context.log("[dry-run] would uninstall old Zalo versions")
        return

    # Xóa các file cũ
    old_files = [
        Path("/usr/local/bin/Zalo.AppImage"),  # File cũ không có version
        Path("/usr/share/applications/zalo.desktop"),
        Path("/usr/share/pixmaps/zalo.png"),
    ]
    
    for old_file in old_files:
        if old_file.exists():
            old_file.unlink()
            context.log(f"Removed old file: {old_file}")


def run(context: MigrationContext) -> None:
    """Install Zalo messaging application."""
    
    # Kiểm tra root
    if os.geteuid() != 0:
        raise RuntimeError("This migration must be run as root")
    
    context.log(f"Starting Zalo installation (version {ZALO_VERSION})")
    
    if context.dry_run:
        context.log("[dry-run] would install Zalo messaging application")
        _check_dependencies(context)
        _uninstall_old_version(context)
        _install_appimage(context)
        _download_icon(context)
        _create_desktop_file(context)
        _register_mime_types(context)
        _update_desktop_database(context)
        context.log("[dry-run] would create desktop entries for all users")
        return
    
    # Kiểm tra dependencies
    _check_dependencies(context)
    
    # Kiểm tra kiến trúc
    arch = subprocess.check_output(["uname", "-m"], text=True).strip()
    if arch != "x86_64":
        context.log(f"Warning: Zalo only supports x86_64, your system: {arch}")
    
    # Gỡ phiên bản cũ
    _uninstall_old_version(context)
    
    # Cài đặt AppImage
    _install_appimage(context)
    
    # Tải icon
    _download_icon(context)
    
    # Tạo desktop file
    _create_desktop_file(context)
    
    # Đăng ký MIME
    _register_mime_types(context)
    
    # Cập nhật database
    _update_desktop_database(context)
    
    # Tạo desktop entry cho từng user
    users = _get_desktop_users()
    if users:
        context.log(f"Creating desktop entries for {len(users)} users...")
        for username, uid, home in users:
            _create_user_desktop_entry(username, uid, home, context)
    else:
        context.log("No desktop users found")
    
    context.log("=" * 60)
    context.log(f"✅ Zalo {ZALO_VERSION} installed successfully!")
    context.log(f"📦 AppImage: {APPIMAGE_PATH}")
    context.log(f"🔗 Symlink: {SYMLINK_PATH}")
    context.log(f"🖼️  Icon: {ICON_PATH}")
    context.log(f"🚀 Desktop file: {DESKTOP_FILE}")
    context.log("=" * 60)
    context.log("You can launch Zalo from the application menu or by running:")
    context.log(f"  {SYMLINK_PATH}")
    context.log("=" * 60)
