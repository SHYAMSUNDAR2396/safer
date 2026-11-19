from pathlib import Path
from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE,MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN,MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
from PIL import Image
import json
ROOT=Path('/Users/shyamsundar/Documents/SIH 2026');OUT=ROOT/'output/canva-architecture';AS=OUT/'assets'
p=Presentation('/Users/shyamsundar/Downloads/SIH2026-IDEA-Presentation-Format-5.pptx.pptx');s=p.slides[2]
NAVY='1B3A7A';BLUE='004AAD';GREEN='4F6B2A';INK='111111';SOFTBLUE='DCEEF8';SOFTGREEN='DDE8D5';SOFTPINK='F8CECF';YELLOW='FFF6D8';BEIGE='E7DFD0';GREY='575757'
# Preserve the original slide's title, logos, footer, page number and tech panel.
keep={2,4,7,10,13,15,51,52}
for sh in list(s.shapes):
 if sh.shape_id not in keep:s.shapes._spTree.remove(sh._element)
for sh in s.shapes:
 if sh.shape_id==51:
  sh.text='TECH STACK';sh.width=Inches(3.05);sh.left=Inches(.22);sh.height=Inches(.58)
  for pp in sh.text_frame.paragraphs:
   pp.alignment=PP_ALIGN.CENTER
   for rr in pp.runs:rr.font.size=Pt(30);rr.font.bold=True;rr.font.color.rgb=RGBColor.from_string('FFFFFF');rr.font.name='Arial'

def rect(x,y,w,h,fill='FFFFFF',line=NAVY,radius=True,width=1.5):
 z=s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,Inches(x),Inches(y),Inches(w),Inches(h));z.fill.solid();z.fill.fore_color.rgb=RGBColor.from_string(fill);z.line.color.rgb=RGBColor.from_string(line);z.line.width=Pt(width)
 if radius:
  try:z.adjustments[0]=.08
  except:pass
 return z

def text(x,y,w,h,copy,size=21,color=INK,bold=False,align=PP_ALIGN.CENTER,font='Times New Roman'):
 z=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h));tf=z.text_frame;tf.word_wrap=True;tf.margin_left=tf.margin_right=Inches(.035);tf.margin_top=tf.margin_bottom=Inches(.015);tf.vertical_anchor=MSO_ANCHOR.MIDDLE
 for i,line in enumerate(copy.split('\n')):
  q=tf.paragraphs[0] if i==0 else tf.add_paragraph();q.text=line;q.alignment=align;q.space_before=Pt(0);q.space_after=Pt(0);q.line_spacing=1.0
  for r in q.runs:r.font.name=font;r.font.size=Pt(size);r.font.bold=bold;r.font.color.rgb=RGBColor.from_string(color)
 return z

def image(name,x,y,w,h):
 fp=AS/(name+'.png');iw,ih=Image.open(fp).size;k=min(w/iw,h/ih);return s.shapes.add_picture(str(fp),Inches(x+(w-iw*k)/2),Inches(y+(h-ih*k)/2),width=Inches(iw*k),height=Inches(ih*k))

def arrow(x1,y1,x2,y2,color=BLUE,dashed=False):
 z=s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT,Inches(x1),Inches(y1),Inches(x2),Inches(y2));z.line.color.rgb=RGBColor.from_string(color);z.line.width=Pt(2)
 ln=z.line._get_or_add_ln();a=OxmlElement('a:tailEnd');a.set('type','triangle');a.set('w','med');a.set('len','med');ln.append(a)
 if dashed:
  from pptx.enum.dml import MSO_LINE_DASH_STYLE
  z.line.dash_style=MSO_LINE_DASH_STYLE.DASH
 return z

# Curated stack: each label identifies the artwork and corresponds to the target design.
stack=[('react','React'),('typescript','TypeScript'),('fastapi','FastAPI'),('postgresql','PostgreSQL'),('keycloak','Keycloak'),('celery','Celery'),('docker','Docker'),('clamav','ClamAV'),('compute','OCI Compute'),('objects','Object Storage'),('vault','OCI Vault'),('actions','GitHub Actions')]
for i,(art,label) in enumerate(stack):
 col=i%2;row=i//2;x=.32+col*1.49;y=2.04+row*1.34
 image(art,x,y,1.35,.73);text(x,y+.78,1.35,.35,label,13,NAVY,True,font='Arial')

# Main cloud hosting boundary and regional heading.
rect(6.35,1.42,13.35,8.77,'FFFFFF',BLUE,True,2)
text(6.6,1.56,12.82,.43,'ORACLE CLOUD  •  MUMBAI  |  PROPOSED PRODUCTION',25,BLUE,True)
text(6.6,2.0,12.82,.35,'VCN isolation  •  Private compute  •  Managed regional services',18,GREY)

# External stakeholders and integration evidence.
rect(3.7,2.73,2.22,1.45,SOFTBLUE,BLUE)
image('users',4.45,2.86,.7,.5);text(3.8,3.38,2.02,.42,'Portal users',20,NAVY,True)
text(3.8,3.76,2.02,.36,'Institutions / AICTE',15,GREY)
rect(3.7,5.0,2.22,1.45,SOFTPINK,'C0392B')
image('bank',4.45,5.12,.7,.46);text(3.8,5.6,2.02,.34,'Bank evidence',20,'C0392B',True)
text(3.8,5.96,2.02,.42,'Manual evidence\nAPI approval pending',14,INK)
rect(3.7,7.35,2.22,1.48,YELLOW,'B68E20')
image('gemini',4.47,7.48,.65,.48);text(3.8,7.99,2.02,.32,'Optional Gemini',20,NAVY,True)
text(3.8,8.34,2.02,.43,'OFF by default\nLocal fallback remains',14,INK)

# Public entry: regional WAF is an LB policy, not a separate host.
rect(6.72,2.55,12.55,1.2,SOFTBLUE,BLUE)
image('dns',6.94,2.83,.53,.53);text(7.5,2.75,1.85,.66,'OCI DNS',21,NAVY,True)
image('waf',10.0,2.83,.53,.53);text(10.6,2.75,2.12,.66,'WAF policy',21,NAVY,True)
image('lb',13.48,2.8,.6,.6);text(14.22,2.66,4.65,.4,'OCI Load Balancer',23,NAVY,True)
text(14.22,3.13,4.65,.34,'HTTPS • healthy backend routing',17,INK)
arrow(5.94,3.22,6.65,3.22);arrow(9.35,3.15,9.87,3.15);arrow(12.72,3.15,13.32,3.15)

# Private application hosts and shared monolith workflow.
rect(6.72,4.2,12.55,2.6,'FFFFFF',NAVY)
text(6.96,4.26,12.02,.33,'PRIVATE APPLICATION SUBNET  |  TWO FAULT DOMAINS',21,NAVY,True)
for x,title,fill in [(7.0,'Compute A  •  Fault domain 1',SOFTGREEN),(13.18,'Compute B  •  Fault domain 2',BEIGE)]:
 rect(x,4.8,5.82,1.36,fill,NAVY)
 text(x+.1,4.9,5.62,.32,title,21,GREEN,True)
 image('react',x+.25,5.31,.58,.52);image('fastapi',x+1.1,5.31,.58,.52);image('keycloak',x+2.05,5.33,1.6,.45)
 text(x+3.8,5.23,1.85,.76,'Nginx + API\nOIDC / TOTP',17,INK)
text(7.0,6.32,12.0,.34,'FDR records  →  Evidence review  →  Renewal tracking  →  Authorized release',20,NAVY,True)
arrow(15.5,3.81,15.5,4.12)
arrow(5.96,5.67,6.65,5.67,'C0392B')
arrow(5.98,8.1,6.12,8.1,'B68E20',True);arrow(6.12,8.1,6.12,6.52,'B68E20',True);arrow(6.12,6.52,6.65,6.52,'B68E20',True)

# Card titles identify the data/worker row; keep arrow channels clear of headings.
# These are logical service cards; managed endpoints are private and are detailed in notes.
services=[(6.74,'postgresql','PostgreSQL HA','Records + audit\nManaged: ≥2 nodes',SOFTGREEN),(9.94,'objects','Object Storage','Encrypted FDR files\nVersions + SHA-256',SOFTBLUE),(13.14,'celery','Celery + ClamAV','Two worker hosts\nScan • extract • remind',SOFTPINK),(16.34,'cache','OCI Cache','TLS job transport\nPostgreSQL owns job state',YELLOW)]
for x,art,title,body,fill in services:
 rect(x,7.38,2.95,1.3,fill,NAVY)
 image(art,x+.11,7.51,.48,.48);text(x+.62,7.48,2.2,.36,title,19,NAVY,True)
 text(x+.12,7.97,2.71,.57,body,17,INK)
arrow(9.0,6.82,9.0,7.3);arrow(11.4,6.82,11.4,7.3);arrow(14.7,6.82,14.7,7.3);arrow(16.3,8.0,16.15,8.0)
# Security, operations and notification dependencies.
for x,art,label,w in [(6.84,'vault','Vault / KMS + Secrets',4.15),(11.17,'monitor','Logging + Monitoring',4.0),(15.47,'email','Email Delivery',3.67)]:
 image(art,x,8.98,.44,.44);text(x+.5,8.94,w-.5,.55,label,18,NAVY,True)
rect(6.74,9.66,12.55,.38,YELLOW,'B68E20')
text(6.84,9.67,12.34,.34,'HYDERABAD RECOVERY   |   DB + documents + keys   |   RPO ≤1 h / RTO ≤4 h: targets',17,NAVY,True)
text(3.7,10.28,15.9,.28,'Proposed paid target; failover, security and recovery acceptance required. Current demo uses synthetic data.',15,GREY)

s.notes_slide.notes_text_frame.text='''SAFER proposed OCI production architecture. This slide is a logical deployment overview, not a declaration of deployed infrastructure or readiness. Full design: SAFER-OCI-PRODUCTION-ARCHITECTURE.md. Mumbai primary and Hyderabad recovery are proposed pending service/tenancy/residency approval. Two app hosts in different fault domains run Nginx, FastAPI and clustered production Keycloak. Separate two worker hosts run Celery and isolated ClamAV/parser processes. Managed PostgreSQL has at least two nodes; OCI Cache has at least three non-sharded nodes subject to client compatibility. Object Storage, KMS/Secrets, telemetry and Email Delivery are regional managed dependencies with private authorization and per-endpoint routing. WAF is attached to the load balancer. Managed-service cards do not imply those control planes are VMs in the application subnet. DNS performs lookup rather than proxying HTTP. Scanner failure keeps exact document versions quarantined. Bank confirmation requires authorization and independently sourced evidence; API and Gemini remain gated. RPO/RTO are unproven acceptance targets. The free 2 OCPU/12 GB pilot cannot provide this HA topology. No real receipts or secrets appear on the slide. Original source deck's other slides are preserved. OCI service artwork: official OCI Architecture Diagram Toolkit; original technology logos from the existing attributed SAFER asset collection.'''
full=OUT/'SAFER-Technical-Approach-themed.pptx';p.save(full)
# Standalone editable diagram slide for convenient Canva import/reuse.
for i in reversed(range(len(p.slides))):
 if i!=2:
  sid=p.slides._sldIdLst[i];p.part.drop_rel(sid.rId);p.slides._sldIdLst.remove(sid)
one=OUT/'SAFER-Architecture-Canva.pptx';p.save(one)
print(json.dumps({'updated_deck':str(full),'standalone_slide':str(one),'slide_size':'20 x 11.25 in','diagram_shapes':len(s.shapes)}))
