# scraper.py
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import time

BASE_URL = "https://www.jagobd.com/"
OUTPUT_FILE = "playlist.m3u"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}
REQUEST_TIMEOUT = 10
MAX_CRAWL_PAGES = 30

def fetch_text(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200:
            return r.text
    except Exception:
        pass
    return None

def extract_m3u8_from_text(text):
    # catches urls like ...mono.m3u8?...wmsAuthSign=...
    pattern = re.compile(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', re.IGNORECASE)
    return list(set(pattern.findall(text or "")))

def find_candidate_pages(root_html, base):
    # Heuristic: gather internal links that look like channel/player pages
    links = set()
    for m in re.finditer(r'href=["\']([^"\']+)["\']', root_html or "", re.IGNORECASE):
        href = m.group(1)
        if href.startswith("#"):
            continue
        full = urljoin(base, href)
        # only same-origin
        if base.split("/")[2] not in full:
            continue
        # filter likely channel pages
        if any(x in href for x in ["/tvs/", "/live/", "/channel", "/watch", "/player"]):
            links.add(full)
        # also consider links with "jagobd.com" and path length
        elif len(href) < 80 and ("/" in href):
            links.add(full)
        if len(links) >= MAX_CRAWL_PAGES:
            break
    return list(links)

def extract_ids_for_ajax(html):
    # Search for possible channel identifiers in data-* attributes or inline JS
    ids = set()
    # data-id="channel-name" or data-channel="xyz"
    for m in re.finditer(r'data-(?:id|channel)[\s]*=["\']([^"\']+)["\']', html or "", re.IGNORECASE):
        ids.add(m.group(1))
    # inline JS patterns: id: "xxx" or id:'xxx'
    for m in re.finditer(r'id["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]+)["\']', html or ""):
        ids.add(m.group(1))
    # look for "player_id" or similar
    for m in re.finditer(r'player[_-]?id["\']?\s*[:=]\s*["\']([a-zA-Z0-9_\-]+)["\']', html or "", re.IGNORECASE):
        ids.add(m.group(1))
    return list(ids)

def call_jagobd_ajax(channel_id):
    # Known endpoint pattern (heuristic). Adjust if jagobd uses different parameters.
    api = f"https://www.jagobd.com/wp-admin/admin-ajax.php?action=channelembed&id={channel_id}"
    try:
        r = requests.get(api, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            return None
        # response might be JSON or HTML containing m3u8
        # try parse JSON first
        try:
            data = r.json()
            # common fields to check: stream_url, url, src
            for k in ("stream_url", "url", "src", "m3u8"):
                if k in data and data[k]:
                    return data[k]
            # some responses embed HTML containing m3u8
            html = str(data)
            found = extract_m3u8_from_text(html)
            if found:
                return found[0]
        except ValueError:
            # not JSON — fallback to text search
            found = extract_m3u8_from_text(r.text)
            if found:
                return found[0]
    except Exception:
        pass
    return None

def check_alive(url):
    try:
        # Use HEAD first, fallback to GET for some servers
        r = requests.head(url, headers=HEADERS, timeout=8, allow_redirects=True)
        if r.status_code in (200, 206):
            return True
        # some servers block HEAD — try GET small range
        r2 = requests.get(url, headers=HEADERS, timeout=8, stream=True)
        return r2.status_code in (200, 206)
    except Exception:
        return False

def build_m3u(entries):
    lines = ["#EXTM3U"]
    for e in entries:
        name = e.get("name") or e.get("id") or "Channel"
        url = e["url"]
        group = e.get("group", "Live")
        lines.append(f'#EXTINF:-1 group-title="{group}",{name}')
        lines.append(url)
    lines.append(f"# Generated: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    return "\n".join(lines) + "\n"

def main():
    root_html = fetch_text(BASE_URL)
    if not root_html:
        print("Failed to fetch base URL")
        return

    results = {}
    # 1) direct m3u8 in root html
    direct = extract_m3u8_from_text(root_html)
    for url in direct:
        if check_alive(url):
            results[url] = {"url": url, "name": url.split("/")[-1].split("?")[0]}

    # 2) iframes
    soup = BeautifulSoup(root_html, "html.parser")
    iframe_srcs = set()
    for tag in soup.find_all("iframe"):
        src = tag.get("src")
        if not src:
            continue
        iframe_srcs.add(urljoin(BASE_URL, src))

    for iframe in iframe_srcs:
        text = fetch_text(iframe)
        if not text:
            continue
        found = extract_m3u8_from_text(text)
        for url in found:
            if url not in results and check_alive(url):
                results[url] = {"url": url, "name": iframe.split("/")[-1]}

    # 3) candidate internal pages
    candidates = find_candidate_pages(root_html, BASE_URL)
    for page in candidates:
        text = fetch_text(page)
        if not text:
            continue
        # inline m3u8
        found = extract_m3u8_from_text(text)
        for url in found:
            if url not in results and check_alive(url):
                results[url] = {"url": url, "name": page.split("/")[-1]}

        # try AJAX ids -> admin-ajax endpoint
        ids = extract_ids_for_ajax(text)
        for cid in ids:
            m = call_jagobd_ajax(cid)
            if m and m not in results and check_alive(m):
                results[m] = {"url": m, "id": cid}

    # 4) final fallback: try to crawl player.js files for m3u8
    for script in soup.find_all("script", src=True):
        src = urljoin(BASE_URL, script["src"])
        text = fetch_text(src)
        if not text:
            continue
        found = extract_m3u8_from_text(text)
        for url in found:
            if url not in results and check_alive(url):
                results[url] = {"url": url, "name": src.split("/")[-1]}

    # write playlist
    entries = list(results.values())
    if not entries:
        print("No streams discovered.")
    else:
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(build_m3u(entries))
        print(f"Wrote {len(entries)} entries to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
