# PR Watcher

A macOS menu-bar app that watches a GitHub repository and notifies you when your pull requests change status.

## Features

- Lives in the menu bar — no Dock icon
- Shows all open PRs you authored, are assigned to, or are requested to review
- Colour-coded build status per PR (🟢 passing / 🟡 pending / 🔴 failing)
- Review status per PR (👍 approved / 💬 changes requested / 👀 awaiting review)
- Desktop notifications when a PR passes checks, gets approved, or receives new comments
- Polls every 90 seconds with a manual "Refresh now" option
- Per-user repo configuration — no hardcoded repo name

## Requirements

- macOS 11+
- Python 3.9+
- [`gh` CLI](https://cli.github.com) installed and authenticated (`gh auth login`)

## Building

```bash
python setup.py py2app
```

This installs all dependencies automatically and produces `dist/Pr Watcher.app`.
Zip that file and share it — **teammates don't need to build anything**. No Python installation required on the receiving end; the app is fully self-contained.

> `build/` and `dist/` are generated artifacts and are excluded from version control.

## First launch

On first launch the app will ask you which repo to watch:

```
Enter the GitHub repo to watch (e.g. org/repo):
```

This is saved to `~/Library/Application Support/Pr Watcher/config.json` and can be changed at any time via **Set Repo…** in the menu.

## Development

Run the script directly (no app bundle needed):

```bash
python pr_watcher.py
```

Or build in alias mode, which symlinks your source files so changes take effect on the next app launch without rebuilding:

```bash
python setup.py py2app -A
```

Only do a full rebuild (`rm -rf build dist && python setup.py py2app`) when you're ready to produce a distributable bundle.

## Running at login (background process)

Copy the included LaunchAgent plist to your user LaunchAgents directory and load it:

```bash
cp com.bryan.wu.pr-watcher.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.bryan.wu.pr-watcher.plist
```

The app will now start automatically at login and restart if it ever crashes.

To stop it and remove it from login:

```bash
launchctl unload ~/Library/LaunchAgents/com.bryan.wu.pr-watcher.plist
rm ~/Library/LaunchAgents/com.bryan.wu.pr-watcher.plist
```

> The plist assumes the app is installed at `/Applications/Pr Watcher.app`. Edit the `Program` key if you put it elsewhere.
