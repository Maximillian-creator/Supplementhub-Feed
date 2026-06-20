"""
Supplementhub scraper (Storefront API)
- Haalt alle producten op via Shopify Storefront GraphQL API
- Prijzen exact incl. correcte BTW via @inContext(country: NL)
- Genereert één gecombineerde XML voor Stock Sync
"""

import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
import time
import json

STOREFRONT_TOKEN = "78b4cf4eea62489af1b61f38cc674fdc"
API_URL = "https://supplementhub.com/api/2024-01/graphql.json"
OUTPUT_FILE = "supplementhub_feed.xml"

HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Storefront-Access-Token": STOREFRONT_TOKEN,
}

PRODUCTS_QUERY = """
query ($cursor: String) @inContext(country: NL) {
  products(first: 50, after: $cursor) {
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        title
        handle
        vendor
        productType
        descriptionHtml
        tags
        images(first: 5) {
          edges {
            node {
              url
            }
          }
        }
        variants(first: 10) {
          edges {
            node {
              sku
              barcode
              title
              price {
                amount
              }
              compareAtPrice {
                amount
              }
              availableForSale
              selectedOptions {
                name
                value
              }
              weight
              weightUnit
              image {
                url
              }
            }
          }
        }
      }
    }
  }
}
"""


def fetch_with_retry(query, variables=None, max_retries=3):
    """GraphQL request met retry-logica."""
    for attempt in range(max_retries):
        try:
            payload = {"query": query}
            if variables:
                payload["variables"] = variables
            response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            if "errors" in data:
                print(f"    ⚠️  GraphQL errors: {data['errors']}")
            return data
        except Exception as e:
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 30
                print(f"    ⚠️  Fout ({e}), opnieuw proberen in {wait}s...")
                time.sleep(wait)
            else:
                raise


def fetch_all_products():
    """Haalt alle producten op via Storefront API met cursor-paginatie."""
    products = []
    cursor = None
    page = 1

    print("📦 Producten ophalen via Storefront API...")

    while True:
        variables = {"cursor": cursor} if cursor else {}
        data = fetch_with_retry(PRODUCTS_QUERY, variables)

        edges = data.get("data", {}).get("products", {}).get("edges", [])
        page_info = data.get("data", {}).get("products", {}).get("pageInfo", {})

        for edge in edges:
            products.append(edge["node"])

        print(f"  Pagina {page}: {len(edges)} producten (totaal: {len(products)})")

        if not page_info.get("hasNextPage", False):
            break

        cursor = page_info.get("endCursor")
        page += 1
        time.sleep(1)  # Rate limiting

    print(f"✅ {len(products)} producten gevonden\n")
    return products


def build_xml(products):
    root = ET.Element("products")
    total = len(products)

    for i, product in enumerate(products, 1):
        handle = product.get("handle", "")
        title = product.get("title", "")
        vendor = product.get("vendor", "")
        product_type = product.get("productType", "")
        description_html = product.get("descriptionHtml", "") or ""
        tags = product.get("tags", [])
        tags_str = ", ".join(tags)

        images = product.get("images", {}).get("edges", [])
        image_url = images[0]["node"]["url"] if images else ""

        variants = product.get("variants", {}).get("edges", [])

        print(f"  [{i}/{total}] {title[:60]}...")

        for variant_edge in variants:
            variant = variant_edge["node"]
            sku = variant.get("sku", "") or ""
            barcode = variant.get("barcode", "") or ""
            available = variant.get("availableForSale", False)
            price = float(variant.get("price", {}).get("amount", "0"))

            compare_at = variant.get("compareAtPrice")
            compare_at_price = float(compare_at["amount"]) if compare_at else ""

            # Variant afbeelding
            variant_image = variant.get("image", {})
            variant_image_url = variant_image.get("url", image_url) if variant_image else image_url

            # Opties
            options = variant.get("selectedOptions", [])
            option1 = options[0]["value"] if len(options) > 0 else ""
            option2 = options[1]["value"] if len(options) > 1 else ""

            variant_title = variant.get("title", "")
            weight = variant.get("weight") or ""
            weight_unit = variant.get("weightUnit", "") or ""

            item = ET.SubElement(root, "product")

            def add(tag, value):
                el = ET.SubElement(item, tag)
                el.text = str(value) if value is not None else ""

            add("sku", sku)
            add("barcode", barcode)
            add("title", title)
            add("vendor", vendor)
            add("product_type", product_type)
            add("description", description_html)
            add("tags", tags_str)
            add("price", f"{price:.2f}")
            add("compare_at_price", f"{compare_at_price:.2f}" if compare_at_price else "")
            add("available", "true" if available else "false")
            add("quantity", "0")
            add("handle", handle)
            add("image", variant_image_url)
            add("variant_title", variant_title)
            add("option1", option1)
            add("option2", option2)
            add("weight", weight)
            add("weight_unit", weight_unit)

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
