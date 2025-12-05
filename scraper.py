import re
import requests
from bs4 import BeautifulSoup

TARGET_URL = "https://www.jagobd.com/"
OUTPUT_FILE = "playlist.m3u"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def extract_m3u8_from_iframe(url):
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return None

        text = r.text
        # Find direct m3u8
        m = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', text)
        if m:
            return m.group(1)

    except:
        return None
    return None

def scrape_channels():
    r = requests.get(TARGET_URL, headers=headers, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")

    channels = []
    for iframe in soup.find_all("iframe"):
        if "src" in iframe.attrs:
            src = iframe["src"]
            full = requests.compat.urljoin(TARGET_URL, src)
            m3u8 = extract_m3u8_from_iframe(full)
            if m3u8:
                channels.append(m3u8)

    return list(set(channels))

def build_m3u(urls):
    lines = ["#EXTM3U"]
    for i, url in enumerate(urls, start=1):
        lines.append(f'#EXTINF:-1 group-title="Jagobd",Channel_{i}')
        lines.append(url)
    return "\n".join(lines) + "\n"

def main():
    urls = scrape_channels()
    print("Found:", len(urls))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(build_m3u(urls))

if __name__ == "__main__":
    main()
