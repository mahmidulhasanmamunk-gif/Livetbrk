import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.jagobd.com/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

OUTPUT_FILE = "playlist.m3u"

def extract_m3u8_from_js(text):
    # regex to catch any m3u8 inside JS
    m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', text)
    if m:
        return m.group(1)
    return None

def find_iframe_sources():
    r = requests.get(BASE_URL, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    iframes = []
    for tag in soup.find_all("iframe"):
        if "src" in tag.attrs:
            src = tag["src"]
            full = requests.compat.urljoin(BASE_URL, src)
            iframes.append(full)

    return list(set(iframes))

def scrape_all():
    m3u_list = []

    iframe_links = find_iframe_sources()
    print("Iframe count:", len(iframe_links))

    for link in iframe_links:
        try:
            r = requests.get(link, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                continue

            m3u8 = extract_m3u8_from_js(r.text)
            if m3u8:
                m3u_list.append(m3u8)

        except:
            continue

    return list(set(m3u_list))

def build_m3u(urls):
    lines = ["#EXTM3U"]
    for i, url in enumerate(urls, start=1):
        lines.append(f'#EXTINF:-1 group-title="Jagobd",Channel_{i}')
        lines.append(url)
    return "\n".join(lines) + "\n"

def main():
    urls = scrape_all()
    print("Found streams:", len(urls))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(build_m3u(urls))

if __name__ == "__main__":
    main()
