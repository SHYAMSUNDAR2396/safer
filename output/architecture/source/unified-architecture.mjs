import {Scene,icon,logo,C,OUT,sharp,fs} from './shared-scene.mjs';
import path from 'node:path';

// One wide logical architecture, arranged to match the user's layered reference.
const s=new Scene('unified-technology-architecture',3000,1600);
const graphite='#73818c';
s.text(60,30,'SAFER — Security Deposit / FDR Technology Architecture',48,C.ink,2880);
s.text(62,96,'Modular monolith • portable Docker Compose runtime • source-linked financial review • synthetic demonstration',24,C.muted,2870);
s.text(62,147,'CLIENTS / ACCESS',22,C.ink,350);
s.text(490,147,'PRIVATE RUNTIME · LOGICAL APPLICATION AND SERVICE BOUNDARIES',22,C.ink,1920);
s.text(2535,147,'INTEGRATIONS / OUTPUTS',22,C.ink,420);

s.rect(40,190,390,1055,{strokeColor:graphite,strokeStyle:'dashed',strokeWidth:1.6});
s.rect(460,190,2040,1055,{strokeColor:graphite,strokeStyle:'dashed',strokeWidth:1.6});
s.rect(2520,190,440,1055,{strokeColor:graphite,strokeStyle:'dashed',strokeWidth:1.6});

function group(x,y,w,h,title,color=C.ink){
  const box=s.rect(x,y,w,h,{strokeColor:graphite,backgroundColor:'#ffffff',strokeStyle:'dashed',strokeWidth:1.4});
  s.text(x+16,y+12,title,22,color,w-32);
  return box;
}

async function centered(x,y,w,h,title,tech,body,ico,color=C.blue,brand=null){
  const box=s.rect(x,y,w,h,{strokeColor:graphite,backgroundColor:'#ffffff',strokeStyle:'dashed',strokeWidth:1.4});
  s.image(brand?await logo(brand):await icon(ico,color),x+w/2-29,y+22,58,58);
  s.text(x+14,y+91,title,25,color,w-28,{textAlign:'center'});
  s.text(x+14,y+126,tech,19,C.muted,w-28,{textAlign:'center'});
  if(body)s.text(x+15,y+161,body,20,C.ink,w-30,{textAlign:'center'});
  return box;
}

const people=await centered(65,225,340,195,'Institutions + AICTE','Officer · reviewer · approver','Admin / auditor permissions','Users');
const portal=await centered(65,500,340,255,'Browser portal','React + TypeScript','Vite build / responsive UI\nOpaque session + CSRF\nInstitution-scoped records','Monitor',C.blue,'react.svg');
s.text(86,822,'ACCESS PROFILES',20,C.ink,295);
s.image(await icon('ShieldCheck',C.blue),90,865,50,50);
s.text(156,860,'Development: Vite proxy\nReadiness: local HTTPS\nOnly local origins accepted',19,C.muted,240);
s.image(await icon('Laptop',C.grey),90,1031,50,50);
s.text(156,1024,'Operator workstation\nPrivate key / recovery custody\nOCI SSH tunnel: proposed',18,C.muted,240);

const identity=group(490,225,380,215,'IDENTITY + ACCESS');
s.image(await icon('KeyRound',C.blue),512,276,62,62);
s.text(590,275,'Keycloak + Authlib',25,C.blue,256);
s.text(512,355,'OIDC · authorization code + PKCE\nPrivileged TOTP / signed assurance\nLocal roles + institution grants',19,C.ink,337);

const keyService=group(900,225,380,215,'KEYS + ENCRYPTION',C.teal);
s.image(await icon('KeySquare',C.teal),922,276,62,62);
s.text(1000,275,'OpenBao Transit',25,C.teal,250);
s.text(922,355,'Envelope encryption / AES-GCM\nWrap / unwrap random data keys\nReadiness profile · private tokens',19,C.ink,336);

const observation=group(1310,225,520,215,'AUDIT + OBSERVABILITY');
s.image(await icon('Logs',C.blue),1332,276,62,62);
s.text(1410,275,'Structured application events',25,C.blue,393);
s.text(1332,355,'Request IDs + timings · safe error categories\nPostgreSQL audit / AI usage metadata\nLocal security-alert evidence and recovery drills',19,C.ink,477);

const config=group(1860,225,610,215,'CONFIGURATION + GOVERNANCE');
s.image(await icon('Settings2',C.blue),1882,276,62,62);
s.text(1960,275,'Settings + versioned policies',25,C.blue,480);
s.text(1882,355,'Pydantic settings · published release rules\nSource approvals · feature flags · spending limits\nSecrets are private files, outside .env / repository',19,C.ink,566);

const edge=await centered(490,550,250,315,'Nginx','Readiness front door','Built React assets\nSame-origin /api routing\nNo public API in demo','Network');
const guard=group(790,520,340,375,'ACCESS + VALIDATION',C.blue);
s.image(await icon('ShieldCheck',C.blue),924,574,64,64);
s.text(812,668,'Session / CSRF verification\nCurrent role + scoped grants\nStrict Pydantic validation\nRow version + idempotency\nExact document hash/version',21,C.ink,296);
s.badge(821,851,'ENFORCED IN FASTAPI',C.blue,C.blueBg,276);

const core=group(1180,520,1290,375,'FASTAPI MODULAR MONOLITH · ONE APPLICATION',C.blue);
s.image(await logo('fastapi.svg'),2387,532,52,52);

async function module(x,y,title,body,ico,color=C.blue){
  s.rect(x,y,394,125,{strokeColor:'#c2d0da',backgroundColor:'#f8fafc',strokeWidth:1});
  s.image(await icon(ico,color),x+14,y+16,38,38);
  s.text(x+64,y+15,title,23,color,316);
  s.text(x+16,y+65,body,19,C.ink,364);
}
await module(1203,583,'FDR repository','Metadata / drafts / immutable submission\nInstitution-wise and instrument-wise','Files');
await module(1625,583,'Document management','Private versions / hashes / quarantine\nText extraction proposes values','FolderLock');
await module(2047,583,'Evidence + scrutiny','Claims vs recorded evidence / mismatch\nObservation threads / human review','FileSearch');
await module(1203,737,'Maturity + renewal','Configured reminders / escalations\nReplacement history + acceptance','CalendarClock');
await module(1625,737,'Release governance','Clearances / competent decision\nInstruction / execution / reconciliation','BadgeCheck');
await module(2047,737,'Reports + summaries','Scoped dashboard / CSV exports\nSource-linked summaries + AI adapter','ChartNoAxesCombined');

// Integrations are explicitly distinguished from the running private application.
const gemini=group(2540,225,400,295,'OPTIONAL EXTERNAL AI',C.purple);
s.image(await icon('Bot',C.purple),2696,270,64,64);
s.text(2560,346,'Gemini API adapter',25,C.purple,360,{textAlign:'center'});
s.text(2560,390,'Approved synthetic facts only\nBounded JSON + source/access recheck\nDeterministic fallback on failure',18,C.ink,360,{textAlign:'center'});
s.badge(2580,478,'OFF BY DEFAULT',C.purple,C.purpleBg,320);

const bank=group(2540,570,400,240,'BANK EVIDENCE STATUS',C.grey);
s.image(await icon('Landmark',C.grey),2696,615,64,64);
s.text(2562,692,'Recorded manual evidence',23,C.ink,356,{textAlign:'center'});
s.text(2562,733,'Bank simulator is labelled\nReal bank API: pending authorization',18,C.muted,356,{textAlign:'center'});

const mail=group(2540,860,400,205,'LOCAL NOTIFICATION CAPTURE',C.amber);
s.image(await icon('Mail',C.amber),2563,914,57,57);
s.text(2640,915,'Mailpit',25,C.amber,270);
s.text(2563,990,'Reminder / escalation job outputs\nMessages stay in the local inbox',19,C.ink,354);
s.text(2562,1140,'AI wording is advisory.\nClean scan ≠ authenticity.\nRelease needs competent approval.',18,C.muted,356);

const pg=await centered(490,980,350,220,'PostgreSQL','SQLAlchemy / transaction boundary','Claims / evidence / grants / audit\nOutbox + model usage reservations','Database',C.teal,'postgresql.svg');
const objects=await centered(880,980,350,220,'Private document store','SeaweedFS / S3-compatible API','Exact object versions + SHA-256\nReadiness: encrypted envelopes','FolderLock',C.teal,'seaweedfs.png');
const queue=await centered(1270,980,350,220,'Valkey','Redis-compatible job transport','Job IDs only\nPostgreSQL owns durable job state','Workflow',C.amber);
const worker=await centered(1660,980,370,220,'Celery + relay','Python workers / job scheduler','Scan / extract / reminders / reports\nIdempotent dispatch + recovery','Repeat2',C.amber,'python.svg');
const scanner=await centered(2070,980,400,220,'Isolated ClamAV','Separate scanning network','Bytes only / no database or key secrets\nFreshclam signature updates','ShieldCheck',C.amber,'clamav.png');

// Explicit data/control flows. Lines represent labelled dependencies, not clusters.
s.arrow([[235,420],[235,500]],'Use portal',{labelX:254,labelY:446,font:17,labelWidth:145,start:people,end:portal});
s.arrow([[405,644],[490,644]],'HTTPS*',{labelX:411,labelY:613,font:15,labelWidth:80,start:portal,end:edge});
s.arrow([[405,550],[447,550],[447,470],[680,470],[680,440]],'OIDC / PKCE + TOTP',{labelX:467,labelY:445,font:16,labelWidth:245,start:portal,end:identity});
s.arrow([[740,700],[790,700]],'Route',{labelX:743,labelY:671,font:14,labelWidth:50,start:edge,end:guard});
s.arrow([[1130,700],[1180,700]],'Check',{labelX:1133,labelY:671,font:14,labelWidth:50,start:guard,end:core});
s.arrow([[960,520],[960,483],[850,483],[850,440]],'Code / JWKS',{labelX:880,labelY:450,font:15,labelWidth:170,start:guard,end:identity});
s.arrow([[1420,520],[1420,483],[1090,483],[1090,440]],'App-side wrap / unwrap',{color:C.teal,labelX:1130,labelY:451,font:16,labelWidth:300,start:core,end:keyService});
s.arrow([[2190,520],[2190,470],[1570,470],[1570,440]],'Request and audit metadata',{labelX:1690,labelY:445,font:16,labelWidth:395,start:core,end:observation});
s.arrow([[2470,640],[2505,640],[2505,366],[2540,366]],'Gated HTTPS',{color:C.purple,dashed:true,labelX:2330,labelY:491,font:16,labelWidth:190,start:core,end:gemini});
s.arrow([[2470,737],[2540,737]],'Pending',{color:C.grey,dashed:true,labelX:2475,labelY:706,font:14,labelWidth:65,start:core,end:bank});
s.arrow([[1320,895],[1320,921],[665,921],[665,980]],'Transactions + audit',{color:C.teal,labelX:770,labelY:895,font:16,labelWidth:300,start:core,end:pg});
s.arrow([[1545,895],[1545,955],[1055,955],[1055,980]],'Private object API',{color:C.teal,labelX:1110,labelY:930,font:16,labelWidth:225,start:core,end:objects});
s.arrow([[1915,895],[1915,952],[1845,952],[1845,980]],'Claim / persist jobs',{color:C.amber,labelX:1950,labelY:925,font:16,labelWidth:270,start:core,end:worker});
s.arrow([[665,1200],[665,1229],[1445,1229],[1445,1200]],'Committed outbox → relay → publish job IDs',{color:C.amber,labelX:780,labelY:1206,font:16,labelWidth:610,start:pg,end:queue});
s.arrow([[1620,1104],[1660,1104]],'IDs',{color:C.amber,labelX:1627,labelY:1076,font:14,labelWidth:35,start:queue,end:worker});
s.arrow([[2030,1104],[2070,1104]],'Bytes',{color:C.amber,labelX:2031,labelY:1075,font:13,labelWidth:40,start:worker,end:scanner});
s.arrow([[1945,980],[1945,966],[2508,966],[2540,966]],'Local SMTP capture',{color:C.amber,labelX:2190,labelY:941,font:16,labelWidth:290,start:worker,end:mail});

// Configured delivery checks; the final OCI step remains a proposal, not an automated live deployment.
group(40,1290,2920,205,'DEVELOPMENT / VERIFICATION / PORTABLE DELIVERY');
const dev=await s.card(65,1344,350,125,'Development','Git + application source','',{iconName:'CodeXml'});
const git=await s.card(495,1344,370,125,'GitHub','Source and pull requests','',{iconName:'Github'});
const ci=await s.card(945,1344,630,125,'GitHub Actions checks','Backend / browser tests · synthetic evaluation','',{brand:'githubactions.svg'});
s.text(969,1435,'Dependency + image / secret scans · SBOM artifacts',17,C.muted,582);
const docker=await s.card(1655,1344,450,125,'Portable images','Docker · API + web + Compose','',{brand:'docker.svg'});
const cloud=await s.card(2185,1344,750,125,'OCI private demo — PROPOSED','A1 budget: 2 OCPUs / 12 GB · operator deployment gates','',{iconName:'Cloud',color:C.grey,bg:C.greyBg,dashed:true});
s.arrow([[415,1407],[495,1407]],'Commit',{labelX:423,labelY:1376,font:15,labelWidth:70,start:dev,end:git});
s.arrow([[865,1407],[945,1407]],'Verify',{labelX:878,labelY:1376,font:15,labelWidth:70,start:git,end:ci});
s.arrow([[1575,1407],[1655,1407]],'Build',{labelX:1590,labelY:1376,font:15,labelWidth:65,start:ci,end:docker});
s.arrow([[2105,1407],[2185,1407]],'Review',{color:C.grey,dashed:true,labelX:2118,labelY:1376,font:15,labelWidth:70,start:docker,end:cloud});
s.text(56,1520,'Legend: solid arrows = implemented dependencies / configured checks · purple dashed = optional AI, disabled · grey dashed = pending integration / proposed deployment',19,C.muted,2880);
s.text(56,1555,'*HTTPS front door is the local readiness profile; development uses a Vite proxy. Internal groups are logical boundaries, not independent microservices. No live bank or Oracle deployment is claimed.',18,C.muted,2880);

const base=path.join(OUT,'SAFER-unified-technology-architecture');
await fs.writeFile(base+'.excalidraw',JSON.stringify(s.json(),null,2));
await fs.writeFile(base+'.svg',s.svg());
await sharp(Buffer.from(s.svg()),{density:144}).png().toFile(base+'.png');
await sharp(Buffer.from(s.svg())).resize({width:2400}).png().toFile(base+'-preview.png');
console.log(JSON.stringify({base,elements:s.elements.length,embeddedAssets:Object.keys(s.files).length}));
