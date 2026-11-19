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


export {Scene, icon, logo, C, OUT, sharp, fs, ROOT};
