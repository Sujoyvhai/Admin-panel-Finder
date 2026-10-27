#!/usr/bin/env python3
"""
APF - Admin Panel Finder
Author: Sujoy Karmakar
A fast multi-threaded tool to discover admin login panels on a target website.
"""

import argparse
import random
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

# ---------------- Colors ----------------
COLORS = ["\033[91m", "\033[92m", "\033[93m", "\033[94m", "\033[95m", "\033[96m"]
RESET = "\033[0m"
BOLD = "\033[1m"


def c(text):
    """random hacker-style color"""
    return f"{random.choice(COLORS)}{text}{RESET}"


BANNER = f"""
{c('   _____  _____  ______ ')}
{c('  /  _  \\ \\\\   / | ____|')}
{c(' /  /_\\  \\  \\\\ /  |  __| ')}
{c('/    |    \\  ||   | |     ')}
{c('\\___ | _  / _ ||_  |_|     ')}
{BOLD}{c('      Admin Panel Finder')}{RESET}
{c('      by Sujoy Karmakar')}
"""

DEFAULT_PATHS = [
    "admin", "admin/", "admin.php", "admin/login", "admin/login.php",
    "administrator", "administrator/", "administrator/index.php",
    "login", "login.php", "wp-admin", "wp-login.php",
    "cpanel", "panel", "panel/", "controlpanel", "admincp",
    "moderator", "webadmin", "adminarea", "admin_area",
    "admin-login", "admin_login", "bb-admin", "adminpanel",
    "siteadmin", "manager", "management", "admin/account.php",
    "admin1", "admin2", "useradmin", "sysadmin", "account",
    "admincontrol", "admin/cp.php", "adm", "admin/admin.php",
    "admin/admin_login.php", "admin/home.php", "admin/dashboard",
    "dashboard", "dashboard/login", "backend", "backend/login",
    "portal", "portal/login", "secure", "staff", "staff/login",
]


def load_wordlist(path):
    if not path:
        return DEFAULT_PATHS
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(c(f"[!] Wordlist not found: {path} — using built-in list"))
        return DEFAULT_PATHS


def check_url(base_url, path, timeout, found, lock, verbose, codes):
    url = urljoin(base_url + "/", path)
    try:
        r = requests.get(url, timeout=timeout, allow_redirects=False,
                          headers={"User-Agent": "Mozilla/5.0 (APF-Scanner)"})
        if r.status_code in codes:
            with lock:
                print(c(f"[+] FOUND ({r.status_code}): ") + url)
                found.append((url, r.status_code))
        elif verbose:
            with lock:
                print(f"[-] ({r.status_code}) {url}")
    except requests.RequestException:
        if verbose:
            with lock:
                print(c(f"[x] Error: {url}"))


def worker(q, base_url, timeout, found, lock, verbose, codes):
    while True:
        try:
            path = q.get_nowait()
        except queue.Empty:
            return
        check_url(base_url, path, timeout, found, lock, verbose, codes)
        q.task_done()


def main():
    parser = argparse.ArgumentParser(
        prog="apf", description="APF - Admin Panel Finder by Sujoy Karmakar")
    parser.add_argument("-d", "--domain", required=True,
                         help="Target domain/URL, e.g. example.com")
    parser.add_argument("-w", "--wordlist", help="Path to custom wordlist file")
    parser.add_argument("-t", "--threads", type=int, default=20, help="Number of threads (default 20)")
    parser.add_argument("-T", "--timeout", type=float, default=5, help="Request timeout seconds (default 5)")
    parser.add_argument("-o", "--output", help="Save found panels to file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show all attempts, not just hits")
    parser.add_argument("-c", "--codes", default="200,301,302,401,403",
                         help="Comma-separated status codes counted as 'found' (default 200,301,302,401,403)")
    args = parser.parse_args()

    print(BANNER)

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
    print("-" * 50)

    q = queue.Queue()
    for p in paths:
        q.put(p)

    found = []
    lock = threading.Lock()
    start = time.time()

    threads = []
    for _ in range(min(args.threads, len(paths)) or 1):
        th = threading.Thread(target=worker, args=(q, base_url, args.timeout, found, lock, args.verbose, codes))
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
