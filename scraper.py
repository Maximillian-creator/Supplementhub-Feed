"""
Supplementhub scraper
- Haalt alle producten op via products.json (alle pagina's)
- Berekent prijs incl. BTW (9% bij low_vat_rate tag, anders 21%)
- Genereert één gecombineerde XML voor Stock Sync
"""

import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
import time
import re
import os

BASE_URL = "https://supplementhub.com"
LOCALE = "/nl"
OUTPUT_FILE = "supplementhub_feed.xml"
BTW_HOOG = 1.21
BTW_LAAG = 1.09
REQUEST_DELAY = 0.75

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StockSyncBot/1.0)",
    "Accept-Language": "nl-NL,nl;q=0.9",
}


def fetch_with_retry(url, max_retries=3):
    """Fetch een URL met retry-logica bij fouten."""
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            return response
        except Exception as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 30
                print(f"    ⚠️  Fout ({e}), opnieuw proberen in {wait}s...")
                time.sleep(wait)
            else:
                print(f"    ❌ Mislukt na {max_retries} pogingen: {e}")
                raise


def fetch_all_products():
    products = []
    page = 1
    print("📦 Producten ophalen via JSON API...")

    while True:
        url = f"{BASE_URL}/products.json?limit=250&page={page}"
        response = fetch_with_retry(url)
        batch = response.json().get("products", [])
        if not batch:
            break
        products.extend(batch)
        print(f"  Pagina {page}: {len(batch)} producten (totaal: {len(products)})")
        if len(batch) < 250:
            break
        page += 1
        time.sleep(REQUEST_DELAY)

    print(f"✅ {len(products)} producten gevonden\n")
    return products


def extract_meta(html, property_name):
    """Haal een meta-tag waarde op uit HTML."""
    match = re.search(
        rf'<meta[^>]+property=["\']og:{property_name}["\'][^>]+content=["\']([^"\']+)["\']',
        html
    )
    if not match:
        match = re.search(
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:{property_name}["\']',
            html
        )
    return match.group(1) if match else None


def fetch_live_details(handle):
    """Haalt beschrijving op van de live productpagina."""
    url = f"{BASE_URL}{LOCALE}/products/{handle}"
    result = {"description": None}

    try:
        response = fetch_with_retry(url, max_retries=2)
        html = response.text

        desc = extract_meta(html, "description")
        if desc:
            result["description"] = desc

    except Exception as e:
        print(f"    ⚠️  Fout bij {handle}: {e}")

    return result


def build_xml(products):
    root = ET.Element("products")
    total = len(products)

    for i, product in enumerate(products, 1):
        handle = product.get("handle", "")
        title = product.get("title", "")
        vendor = product.get("vendor", "")
        product_type = product.get("product_type", "")
        body_html = product.get("body_html", "") or ""
        tags = product.get("tags", [])
        tags_str = ", ".join(tags)
        images = product.get("images", [])
        image_url = images[0].get("src", "") if images else ""

        # BTW bepalen op basis van tags
        btw = BTW_LAAG if "low_vat_rate" in tags else BTW_HOOG
        btw_label = "9%" if btw == BTW_LAAG else "21%"

        print(f"  [{i}/{total}] {title[:60]}... (BTW: {btw_label})")
        live = fetch_live_details(handle)

        description = live.get("description") or body_html

        for variant in product.get("variants", []):
            sku = variant.get("sku", "")
            barcode = variant.get("barcode", "") or ""
            available = variant.get("available", False)
            quantity = variant.get("inventory_quantity", 0)

            # Prijs: JSON prijs × juiste BTW
            raw_price = float(variant.get("price", "0"))
            price = round(raw_price * btw, 2)

            raw_compare = variant.get("compare_at_price")
            compare_at_price = round(float(raw_compare) * btw, 2) if raw_compare else ""

            variant_image_id = variant.get("image_id")
            variant_image = image_url
            for img in images:
                if img.get("id") == variant_image_id:
                    variant_image = img.get("src", image_url)
                    break

            item = ET.SubElement(root, "product")

            def add(tag, value):
                el = ET.SubElement(item, tag)
                el.text = str(value) if value is not None else ""

            add("sku", sku)
            add("barcode", barcode)
            add("title", title)
            add("vendor", vendor)
            add("product_type", product_type)
            add("description", description)
            add("tags", tags_str)
            add("price", f"{price:.2f}")
            add("compare_at_price", f"{compare_at_price:.2f}" if compare_at_price else "")
            add("available", "true" if available else "false")
            add("quantity", quantity if available else 0)
            add("handle", handle)
            add("image", variant_image)
            add("variant_title", variant.get("title", ""))
            add("option1", variant.get("option1", "") or "")
            add("option2", variant.get("option2", "") or "")
            add("weight", variant.get("weight", ""))
            add("weight_unit", variant.get("weight_unit", ""))

        time.sleep(REQUEST_DELAY)

    return root


def save_xml(root, filepath):
    xml_str = ET.tostring(root, encoding="unicode")
    pretty = minidom.parseString(xml_str).toprettyxml(indent="  ")
    lines = pretty.split("\n")
    if lines[0].startswith("<?xml"):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n💾 XML opgeslagen: {filepath}")


def main():
    print("🚀 Supplementhub scraper gestart\n")
    start = time.time()

    products = fetch_all_products()
    root = build_xml(products)
    save_xml(root, OUTPUT_FILE)

    elapsed = time.time() - start
    print(f"⏱️  Klaar in {elapsed:.0f} seconden")
    print(f"\n📋 Feed URL voor Stock Sync:")
    print(f"https://raw.githubusercontent.com/Maximillian-creator/Supplementhub-Feed/main/supplementhub_feed.xml")


if __name__ == "__main__":
    main()
