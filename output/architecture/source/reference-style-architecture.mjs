import {Scene,icon,logo,C,OUT,sharp,fs,ROOT} from './shared-scene.mjs';
import path from 'node:path';
const s=new Scene('reference-style',2900,1640);
const grey='#65717a',cyan='#0eabd1';
async function asset(name){return {mime:name.endsWith('.svg')?'image/svg+xml':'image/png',buffer:await fs.readFile(path.join(OUT,'real-logo-assets',name))};}
async function img(a,x,y,w,h){const m=await sharp(a.buffer).metadata(),k=Math.min(w/m.width,h/m.height);return s.image(a,x+(w-m.width*k)/2,y+(h-m.height*k)/2,m.width*k,m.height*k);}
function txt(x,y,t,size=22,width=270,color=C.ink,center=true){return s.text(x,y,t,size,color,width,{textAlign:center?'center':'left'});}
function boundary(x,y,w,h,title,sub='',color=cyan,dash=true){const b=s.rect(x,y,w,h,{strokeColor:color,strokeStyle:dash?'dashed':'solid',strokeWidth:2,roundness:null});txt(x+20,y+14,title,23,w-40,color,false);if(sub)txt(x+20,y+47,sub,17,w-40,C.muted,false);return b;}
async function node(cx,y,title,tech,detail,a,{w=230,size=92,logoWidth=size,color=C.ink}={}){const g='n-'+s.n;await img(a,cx-logoWidth/2,y,logoWidth,size);txt(cx-w/2,y+size+15,title,24,w,color);txt(cx-w/2,y+size+48,tech,19,w,C.muted);if(detail)txt(cx-w/2,y+size+81,detail,17,w,C.muted);}
function line(points,label='',opts={}){return s.arrow(points,label,{color:grey,font:18,labelWidth:300,...opts});}

s.text(54,36,'SAFER — System Architecture',45,C.ink,2100);
s.text(56,97,'Security Deposit / FDR Management · application, data and delivery flows',23,C.muted,2100);
// External optional AI is outside the runtime boundary.
await img(await asset('gemini.svg'),2390,43,80,80);
txt(2490,44,'Gemini API',26,340,C.purple,false);
txt(2490,83,'Optional · OFF by default',19,340,C.purple,false);
txt(2490,113,'Synthetic facts / advisory output',17,350,C.muted,false);

boundary(365,180,2470,1370,'PORTABLE SAFER RUNTIME','Docker Compose · OCI A1 private demo target: proposed, 2 OCPUs / 12 GB',grey,false);
boundary(985,270,1770,260,'Security and operational services','Private services and application metadata');
boundary(985,600,1770,345,'Application layer','One FastAPI modular monolith · current roles and institution grants enforced');
boundary(985,1010,1770,350,'Data and background processing','Private storage · durable job state · asynchronous processing');

// Sources and ingress: large logos with compact captions, like the supplied reference.
boundary(45,265,255,280,'Evidence sources','',grey,false);
await node(172,323,'Bank records','Manual bank evidence','Simulator explicitly labelled',await icon('Landmark',grey),{w:230,size:82});
await node(172,728,'Users','Institution / AICTE','Reviewer · approver · auditor',await icon('Users',grey),{w:280,size:92});
await node(570,725,'Web portal','React · TypeScript · Vite','Session cookie + CSRF',await logo('react.svg'),{w:270,size:100});
await img(await logo('typescript.svg'),480,930,45,45);await img(await logo('vite.svg'),600,930,45,45);
await node(820,731,'Web entry','Nginx','HTTPS / same-origin API',await asset('nginx.svg'),{w:260,size:88,logoWidth:190});
await node(585,326,'Identity provider','Keycloak · OIDC + PKCE','Privileged users: TOTP MFA',await logo('keycloak.svg'),{w:320,size:100,logoWidth:280});

// Controls.
await node(1200,330,'Key protection','OpenBao Transit','Envelope encryption / AES-GCM',await asset('openbao.svg'),{w:340,size:80,logoWidth:250,color:C.teal});
await node(1750,330,'Audit and visibility','Python · structured events','Request IDs / PostgreSQL audit',await logo('python.svg'),{w:360,size:80});
await node(2360,330,'Notifications','Mailpit','Local reminder / escalation inbox',await asset('mailpit.svg'),{w:360,size:80,color:C.amber});

// Central API and business modules: no invented service logos.
await node(1125,704,'REST API','FastAPI · Pydantic','Validate · authorize · transact',await logo('fastapi.svg'),{w:260,size:90});
const modules=[
[1435,'FDR records','Draft → submit','Files'],
[1700,'Evidence review','Compare → scrutinize','FileSearch'],
[1965,'Renewal tracking','Maturity → remind','CalendarClock'],
[2230,'Release workflow','Clearance → approval','BadgeCheck'],
[2495,'Reports + AI','Sources → summary','ChartNoAxesCombined']
];
for(const [x,title,logic,ico] of modules)await node(x,710,title,logic,'',await icon(ico,C.blue),{w:250,size:76});

// Persistence and job execution.
await node(1140,1100,'System of record','PostgreSQL / SQLAlchemy','Claims · evidence · grants · audit',await logo('postgresql.svg'),{w:300,size:86,color:C.teal});
await node(1500,1100,'Document storage','SeaweedFS / private S3 API','Versions · hashes · encrypted files',await logo('seaweedfs.png'),{w:330,size:86,color:C.teal});
await node(1860,1100,'Job transport','Valkey','Job IDs only',await asset('valkey.svg'),{w:300,size:86,logoWidth:210,color:C.amber});
await node(2210,1100,'Workers + relay','Celery / Python','Scan · extract · remind · export',await asset('celery.png'),{w:320,size:86,color:C.amber});
await node(2560,1100,'Malware scan','Isolated ClamAV','File bytes / separate network',await logo('clamav.png'),{w:300,size:86,color:C.amber});

// Labelled orthogonal routes with generous whitespace.
line([[237,775],[495,775]],'Sign in / submit',{labelX:285,labelY:741,labelWidth:215});
line([[635,775],[715,775]],'HTTPS',{labelX:655,labelY:741,labelWidth:95});
line([[925,775],[1070,775]],'/api/v1',{labelX:922,labelY:741,labelWidth:120});
line([[585,720],[585,585]],'OIDC + MFA',{labelX:605,labelY:640,labelWidth:200});
line([[745,436],[915,436],[915,686],[1125,686],[1125,695]],'Code / JWKS',{labelX:760,labelY:402,labelWidth:160});
line([[300,407],[340,407],[340,567],[1700,567],[1700,701]],'Record evidence · retain source and provenance',{labelX:1030,labelY:542,labelWidth:570});
line([[1200,600],[1200,554],[1200,530]],'Wrap / unwrap keys',{color:C.teal,labelX:1230,labelY:574,labelWidth:260});
line([[2035,600],[2035,554],[1750,554],[1750,530]],'Audit / request metadata',{labelX:1810,labelY:532,labelWidth:340});
line([[1180,750],[1375,750]],'Route',{labelX:1248,labelY:717,labelWidth:110});
line([[2560,710],[2725,710],[2725,155]],'Bounded HTTPS request',{color:C.purple,dashed:true,labelX:2410,labelY:220,labelWidth:270});
line([[1125,945],[1125,1000]],'Transactions',{color:C.teal,labelX:1148,labelY:973,labelWidth:185});
line([[1435,945],[1435,978],[1500,978],[1500,1000]],'Object versions',{color:C.teal,labelX:1520,labelY:971,labelWidth:200});
line([[1965,945],[1965,980],[2210,980],[2210,1000]],'Persist / claim jobs',{color:C.amber,labelX:2075,labelY:951,labelWidth:260});
line([[1140,1330],[1140,1391],[1860,1391],[1860,1330]],'Committed outbox → relay → publish job IDs',{color:C.amber,labelX:1270,labelY:1366,labelWidth:600});
line([[1980,1143],[2150,1143]],'Consume IDs',{color:C.amber,labelX:1982,labelY:1110,labelWidth:180});
line([[2270,1143],[2502,1143]],'Scan bytes',{color:C.amber,labelX:2334,labelY:1110,labelWidth:150});
line([[2210,1360],[2210,1391],[2800,1391],[2800,566],[2360,566],[2360,530]],'Local SMTP output',{color:C.amber,labelX:2465,labelY:540,labelWidth:260});

// Compact delivery strip with genuine product artwork.
line([[405,1430],[2800,1430]],'',{head:false,color:'#cad2d8'});
txt(410,1444,'DELIVERY',19,180,grey,false);
const delivery=[
[650,'Git source',await asset('git.svg')],
[1060,'GitHub',await asset('github.png')],
[1515,'GitHub Actions',await logo('githubactions.svg')],
[2010,'Docker images',await logo('docker.svg')],
[2550,'OCI demo · proposed',await asset('oci-compute.svg')]
];
for(const [x,label,a] of delivery){await img(a,x-90,1466,55,55);txt(x-20,1476,label,22,340,C.ink,false);}
line([[825,1495],[965,1495]],'Commit',{font:15,labelX:850,labelY:1466,labelWidth:110});
line([[1230,1495],[1420,1495]],'Test + scan',{font:15,labelX:1258,labelY:1466,labelWidth:150});
line([[1735,1495],[1915,1495]],'Build',{font:15,labelX:1785,labelY:1466,labelWidth:100});
line([[2245,1495],[2455,1495]],'Deployment gates',{dashed:true,font:15,labelX:2270,labelY:1466,labelWidth:195});

// Concise explicit scope protects against misleading visual similarity to the AWS example.
s.text(54,1580,'Solid arrows: application flows   ·   Purple dashed: optional AI   ·   OCI deployment: proposed   ·   Real bank API: authorization pending',20,C.muted,2800);
s.text(54,1610,'Synthetic demonstration only. AI output is advisory; release requires competent approval. Runtime boundaries are logical, with local readiness security profiles.',18,C.muted,2800);
const base=path.join(OUT,'SAFER-reference-style-architecture');
await fs.writeFile(base+'.excalidraw',JSON.stringify(s.json(),null,2));
await fs.writeFile(base+'.svg',s.svg());
await sharp(Buffer.from(s.svg()),{density:144}).png().toFile(base+'.png');
await sharp(Buffer.from(s.svg())).resize({width:2400}).png().toFile(base+'-preview.png');
console.log(JSON.stringify({base,elements:s.elements.length,files:Object.keys(s.files).length}));
