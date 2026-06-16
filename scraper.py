"""
Supplementhub scraper
- Haalt alle producten op via products.json (alle pagina's)
- Scrapt live pagina voor: prijs (og:price), beschrijving (og:description)
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
REQUEST_DELAY = 0.75

# Supplementhub prijzen lijken incl. BTW te zijn (site zegt "Inclusief belasting")
# Zet op True als og:price EXCL BTW is, dan wordt BTW berekend
APPLY_BTW = False
BTW = 1.21

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; StockSyncBot/1.0)",
    "Accept-Language": "nl-NL,nl;q=0.9",
}


def fetch_all_products():
    products = []
    page = 1
    print("📦 Producten ophalen via JSON API...")

    while True:
        url = f"{BASE_URL}/products.json?limit=250&page={page}"
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
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
    """Haalt prijs en beschrijving op van de live productpagina."""
    url = f"{BASE_URL}{LOCALE}/products/{handle}"
    result = {"price": None, "description": None}

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        html = response.text

        price_str = extract_meta(html, "price:amount")
        if price_str:
            price = float(price_str.replace(",", "."))
            result["price"] = round(price * BTW, 2) if APPLY_BTW else price

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

        print(f"  [{i}/{total}] {title[:60]}...")
        live = fetch_live_details(handle)

        description = live.get("description") or body_html

        for variant in product.get("variants", []):
            sku = variant.get("sku", "")
            barcode = variant.get("barcode", "") or ""
            available = variant.get("available", False)
            quantity = variant.get("inventory_quantity", 0)

            if live.get("price") is not None:
                price = live["price"]
            else:
                raw_price = float(variant.get("price", "0"))
                price = round(raw_price * BTW, 2) if APPLY_BTW else raw_price

            raw_compare = variant.get("compare_at_price")
            if raw_compare:
                compare_at_price = round(float(raw_compare) * BTW, 2) if APPLY_BTW else float(raw_compare)
            else:
                compare_at_price = ""

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
    print(f"https://raw.githubusercontent.com/Maximillian-creator/supplementhub-feed/main/supplementhub_feed.xml")


if __name__ == "__main__":
    main()
