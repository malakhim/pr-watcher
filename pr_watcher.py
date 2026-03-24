import os
import sys
import shutil

bundle_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(bundle_dir, "libs"))

import json
import queue
import subprocess
import threading
import rumps
import webbrowser

POLL_INTERVAL = 90

GH = shutil.which("gh") or "/opt/homebrew/bin/gh"

CONFIG_DIR = os.path.expanduser("~/Library/Application Support/Pr Watcher")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")


def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

class PRWatcher(rumps.App):
    def __init__(self):
        icon_path = os.path.join(bundle_dir, "icon.png")
        super(PRWatcher, self).__init__("PRs", icon=icon_path, quit_button="Quit")
        self.prs = []
        self.last_checks = {}
        self.last_reviews = {}
        self.last_comment_counts = {}
        self.gh_user = self.detect_gh_user()
        self._ensure_status_icons()

        cfg = load_config()
        self.repo = cfg.get("repo", "")

        if not os.path.exists(icon_path):
            print("Warning: icon not found at", icon_path)

        if not os.path.exists(GH):
            print("Warning: gh not found at", GH)

        self._result_queue = queue.Queue()

        self.menu.clear()
        self.menu.add(rumps.MenuItem("Refreshing…"))
        self.menu.add(None)
        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

        self.timer = rumps.Timer(self.refresh_prs, POLL_INTERVAL)
        self.timer.start()

        self._apply_timer = rumps.Timer(self._apply_pending, 0.5)
        self._apply_timer.start()

        if not self.repo:
            self._startup = rumps.Timer(lambda _: self.set_repo(None), 1)
            self._startup.start()
        else:
            threading.Thread(target=self._do_refresh, daemon=True).start()

    def _ensure_status_icons(self):
        import struct, zlib

        def make_png(r, g, b):
            size = 16
            def chunk(tag, data):
                crc = zlib.crc32(tag + data) & 0xffffffff
                return struct.pack('>I', len(data)) + tag + data + struct.pack('>I', crc)
            ihdr = struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0)
            row = b'\x00' + bytes([r, g, b] * size)
            idat = zlib.compress(row * size)
            return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')

        icons = {
            "icon_green.png":  (52, 199, 89),
            "icon_yellow.png": (255, 204, 0),
            "icon_red.png":    (255, 59, 48),
        }
        for name, (r, g, b) in icons.items():
            path = os.path.join(bundle_dir, name)
            if not os.path.exists(path):
                with open(path, 'wb') as f:
                    f.write(make_png(r, g, b))

        self.icon_green   = os.path.join(bundle_dir, "icon_green.png")
        self.icon_yellow  = os.path.join(bundle_dir, "icon_yellow.png")
        self.icon_red     = os.path.join(bundle_dir, "icon_red.png")
        self.icon_default = os.path.join(bundle_dir, "icon.png")

    def set_repo(self, _):
        window = rumps.Window(
            message="Enter the GitHub repo to watch (e.g. org/repo):",
            title="Set Repository",
            default_text=self.repo,
            ok="Save",
            cancel="Cancel",
            dimensions=(320, 24),
        )
        response = window.run()
        if response.clicked and response.text.strip():
            self.repo = response.text.strip()
            cfg = load_config()
            cfg["repo"] = self.repo
            save_config(cfg)
            threading.Thread(target=self._do_refresh, daemon=True).start()

    def detect_gh_user(self):
        if not GH or not os.path.exists(GH):
            return None
        try:
            result = subprocess.run([GH, "api", "user"], capture_output=True, text=True, encoding="utf-8", check=True, timeout=15)
            data = json.loads(result.stdout)
            return data.get("login")
        except Exception as e:
            print("Could not detect gh user:", e)
            return None

    def call_github(self, endpoint):
        if not GH or not os.path.exists(GH):
            print("gh binary not found:", GH)
            return None
        if not self.repo:
            return None
        try:
            result = subprocess.run(
                [GH, "api", f"repos/{self.repo}/{endpoint}"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
                timeout=15,
            )
            return json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            print("Error calling gh:", e.stderr.strip())
            return None
        except json.JSONDecodeError as e:
            print("JSON decode error:", e)
            return None

    def refresh_prs(self, _):
        threading.Thread(target=self._do_refresh, daemon=True).start()

    def _do_refresh(self):
        try:
            prs = self.fetch_my_prs()
            self._result_queue.put(('ok', prs or []))
        except Exception as e:
            print("Error in _do_refresh:", e)
            self._result_queue.put(('error', str(e)))

    def _apply_pending(self, _):
        try:
            kind, data = self._result_queue.get_nowait()
        except queue.Empty:
            return
        if kind == 'ok':
            self.prs = data
            self.update_menu(data)
        else:
            self.menu.clear()
            self.menu.add(rumps.MenuItem(f"Error: {data}"))
            self.menu.add(rumps.MenuItem("Refresh now", callback=lambda _: self.refresh_prs(None)))
            self.menu.add(rumps.MenuItem(f"Set Repo… ({self.repo or 'not set'})", callback=self.set_repo))
            self.menu.add(None)
            self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

    def update_menu(self, prs):
        self.menu.clear()
        if not prs:
            self.menu.add(rumps.MenuItem("No open PRs"))
        else:
            for pr in prs:
                label = f"#{pr['number']} {pr['title']}   {pr['check_emoji']} {pr['review_emoji']}"
                item = rumps.MenuItem(label, callback=lambda _, url=pr["url"]: webbrowser.open(url))
                self.menu.add(item)

                num = pr["number"]
                if self.last_checks.get(num) != pr["check_status"]:
                    if pr["check_status"] == "success":
                        rumps.notification(
                            title=f"PR #{num} Passed All Checks",
                            subtitle=pr["title"],
                            message="",
                            sound=True,
                            data={"url": pr["url"]}
                        )
                    elif pr["check_status"] == "failure":
                        rumps.notification(
                            title=f"PR #{num} Checks Failed",
                            subtitle=pr["title"],
                            message="",
                            sound=True,
                            data={"url": pr["url"]}
                        )

                if self.last_reviews.get(num) != pr["review_status"] and pr["review_status"] == "approved":
                    rumps.notification(
                        title=f"PR #{num} Approved",
                        subtitle=pr["title"],
                        message="",
                        sound=True,
                        data={"url": pr["url"]}
                    )

                prev_comments = self.last_comment_counts.get(num)
                new_comments = pr["comment_count"]
                if prev_comments is not None and new_comments > prev_comments:
                    diff = new_comments - prev_comments
                    noun = "comment" if diff == 1 else "comments"
                    rumps.notification(
                        title=f"PR #{num}: {diff} new {noun}",
                        subtitle=pr["title"],
                        message="",
                        sound=True,
                        data={"url": pr["url"]}
                    )

                self.last_checks[num] = pr["check_status"]
                self.last_reviews[num] = pr["review_status"]
                self.last_comment_counts[num] = new_comments

        self.menu.add(rumps.MenuItem("Refresh now", callback=lambda _: self.refresh_prs(None)))
        self.menu.add(rumps.MenuItem(f"Set Repo… ({self.repo or 'not set'})", callback=self.set_repo))
        self.menu.add(None)
        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

        if prs:
            statuses = {pr["check_status"] for pr in prs}
            if "failure" in statuses:
                self.icon = self.icon_red
            elif "pending" in statuses:
                self.icon = self.icon_yellow
            else:
                self.icon = self.icon_green
        else:
            self.icon = self.icon_default

    def fetch_open_prs(self):
        data = self.call_github("pulls?state=open&per_page=100")
        return data or []

    def fetch_check_status(self, sha):
        if not sha:
            return "pending", "🟡"
        runs = self.call_github(f"commits/{sha}/check-runs")
        if runs and isinstance(runs, dict):
            check_runs = runs.get("check_runs", [])
            if check_runs:
                conclusions = [cr.get("conclusion") for cr in check_runs if cr.get("conclusion") is not None]
                if any(c in ("failure", "cancelled", "timed_out", "action_required") for c in conclusions):
                    return "failure", "🔴"
                if len(conclusions) == len(check_runs) and all(c in ("success", "skipped", "neutral") for c in conclusions):
                    return "success", "🟢"
                return "pending", "🟡"
        status = self.call_github(f"commits/{sha}/status")
        if not status:
            return "pending", "🟡"
        state = status.get("state", "pending")
        if state == "success":
            return "success", "🟢"
        if state in ("failure", "error"):
            return "failure", "🔴"
        return "pending", "🟡"

    def fetch_review_status(self, pr_number):
        data = self.call_github(f"pulls/{pr_number}/reviews")
        if not data:
            return "none", "👀"
        reviews = [r for r in data if r.get("submitted_at")]
        if not reviews:
            return "none", "👀"
        latest_by_user = {}
        for r in sorted(reviews, key=lambda r: r["submitted_at"]):
            state = r.get("state", "").upper()
            user = r.get("user", {}).get("login")
            if state in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
                latest_by_user[user] = state
        if not latest_by_user:
            return "pending", "👀"
        states = set(latest_by_user.values())
        if "CHANGES_REQUESTED" in states:
            return "changes", "💬"
        if states == {"APPROVED"}:
            return "approved", "👍"
        return "pending", "👀"

    def is_assigned_or_requested(self, pr):
        if not self.gh_user:
            return False
        assignees = pr.get("assignees", []) or []
        if any(a.get("login") == self.gh_user for a in assignees):
            return True
        requested = pr.get("requested_reviewers", []) or []
        if any(r.get("login") == self.gh_user for r in requested):
            return True
        if pr.get("user", {}).get("login") == self.gh_user:
            return True
        return False

    def fetch_my_prs(self):
        raw = self.fetch_open_prs()
        if not raw:
            return []

        prs = []
        for pr in raw:
            if not self.is_assigned_or_requested(pr):
                continue

            sha = pr.get("head", {}).get("sha")
            check_status, check_emoji = self.fetch_check_status(sha)
            review_status, review_emoji = self.fetch_review_status(pr["number"])
            comment_count = pr.get("comments", 0) + pr.get("review_comments", 0)

            prs.append({
                "number": pr["number"],
                "title": pr.get("title", "<no title>"),
                "url": pr.get("html_url"),
                "check_status": check_status,
                "check_emoji": check_emoji,
                "review_status": review_status,
                "review_emoji": review_emoji,
                "comment_count": comment_count,
            })

        prs.sort(key=lambda p: p["number"], reverse=True)
        return prs

@rumps.notifications
def on_notification(info):
    url = info.get("url")
    if url:
        webbrowser.open(url)

if __name__ == "__main__":
    PRWatcher().run()
