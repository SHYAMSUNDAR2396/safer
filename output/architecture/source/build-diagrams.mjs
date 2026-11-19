import fs from 'node:fs/promises';
import path from 'node:path';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';

const ROOT='/Users/shyamsundar/Documents/SIH 2026';
const OUT=path.join(ROOT,'output/architecture');
const app=createRequire(path.join(ROOT,'safer/apps/web/package.json'));
const runtime=createRequire('/Users/shyamsundar/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/package.json');
const React=app('react'), {renderToStaticMarkup}=app('react-dom/server'), icons=app('lucide-react'), sharp=runtime('sharp');
const C={ink:'#123047',muted:'#526779',blue:'#2363ad',blueBg:'#edf5ff',teal:'#0d786c',tealBg:'#eaf7f3',amber:'#a3650a',amberBg:'#fff6df',purple:'#7544a6',purpleBg:'#f4edfc',grey:'#6b7886',greyBg:'#f1f4f7',line:'#bdcbd5',red:'#b33b42'};
const updated=1792972800000;
const xml=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const assets=new Map();
async function icon(name,color=C.blue){
  const key=name+color;
  if(!assets.has(key)){
    const svg=renderToStaticMarkup(React.createElement(icons[name],{size:64,color,strokeWidth:1.65}));
    assets.set(key,{mime:'image/svg+xml',buffer:Buffer.from(svg)});
  }
  return assets.get(key);
}
async function logo(name){
  const p=path.join(ROOT,'output/SAFER-tech-stack-logos/01-main-stack',name);
  if(!assets.has(p))assets.set(p,{mime:name.endsWith('.svg')?'image/svg+xml':'image/png',buffer:await fs.readFile(p)});
  return assets.get(p);
}
async function cropCapture(name,region){
  return {mime:'image/png',buffer:await sharp(path.join(ROOT,'safer/apps/web/test-results',name)).extract(region).png().toBuffer()};
}

class Scene{
  constructor(name,w,h){this.name=name;this.w=w;this.h=h;this.elements=[];this.files={};this.n=0;}
  base(type,x,y,w,h,opts={}){
    const id=this.name+'-'+String(++this.n).padStart(4,'0');
    const e={id,type,x,y,width:w,height:h,angle:0,strokeColor:C.ink,backgroundColor:'transparent',fillStyle:'solid',strokeWidth:2,strokeStyle:'solid',roughness:0,opacity:100,groupIds:[],frameId:null,roundness:null,seed:this.n*6413,version:1,versionNonce:this.n*9091,isDeleted:false,boundElements:null,updated,link:null,locked:false,...opts};
    this.elements.push(e);return e;
  }
  rect(x,y,w,h,opts={}){return this.base('rectangle',x,y,w,h,{roundness:{type:3},...opts});}
  text(x,y,value,size=22,color=C.ink,width=500,opts={}){
    const lines=String(value).split('\n');
    return this.base('text',x,y,width,lines.length*size*1.25,{strokeColor:color,strokeWidth:1,text:String(value),originalText:String(value),fontSize:size,fontFamily:2,textAlign:'left',verticalAlign:'top',containerId:null,autoResize:false,lineHeight:1.25,...opts});
  }
  badge(x,y,label,color=C.teal,bg=C.tealBg,width=230){
    const group=this.name+'-badge-'+this.n;
    this.rect(x,y,width,31,{strokeColor:color,backgroundColor:bg,strokeWidth:1,groupIds:[group]});
    this.text(x+10,y+5,label,16,color,width-20,{groupIds:[group]});
  }
  image(asset,x,y,w,h,groupIds=[]){
    const id=crypto.createHash('sha256').update(asset.buffer).digest('hex');
    this.files[id]={id,mimeType:asset.mime,dataURL:`data:${asset.mime};base64,${asset.buffer.toString('base64')}`,created:updated,lastRetrieved:updated};
    return this.base('image',x,y,w,h,{strokeColor:'transparent',fileId:id,status:'saved',scale:[1,1],crop:null,groupIds});
  }
  async card(x,y,w,h,title,tech,body,{color=C.blue,bg=C.blueBg,iconName='Server',brand=null,badge=null,badgeWidth=210,dashed=false}={}){
    const group=this.name+'-node-'+this.n;
    const e=this.rect(x,y,w,h,{strokeColor:color,backgroundColor:bg,strokeStyle:dashed?'dashed':'solid',groupIds:[group]});
    const a=brand?await logo(brand):await icon(iconName,color);
    this.image(a,x+18,y+19,46,46,[group]);
    this.text(x+80,y+18,title,25,color,w-96,{groupIds:[group]});
    this.text(x+80,y+52,tech,18,C.muted,w-96,{groupIds:[group]});
    if(body)this.text(x+22,y+89,body,21,C.ink,w-44,{groupIds:[group]});
    if(badge)this.badge(x+w-badgeWidth-16,y+h-42,badge,color,bg,badgeWidth);
    return e;
  }
  arrow(points,label='',{color=C.blue,dashed=false,labelX=null,labelY=null,font=17,labelWidth=320,start=null,end=null,head=true}={}){
    const [x,y]=points[0], rel=points.map(([a,b])=>[a-x,b-y]);
    const e=this.base(head?'arrow':'line',x,y,Math.max(...rel.map(p=>p[0]))-Math.min(...rel.map(p=>p[0])),Math.max(...rel.map(p=>p[1]))-Math.min(...rel.map(p=>p[1])),{strokeColor:color,strokeWidth:2.2,strokeStyle:dashed?'dashed':'solid',points:rel,lastCommittedPoint:null,startBinding:start?{elementId:start.id,focus:0,gap:8}:null,endBinding:end?{elementId:end.id,focus:0,gap:8}:null,startArrowhead:null,endArrowhead:head?'arrow':null,elbowed:false});
    for(const node of [start,end])if(node){node.boundElements??=[];node.boundElements.push({type:'arrow',id:e.id});}
    if(label){
      const lx=labelX??(points[0][0]+points.at(-1)[0])/2-80,ly=labelY??(points[0][1]+points.at(-1)[1])/2-30;
      const tw=Math.min(labelWidth,label.length*font*.55+18);
      this.rect(lx-6,ly-2,tw,label.split('\n').length*font*1.25+6,{strokeColor:'transparent',backgroundColor:'#ffffff',strokeWidth:0,opacity:96});
      this.text(lx,ly,label,font,color,labelWidth);
    }
    return e;
  }
  header(title,subtitle){
    this.text(44,26,title,42,C.ink,this.w-88);
    this.text(46,84,subtitle,21,C.muted,this.w-92);
    this.arrow([[44,125],[this.w-44,125]],'',{color:C.line,head:false});
  }
  footer(note){
    this.arrow([[44,this.h-70],[this.w-44,this.h-70]],'',{color:C.line,head:false});
    this.text(46,this.h-53,note,17,C.muted,this.w-92);
  }
  json(){return {type:'excalidraw',version:2,source:'https://excalidraw.com',elements:this.elements,appState:{viewBackgroundColor:'#ffffff',gridSize:null,zoom:{value:.7},scrollX:20,scrollY:20,exportBackground:true},files:this.files};}
  svg(){
    const output=[];
    for(const e of this.elements){
      if(e.type==='rectangle')output.push(`<rect x="${e.x}" y="${e.y}" width="${e.width}" height="${e.height}" rx="12" fill="${e.backgroundColor==='transparent'?'none':e.backgroundColor}" stroke="${e.strokeColor}" stroke-width="${e.strokeWidth}" ${e.strokeStyle==='dashed'?'stroke-dasharray="9 7"':''} opacity="${e.opacity/100}"/>`);
      else if(e.type==='text'){
        const anchor=e.textAlign==='center'?'middle':e.textAlign==='right'?'end':'start';
        const x=e.x+(anchor==='middle'?e.width/2:anchor==='end'?e.width:0);
        const lines=e.text.split('\n').map((l,i)=>`<tspan x="${x}" y="${e.y+e.fontSize*.95+i*e.fontSize*1.25}">${xml(l)}</tspan>`).join('');
        output.push(`<text font-family="Arial,Helvetica,sans-serif" font-size="${e.fontSize}" font-weight="${e.fontSize>=25?600:400}" fill="${e.strokeColor}" text-anchor="${anchor}">${lines}</text>`);
      }else if(e.type==='image')output.push(`<image x="${e.x}" y="${e.y}" width="${e.width}" height="${e.height}" href="${this.files[e.fileId].dataURL}"/>`);
      else if(['line','arrow'].includes(e.type)){
        const pts=e.points.map(([x,y])=>[x+e.x,y+e.y]);
        output.push(`<polyline points="${pts.map(p=>p.join(',')).join(' ')}" fill="none" stroke="${e.strokeColor}" stroke-width="${e.strokeWidth}" stroke-linejoin="round" stroke-linecap="round" ${e.strokeStyle==='dashed'?'stroke-dasharray="8 7"':''}/>`);
        if(e.type==='arrow'&&e.endArrowhead){
          const b=pts.at(-1),a=pts.at(-2),angle=Math.atan2(b[1]-a[1],b[0]-a[0]),d=11,spread=.47;
          const left=[b[0]-d*Math.cos(angle-spread),b[1]-d*Math.sin(angle-spread)],right=[b[0]-d*Math.cos(angle+spread),b[1]-d*Math.sin(angle+spread)];
          output.push(`<polyline points="${[left,b,right].map(p=>p.join(',')).join(' ')}" fill="none" stroke="${e.strokeColor}" stroke-width="${e.strokeWidth}" stroke-linecap="round"/>`);
        }
      }
    }
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${this.w}" height="${this.h}" viewBox="0 0 ${this.w} ${this.h}"><rect width="100%" height="100%" fill="white"/>${output.join('')}</svg>`;
  }
  async save(){
    const base=path.join(OUT,'SAFER-v2-'+this.name);
    await fs.writeFile(base+'.excalidraw',JSON.stringify(this.json(),null,2));
    const svg=this.svg();await fs.writeFile(base+'.svg',svg);
    await sharp(Buffer.from(svg),{density:144}).png().toFile(base+'.png');
    return this;
  }
}

async function overview(){
  const s=new Scene('overview',2160,1410);
  s.header('SAFER | System architecture','C4-inspired application view + lifecycle guide • current local/readiness capabilities • synthetic demonstration');
  s.rect(860,150,810,800,{strokeColor:C.line,backgroundColor:'#fafcfe',strokeStyle:'dashed'});
  s.text(883,160,'CORE APPLICATION + PERSISTENCE',17,C.muted,750);
  const users=await s.card(48,218,280,175,'People','Institution + AICTE','Officer • reviewer\nApprover • admin\nAuditor',{iconName:'Users'});
  const portal=await s.card(400,218,400,175,'Web portal','React + TypeScript / Vite','Submit • review • track\nOpaque session + CSRF',{brand:'react.svg'});
  const identity=await s.card(400,470,400,150,'Identity','Keycloak + Authlib','OIDC / PKCE • privileged TOTP',{brand:'keycloak.svg'});
  const api=await s.card(900,218,700,402,'FastAPI modular monolith','Pydantic validation + scoped authorization','',{brand:'fastapi.svg'});
  const modules=[['Intake + documents','Validation • quarantine • submission'],['Evidence + discrepancies','Claims remain separate from evidence'],['Deadlines + replacement','Monitor • remind • accept renewals'],['Governed release','Clearances • decision • reconciliation']];
  modules.forEach(([title,detail],i)=>{
    const y=326+i*65;
    s.rect(923,y,654,56,{strokeColor:'#c5d9ed',backgroundColor:'#ffffff',strokeWidth:1});
    s.text(939,y+5,title,21,C.blue,620);s.text(939,y+31,detail,17,C.muted,620);
  });
  const model=await s.card(1760,218,348,205,'Optional AI wording','Gemini API adapter','Approved synthetic facts only\nSource + access recheck\nLocal fallback on failure',{iconName:'Bot',color:C.purple,bg:C.purpleBg});
  s.badge(1790,444,'OFF BY DEFAULT',C.purple,C.purpleBg,270);
  const pg=await s.card(900,770,330,164,'Case records','PostgreSQL + SQLAlchemy','Grants • claims • evidence\nAudit • jobs • AI usage',{brand:'postgresql.svg',color:C.teal,bg:C.tealBg});
  const obj=await s.card(1290,770,330,164,'Private documents','SeaweedFS / S3-compatible','Exact versions + SHA-256\nEncrypted in readiness',{brand:'seaweedfs.png',color:C.teal,bg:C.tealBg});
  const keys=await s.card(1760,770,348,164,'Key wrapping','OpenBao Transit','Random data keys / AES-GCM\nSeparate private runtime token',{iconName:'KeyRound',color:C.teal,bg:C.tealBg});
  const relay=await s.card(48,1090,280,150,'Outbox relay','Python / job scheduler','Publish committed jobs\nReclaim stalled work',{iconName:'Repeat2',color:C.amber,bg:C.amberBg});
  const queue=await s.card(420,1090,360,150,'Job transport','Valkey','Delivers job IDs only\nPostgreSQL owns job state',{iconName:'Workflow',color:C.amber,bg:C.amberBg});
  const worker=await s.card(900,1090,330,150,'Background worker','Celery / Python','Claim jobs • read versions\nPersist outcomes + audit',{brand:'python.svg',color:C.amber,bg:C.amberBg});
  const scan=await s.card(1290,1090,330,150,'Malware inspection','Isolated ClamAV','Bytes only • no DB/key secrets\nClean scan ≠ authenticity',{brand:'clamav.png',color:C.amber,bg:C.amberBg});
  const mail=await s.card(1760,1090,348,150,'Local notifications','Mailpit capture','Reminder and escalation jobs\nNo external email delivery',{iconName:'Mail',color:C.amber,bg:C.amberBg});
  s.rect(48,710,730,264,{strokeColor:C.line,backgroundColor:'#ffffff'});
  s.text(72,731,'LIFECYCLE GUIDE · modules inside the API',23,C.ink,680);
  s.text(72,778,'1 Capture → 2 Quarantine / scan → 3 Freeze submission',23,C.blue,680);
  s.text(72,824,'4 Compare recorded evidence → human scrutiny',23,C.blue,680);
  s.text(72,873,'5a Monitor / renew   OR   5b Authorized release process',21,C.teal,680);
  s.text(72,921,'Extraction proposes values; recorded bank evidence is separate.',18,C.muted,680);
  s.arrow([[328,302],[400,302]],'Use portal',{labelX:331,labelY:266,font:15,labelWidth:90,start:users,end:portal});
  s.arrow([[800,302],[900,302]],'JSON API',{labelX:805,labelY:268,font:15,labelWidth:90,start:portal,end:api});
  s.arrow([[600,393],[600,470]],'Login / TOTP',{labelX:622,labelY:415,labelWidth:160,start:portal,end:identity});
  s.arrow([[900,544],[800,544]],'OIDC / JWKS',{labelX:800,labelY:510,font:15,labelWidth:110,start:api,end:identity});
  s.arrow([[1040,620],[1040,770]],'Transactions + audit',{labelX:1060,labelY:688,labelWidth:210,start:api,end:pg});
  s.arrow([[1450,620],[1450,770]],'Versioned object API',{labelX:1466,labelY:688,labelWidth:230,start:api,end:obj});
  s.arrow([[1600,310],[1760,310]],'Gated HTTPS',{color:C.purple,dashed:true,labelX:1607,labelY:274,font:16,labelWidth:150,start:api,end:model});
  s.arrow([[1550,620],[1695,620],[1695,850],[1760,850]],'App-side wrap / unwrap',{color:C.teal,labelX:1709,labelY:649,font:16,labelWidth:220,start:api,end:keys});
  s.arrow([[960,934],[960,1010],[188,1010],[188,1090]],'Committed outbox rows',{color:C.amber,labelX:430,labelY:982,labelWidth:280,start:pg,end:relay});
  s.arrow([[328,1165],[420,1165]],'Publish',{color:C.amber,labelX:335,labelY:1133,font:15,labelWidth:80,start:relay,end:queue});
  s.arrow([[780,1165],[900,1165]],'Job IDs',{color:C.amber,labelX:793,labelY:1133,font:15,labelWidth:95,start:queue,end:worker});
  s.arrow([[1080,1090],[1080,934]],'Claim / save results',{color:C.amber,labelX:1098,labelY:980,font:16,labelWidth:200,start:worker,end:pg});
  s.arrow([[1190,1090],[1190,986],[1450,986],[1450,934]],'Exact object version',{color:C.teal,labelX:1260,labelY:956,font:16,labelWidth:230,start:worker,end:obj});
  s.arrow([[1230,1165],[1290,1165]],'Bytes',{color:C.amber,labelX:1232,labelY:1133,font:14,labelWidth:60,start:worker,end:scan});
  s.arrow([[1130,1240],[1130,1291],[1934,1291],[1934,1240]],'Notification jobs → local SMTP capture',{color:C.amber,labelX:1335,labelY:1262,labelWidth:500,start:worker,end:mail});
  s.footer('Solid: implemented capability/dependency   ·   Purple dashed: optional AI, disabled   ·   Real bank connectivity pending; simulator is labelled   ·   Oracle deployment is a separate proposal');
  return s.save();
}

async function slide(){
  const s=new Scene('slide-fit',1700,1050);
  s.header('SAFER | Technical architecture','L-shaped presentation view • technologies + lifecycle • actual synthetic prototype captures');
  const users=await s.card(40,150,540,94,'Institutions + AICTE','Officer • reviewer • competent approver / admin','',{iconName:'Users'});
  const portal=await s.card(40,290,540,108,'Secure web portal','React + TypeScript • Keycloak / Authlib','',{brand:'react.svg'});
  s.text(63,370,'OIDC / PKCE • privileged TOTP • session + CSRF',17,C.muted,500);
  const api=await s.card(40,450,540,300,'Case and lifecycle engine','FastAPI + Pydantic • scoped grants','',{brand:'fastapi.svg'});
  s.text(64,547,'1  Validate metadata + institution scope',21,C.ink,494);
  s.text(64,585,'2  Quarantine / scan → freeze submission',21,C.ink,494);
  s.text(64,623,'3  Compare claims with recorded evidence',21,C.ink,494);
  s.text(64,661,'4  Human scrutiny + complete audit history',21,C.ink,494);
  s.text(64,706,'Monitor / renew  OR  authorized release workflow',18,C.teal,500);
  s.arrow([[310,244],[310,290]],'Role-scoped access',{labelX:333,labelY:255,font:16,labelWidth:240,start:users,end:portal});
  s.arrow([[310,398],[310,450]],'Same-origin JSON API',{labelX:333,labelY:410,font:16,labelWidth:240,start:portal,end:api});
  s.text(680,152,'PROTOTYPE · Evidence comparison',23,C.ink,460);
  s.text(1170,152,'PROTOTYPE · Deadlines + renewal',23,C.ink,480);
  const cap1=await cropCapture('review-case.png',{left:285,top:590,width:970,height:850});
  const cap2=await cropCapture('review-case.png',{left:285,top:1560,width:970,height:770});
  s.rect(678,190,456,410,{strokeColor:C.line,backgroundColor:'#f6f9fa'});
  s.rect(1168,190,456,410,{strokeColor:C.line,backgroundColor:'#f6f9fa'});
  s.image(cap1,686,199,440,386);
  s.image(cap2,1176,208,440,349);
  s.text(1184,566,'Cropped prototype capture · synthetic data',16,C.muted,420);
  s.badge(680,636,'Claims ≠ confirmation',C.teal,C.tealBg,290);
  s.badge(1000,636,'Clean scan ≠ authenticity',C.amber,C.amberBg,310);
  s.badge(1340,636,'AI ≠ approval',C.purple,C.purpleBg,280);
  const data=await s.card(40,840,540,125,'Records + private documents','PostgreSQL • SeaweedFS • OpenBao Transit','',{brand:'postgresql.svg',color:C.teal,bg:C.tealBg});
  s.text(64,931,'Versions / hashes • audit • readiness encryption',18,C.teal,492);
  const jobs=await s.card(640,840,480,125,'Asynchronous processing','Outbox → Valkey → Celery','',{iconName:'Workflow',color:C.amber,bg:C.amberBg});
  s.text(664,931,'Isolated ClamAV • local Mailpit capture',18,C.amber,435);
  const ai=await s.card(1170,840,450,125,'Optional advisory AI','Gemini adapter • OFF BY DEFAULT','',{iconName:'Bot',color:C.purple,bg:C.purpleBg});
  s.text(1194,931,'Approved synthetic facts • local fallback',18,C.purple,405);
  s.arrow([[310,750],[310,840]],'Records + versions',{color:C.teal,labelX:333,labelY:790,font:17,labelWidth:230,start:api,end:data});
  s.arrow([[580,700],[610,700],[610,799],[880,799],[880,840]],'Committed job IDs',{color:C.amber,labelX:684,labelY:768,font:17,labelWidth:235,start:api,end:jobs});
  s.arrow([[580,665],[625,665],[625,742],[1395,742],[1395,840]],'Explicit reviewer action + processing approval gates',{color:C.purple,dashed:true,labelX:890,labelY:708,font:17,labelWidth:650,start:api,end:ai});
  s.footer('Implemented local/readiness architecture • bank exchange is simulated • text extraction proposes values; OCR is not configured • Oracle deployment remains proposed');
  return s.save();
}

async function security(){
  const s=new Scene('security-data-flow',2040,1370);
  s.header('SAFER | Security and data flow','Level-1 DFD-style view • separate claims, evidence and advisory wording • trust boundaries are labelled');
  s.rect(400,180,1040,1010,{strokeColor:C.teal,backgroundColor:'#fcfefd',strokeStyle:'dashed'});
  s.text(422,192,'TB1 · TRUSTED APPLICATION / PRIVATE DATA',18,C.teal,950);
  s.rect(1510,180,475,360,{strokeColor:C.purple,backgroundColor:C.purpleBg,strokeStyle:'dashed'});
  s.text(1530,196,'TB2 · EXTERNAL MODEL PROCESSOR',18,C.purple,430);
  s.rect(1510,770,475,266,{strokeColor:C.amber,backgroundColor:C.amberBg,strokeStyle:'dashed'});
  s.text(1530,786,'TB3 · ISOLATED SCANNING NETWORK',18,C.amber,430);
  const institution=await s.card(40,250,300,148,'Institution officer','Untrusted upload / claims','Own institution only',{iconName:'UserRound'});
  const official=await s.card(40,480,300,148,'AICTE official','Reviewer / approver','Scoped grants / TOTP MFA',{iconName:'UserCheck'});
  const intake=await s.card(450,250,380,170,'P1 · Intake + submit','Validate / quarantine / freeze','Claims stay unverified\nExact document versions',{iconName:'FileInput',color:C.teal,bg:C.tealBg});
  const review=await s.card(960,250,380,170,'P2 · Review + authorize','Compare rules / scoped decisions','Human clearances and approval\nNo AI-authoritative writes',{iconName:'ClipboardCheck',color:C.teal,bg:C.tealBg});
  const inspect=await s.card(960,585,380,160,'P3 · Inspect documents','Trusted worker + limited parser','Scan exact bytes / record result\nExtraction remains a proposal',{iconName:'FileSearch',color:C.amber,bg:C.amberBg});
  const pg=await s.card(450,950,380,170,'D1 · Case + audit store','PostgreSQL','Claims / independent evidence\nGrants / decisions / job ledger',{brand:'postgresql.svg',color:C.teal,bg:C.tealBg});
  const obj=await s.card(960,950,380,170,'D2 · Private documents','Versioned object storage','Frozen hashes / clean-only access\nReadiness: encrypted envelopes',{iconName:'FolderLock',color:C.teal,bg:C.tealBg});
  const model=await s.card(1540,250,410,185,'Gemini advisory wording','No tools or financial authority','Only exact approved synthetic basis\nNo raw PDFs / free-text notes\nNo promise of India-only processing',{iconName:'Bot',color:C.purple,bg:C.purpleBg});
  s.badge(1574,476,'OFF BY DEFAULT',C.purple,C.purpleBg,320);
  const scan=await s.card(1540,838,410,160,'ClamAV','Bytes in / scan verdict out','No database, object or key secrets\nClean scan ≠ authenticity',{brand:'clamav.png',color:C.amber,bg:C.amberBg});
  const keys=await s.card(1540,1110,410,140,'TB4 · Key service','OpenBao / separate credentials','App wraps data keys; store has none',{iconName:'KeyRound',color:C.teal,bg:C.tealBg,dashed:true});
  s.rect(450,555,380,275,{strokeColor:C.line,backgroundColor:C.greyBg});
  s.text(470,575,'EVIDENCE AND AUTHORITY',21,C.ink,340);
  s.text(470,620,'Submitted claim ≠ confirmation\nText extraction ≠ bank evidence\nSimulator ≠ independent evidence\nLLM prose ≠ release approval',19,C.ink,340);
  s.text(470,740,'Controls: session / CSRF / grants\nVersion + hash / source digest\nPost-generation access recheck',17,C.muted,340);
  s.arrow([[340,324],[450,324]],'Claims + files',{labelX:342,labelY:288,font:15,labelWidth:110,start:institution,end:intake});
  s.arrow([[340,554],[376,554],[376,225],[1150,225],[1150,250]],'Scope-checked case review',{labelX:710,labelY:225,font:16,labelWidth:270,start:official,end:review});
  s.arrow([[450,375],[420,375],[420,1035],[450,1035]],'Validated metadata + frozen references',{color:C.teal,labelX:450,labelY:863,font:17,labelWidth:390,start:intake,end:pg});
  s.arrow([[830,335],[880,335],[880,1160],[1150,1160],[1150,1120]],'Quarantined, private versions',{color:C.teal,labelX:901,labelY:1132,font:16,labelWidth:320,start:intake,end:obj});
  s.arrow([[1150,420],[1150,475],[850,475],[850,1035],[830,1035]],'Scoped evidence / decisions / audit',{color:C.teal,labelX:876,labelY:503,font:17,labelWidth:420,start:review,end:pg});
  s.arrow([[1150,745],[1150,950]],'Exact version / recorded scan status',{color:C.teal,labelX:1174,labelY:862,font:16,labelWidth:350,start:inspect,end:obj});
  s.arrow([[1340,665],[1466,665],[1466,918],[1540,918]],'Scan bytes only',{color:C.amber,labelX:1400,labelY:693,font:16,labelWidth:180,start:inspect,end:scan});
  s.arrow([[1340,303],[1540,303]],'Minimized synthetic facts',{color:C.purple,dashed:true,labelX:1345,labelY:269,font:14,labelWidth:210,start:review,end:model});
  s.arrow([[1540,373],[1340,373]],'Untrusted advisory JSON',{color:C.purple,dashed:true,labelX:1344,labelY:340,font:14,labelWidth:210,start:model,end:review});
  s.arrow([[1340,706],[1420,706],[1420,1180],[1540,1180]],'App-side wrap / unwrap',{color:C.teal,labelX:1444,labelY:1063,font:16,labelWidth:250,start:inspect,end:keys});
  s.text(48,734,'Identity check on every request:\nKeycloak OIDC / PKCE + TOTP\nLocal role and institution grants\nNo browser-to-store/model access',18,C.muted,310);
  s.text(48,890,'Parser limitation:\nResource/time limits exist; the\nformat-check process still shares\nthe application UID/filesystem.',18,C.muted,310);
  s.footer('Dashed TB borders = trust boundaries • purple dashed edges = optional external AI • source approval is an operator gate, not automatic proof that data is synthetic');
  return s.save();
}

async function deployment(){
  const s=new Scene('oci-proposed-deployment',2160,1450);
  s.header('SAFER | Proposed Oracle private demo','Deployment view • NOT DEPLOYED • account, region, capacity and deployment approval remain open');
  s.rect(460,250,1640,890,{strokeColor:C.grey,backgroundColor:'#f7f9fc',strokeStyle:'dashed'});
  s.text(484,268,'OCI · INDIAN HOME REGION — confirmation required',23,C.grey,1510);
  s.rect(500,325,1560,770,{strokeColor:C.blue,backgroundColor:'#ffffff'});
  s.text(525,342,'ONE A1 VM · proposed 2 OCPUs / 12 GB RAM · Docker Compose · one failure domain',23,C.blue,1490);
  const operator=await s.card(42,418,340,184,'Team / operator','Browser + workstation','Restricted SSH tunnel\nLoopback app + identity origins\nNo public application ports',{iconName:'Laptop'});
  const web=await s.card(550,418,360,150,'Private front door','Nginx + built React assets','TLS at the local browser endpoint',{iconName:'PanelsTopLeft'});
  const api=await s.card(1010,418,400,180,'API application','FastAPI · one process','Scoped sessions / CSRF / grants\nExisting modular monolith',{brand:'fastapi.svg'});
  const identity=await s.card(1510,418,450,150,'Identity','Keycloak + TOTP','Stage A: private start-dev only',{brand:'keycloak.svg'});
  s.rect(1510,600,450,68,{strokeColor:C.line,backgroundColor:C.greyBg});
  s.text(1528,614,'Separate identity volume · Stage A local DB',18,C.muted,420);
  const pg=await s.card(550,735,360,145,'App database','PostgreSQL','Case / audit / outbox / usage',{brand:'postgresql.svg',color:C.teal,bg:C.tealBg});
  const objects=await s.card(1010,735,400,145,'Private document store','SeaweedFS / exact versions','Encrypted envelopes + hashes',{brand:'seaweedfs.png',color:C.teal,bg:C.tealBg});
  const keys=await s.card(1510,735,450,145,'Key service','OpenBao Transit','Runtime token only on VM\nNo root / unseal recovery material',{iconName:'KeyRound',color:C.teal,bg:C.tealBg});
  const jobs=await s.card(550,950,700,125,'Background processing','Outbox relay → Valkey → Celery (one slot)','',{iconName:'Workflow',color:C.amber,bg:C.amberBg});
  s.text(576,1041,'Local Mailpit capture • bounded pools and worker concurrency',17,C.amber,640);
  const scan=await s.card(1350,950,610,125,'Isolated scanning network','ClamAV + separate signature updater','',{brand:'clamav.png',color:C.amber,bg:C.amberBg});
  s.text(1376,1041,'No DB / document-store / key-service credentials',17,C.amber,554);
  const model=await s.card(42,785,340,185,'External Gemini API','Optional, OFF BY DEFAULT','Synthetic egress exception\nPrivate key + source gates\nOutside OCI data boundary',{iconName:'Bot',color:C.purple,bg:C.purpleBg,dashed:true});
  const backup=await s.card(500,1210,740,140,'Proposed encrypted off-host backups','Conditional private object bucket / quota review','Whole-system restore remains a separate acceptance gate',{iconName:'ArchiveRestore',color:C.grey,bg:C.greyBg,dashed:true});
  const recovery=await s.card(1310,1210,750,140,'Independent recovery material','Approved operator custody in India','Root / unseal / recovery keys remain outside the cloud VM',{iconName:'KeySquare',color:C.grey,bg:C.greyBg,dashed:true});
  s.arrow([[382,490],[550,490]],'App tunnel',{labelX:397,labelY:457,font:17,labelWidth:150,start:operator,end:web});
  s.arrow([[220,418],[220,190],[1735,190],[1735,418]],'Separate identity tunnel → operator localhost:18090',{labelX:670,labelY:160,font:18,labelWidth:740,start:operator,end:identity});
  s.arrow([[910,490],[1010,490]],'Private HTTP',{labelX:914,labelY:453,font:14,labelWidth:105,start:web,end:api});
  s.arrow([[1110,598],[1110,690],[730,690],[730,735]],'SQL / authoritative records',{color:C.teal,labelX:760,labelY:660,font:17,labelWidth:350,start:api,end:pg});
  s.arrow([[1290,598],[1290,735]],'Object API',{color:C.teal,labelX:1310,labelY:685,font:16,labelWidth:150,start:api,end:objects});
  s.arrow([[1410,520],[1460,520],[1460,810],[1510,810]],'Wrap / unwrap',{color:C.teal,labelX:1473,labelY:695,font:16,labelWidth:190,start:api,end:keys});
  s.arrow([[730,880],[730,950]],'Outbox jobs',{color:C.amber,labelX:751,labelY:903,font:16,labelWidth:180,start:pg,end:jobs});
  s.arrow([[1100,950],[1100,880]],'Exact versions',{color:C.teal,labelX:1118,labelY:907,font:16,labelWidth:190,start:jobs,end:objects});
  s.arrow([[1250,1010],[1350,1010]],'Bytes only',{color:C.amber,labelX:1253,labelY:980,font:14,labelWidth:100,start:jobs,end:scan});
  s.arrow([[1010,560],[425,560],[425,875],[382,875]],'Gated HTTPS; disabled',{color:C.purple,dashed:true,labelX:455,labelY:591,font:17,labelWidth:360,start:api,end:model});
  s.arrow([[870,1140],[870,1210]],'Proposed checkpoint transfer',{color:C.grey,dashed:true,labelX:550,labelY:1161,font:17,labelWidth:380,end:backup});
  s.arrow([[1685,1210],[1685,1140]],'Recovery drill / independent custody',{color:C.grey,dashed:true,labelX:1300,labelY:1161,font:17,labelWidth:430,start:recovery});
  s.footer('Single VM ≠ high availability • Stage B public HTTPS / production Keycloak / identity PostgreSQL requires a separate reviewed migration • no Oracle resources provisioned');
  return s.save();
}

async function sequence(){
  const s=new Scene('ai-sequence',2040,1600);
  s.header('SAFER | Advisory AI request sequence','Explicit reviewer action • source-bound answers • deterministic financial authority • no model tools');
  const cols=[190,600,1010,1420,1840];
  const labels=[['Reviewer','Browser / explicit action','UserRound'],['FastAPI','Authorize + build sources','ShieldCheck'],['PostgreSQL','Grants / facts / usage','Database'],['Provider adapter','Bound transport + validate','Braces'],['Gemini API','Untrusted external wording','Bot']];
  for(let i=0;i<cols.length;i++){
    const [title,tech,ico]=labels[i];
    await s.card(cols[i]-155,170,310,95,title,tech,'',{iconName:ico,color:i===4?C.purple:C.blue,bg:i===4?C.purpleBg:C.blueBg});
    s.arrow([[cols[i],275],[cols[i],1190]],'',{color:C.line,dashed:true,head:false});
  }
  const msg=(a,b,y,label,purple=false)=>s.arrow([[cols[a],y],[cols[b],y]],label,{color:purple?C.purple:C.blue,labelX:Math.min(cols[a],cols[b])+20,labelY:y-30,font:18,labelWidth:Math.abs(cols[a]-cols[b])-30});
  msg(0,1,324,'1  GET authorized source package');
  msg(1,2,390,'2  Read current grants + case facts');
  msg(1,0,456,'3  Return sources + digest; no model call');
  msg(0,1,522,'4  POST purpose + digest + CSRF');
  s.rect(445,554,310,88,{strokeColor:C.teal,backgroundColor:C.tealBg});
  s.text(461,564,'Check MFA / scope / feature switch\nSynthetic consent + exact approval\nPrivate credential configuration',17,C.teal,280);
  msg(1,2,700,'5  One slot + durable cost reservation');
  msg(1,3,775,'6  Minimized, bounded source blocks');
  msg(3,4,850,'7  Fixed HTTPS request; no tools',true);
  msg(4,3,925,'8  Untrusted JSON response',true);
  msg(3,1,1000,'9  Validate complete schema + exact block IDs');
  msg(1,2,1075,'10  Recheck session, grants + sources');
  msg(1,0,1150,'11  Advisory text + server facts/citations');
  s.rect(48,1230,1944,100,{strokeColor:C.amber,backgroundColor:C.amberBg});
  s.text(72,1245,'ALT A · Switched off / unapproved / busy / budget exhausted / provider failure',23,C.amber,1870);
  s.text(72,1283,'Use deterministic local fallback. A failing admission gate never dispatches a model request.',21,C.ink,1870);
  s.rect(48,1360,1944,100,{strokeColor:C.purple,backgroundColor:C.purpleBg});
  s.text(72,1375,'ALT B · Session or grant revoked / source digest changed during generation',23,C.purple,1870);
  s.text(72,1413,'Discard generated wording and return an access/stale-source error. The model never updates verification or release state.',21,C.ink,1870);
  s.footer('Default OFF • no automatic retries • conservative reservation retained on uncertain failures • browser checks sources every 15 seconds and on focus • live model evaluation pending');
  return s.save();
}

await fs.mkdir(OUT,{recursive:true});
const scenes=[];
for(const build of [overview,slide,security,deployment,sequence]){const s=await build();scenes.push(s);console.log('Created',s.name,s.elements.length,'editable elements');}

const all={type:'excalidraw',version:2,source:'https://excalidraw.com',elements:[],appState:{viewBackgroundColor:'#eef2f6',gridSize:null,zoom:{value:.25},scrollX:50,scrollY:50},files:{}};
scenes.forEach((s,i)=>{
  const dx=(i%2)*2400,dy=Math.floor(i/2)*1850,frameId='frame-'+s.name;
  const frame={...s.base('frame',-20,-20,s.w+40,s.h+40),id:frameId,x:dx-20,y:dy-20,name:'SAFER · '+s.name};
  all.elements.push(frame);
  // Each standalone scene was saved before adding its frame.
  all.elements.push(...s.elements.filter(e=>e.type!=='frame').map(e=>({...e,x:e.x+dx,y:e.y+dy,frameId})));
  Object.assign(all.files,s.files);
});
await fs.writeFile(path.join(OUT,'SAFER-v2-all-views.excalidraw'),JSON.stringify(all,null,2));

const thumbs=await Promise.all(scenes.map(async s=>({name:s.name,png:await sharp(path.join(OUT,'SAFER-v2-'+s.name+'.png')).resize({width:1000,height:760,fit:'contain',background:'#ffffff'}).png().toBuffer()})));
await sharp({create:{width:2040,height:2360,channels:4,background:'#e7edf3'}}).composite(thumbs.map((t,i)=>({input:t.png,left:10+(i%2)*1020,top:10+Math.floor(i/2)*780}))).png().toFile(path.join(OUT,'SAFER-v2-contact-sheet.png'));

await fs.writeFile(path.join(OUT,'SAFER-v2-ai-sequence.mmd'),`sequenceDiagram
  actor R as Reviewer
  participant A as FastAPI
  participant P as PostgreSQL
  participant G as Provider adapter
  participant M as Gemini (off by default)
  R->>A: GET source package
  A->>P: Check session/grants and read case
  A-->>R: Server facts, citations and source digest
  R->>A: POST purpose, digest and CSRF
  A->>A: Check consent, exact synthetic approval and private key
  alt Gates pass and capacity available
    A->>P: Acquire shared admission slot; commit cost reservation
    A->>G: Minimized bounded source blocks
    G->>M: Fixed HTTPS request without tools
    M-->>G: Untrusted response
    G->>G: Validate schema, completeness and block identities
    G-->>A: Advisory wording or safe failure
    A->>P: Recheck current session, grants and case sources
    alt Access valid and source unchanged
      A-->>R: AI draft beside server facts, or local fallback
    else Access revoked or sources changed
      A-->>R: Discard wording; access/stale error
    end
  else Disabled, unapproved, busy or allowance exhausted
    A-->>R: Deterministic local fallback; no model request
  end
`);

console.log('All five views and combined canvas exported.');
