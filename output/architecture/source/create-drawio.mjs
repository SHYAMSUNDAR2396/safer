import fs from 'node:fs/promises';
import path from 'node:path';
const root='/Users/shyamsundar/Documents/SIH 2026/output/architecture';
const base=path.join(root,'SAFER-OCI-production-target');
const src=JSON.parse(await fs.readFile(base+'.excalidraw','utf8'));
const esc=s=>String(s).replaceAll('&','&amp;').replaceAll('"','&quot;').replaceAll('<','&lt;').replaceAll('>','&gt;');
const all=[];let vertices=0,edges=0;
for(const e of src.elements){
 if(e.isDeleted)continue;
 let style='',value='',body='',kind='vertex="1"';
 const common=`strokeColor=${e.strokeColor==='transparent'?'none':e.strokeColor};strokeWidth=${e.strokeWidth};opacity=${e.opacity};`;
 if(e.type==='rectangle'){
  style=`rounded=1;arcSize=6;whiteSpace=wrap;html=0;fillColor=${e.backgroundColor==='transparent'?'none':e.backgroundColor};${common}dashed=${e.strokeStyle==='dashed'?1:0};dashPattern=8 6;`;
 }else if(e.type==='text'){
  style=`text;html=0;whiteSpace=wrap;overflow=visible;align=${e.textAlign||'left'};verticalAlign=top;fontFamily=Arial;fontSize=${e.fontSize};fontStyle=${e.fontSize>=25?1:0};fontColor=${e.strokeColor};fillColor=none;strokeColor=none;spacing=0;lineHeight=1.25;`;
  value=e.text;
 }else if(e.type==='image'){
  const f=src.files[e.fileId];if(!f)throw new Error('missing embedded asset');
  const data=f.dataURL.replace(';base64,',',');
  style=`shape=image;verticalLabelPosition=bottom;verticalAlign=top;imageAspect=0;aspect=fixed;image=${data};`;
 }else if(e.type==='arrow'||e.type==='line'){
  const p=e.points.map(([x,y])=>({x:x+e.x,y:y+e.y}));
  style=`edgeStyle=none;rounded=0;html=0;${common}dashed=${e.strokeStyle==='dashed'?1:0};dashPattern=8 6;endArrow=${e.type==='arrow'?'open':'none'};endFill=0;endSize=10;startArrow=none;`;
  body=`<mxGeometry relative="1" as="geometry"><mxPoint x="${p[0].x}" y="${p[0].y}" as="sourcePoint"/><mxPoint x="${p.at(-1).x}" y="${p.at(-1).y}" as="targetPoint"/>${p.length>2?'<Array as="points">'+p.slice(1,-1).map(t=>`<mxPoint x="${t.x}" y="${t.y}"/>`).join('')+'</Array>':''}</mxGeometry>`;
  kind='edge="1"';edges++;
 }else throw new Error('Unsupported type '+e.type);
 if(!body){body=`<mxGeometry x="${e.x}" y="${e.y}" width="${e.width}" height="${e.height}" as="geometry"/>`;vertices++;}
 all.push(`<mxCell id="${esc(e.id)}" value="${esc(value)}" style="${esc(style)}" ${kind} parent="1">${body}</mxCell>`);
}
const graph=`<mxGraphModel dx="1600" dy="1000" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" pageWidth="3600" pageHeight="2480" math="0" shadow="0" background="#ffffff"><root><mxCell id="0"/><mxCell id="1" parent="0"/>${all.join('')}</root></mxGraphModel>`;
const xml=`<?xml version="1.0" encoding="UTF-8"?><mxfile host="app.diagrams.net" agent="SAFER Architecture" version="29.0.0"><diagram id="safer-oci-production" name="SAFER OCI Production">${graph}</diagram></mxfile>`;
await fs.writeFile(base+'.drawio',xml);
await fs.writeFile(base+'-drawio-model.xml',graph);
console.log(JSON.stringify({file:base+'.drawio',vertices,edges,embeddedImages:src.elements.filter(e=>e.type==='image').length,bytes:Buffer.byteLength(xml)}));
