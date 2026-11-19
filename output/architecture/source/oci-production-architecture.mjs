import {Scene,icon,logo,C,OUT,sharp,fs,ROOT} from './shared-scene.mjs';
import path from 'node:path';
const s=new Scene('oci-production-target',3600,2480),red='#a83a2e',cyan='#138ba6',grey='#73818c';
async function asset(n){return {mime:n.endsWith('.svg')?'image/svg+xml':'image/png',buffer:await fs.readFile(path.join(OUT,'real-logo-assets',n))};}
async function pic(a,x,y,w,h){const m=await sharp(a.buffer).metadata(),k=Math.min(w/m.width,h/m.height);return s.image(a,x+(w-m.width*k)/2,y+(h-m.height*k)/2,m.width*k,m.height*k);}
function text(x,y,t,size=22,w=400,c=C.ink,align='left'){return s.text(x,y,t,size,c,w,{textAlign:align});}
function box(x,y,w,h,title,sub='',c=cyan,bg='#ffffff',dash=true){const b=s.rect(x,y,w,h,{strokeColor:c,backgroundColor:bg,strokeStyle:dash?'dashed':'solid',strokeWidth:1.8});text(x+20,y+15,title,25,w-40,c);if(sub)text(x+20,y+54,sub,19,w-40,C.muted);return b;}
function flow(p,label='',o={}){return s.arrow(p,label,{font:19,labelWidth:360,color:C.blue,...o});}
async function product(cx,y,a,title,sub,w=300,size=86,color=C.ink){await pic(a,cx-w/2,y,w,size);text(cx-w/2,y+size+12,title,25,w,color,'center');if(sub)text(cx-w/2,y+size+48,sub,18,w,C.muted,'center');}

text(55,30,'SAFER inside Oracle Cloud — Production Target',47,3450);
text(57,96,'Proposed paid architecture · Mumbai primary / Hyderabad recovery · modular monolith · containers on Compute',25,3450,C.muted);
text(57,139,'Planning ceiling: ₹75,000/month before tax; price validation required. Existing application remains local and synthetic-only.',21,3450,C.muted);

box(570,210,2980,2065,'ORACLE CLOUD INFRASTRUCTURE · SAFER PRODUCTION TENANCY','Compartments + least-privilege IAM · budget / quota controls · residency and data-owner approval required',red,'#fffdfc',false);
box(610,315,2900,1540,'PRIMARY REGION · INDIA WEST (MUMBAI) · ap-mumbai-1','One availability domain: distribute compute across fault domains; service SKU / capacity confirmation required',red,'#ffffff',false);
box(650,425,2130,1375,'VIRTUAL CLOUD NETWORK (VCN)','Regional subnets · NSGs · private host addresses · no public database, cache or scanner',cyan);

// Public entry / TLS enforcement.
box(690,535,2050,255,'PUBLIC LOAD BALANCER SUBNET','Internet Gateway supplies public reachability; only approved HTTPS listeners',cyan,'#f8fcff');
await product(1020,625,await asset('oci-waf.svg'),'Regional WAF','Attached to load balancer',300,72);
await product(1700,625,await asset('oci-load-balancer.svg'),'Flexible Load Balancer','App + auth backend sets / health checks',460,72);
await product(2380,625,await asset('oci-certificates.svg'),'Certificates','Public TLS + verified backend TLS',420,72);
flow([[1190,662],[1460,662]],'Policy enforced',{labelX:1210,labelY:628,labelWidth:240});
flow([[2180,662],[1960,662]],'Certificate chain',{color:C.teal,labelX:1970,labelY:628,labelWidth:260});

// Two private hosts; Keycloak is clustered across the same hosts to keep the baseline cost smaller.
box(690,865,2050,390,'PRIVATE APPLICATION SUBNET','LB routes app hostname to Nginx and auth hostname to Keycloak; admin / health / cluster ports stay private',cyan,'#f9fbff');
async function appVm(x,title){
 const b=box(x,970,925,215,title,'Pinned containers · host-level resource limits · private IP only',grey,'#ffffff',false);
 await pic(await asset('oci-compute.svg'),x+24,1063,70,70);
 await pic(await logo('react.svg'),x+145,1058,72,72);
 await pic(await asset('nginx.svg'),x+285,1058,165,72);
 await pic(await logo('fastapi.svg'),x+505,1058,72,72);
 await pic(await logo('keycloak.svg'),x+655,1063,235,62);
 text(x+118,1145,'React / Nginx         FastAPI API         Keycloak production',21,780,C.ink,'center');
 return b;
}
const appA=await appVm(730,'COMPUTE A · FAULT DOMAIN 1');
const appB=await appVm(1755,'COMPUTE B · FAULT DOMAIN 2');
text(735,1205,'ONE APPLICATION: FDR repository → evidence / scrutiny → renewal / reminders → authorized release → reports / audit',22,1940,C.blue,'center');
flow([[1700,790],[1700,825],[1190,825],[1190,960]],'Healthy app backend A',{labelX:1210,labelY:800,labelWidth:360});
flow([[1700,825],[2215,825],[2215,960]],'Healthy app backend B',{labelX:2260,labelY:800,labelWidth:360});

// Private job execution and managed data endpoints.
box(690,1340,1120,325,'PRIVATE WORKER SUBNET','Two worker hosts in different fault domains; one leased / fenced relay',cyan,'#fffcf5');
await pic(await asset('oci-compute.svg'),720,1440,64,64);
await pic(await asset('celery.png'),820,1435,95,80);
await pic(await logo('python.svg'),960,1435,76,80);
await pic(await logo('clamav.png'),1100,1435,92,80);
text(1220,1432,'Workers A + B',26,520,C.amber);
text(1220,1475,'Celery jobs · bounded parser sandbox\nIsolated ClamAV: bytes only\nNo DB / object / KMS secrets in scanner',20,520);
text(725,1560,'Durable job claims / retries in PostgreSQL · broker transports job IDs\nFresh signatures required; scan failure keeps documents quarantined',21,1030,C.muted);

box(1880,1340,860,325,'PRIVATE DATA ENDPOINTS','Managed services; permitted clients only; verified TLS',cyan,'#f7fcfa');
await product(2100,1440,await logo('postgresql.svg'),'PostgreSQL HA','≥2 managed nodes\nApp + separate identity DB',340,75,C.teal);
await product(2520,1440,await icon('Database',red),'OCI Cache','≥3 non-sharded nodes\nRedis-compatible / TLS',340,75,C.amber);
text(1900,1620,'Cache / Celery contract and failover testing required',18,810,C.muted,'center');
flow([[2115,1255],[2115,1325]],'DB sessions / transactions',{color:C.teal,labelX:1890,labelY:1282,labelWidth:390});
flow([[2160,1477],[2460,1477]],'Outbox → relay',{color:C.amber,labelX:2210,labelY:1445,labelWidth:245});
flow([[2520,1648],[1830,1648],[1830,1530],[1815,1530]],'',{color:C.amber});
flow([[1250,1255],[1250,1325]],'Background work',{color:C.amber,labelX:1280,labelY:1282,labelWidth:300});

// Routing / administrative controls on the VCN boundary.
await pic(await asset('oci-service-gateway.svg'),750,1705,62,62);
text(835,1707,'Service Gateway',24,425,C.teal);
text(835,1745,'Supported regional OCI service routes',18,600,C.muted);
await pic(await asset('oci-nat.svg'),1560,1705,62,62);
text(1645,1707,'NAT + controlled egress',24,590,C.amber);
text(1645,1745,'Updates / signatures / approved integrations',18,600,C.muted);
await pic(await asset('oci-bastion.svg'),2370,1705,62,62);
text(2450,1707,'Bastion',24,260,red);
text(2450,1745,'Time-limited admin',18,270,C.muted);

// OCI managed regional services stay outside the VCN subnet boxes.
box(2840,425,630,1375,'OCI REGIONAL SERVICES','Private authorization / endpoint routes verified per service',red,'#fffcfa',false);
async function service(y,name,tech,body,art,color=red){
 const b=box(2870,y,570,225,name,'',color,'#ffffff',false);
 await pic(await asset(art),2895,y+65,82,82);
 text(3005,y+61,tech,24,410,color);
 text(3005,y+104,body,19,410,C.ink);
 return b;
}
await service(535,'PRIVATE OBJECT STORAGE','Encrypted FDR documents','Exact object versions / SHA-256\nSeparate document + audit buckets\nSource locator migration required','oci-object-storage.svg',C.teal);
await service(790,'VAULT / KMS + SECRETS','Keys stay managed','Envelope key wrapping adapter\nScoped instance-principal access\nNo keys in repo / .env','oci-vault.svg',C.teal);
await service(1045,'LOGGING / AUDIT / MONITORING','Operational visibility','App events + WAF / LB / VCN logs\nMetrics / alarms → Notifications\nNamed incident responder','oci-monitoring.svg',C.blue);
await service(1300,'EMAIL DELIVERY','Approved reminder channel','Sender / domain approval\nBounce + uncertain-send handling\nMailpit remains test-only','oci-email.svg',C.amber);
await service(1555,'IAM + SECURITY OWNERSHIP','Least privilege','Separate app / backup / key duties\nPrivate admin access + MFA\nData-owner / procurement gates','oci-iam.svg',red);

// Significant data/control routes; labels refer to the written plan for exact endpoint policies.
flow([[2740,1050],[2800,1050],[2800,645],[2860,645]],'',{color:C.teal});
flow([[2740,1130],[2817,1130],[2817,900],[2860,900]],'',{color:C.teal});
flow([[2740,1455],[2790,1455],[2790,1155],[2860,1155]],'',{color:C.blue});
flow([[1810,1580],[1838,1580],[1838,1685],[2805,1685],[2805,1410],[2860,1410]],'Reminder outputs',{color:C.amber,labelX:1840,labelY:1660,labelWidth:300});

// External users, global DNS and integration controls.
await product(260,585,await icon('Users',C.blue),'Institutions + AICTE','Officer · reviewer · approver',430,100,C.blue);
await pic(await asset('oci-dns.svg'),75,365,76,76);
text(175,365,'OCI DNS',26,340,C.blue);
text(175,407,'Resolve app + auth to public LB',18,350,C.muted);
flow([[260,580],[260,470]],'Name lookup',{labelX:285,labelY:500,labelWidth:220});
flow([[490,662],[680,662]],'1 · HTTPS',{labelX:505,labelY:628,labelWidth:160});

box(50,890,460,530,'HOW SAFER RUNS','',C.blue,'#f7fbff',false);
text(75,955,'1   Browser → WAF / HTTPS LB\n\n2   Healthy private app host\n     Nginx → FastAPI + Keycloak\n\n3   FDR record → PostgreSQL\n     Encrypted file → Object Storage\n\n4   Outbox → Cache → workers\n     Scan / extract / remind\n\n5   Human review / approval\n     Audit + monitoring + recovery',21,410);
box(50,1495,460,290,'EXTERNAL INTEGRATIONS','',C.purple,'#fbf8ff',false);
await pic(await asset('gemini.svg'),80,1557,65,65);
text(165,1555,'Gemini: OFF by default',22,310,C.purple);
text(75,1650,'Real data / bank API needs approval.\nAI remains advisory; local fallback.\nControlled egress; no model on A1.',19,410);

// DR is a separate region, not another fault domain in Mumbai.
box(610,1920,2900,300,'RECOVERY REGION · INDIA SOUTH (HYDERABAD) · ap-hyderabad-1','Reconstructable environment + approved recovery copies; no active-active claim',red,'#fffdfb',false);
await pic(await asset('oci-object-storage.svg'),655,2025,80,80);
text(765,2025,'Recovery copies + manifests',25,700,C.teal);
text(765,2075,'DB / object versions / identity / config / keys\nSeparate administration and decryption custody',21,800);
await pic(await asset('oci-compute.svg'),1790,2025,80,80);
text(1900,2025,'Fenced restore + tested cutover',25,970,C.blue);
text(1900,2075,'Targets: whole-system RPO ≤1 hour / RTO ≤4 hours\nCold rebuild may need funded warm capacity to meet the target',21,1500);
flow([[2100,1855],[2100,1910]],'Verified India-region copies',{color:C.teal,dashed:true,labelX:2140,labelY:1870,labelWidth:470});

// Delivery is a controlled path into the cloud, not the representation of the cloud itself.
box(50,2330,3460,110,'CONTROLLED DELIVERY','',grey,'#f8fafc',false);
await pic(await asset('github.png'),500,2353,52,52);
text(575,2360,'GitHub Actions: test / scan / SBOM / sign',23,820);
await pic(await asset('oci-registry.svg'),1450,2353,52,52);
text(1525,2360,'OCIR: pinned image digests',23,650);
text(2300,2360,'Reviewed rollout → drain / health / rollback',23,1140,C.blue);
flow([[1330,2385],[1430,2385]],'',{});flow([[2160,2385],[2280,2385]],'',{});
text(70,2268,'PROPOSAL ONLY: no resources provisioned. Paid HA design exceeds the free pilot. All targets require implementation, load / failover / restore tests and acceptance.',19,3400,C.muted);

const base=path.join(OUT,'SAFER-OCI-production-target');
await fs.writeFile(base+'.excalidraw',JSON.stringify(s.json(),null,2));
await fs.writeFile(base+'.svg',s.svg());
await sharp(Buffer.from(s.svg()),{density:144}).png().toFile(base+'.png');
await sharp(Buffer.from(s.svg())).resize({width:2400}).png().toFile(base+'-preview.png');
console.log(JSON.stringify({base,elements:s.elements.length,assets:Object.keys(s.files).length}));
