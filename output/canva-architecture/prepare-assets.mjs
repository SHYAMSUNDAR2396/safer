import {fs,sharp,icon,ROOT} from '../architecture/source/shared-scene.mjs';
import path from 'node:path';
const out=path.join(ROOT,'output/canva-architecture/assets');
const sets={react:['main','react.svg'],typescript:['main','typescript.svg'],fastapi:['main','fastapi.svg'],postgresql:['main','postgresql.svg'],keycloak:['main','keycloak.svg'],docker:['main','docker.svg'],clamav:['main','clamav.png'],actions:['main','githubactions.svg'],celery:['real','celery.png'],dns:['real','oci-dns.svg'],waf:['real','oci-waf.svg'],lb:['real','oci-load-balancer.svg'],compute:['real','oci-compute.svg'],objects:['real','oci-object-storage.svg'],vault:['real','oci-vault.svg'],monitor:['real','oci-monitoring.svg'],email:['real','oci-email.svg'],gemini:['real','gemini.svg']};
for(const [name,[where,file]] of Object.entries(sets)){
 const p=where==='main'?path.join(ROOT,'output/SAFER-tech-stack-logos/01-main-stack',file):path.join(ROOT,'output/architecture/real-logo-assets',file);
 await sharp(p,{density:180}).resize({width:700,height:350,fit:'inside'}).png().toFile(path.join(out,name+'.png'));
}
for(const [name,ico] of [['users','Users'],['bank','Landmark'],['cache','Database'],['shield','ShieldCheck']])await sharp((await icon(ico,'#1B3A7A')).buffer).resize(200,200).png().toFile(path.join(out,name+'.png'));
console.log('Prepared original technology logos and concept symbols');
