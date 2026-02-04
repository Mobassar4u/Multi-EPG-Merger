import requests
import gzip
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
    # Create the final root element
    combined_root = etree.Element("tv")
    seen_channels = set()
    seen_programmes = set()

    for url in EPG_URLS:
        try:
            print(f"Fetching: {url}")
            response = requests.get(url, timeout=45)
            response.raise_for_status()
            
            # 1. Use a more aggressive recovery parser for broken XML
            parser = etree.XMLParser(recover=True, remove_blank_text=True, resolve_entities=False)
            tree = etree.fromstring(response.content, parser=parser)
            
            # 2. Handle Namespaces: Use local-name() to ignore the xmlns prefix
            # This ensures we find <channel> even if it's <ns:channel> or similar.
            channels = tree.xpath("//*[local-name()='channel']")
            programmes = tree.xpath("//*[local-name()='programme']")
            
            print(f"  - Found {len(channels)} channels and {len(programmes)} programmes")

            # Merge Channels (Unique by ID)
            for channel in channels:
                channel_id = channel.get("id")
                if channel_id and channel_id not in seen_channels:
                    # Clean the element of its old namespace to keep the output clean
                    channel.tag = "channel" 
                    combined_root.append(channel)
                    seen_channels.add(channel_id)

            # Merge Programmes (Unique by channel + start time)
            for prog in programmes:
                ch_id = prog.get("channel")
                start_time = prog.get("start")
                # Create a unique key to prevent duplicate shows
                prog_key = f"{ch_id}_{start_time}"
                
                if prog_key not in seen_programmes:
                    prog.tag = "programme"
                    combined_root.append(prog)
                    seen_programmes.add(prog_key)

        except Exception as e:
            print(f"Error processing {url}: {e}")

    # Final Save
    xml_data = etree.tostring(combined_root, encoding="utf-8", xml_declaration=True, pretty_print=True)

    with open("merged_epg.xml", "wb") as f:
        f.write(xml_data)
    
    with gzip.open("merged_epg.xml.gz", "wb") as f:
        f.write(xml_data)

    print(f"Done! Total unique channels: {len(seen_channels)}")

if __name__ == "__main__":
    merge_epgs()
