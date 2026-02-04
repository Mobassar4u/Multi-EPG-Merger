import requests
from lxml import etree
import os

# List your EPG URLs here
EPG_URLS = [
    "https://www.open-epg.com/files/india1.xml",
    "https://www.open-epg.com/files/india2.xml"
    "https://www.open-epg.com/files/india3.xml"
    "https://www.open-epg.com/files/india4.xml"
    "https://www.open-epg.com/files/india5.xml"
    "https://www.open-epg.com/files/india6.xml"
]

def merge_epgs():
    combined_root = etree.Element("tv")
    seen_channels = set()
    seen_programmes = set()

    for url in EPG_URLS:
        try:
            print(f"Fetching: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            tree = etree.fromstring(response.content)
            
            # Merge Channels (Unique by ID)
            for channel in tree.xpath("//channel"):
                channel_id = channel.get("id")
                if channel_id not in seen_channels:
                    combined_root.append(channel)
                    seen_channels.add(channel_id)

            # Merge Programmes (Unique by channel + start time)
            for prog in tree.xpath("//programme"):
                prog_id = f"{prog.get('channel')}_{prog.get('start')}"
                if prog_id not in seen_programmes:
                    combined_root.append(prog)
                    seen_programmes.add(prog_id)

        except Exception as e:
            print(f"Error processing {url}: {e}")

    # Write to file
    with open("merged_epg.xml", "wb") as f:
        f.write(etree.tostring(combined_root, encoding="utf-8", xml_declaration=True, pretty_print=True))
    print("Successfully created merged_epg.xml")

if __name__ == "__main__":
    merge_epgs()
