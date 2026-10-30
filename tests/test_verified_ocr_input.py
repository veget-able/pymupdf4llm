"""Form bounds are corrected only with explicitly reviewed signatures."""
import hashlib
import importlib.util
from pathlib import Path
import pytest
import pymupdf as p

spec=importlib.util.spec_from_file_location("prepare_input", Path(__file__).parents[1]/"examples/prepare_verified_ocr_input.py")
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def fixture():
    with p.open() as source:
        page=source.new_page(width=200,height=100)
        page.insert_text((20,40),"FORM TEXT")
        doc=p.open();page=doc.new_page(width=200,height=100)
        page.show_pdf_page(page.rect,source,0)
    xref, name, _ = page.get_xobjects()[0][:3]
    doc.xref_set_key(xref,"BBox","[0 0 0 0]")
    doc.xref_set_key(xref,"Matrix","null")
    data=doc.tobytes(); doc.close();doc=p.open(stream=data,filetype="pdf")
    digest=hashlib.sha256(data).hexdigest()
    rule=dict(source_sha256=digest,page_index=0,xref=xref,resource=name,
              Form_stream_sha256=hashlib.sha256(doc.xref_stream(xref)).hexdigest(),
              before=[0,0,0,0],after=[0,0,200,100])
    return doc,data,rule

def test_explicit_repair_restores_render_without_changing_source():
    doc,data,rule=fixture()
    with doc:
        assert not doc[0].get_text().strip()
        assert module.prepare_document(doc,rule["source_sha256"],[rule])==[rule]
        assert "FORM TEXT" in doc.reload_page(doc[0]).get_text()
    with p.open(stream=data,filetype="pdf") as original:
        assert original.xref_get_key(rule["xref"],"BBox")[1].replace(" ","")=="[0000]"

def test_unknown_or_mismatched_input_is_not_repaired():
    doc,data,rule=fixture()
    with doc:
        before=doc.xref_object(rule["xref"])
        assert module.prepare_document(doc,"other",[rule])==[]
        bad=dict(rule,Form_stream_sha256="bad")
        with pytest.raises(ValueError,match="signature"):
            module.prepare_document(doc,rule["source_sha256"],[bad])
        assert doc.xref_object(rule["xref"])==before
