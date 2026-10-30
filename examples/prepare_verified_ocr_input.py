"""Apply explicitly configured, previously verified PDF input repairs.

This is input configuration, not an OCR selector or a rule inferred from GT.
Only matching PDF and Form-stream signatures are accepted. Work is in memory;
source files are never written. Arbitrary empty Form bounds are not expanded.
"""
from pathlib import Path
import hashlib,json,math

def sha256(data):return hashlib.sha256(data).hexdigest()

def prepare_document(document,source_digest,rules):
 plans=[]
 for rule in rules:
  if rule['source_sha256']!=source_digest:continue
  index=rule['page_index'];xref=rule['xref'];page=document[index]
  if document.xref_get_key(xref,'Subtype')!=('name','/Form'):
   raise ValueError('Configured repair no longer identifies a Form')
  if sha256(document.xref_stream(xref))!=rule['Form_stream_sha256']:
   raise ValueError('Configured Form content does not match its verified signature')
  if (xref,rule['resource'],0)not in[q[:3]for q in page.get_xobjects()]:
   raise ValueError('Configured Form resource is not present on the expected page')
  kind,value=document.xref_get_key(xref,'BBox')
  try:before=[float(x)for x in value.strip('[]').split()]
  except ValueError:raise ValueError('Configured Form BBox is not numeric')from None
  if kind!='array'or before!=rule['before']or document.xref_get_key(xref,'Matrix')[0]!='null':
   raise ValueError('Configured Form geometry does not match the reviewed input')
  after=rule['after']
  if len(after)!=4 or not all(math.isfinite(x)for x in after)or after[2]<=after[0]or after[3]<=after[1]:
   raise ValueError('Configured replacement BBox is invalid')
  plans.append((xref,after,rule))
 for xref,after,rule in plans:
  document.xref_set_key(xref,'BBox','['+' '.join(map(str,after))+']')
 return [rule for _,_,rule in plans]


def main():
    import argparse
    import pymupdf
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--rules", required=True, type=Path)
    args = parser.parse_args()
    if args.source.resolve() == args.output.resolve() or args.output.exists():
        parser.error("Output must be a new file distinct from the source")
    data = args.source.read_bytes()
    rules = json.loads(args.rules.read_text())["repairs"]
    with pymupdf.open(stream=data, filetype="pdf") as document:
        applied = prepare_document(document, sha256(data), rules)
        document.save(args.output)
    print(f"Applied {len(applied)} explicitly verified input repair(s)")

if __name__ == "__main__":
    main()
