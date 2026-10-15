from pathlib import Path
import json,sys,xml.etree.ElementTree as ET
root=Path(sys.argv[1]);rows=[]
for module in sorted(p for p in root.iterdir() if p.is_dir()):
 suites=[]
 for f in sorted(module.glob('TEST-*.xml')):
  r=ET.parse(f).getroot();suite={k:int(r.get(k,0)) for k in ['tests','failures','errors','skipped']};suite['suite']=r.get('name');suite['skips']=[dict(name=t.get('name'),reason=t.find('skipped').get('message')) for t in r.findall('testcase') if t.find('skipped') is not None];suites.append(suite)
 if suites:
  row={'module':module.name,**{k:sum(s[k] for s in suites) for k in ['tests','failures','errors','skipped']},'suites':suites};rows.append(row)
(root/'test-counts.json').write_text(json.dumps(rows,indent=2)+'\n')
for r in rows:print({k:v for k,v in r.items() if k!='suites'})
