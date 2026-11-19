import json,zlib,base64,urllib.parse,re,xml.etree.ElementTree as E
from pathlib import Path
import zipfile
out=Path(__file__).resolve().parent.parent/'real-logo-assets';z=zipfile.ZipFile(out/'oci-toolkit.zip')
items=json.loads(E.fromstring(z.read('OCI Style Guide for Drawio/OCI Library.xml')).text)
choose={3:'compute',11:'object-storage',17:'vcn',19:'load-balancer',20:'dns',31:'service-gateway',32:'internet-gateway',33:'nat',75:'registry',82:'notifications',83:'email',102:'waf',103:'certificates',105:'vault',106:'bastion',107:'iam',117:'logging',119:'audit',120:'monitoring'}
for index,name in choose.items():
 raw=urllib.parse.unquote(zlib.decompress(base64.b64decode(items[index]['xml']),-15).decode());root=E.fromstring(raw);cells={c.get('id'):c for c in root.iter('mxCell')}
 def pos(c):
  g=c.find('mxGeometry');p=cells.get(c.get('parent'));px,py=pos(p) if p is not None else (0,0)
  return px+(float(g.get('x',0)) if g is not None else 0),py+(float(g.get('y',0)) if g is not None else 0)
 paths=[]
 for c in cells.values():
  style=c.get('style','');m=re.search(r'stencil\(([^)]+)\)',style)
  if not m:continue
  st=dict(v.split('=',1) for v in style.split(';') if '=' in v);g=c.find('mxGeometry');x,y=pos(c)
  if y>=84:continue
  d=E.fromstring(urllib.parse.unquote(zlib.decompress(base64.b64decode(m[1]),-15).decode()))
  for p in d.iter('path'):
   seg=[]
   for n in p:
    a=n.attrib
    if n.tag in ['move','line']:seg.append(('M' if n.tag=='move' else 'L')+a['x']+','+a['y'])
    elif n.tag=='curve':seg.append('C'+' '.join(a[k] for k in ['x1','y1','x2','y2','x3','y3']))
    else:raise ValueError(n.tag)
   paths.append(f'<path d="{" ".join(seg)}" fill="{st.get("fillColor","#000000")}" transform="translate({x} {y}) scale({float(g.get("width"))/100} {float(g.get("height"))/100})"/>')
 (out/f'oci-{name}.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="84" height="84" viewBox="0 0 84 84">'+''.join(paths)+'</svg>')
print('Extracted',len(choose),'official OCI service symbols')
