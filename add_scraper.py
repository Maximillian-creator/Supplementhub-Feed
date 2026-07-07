"""
Supplementhub ADD-feed
======================
Tweelingbroer van scraper.py (de update-feed). Zelfde bron (Shopify Storefront
GraphQL API), maar output = ALLE productinfo om met Stock Sync NIEUWE producten
aan te maken: naast prijs/voorraad ook álle afbeeldingen (images-blok +
image_links) en de optienamen.

Output: supplementhub_add_feed.xml
"""

import xml.etree.ElementTree as ET

from scraper import fetch_all_products, save_xml

OUTPUT_FILE = "supplementhub_add_feed.xml"


def build_xml(products):
    root = ET.Element("products")
    total = len(products)

    for i, product in enumerate(products, 1):
        handle = product.get("handle", "")
        title = product.get("title", "")
        vendor = product.get("vendor", "")
        product_type = product.get("productType", "")
        description_html = product.get("descriptionHtml", "") or ""
        tags_str = ", ".join(product.get("tags", []))

        image_edges = product.get("images", {}).get("edges", [])
        image_urls = [e["node"]["url"] for e in image_edges if e.get("node", {}).get("url")]
        first_image = image_urls[0] if image_urls else ""

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

            options = variant.get("selectedOptions", [])
            v_img = (variant.get("image") or {}).get("url") or first_image

            item = ET.SubElement(root, "product")

            def add(tag, value):
                el = ET.SubElement(item, tag)
                el.text = "" if value is None else str(value)

            add("handle", handle)
            add("title", title)
            add("vendor", vendor)
            add("product_type", product_type)
            add("sku", sku)
            add("barcode", barcode)
            add("price", f"{price:.2f}")
            add("compare_at_price", f"{compare_at_price:.2f}" if compare_at_price else "")
            add("available", "true" if available else "false")
            add("quantity", "")
            add("description", description_html)
            add("tags", tags_str)
            add("option1", options[0]["value"] if len(options) > 0 else "")
            add("option2", options[1]["value"] if len(options) > 1 else "")
            add("option1_name", options[0]["name"] if len(options) > 0 else "")
            add("option2_name", options[1]["name"] if len(options) > 1 else "")
            add("variant_title", variant.get("title", ""))
            add("weight", variant.get("weight") or "")
            add("weight_unit", variant.get("weightUnit", "") or "")
            add("image", v_img)

            # Alle afbeeldingen: genest + komma-gescheiden (voor Stock Sync)
            images_el = ET.SubElement(item, "images")
            for u in image_urls:
                img = ET.SubElement(images_el, "image")
                src = ET.SubElement(img, "src")
                src.text = u
            add("image_links", ",".join(image_urls))

    return root


def main():
    print("🚀 Supplementhub ADD-feed gestart\n")
    products = fetch_all_products()
    root = build_xml(products)
    save_xml(root, OUTPUT_FILE)
    print(f"\n💾 {len(products)} producten verwerkt")
    print("\n📋 Feed-URL voor Stock Sync (Add products):")
    print("https://raw.githubusercontent.com/Maximillian-creator/Supplementhub-Feed/main/supplementhub_add_feed.xml")


if __name__ == "__main__":
    main()
