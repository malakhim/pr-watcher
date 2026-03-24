"""
Build a self-contained macOS .app with py2app.

Usage (from this directory):
    python setup.py py2app

Dependencies are installed automatically. The finished app lands in
dist/Pr Watcher.app — zip it and share.
"""
import subprocess
import sys

subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

from setuptools import setup

APP = ["pr_watcher.py"]
DATA_FILES = ["icon.png"]
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "AppIcon.icns",
    "plist": {
        "CFBundleName": "Pr Watcher",
        "CFBundleDisplayName": "Pr Watcher",
        "CFBundleIdentifier": "org.bryan.wu.PrWatcher",
        "CFBundleShortVersionString": "1.0",
        "LSMinimumSystemVersion": "11.0",
        # Hide from Dock — menu-bar-only app
        "LSUIElement": True,
        "NSAppTransportSecurity": {"NSAllowsArbitraryLoads": True},
    },
    "packages": [
        "rumps",
        "requests",
        "urllib3",
        "idna",
        "charset_normalizer",
        "chardet",
        "certifi",
    ],
    # PyObjC frameworks are picked up automatically via the packages below;
    # listing them explicitly ensures they're included even without an import
    # at module level.
    "frameworks": [],
    "includes": [
        "objc",
        "Foundation",
        "AppKit",
        "CoreFoundation",
        "PyObjCTools",
    ],
}

setup(
    name="Pr Watcher",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
