/* Shared controls for the audience deck and the presenter's live preview. */
(() => {
  'use strict';
  const api=window.DLI_PRESENTATION;if(!api)return;
  const $=s=>document.querySelector(s),stage=$('#stage');
  const sleep=ms=>new Promise(r=>setTimeout(r,ms));
  let restoring=false,pending=null,queue=Promise.resolve(),syncTimer;
  const uploads=new Map();
  const wired=new WeakSet();
  const slide=()=>api.course.slides[api.index];
  const key=()=>`${api.index}:${api.pane}:${api.media}`;
  const frames=()=>[...stage.querySelectorAll('iframe')].filter(f=>{try{return !!f.contentDocument?.body;}catch{return false;}});
  const roots=()=>[stage,...frames().map(f=>f.contentDocument)];
  const videos=()=>roots().flatMap(r=>[...r.querySelectorAll('video')]);
  const fields=d=>[...d.querySelectorAll('.groot-explorers input,.groot-explorers select,.image-comparison input:not([type=file]),.image-comparison select')];
  const scrollables=d=>[...d.querySelectorAll('.diagram-overview-prose,.panel-content,.detail-panel,.detail-body,.details-body,.detail-content,[tabindex="0"]')].filter(n=>n.scrollHeight>n.clientHeight+3&&['auto','scroll'].includes(d.defaultView.getComputedStyle(n).overflowY));

  function widgetState(d){return {values:fields(d).map(n=>({value:n.value,checked:n.checked})),tab:d.querySelector('.widget-tabs [aria-selected="true"]')?.id,details:[...d.querySelectorAll('details')].map(n=>n.open),scroll:scrollables(d).map(n=>n.scrollTop/Math.max(1,n.scrollHeight-n.clientHeight))};}
  function capture(){
    return {key:key(),reading:api.reading,blank:!$('#blank-screen').hidden,
      objectiveScroll:$('#objectives-body').scrollTop,
      widgets:frames().map(f=>widgetState(f.contentDocument)),uploads:uploads.get(key())||{},
      video:videos().map(v=>({paused:v.paused,time:v.currentTime,muted:v.muted,rate:v.playbackRate,seekId:v.dataset.seekId||'',seekTime:Number(v.dataset.seekTime||0)}))};
  }
  function changed(){if(restoring)return;clearTimeout(syncTimer);syncTimer=setTimeout(()=>api.sendState(),70);}
  function applyUploads(d,files){
    if(!d.querySelector('.image-comparison'))return;
    const previous=d.__dliFiles||{};
    if(Object.keys(previous).some(k=>!files[k]))d.querySelector('button[data-control="reset"]').click();
    for(const [selector,file] of Object.entries(files)){
      if(previous[selector]?.data===file.data)continue;
      const input=d.querySelector(selector);if(!input)continue;
      const data=Uint8Array.from(atob(file.data.split(',')[1]),c=>c.charCodeAt(0));
      const transfer=new d.defaultView.DataTransfer();transfer.items.add(new d.defaultView.File([data],file.name,{type:file.type}));
      input.files=transfer.files;input.dispatchEvent(new d.defaultView.Event('change',{bubbles:true}));
    }
    d.__dliFiles=files;
  }
  function restoreWidgets(state){
    if(!state||state.key!==key())return;
    restoring=true;
    try{
      uploads.set(key(),state.uploads||{});
      frames().forEach((f,i)=>{
        const d=f.contentDocument,w=state.widgets?.[i];applyUploads(d,state.uploads||{});if(!w)return;
        const tab=w.tab&&d.getElementById(w.tab);
        if(tab&&tab.getAttribute('aria-selected')!=='true')tab.click();
        fields(d).forEach((n,j)=>{const v=w.values[j];if(!v)return;if(n.value!==v.value||n.checked!==v.checked){n.value=v.value;if(v.checked!==undefined)n.checked=v.checked;n.dispatchEvent(new f.contentWindow.Event('input',{bubbles:true}));n.dispatchEvent(new f.contentWindow.Event('change',{bubbles:true}));}});
        d.querySelectorAll('details').forEach((n,j)=>{if(w.details[j]!==undefined)n.open=w.details[j];});
        scrollables(d).forEach((n,j)=>{if(w.scroll[j]!==undefined)n.scrollTop=w.scroll[j]*Math.max(0,n.scrollHeight-n.clientHeight);});
      });
      videos().forEach((v,i)=>{
        const stateVideo=state.video?.[i];if(!stateVideo)return;
        v.dataset.syncUntil=String(Date.now()+700);
        v.muted=stateVideo.muted;v.playbackRate=stateVideo.rate;
        if(stateVideo.seekId&&stateVideo.seekId!==v.dataset.seekId)v.currentTime=stateVideo.seekTime;
        else if(!v.dataset.receivedState&&stateVideo.time>0)v.currentTime=stateVideo.time;
        v.dataset.receivedState='true';v.dataset.seekId=stateVideo.seekId||'';v.dataset.seekTime=String(stateVideo.seekTime||0);
        if(stateVideo.paused)v.pause();else if(v.paused)v.play().catch(()=>{});
      });
    }finally{restoring=false;}
  }
  function restore(state){
    if(!state)return;pending=state;restoring=true;
    api.syncSilently(()=>{
      $('#blank-screen').hidden=!state.blank;
      const r=state.reading,current=api.reading;
      if(r){
        if(!current||current.html!==r.html||current.title!==r.title)api.openReading(r.title,r.html,r.context,false);
        $('#reading-body').scrollTop=r.scroll||0;
      }else if($('#reading-dialog').open)$('#reading-dialog').close();
      $('#objectives-body').scrollTop=state.objectiveScroll||0;
    });
    restoring=false;restoreWidgets(state);
  }
  function wire(){
    stage.querySelectorAll('iframe').forEach(f=>{
      if(wired.has(f))return;wired.add(f);
      const ready=()=>{
        let d;try{d=f.contentDocument;}catch{return;}if(!d)return;
        d.addEventListener('input',changed);d.addEventListener('change',event=>{
          if(event.target.type==='file'&&!restoring){const file=event.target.files[0];if(file){const id=key(),reader=new f.contentWindow.FileReader();reader.onload=()=>{const files={...(uploads.get(id)||{}),['input[data-control="'+event.target.dataset.control+'"]']:{data:reader.result,name:file.name,type:file.type}};uploads.set(id,files);d.__dliFiles=files;changed();};reader.readAsDataURL(file);}}else changed();
        });
        d.addEventListener('click',event=>{if(!restoring&&event.target.closest('button[data-control="reset"]')){uploads.delete(key());d.__dliFiles={};}setTimeout(changed,0);});d.addEventListener('scroll',changed,true);
        if(pending)restoreWidgets(pending);
        wireVideos();
        if(d.querySelector('.widget-tabs,.image-comparison,.hotspot'))changed();
      };
      f.addEventListener('load',ready);if(f.contentDocument?.readyState==='complete')ready();
    });wireVideos();
  }
  function wireVideos(){videos().forEach(v=>{
    if(wired.has(v))return;wired.add(v);
    for(const name of ['play','pause','seeked','volumechange','ratechange'])v.addEventListener(name,()=>{if(Number(v.dataset.syncUntil||0)<Date.now()){if(name==='seeked'){v.dataset.seekId=String(Date.now());v.dataset.seekTime=String(v.currentTime);}changed();}});
    v.addEventListener('loadedmetadata',()=>{if(pending)restoreWidgets(pending);});
  });}
  new MutationObserver(wire).observe(stage,{childList:true,subtree:true});wire();
  $('#reading-body').addEventListener('scroll',changed);
  $('#objectives-body').addEventListener('scroll',changed);
  $('#blank-screen').addEventListener('click',changed);
  document.addEventListener('keydown',e=>{if(e.key.toLowerCase()==='b')setTimeout(changed,0);});

  async function readyFrame(){
    for(let i=0;i<120;i++){
      const fs=frames();
      if(fs.some(f=>f.contentDocument.querySelector('.diagram-overview-prose,.widget-tabs,.image-comparison')))return fs[0];
      if(!stage.querySelector('iframe'))return null;
      await sleep(25);
    }
    throw Error('Interactive 화면이 아직 준비되지 않았습니다. 잠시 후 다시 눌러 주세요.');
  }
  function close(){api.setObjectivesOpen(false);$('#reading-dialog').close();api.setSourcePopup(null);}
  async function context(a){
    if(a.slide){const index=api.course.slides.findIndex(s=>s.id===a.slide);if(index<0)throw Error('장표를 찾지 못했습니다.');if(api.index!==index)api.go(index);}
    if(a.pane!==undefined&&api.pane!==a.pane)api.selectPane(a.pane);
    if(a.media!==undefined){
      const s=slide(),cards=['compare','cards','reference'].includes(s.layout)&&s.panes.length<4;
      if(cards)api.setCardMedia(a.pane,a.media);else if(api.media!==a.media)api.selectMedia(a.media);
    }
    if(a.accordion)api.setAccordion(a.accordion.key,a.accordion.item);
    await sleep(35);
  }
  function proseTarget(a){
    if(a.scope==='popup')return {box:$('#reading-body')};
    if(a.scope==='objectives')return {box:$('#objectives-body')};
    const anchor=a.anchor;
    for(const root of roots()){
      const norm=s=>s.replace(/\s+/g,'');
      const scope=anchor&&[...root.querySelectorAll('[id],[data-source-anchor]')].find(n=>n.id===anchor||n.dataset.sourceAnchor===anchor);
      const n=(a.text&&[...(scope||root).querySelectorAll('p,li')].find(n=>norm(n.textContent).startsWith(norm(a.text))))||scope;
      if(n){
        const box=n.closest('.explanation-scroll,.diagram-overview-prose')||n.ownerDocument.scrollingElement;
        return {box,node:n};
      }
    }
    return {box:stage.querySelector(`[data-explanation-pane="${api.pane}"] .explanation-scroll`)||frames()[0]?.contentDocument.querySelector('.diagram-overview-prose')||frames().flatMap(f=>scrollables(f.contentDocument))[0]||$('#slide-content')};
  }
  function scroll(a){
    const {box,node}=proseTarget(a);if(!box)return;
    if(node){
      const scale=node.ownerDocument===document?stage.getBoundingClientRect().width/1600:1;
      box.scrollTop+=Math.max(0,(node.getBoundingClientRect().top-box.getBoundingClientRect().top)/scale)-8;
    }else if(a.fraction!==undefined)box.scrollTop=a.fraction*Math.max(0,box.scrollHeight-box.clientHeight);
    else box.scrollTop+=(a.delta||1)*box.clientHeight*.8;
  }
  async function execute(a){
    if(['show','diagram','scroll','accordion','widget','widget-file','zoom','video'].includes(a.kind)&&a.scope!=='popup'&&a.scope!=='objectives')close();
    await context(a);
    const s=slide(),pane=s.panes?.[a.pane??api.pane]||s.rail_overview;
    switch(a.kind){
      case 'show':break;
      case 'slide':close();api.go(a.index??api.index+(a.delta||1));break;
      case 'objectives':api.setObjectivesOpen(a.open!==false);break;
      case 'close':close();break;
      case 'popup':{
        const p=s.popups.find(p=>p.id===a.id);if(!p)throw Error('연결된 설명을 찾지 못했습니다.');
        api.openReading(p.title,p.html,{page:s.page,anchor:p.anchor,sourcePopup:p.id,tablePopup:p.kind==='table',reportPopup:p.kind==='report'});break;
      }
      case 'command':{
        const d=new DOMParser().parseFromString(pane.full,'text/html'),blocks=d.querySelectorAll('pre');
        const indices=(a.blocks||String(a.index||0)).split(',').map(Number);
        const html=indices.map(i=>blocks[i]?.outerHTML||'').join('');
        if(!html)throw Error('명령·출력 내용을 찾지 못했습니다.');
        api.openReading('명령·출력',html,{page:s.page,anchor:pane.anchor});break;
      }
      case 'table':{
        const d=new DOMParser().parseFromString(pane.full,'text/html'),tables=d.querySelectorAll('table');
        const indices=(a.blocks||String(a.index??0)).split(',').map(Number);
        const selected=indices.map(i=>tables[i]);
        if(selected.some(table=>!table))throw Error('연결된 표를 찾지 못했습니다.');
        api.openReading(pane.source_title,selected.map(table=>table.outerHTML).join(''),{page:s.page,anchor:pane.anchor,tablePopup:true});break;
      }
      case 'zoom':{
        const images=roots().flatMap(r=>[...r.querySelectorAll('#slide-content img,.diagram img')]),img=images[a.image||0];
        if(img)api.openReading(img.alt||s.title,img.outerHTML);else throw Error('확대할 이미지를 찾지 못했습니다.');break;
      }
      case 'diagram':await readyFrame();api.setDiagram(a.term||'');await sleep(30);break;
      case 'scroll':if(stage.querySelector('iframe[data-diagram-key]')){await readyFrame();if(a.anchor)api.setDiagram('');}scroll(a);break;
      case 'accordion':api.setAccordion(a.group,a.item||null);break;
      case 'video':{
        const v=videos()[a.video||0];if(!v)throw Error('이 화면에는 직접 제어할 로컬 영상이 없습니다.');
        v.muted=true;
        const play=()=>v.play().catch(error=>{if(error.name!=='AbortError'&&window.DLI_EMBED_CONFIG)parent.postMessage({type:'dli:media-error',message:'영상 재생을 시작하지 못했습니다. 발표 창의 재생 버튼을 확인해 주세요.'},'*');});
        if(a.operation==='play')play();else if(a.operation==='pause')v.pause();
        else if(a.operation==='replay'||a.operation==='seek'){
          const time=a.operation==='replay'?0:Math.min(v.duration||Infinity,Math.max(0,a.time));
          v.dataset.seekId=String(Date.now());v.dataset.seekTime=String(time);v.currentTime=time;
          if(a.operation==='replay')play();
        }
        break;
      }
      case 'widget':{
        const f=await readyFrame(),d=f?.contentDocument;if(!d)throw Error('Widget이 준비되지 않았습니다.');
        if(a.tab){const n=d.getElementById(a.tab);if(n)n.click();}
        if(a.selector){const n=d.querySelector(a.selector);if(!n)throw Error('Widget control을 찾지 못했습니다.');
          if(a.operation==='click')n.click();else{n.value=String(a.value);if(a.checked!==undefined)n.checked=a.checked;n.dispatchEvent(new f.contentWindow.Event('input',{bubbles:true}));n.dispatchEvent(new f.contentWindow.Event('change',{bubbles:true}));}}
        break;
      }
      case 'widget-file':{
        const f=await readyFrame(),files={...(uploads.get(key())||{}),[a.selector]:a.file};
        uploads.set(key(),files);restoring=true;try{applyUploads(f.contentDocument,files);}finally{restoring=false;}await sleep(150);break;
      }
      case 'blank':$('#blank-screen').hidden=a.hidden===true;break;
      case 'timer':$(a.operation==='reset'?'#reset-timer':'#timer-button').click();break;
      default:throw Error('지원하지 않는 발표 조작입니다: '+a.kind);
    }
    await sleep(110);
  }
  function run(actions){
    const work=()=>api.batch(async()=>{pending=null;for(const a of Array.isArray(actions)?actions:[actions])await execute(a);return api.captureState();});
    const result=queue.then(work);queue=result.catch(()=>{});return result;
  }
  function widgetControls(){
    const f=frames().find(f=>f.contentDocument.querySelector('.widget-tabs,.image-comparison'));if(!f)return null;
    const d=f.contentDocument;
    return {tabs:[...d.querySelectorAll('.widget-tabs button')].map(b=>({id:b.id,label:b.textContent,selected:b.getAttribute('aria-selected')==='true'})),
      fields:fields(d).filter(n=>n.getClientRects().length).map(n=>({selector:n.id?'#'+n.id:'[data-control="'+n.dataset.control+'"]',label:n.closest('label')?.childNodes[0]?.textContent.trim()||n.getAttribute('aria-label')||n.id||n.dataset.control,type:n.tagName==='SELECT'?'select':n.type,value:n.value,min:n.min,max:n.max,step:n.step,options:[...n.options||[]].map(o=>({value:o.value,label:o.text}))})),
      files:[...d.querySelectorAll('.image-comparison input[type=file]')].map(n=>({selector:'input[data-control="'+n.dataset.control+'"]',label:n.dataset.control.startsWith('real')?'Real 이미지 선택':'Sim 이미지 선택'})),
      reset:[...d.querySelectorAll('.groot-reset,.image-comparison button[data-control]')].filter(n=>!n.hidden).map(n=>({selector:n.id?'#'+n.id:n.dataset.control?'button[data-control="'+n.dataset.control+'"]':'.groot-reset:not([hidden])',label:n.classList.contains('groot-reset')||n.dataset.control==='reset'?'Reset':n.textContent}))};
  }
  window.DLI_CONTROL={run,capture,restore,widgetControls};
  if(window.DLI_PENDING_CONTROL){restore(window.DLI_PENDING_CONTROL);delete window.DLI_PENDING_CONTROL;}
  if(window.DLI_EMBED_CONFIG)parent.postMessage({type:'dli:ready',role:window.DLI_EMBED_CONFIG.role},'*');
})();
