#!/usr/bin/env python3
"""
APF - Admin Panel Finder
Author: Sujoy Karmakar
A fast multi-threaded tool to discover admin login panels on a target website.
"""

import argparse
import random
import string
import sys
import threading
import queue
import time
from urllib.parse import urljoin

try:
    import requests
except ImportError:
    print("[!] 'requests' module not found. Install it with: pip install requests")
    sys.exit(1)

# ---------------- Version ----------------
VERSION = "1.2"

# ---------------- Update ----------------
# Point this at your real GitHub repo (user/repo) to enable `apf --update`.
GITHUB_REPO = "sujoykarmakar/apf"
RAW_SCRIPT_URL = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/apf.py"

# ---------------- Colors ----------------
COLORS = ["\033[91m", "\033[92m", "\033[93m", "\033[94m", "\033[95m", "\033[96m"]
RESET = "\033[0m"
BOLD = "\033[1m"


def c(text):
    """random hacker-style color"""
    return f"{random.choice(COLORS)}{text}{RESET}"


def banner():
    """Rebuilt on every run so colors are freshly randomized each time."""
    lines = [
        '   _____  _____  ______ ',
        '  /  _  \\ \\   / | ____|',
        ' /  /_\\  \\  \\ /  |  __| ',
        '/    |    \\  ||   | |     ',
        '\\___ | _  / _ ||_  |_|     ',
    ]
    out = "\n" + "\n".join(c(line) for line in lines) + "\n"
    out += f"{BOLD}{c('      Admin Panel Finder')}{RESET}\n"
    out += c('      by Sujoy Karmakar') + "\n"
    out += c(f'      v{VERSION}') + "\n"
    return out


DEFAULT_PATHS = [
    "admin", "admin/", "admin.php", "admin/login", "admin/login.php",
    "admin/index.php", "admin/home", "admin/dashboard", "admin/dashboard.php",
    "admin/account.php", "admin/admin.php", "admin/admin_login.php",
    "admin/cp.php", "admin1", "admin2", "admin3", "admin_area",
    "admin-login", "admin_login", "admincontrol", "admincp",
    "admincp/login.php", "adminarea", "adminlogin", "adminpanel",
    "adminpanel.php", "adm", "adm/", "administrator", "administrator/",
    "administrator/index.php", "administrator/login",
    "administrator/account.php", "moderator", "moderator.php",
    "webadmin", "webadmin/", "webadmin/login.php", "siteadmin",
    "siteadmin/", "siteadmin/login", "sysadmin", "useradmin",
    "bb-admin", "bb-admin/index.php", "cpanel", "cpanel/",
    "controlpanel", "control", "control/", "panel", "panel/",
    "panel/login", "panel/login.php", "backend", "backend/",
    "backend/login", "manage", "manage/", "management", "manager",
    "manager/", "manager/login", "dashboard", "dashboard/",
    "dashboard/login", "portal", "portal/", "portal/login",
    "portal/admin", "login", "login.php", "login/", "signin",
    "signin.php", "user/login", "users/login", "account/login",
    "account", "accounts", "staff", "staff/", "staff/login",
    "member", "member/", "member/login", "members", "members/login",
    "secure", "secure/login", "secure/admin", "cms", "cms/",
    "cms/admin", "cms/login", "blog/admin", "blog/wp-admin",
    "wp-admin", "wp-admin/", "wp-login.php",
]


def load_wordlist(path):
    if not path:
        paths = list(DEFAULT_PATHS)
    else:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                paths = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(c(f"[!] Wordlist not found: {path} — using built-in list"))
            paths = list(DEFAULT_PATHS)
    random.shuffle(paths)  # randomize scan order every run
    return paths


def get_baseline(base_url, timeout):
    """
    Hit a random, almost-certainly-nonexistent path first so we know what
    this site's "fake 200 / soft 404" catch-all page looks like. Any real
    hit is then compared against this baseline so the live status code
    reported is trustworthy instead of flagging every path on sites that
    redirect everything to the same login/error page.
    """
    junk = "apf-" + "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    url = urljoin(base_url + "/", junk)
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0 (APF-Scanner)"})
        return {"status": r.status_code, "length": len(r.content), "final_url": r.url}
    except requests.RequestException:
        return None


def check_url(base_url, path, timeout, found, lock, verbose, codes, baseline):
    url = urljoin(base_url + "/", path)
    try:
        # Live, real-time request (no caching) following redirects so the
        # status code shown is the actual final status, not a 301/302 stub.
        r = requests.get(url, timeout=timeout, allow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0 (APF-Scanner)"})
        status = r.status_code
        length = len(r.content)

        is_soft_404 = (
            baseline is not None
            and status == baseline["status"]
            and r.url == baseline["final_url"]
            and abs(length - baseline["length"]) < 25
        )

        if status in codes and not is_soft_404:
            with lock:
                print(c(f"[+] FOUND ({status}): ") + url)
                found.append((url, status))
        elif verbose:
            tag = "[soft-404]" if is_soft_404 else ""
            with lock:
                print(f"[-] ({status}) {url} {tag}")
    except requests.RequestException:
        if verbose:
            with lock:
                print(c(f"[x] Error: {url}"))


def worker(q, base_url, timeout, found, lock, verbose, codes, baseline):
    while True:
        try:
            path = q.get_nowait()
        except queue.Empty:
            return
        check_url(base_url, path, timeout, found, lock, verbose, codes, baseline)
        q.task_done()


def do_update():
    """Pull the latest apf.py from GitHub and overwrite this file in place."""
    print(c(f"[*] Checking for updates from: ") + RAW_SCRIPT_URL)
    try:
        resp = requests.get(RAW_SCRIPT_URL, timeout=10)
        if resp.status_code != 200:
            print(c(f"[!] Update check failed (HTTP {resp.status_code})."))
            print(c(f"[!] Set GITHUB_REPO at the top of apf.py to your real repo."))
            return
        new_code = resp.text
        with open(__file__, "w", encoding="utf-8") as f:
            f.write(new_code)
        print(c("[+] apf.py updated successfully. Re-run 'apf' to use the latest version."))
    except requests.RequestException as e:
        print(c(f"[!] Could not reach update server: {e}"))
    except Exception as e:
        print(c(f"[!] Update failed: {e}"))


def main():
    parser = argparse.ArgumentParser(
        prog="apf", description=f"APF - Admin Panel Finder v{VERSION} by Sujoy Karmakar")
    parser.add_argument("-d", "--domain", help="Target domain/URL, e.g. example.com")
    parser.add_argument("-w", "--wordlist", help="Path to custom wordlist file")
    parser.add_argument("-t", "--threads", type=int, default=20, help="Number of threads (default 20)")
    parser.add_argument("-T", "--timeout", type=float, default=5, help="Request timeout seconds (default 5)")
    parser.add_argument("-o", "--output", help="Save found panels to file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show all attempts, not just hits")
    parser.add_argument("-c", "--codes", default="200,301,302,401,403",
                         help="Comma-separated status codes counted as 'found' (default 200,301,302,401,403)")
    parser.add_argument("--no-baseline", action="store_true",
                         help="Skip soft-404 baseline check (faster, but noisier on catch-all sites)")
    parser.add_argument("--update", action="store_true", help="Update apf.py to the latest version from GitHub")
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    args = parser.parse_args()

    print(banner())

    if args.version:
        sys.exit(0)

    if args.update:
        do_update()
        sys.exit(0)

    if not args.domain:
        parser.error("the following argument is required: -d/--domain (or use --update)")

    domain = args.domain.strip()
    if not domain.startswith("http://") and not domain.startswith("https://"):
        base_url = "https://" + domain
    else:
        base_url = domain
    base_url = base_url.rstrip("/")

    codes = set(int(x) for x in args.codes.split(","))
    paths = load_wordlist(args.wordlist)

    print(c(f"[*] Target     : ") + base_url)
    print(c(f"[*] Paths      : ") + str(len(paths)))
    print(c(f"[*] Threads    : ") + str(args.threads))
    print(c(f"[*] Status OK  : ") + args.codes)
    print(c(f"[*] Order      : ") + "random")

    baseline = None
    if not args.no_baseline:
        print(c(f"[*] Baseline   : ") + "checking soft-404 signature...")
        baseline = get_baseline(base_url, args.timeout)
        if baseline:
            print(c(f"[*] Baseline   : ") + f"status {baseline['status']}, {baseline['length']} bytes")
        else:
            print(c(f"[!] Baseline check failed — continuing without it"))

    print("-" * 50)

    q = queue.Queue()
    for p in paths:
        q.put(p)

    found = []
    lock = threading.Lock()
    start = time.time()

    threads = []
    for _ in range(min(args.threads, len(paths)) or 1):
        th = threading.Thread(
            target=worker,
            args=(q, base_url, args.timeout, found, lock, args.verbose, codes, baseline))
        th.daemon = True
        th.start()
        threads.append(th)

    for th in threads:
        th.join()

    elapsed = time.time() - start
    print("-" * 50)
    print(c(f"[*] Scan complete in {elapsed:.2f}s — {len(found)} panel(s) found"))

    if args.output and found:
        with open(args.output, "w", encoding="utf-8") as f:
            for url, status in found:
                f.write(f"{url} [{status}]\n")
        print(c(f"[*] Results saved to: ") + args.output)


if __name__ == "__main__":
    main()
