import pymupdf as p

def damaged_page(text="AXB", hidden=True, fontname="helv"):
    raster = p.open(); image = raster.new_page(width=300, height=180)
    image.insert_text((20, 50), text, fontsize=20)
    image.insert_text((20, 120), "ADDED", fontsize=20)
    doc = p.open(); page = doc.new_page(width=300, height=180)
    page.insert_image(page.rect, pixmap=image.get_pixmap())
    font = page.insert_font(fontname=fontname)
    page.insert_text((20, 50), text, fontsize=20, fontname=fontname, render_mode=3 if hidden else 0)
    mapping = doc.get_new_xref(); doc.update_object(mapping, "<<>>")
    pairs = " ".join(f"<{i:02X}> <{0xFFFD if i==88 else i:04X}>" for i in range(32, 127))
    data = ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapType 2 def "
        "/CMapName /Damage def 1 begincodespacerange <00> <FF> endcodespacerange "
        "95 beginbfchar " + pairs + " endbfchar endcmap CMapName currentdict /CMap defineresource pop end end")
    doc.update_stream(mapping, data.encode()); doc.xref_set_key(font, "ToUnicode", f"{mapping} 0 R")
    page = doc.reload_page(page)
    return doc, page
