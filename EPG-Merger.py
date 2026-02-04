import requests
import gzip
from lxml import etree

# List your EPG URLs here
EPG_URLS = [
    "https://www.open-epg.com/files/india1.xml",
    "https://www.open-epg.com/files/india2.xml",
    "https://www.open-epg.com/files/india3.xml",
    "https://www.open-epg.com/files/india4.xml",
    "https://www.open-epg.com/files/india5.xml",
    "https://www.open-epg.com/files/india6.xml",
]

def merge_epgs():
    # Headers to mimic a real web browser (Prevents blocks)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }

    combined_root = etree.Element("tv")
    seen_channels = set()
    seen_programmes = set()

    for url in EPG_URLS:
        try:
            print(f"Fetching: {url}")
            # Verify=False can be added if the source has SSL certificate issues
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            
            # Using a very forgiving parser
            parser = etree.XMLParser(recover=True, remove_blank_text=True)
            tree = etree.fromstring(response.content, parser=parser)
            
            # Find all channels regardless of namespace/prefix
            channels = tree.xpath("//*[local-name()='channel']")
            programmes = tree.xpath("//*[local-name()='programme']")
            
            for channel in channels:
                channel_id = channel.get("id")
                if channel_id and channel_id not in seen_channels:
                    # Strip namespaces for the final output
                    channel.tag = "channel"
                    combined_root.append(channel)
                    seen_channels.add(channel_id)

            for prog in programmes:
                ch_id = prog.get("channel")
                start = prog.get("start")
                # Create a composite key: channel + start time
                prog_key = f"{ch_id}_{start}"
                
                if prog_key not in seen_programmes:
                    prog.tag = "programme"
                    combined_root.append(prog)
                    seen_programmes.add(prog_key)

            print(f"  - Successfully added {len(channels)} channels from this source.")

        except Exception as e:
            print(f"  ! Failed to fetch {url}: {e}")

    # Output files
    xml_data = etree.tostring(combined_root, encoding="utf-8", xml_declaration=True, pretty_print=True)

    with open("in-tv.epg.xml", "wb") as f:
        f.write(xml_data)
    
    with gzip.open("in-tv.epg.xml.gz", "wb") as f:
        f.write(xml_data)

    print(f"\nTotal Unique Channels in Merged File: {len(seen_channels)}")

if __name__ == "__main__":
    merge_epgs()
