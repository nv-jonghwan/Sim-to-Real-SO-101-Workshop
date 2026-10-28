// Exercise the actual built iframes and dynamic prose via Chrome DevTools.
// Usage: node verify_interactive.mjs http://127.0.0.1:8095
import {spawn} from 'node:child_process';
import {mkdtemp,mkdir,readFile,writeFile,readdir,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const repo=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
await mkdir(repo+'/.local',{recursive:true});
const base=process.argv[2] || 'http://127.0.0.1:8095';
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const profile=await mkdtemp(join(tmpdir(),'so101-interactive-chrome-'));
const chrome=spawn(process.env.CHROME || '/usr/bin/google-chrome',['--headless=new','--disable-gpu','--remote-debugging-port=0',`--user-data-dir=${profile}`,'--no-first-run','--no-default-browser-check','--window-size=1440,1000','about:blank'],{stdio:'ignore'});
let ws,seq=0;const pending=new Map();
const report={base,contexts:[],errors:[],screenshots:[]};
function check(ok,message){if(!ok)throw new Error(message);}
function send(method,params={}){return new Promise((resolve,reject)=>{const id=++seq;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('CDP timeout '+method));},20000);pending.set(id,m=>{clearTimeout(timer);m.error?reject(new Error(JSON.stringify(m.error))):resolve(m.result);});ws.send(JSON.stringify({id,method,params}));});}
async function evaluate(expression){const v=await send('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(v.exceptionDetails)throw new Error(JSON.stringify(v.exceptionDetails));return v.result.value;}
async function navigate(path){await send('Page.navigate',{url:base+path});for(let i=0;i<80;i++){if(await evaluate('document.readyState === "complete"'))return;await pause(100);}throw new Error('Page load timeout '+path);}
try{
 let port;for(let i=0;i<100;i++){try{port=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];break;}catch{await pause(100);}}
 check(port,'Chrome startup failed');
 const target=await(await fetch(`http://127.0.0.1:${port}/json/new?about:blank`,{method:'PUT'})).json();
 ws=new WebSocket(target.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j;});
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){pending.get(m.id)?.(m);pending.delete(m.id);}else if(m.method==='Runtime.exceptionThrown')report.errors.push(m.params.exceptionDetails);};
 await send('Page.enable');await send('Runtime.enable');await send('Network.enable');await send('Network.setCacheDisabled',{cacheDisabled:true});
 const pages=[];
 for(const name of (await readdir(repo+'/docs')).sort()){
  if(!name.endsWith('.md'))continue;
  const source=await readFile(repo+'/docs/'+name,'utf8');
  if(source.includes('_static/interactive/')||source.includes('_includes/wrist-image-comparison'))pages.push(name.replace(/\.md$/,'.html'));
 }
 for(const prefix of ['/ko/event/html/','/ko/learner/html/','/ko/instructor/html/','/event/html/','/learner/html/','/instructor/html/']){
  const korean=prefix.startsWith('/ko/');const context={prefix,pages:0,diagrams:0,selections:0,dynamicChecks:[]};report.contexts.push(context);
  for(const page of pages){
   await navigate(prefix+page);context.pages++;
   const result=await evaluate(`(async()=>{
    const korean=${korean};const errors=[];let selections=0;let diagrams=0;
    const delay=ms=>new Promise(r=>setTimeout(r,ms));
    const assert=(ok,message)=>{if(!ok)errors.push(message);};
    const hasKo=text=>/[가-힣]/.test(text);
    for(const frame of document.querySelectorAll('iframe.interactive-learning-diagram')){
     frame.scrollIntoView({behavior:'instant',block:'center'});
     for(let i=0;i<100&&!frame.contentDocument?.querySelector('.is-enhanced');i++)await delay(50);
     const doc=frame.contentDocument,root=doc?.querySelector('#interactive-learning-diagram');
     assert(root?.classList.contains('is-enhanced'),'iframe not enhanced '+frame.src);if(!root)continue;diagrams++;
     assert(doc.documentElement.lang===(korean?'ko':'en'),'iframe language '+frame.src);
     for(const hotspot of doc.querySelectorAll('.hotspot')){
      hotspot.dispatchEvent(new frame.contentWindow.MouseEvent('click',{bubbles:true,cancelable:true}));
      const selected=doc.querySelector('[data-definition="'+hotspot.dataset.term+'"]');selections++;
      assert(selected&&!selected.hidden,'selection missing '+frame.src+' '+hotspot.dataset.term);
      assert(hotspot.getAttribute('aria-expanded')==='true','selection aria-expanded');
      if(korean){
       for(const p of selected.querySelectorAll('p')){
        const clone=p.cloneNode(true);clone.querySelectorAll('code').forEach(c=>c.remove());const text=clone.textContent.trim();
        const technical=/^(?:[\\s.,;:]*|vial_grasped\\.|Training loop · Loss, optimizer, learning rate|GR00T 1.7 · (?:Vision-language backbone|Flow-matching action head))$/.test(text);
        assert(!text||technical||hasKo(text),'untranslated '+frame.src+': '+text);
       }
       assert(hasKo(doc.getElementById('selection-status').textContent),'selection announcement English');
      }else assert(!hasKo(selected.textContent),'English panel unexpectedly Korean');
      // Allow the iframe's ResizeObserver/postMessage to update its parent height.
      await delay(45);
      const size=root.getBoundingClientRect();
      if(frame.clientHeight+3<size.height){await delay(100);assert(frame.clientHeight+3>=root.getBoundingClientRect().height,'iframe clipped '+frame.src);}
      const explanations=doc.querySelector('.explanations').getBoundingClientRect();
      assert(explanations.right<=frame.clientWidth+2,'explanation horizontal overflow '+frame.src);
     }
     doc.getElementById('clear-selection').click();assert(!doc.getElementById('empty-prompt').hidden,'close did not reset');
     const first=doc.querySelector('.hotspot');first.focus();first.dispatchEvent(new frame.contentWindow.KeyboardEvent('keydown',{key:'Enter',bubbles:true,cancelable:true}));
     assert(first.getAttribute('aria-expanded')==='true','keyboard selection failed');
     doc.dispatchEvent(new frame.contentWindow.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
     assert(!doc.getElementById('empty-prompt').hidden,'Escape did not reset');
     const batch=doc.getElementById('batch');
     if(batch){doc.getElementById('batch').value='64';doc.getElementById('gpus').value='4';doc.getElementById('horizon').value='8';batch.dispatchEvent(new frame.contentWindow.Event('change',{bubbles:true}));const text=doc.getElementById('batch-result').textContent;assert(text.includes('256')&&text.includes('2048')&&text.includes('0.27')&&text.includes('0.23'),'training-step calculation incorrect');assert(hasKo(text)===korean,'training-step dynamic language incorrect');}
    }
    assert(document.documentElement.scrollWidth<=innerWidth+2,'parent horizontal overflow');
    return {diagrams,selections,errors};
   })()`);
   context.diagrams+=result.diagrams;context.selections+=result.selections;check(!result.errors.length,result.errors.join('\n'));
   if(page==='10-groot.html'){
    const dynamic=await evaluate(`(()=>{
     const el=id=>document.getElementById(id);const change=(id,value,event)=>{el(id).value=value;el(id).dispatchEvent(new Event(event,{bubbles:true}));};
     change('groot-batch','64','change');change('groot-gpus','4','change');change('groot-steps','10000','change');change('groot-horizon','8','input');
     const result={batch:el('groot-effective-batch').textContent,total:el('groot-total-windows').textContent,repeat:el('groot-repeat-label').textContent,coverage:el('groot-coverage').textContent,tail:el('groot-tail').textContent,tooltip:el('groot-action-window').firstElementChild.title};
     el('groot-training').querySelector('button').click();el('groot-inference').querySelector('button').click();result.resetBatch=el('groot-effective-batch').textContent;result.resetCoverage=el('groot-coverage').textContent;result.resetTail=el('groot-tail').textContent;return result;
    })()`);
    check(dynamic.batch==='256'&&dynamic.total==='2,560,000'&&dynamic.coverage==='267 ms'&&dynamic.tail.includes('3.75'),'groot values '+JSON.stringify(dynamic));
    check(dynamic.resetBatch==='32'&&dynamic.resetCoverage==='533 ms'&&dynamic.resetTail.includes('1.88'),'groot reset failed');
    for(const key of ['repeat','tail','tooltip','resetTail'])check(/[가-힣]/.test(dynamic[key])===korean,'groot language '+key);
    context.dynamicChecks.push({page,...dynamic});
    if(prefix==='/ko/event/html/'){
     const clip=await evaluate(`(()=>{const f=[...document.querySelectorAll('iframe')].find(f=>f.src.endsWith('/groot-training-step.html'));const d=f.contentDocument;d.querySelector('[data-term="targets"]').dispatchEvent(new d.defaultView.MouseEvent('click',{bubbles:true,cancelable:true}));f.scrollIntoView({behavior:'instant',block:'start'});const b=f.getBoundingClientRect();return {x:b.x+scrollX,y:b.y+scrollY,width:b.width,height:Math.min(1100,b.height),scale:1};})()`);
     await pause(200);const shot=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip});const output=repo+'/.local/docs-ko-interactive-preview.png';await writeFile(output,Buffer.from(shot.data,'base64'));report.screenshots.push(output);
    }
   }
   if(await evaluate('!!document.querySelector(".image-comparison")')){
    const images=await evaluate(`(async()=>{const results=[];for(const root of document.querySelectorAll('.image-comparison')){await Promise.all([...root.querySelectorAll('img')].map(i=>i.decode()));const c=n=>root.querySelector('[data-control="'+n+'"]');const status=()=>root.querySelector('[role=status]').textContent;const states=[];for(const mode of ['side','real','sim','overlay']){c('mode').value=mode;c('mode').dispatchEvent(new Event('change',{bubbles:true}));states.push(status());}c('opacity').value='25';c('opacity').dispatchEvent(new Event('input',{bubbles:true}));const opacity=c('value').textContent;c('toggle').click();const toggled=c('mode').value;c('reset').click();await new Promise(r=>setTimeout(r,50));results.push({states,opacity,toggled,resetMode:c('mode').value,resetOpacity:c('value').textContent});}return results;})()`);
    for(const image of images){check(image.opacity==='25%'&&image.toggled==='real'&&image.resetMode==='overlay'&&image.resetOpacity==='50%','image controls failed');check(image.states.every(s=>/[가-힣]/.test(s)===korean),'image status language failed');}
    context.dynamicChecks.push({page,images});
   }
  }
  check(context.diagrams===20,'not all 20 diagrams tested: '+context.diagrams);
  console.log(JSON.stringify({prefix,pages:context.pages,diagrams:context.diagrams,selections:context.selections}));
 }
 // Narrow viewport checks on long explanations and responsive controls.
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
 await navigate('/ko/event/html/10-groot.html');
 const mobile=await evaluate(`(async()=>{const f=[...document.querySelectorAll('iframe')].find(f=>f.src.endsWith('/groot-training-step.html'));f.scrollIntoView({behavior:'instant'});for(let i=0;i<100&&!f.contentDocument?.querySelector('.is-enhanced');i++)await new Promise(r=>setTimeout(r,50));const d=f.contentDocument;d.querySelector('[data-term="targets"]').dispatchEvent(new d.defaultView.MouseEvent('click',{bubbles:true,cancelable:true}));await new Promise(r=>setTimeout(r,250));const p=d.querySelector('.explanations').getBoundingClientRect();return {width:innerWidth,scrollWidth:document.documentElement.scrollWidth,frameWidth:f.clientWidth,explanationRight:p.right,frameHeight:f.clientHeight,contentHeight:d.querySelector('main').getBoundingClientRect().height};})()`);
 check(mobile.explanationRight<=mobile.frameWidth+2&&mobile.contentHeight<=mobile.frameHeight+3,'narrow explanation clipped '+JSON.stringify(mobile));
 await navigate('/event/html/10-groot.html');
 mobile.englishPageScrollWidth=await evaluate('document.documentElement.scrollWidth');
 if(mobile.scrollWidth>mobile.width+2){
  check(mobile.englishPageScrollWidth>mobile.width+2,'new Korean-only page overflow');
  mobile.note='The full GR00T page has pre-existing narrow-screen overflow in both languages. Translated iframe explanations fit horizontally and vertically; general theme/table layout is outside this localization change.';
 }
 report.narrowViewport=mobile;
 check(!report.errors.length,'Browser JavaScript errors');report.passed=true;
}catch(error){report.passed=false;report.failure=String(error);process.exitCode=1;}
finally{
 await writeFile(repo+'/.local/docs-interactive-browser.json',JSON.stringify(report,null,2));
 if(ws)ws.close();chrome.kill('SIGTERM');await pause(200);await rm(profile,{recursive:true,force:true,maxRetries:4,retryDelay:200});
}
console.log(JSON.stringify({passed:report.passed,failure:report.failure,contexts:report.contexts.length,errors:report.errors.length,narrowViewport:report.narrowViewport}));
