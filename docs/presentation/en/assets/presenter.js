/* Script-first presenter console; previews use the audience renderer. */
(() => {
  'use strict';
  const config=window.DLI_CONTROLLER_CONFIG;if(!config)return;
  const course=window.DLI_COURSE,scripts=window.DLI_SCRIPT,template=document.documentElement.outerHTML;
  const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const $=s=>document.querySelector(s);
  const id=decodeURIComponent(location.hash.slice(1));
  let current=Math.max(0,course.slides.findIndex(s=>s.id===id)),active=0,working=false,state=null,lastDisplay=0,displayWindow=window.opener,toolsSignature='';
  let channel;
  try{channel=new BroadcastChannel('so101-dli-'+(config.edition||'self_env')+'-'+config.sessionKey);}catch{}
  document.body.className='script-presenter';
  document.body.innerHTML=`<header class="presenter-top"><a class="presenter-brand" href="#" aria-label="Go to cover"><img src="guide/_static/nvidia-logo-horiz-rgb-blk-for-screen.svg" alt="NVIDIA"><span>AI DAYS SEOUL 2026 <i>/</i> ${esc((config.edition||'self_env').toUpperCase())}</span></a><nav><span id="presenter-connection" role="status">Waiting for presentation connection</span><button id="open-display">Open presentation ↗</button><button id="presenter-agenda">Contents</button><button id="presenter-fullscreen">Fullscreen</button></nav></header>
    <main class="presenter-workspace"><section class="script-main" aria-label="Presenter Script"><header class="script-heading"><div class="script-eyebrow">PRESENTER SCRIPT <span id="script-position"></span></div><h1 id="script-title"></h1><p id="script-meta"></p></header><div id="script-scroll" tabindex="0"><div class="script-instructions">Use ← / → for previous/next cues. Buttons within the script also control the presentation.</div><div id="script-content"></div></div><footer class="script-footer"><span id="cue-position"></span><div><button id="previous-cue" aria-keyshortcuts="ArrowLeft">← Previous explanation</button><button id="next-cue" class="primary" aria-keyshortcuts="ArrowRight">Run next cue →</button></div></footer></section>
    <aside class="presenter-side" aria-label="Slide previews and controls"><section class="preview-card current-card"><header><strong><span class="live-dot"></span>Current slide</strong><span id="current-number"></span></header><div class="preview-viewport" id="current-viewport"><iframe id="current-preview" tabindex="-1" title="Current slide preview" allow="autoplay; fullscreen"></iframe></div><p id="current-selection"></p></section><section class="preview-card next-card"><header><strong>Next slide</strong><button id="advance-slide">Next slide →</button></header><div class="preview-viewport" id="next-viewport"><iframe id="next-preview" title="Next slide preview" tabindex="-1"></iframe></div><p id="next-title"></p></section>
    <div class="presenter-slide-nav"><button id="previous-slide">← Previous slide</button><label><input id="presenter-page" type="number" min="1" max="${course.slides.length}" aria-label="Slide number"> / ${course.slides.length}</label><span id="presenter-clock"></span></div>
    <details class="presenter-tools" open><summary>Display controls</summary><div class="tool-row"><button data-tool="top">Content top</button><button data-tool="up">↑ Scroll</button><button data-tool="down">↓ Scroll</button><button data-tool="bottom">Content bottom</button></div><div class="tool-row"><button data-tool="popup-close">Close popup</button><button data-tool="popup-up">Popup ↑</button><button data-tool="popup-down">Popup ↓</button><button data-tool="blank">Blank screen</button></div><div class="tool-row presenter-timer"><span id="presenter-elapsed">00:00</span><button data-tool="timer-toggle">Start/pause timer</button><button data-tool="timer-reset">Reset</button></div><div id="live-controls"></div></details><div id="presenter-status" role="status" aria-live="polite">The first cue is selected. Continue with Run next cue.</div></aside></main>
    <dialog id="presenter-outline"><header><h2>Slides and presenter script</h2><button id="close-outline">Close</button></header><input id="outline-search" type="search" placeholder="Search titles" aria-label="Search slides"><div id="outline-items"></div></dialog>`;
  const currentFrame=$('#current-preview'),nextFrame=$('#next-preview');
  function frameHTML(role,index){
    const d=new DOMParser().parseFromString(template,'text/html');
    const base=d.createElement('base');base.href=new URL('.',config.base).href;d.head.prepend(base);
    const setup=d.createElement('script');
    setup.textContent='window.DLI_EMBED_CONFIG='+JSON.stringify({role,index,base:config.base,query:'session='+encodeURIComponent(config.sessionKey)}).replace(/</g,'\\u003c')+';';
    d.head.prepend(setup);
    return '<!doctype html>'+d.documentElement.outerHTML;
  }
  function resizePreviews(){
    const workspace=$('.presenter-workspace'),side=$('.presenter-side');
    // Measure the reference layout before assigning the freed width to the script.
    workspace.style.removeProperty('grid-template-columns');
    side.style.setProperty('--preview-scrollbar',(side.offsetWidth-side.clientWidth)+'px');
    const nextWidth=nextFrame.parentElement.getBoundingClientRect().width;
    const sideStyle=getComputedStyle(side);
    const padding=parseFloat(sideStyle.paddingLeft||0)+parseFloat(sideStyle.paddingRight||0);
    const availableWidth=side.clientWidth-padding-2;
    const currentWidth=Math.min(nextWidth*1.5,availableWidth)*0.8;
    $('.current-card').style.width=(currentWidth+2)+'px';
    if(getComputedStyle(workspace).display==='grid'){
      const chrome=side.offsetWidth-side.clientWidth+padding;
      const previewWidth=Math.max(currentWidth+2,$('.next-card').getBoundingClientRect().width);
      workspace.style.gridTemplateColumns=`minmax(0,1fr) ${Math.ceil(previewWidth+chrome)}px`;
    }
    for(const f of [currentFrame,nextFrame])f.style.transform=`scale(${f.parentElement.getBoundingClientRect().width/1600})`;
  }
  const previewResize=new ResizeObserver(resizePreviews);
  previewResize.observe($('.presenter-workspace'));
  window.addEventListener('resize',resizePreviews);
  const scriptScroll=$('#script-scroll');
  // Leave room below the last card so it can use the same reading position.
  new ResizeObserver(()=>{$('#script-content').style.paddingBottom=Math.ceil(scriptScroll.clientHeight*.6)+'px';}).observe(scriptScroll);
  function previewAPI(){return currentFrame.contentWindow?.DLI_PRESENTATION;}
  async function controller(){for(let i=0;i<160;i++){const c=currentFrame.contentWindow?.DLI_CONTROL;if(c)return c;await new Promise(r=>setTimeout(r,25));}throw Error("Preview is loading. Please try again shortly.");}
  const sentenceSplitter=typeof Intl.Segmenter==='function'?new Intl.Segmenter('en',{granularity:'sentence'}):null;
  function safeNotes(html){
    const d=new DOMParser().parseFromString(html,'text/html');
    d.querySelectorAll('script,style,iframe,video,img,button,input,select,textarea').forEach(n=>n.remove());
    d.querySelectorAll('[id]').forEach(n=>n.removeAttribute('id'));
    d.querySelectorAll('a').forEach(n=>{n.target='_blank';n.rel='noopener';});
    // Authored narration is plain paragraphs. Keep its exact text, including
    // technical punctuation, and give each spoken sentence its own reading line.
    if(sentenceSplitter)for(const p of d.querySelectorAll('p')){
      if(p.children.length)continue;
      const sentences=[...sentenceSplitter.segment(p.textContent)];
      p.replaceChildren(...sentences.map(({segment})=>{
        const line=d.createElement('span');line.className='spoken-sentence';line.textContent=segment;return line;
      }));
    }
    return d.body.innerHTML;
  }
  function renderScript(){
    const slide=course.slides[current],session=course.sessions.find(s=>s.id===slide.session),script=scripts[current];
    // Navigation already displays the opening cue. Start there on every visit,
    // matching the audience renderer's reset to its opening pane and media.
    active=0;
    $('#script-title').textContent=slide.title;$('#script-position').textContent=`${current+1} / ${course.slides.length}`;
    $('#script-meta').textContent=[session.time,session.instructor,slide.teaching_type].filter(s=>s&&s!=='—').join(' · ');
    $('#current-number').textContent=String(current+1).padStart(2,'0');$('#presenter-page').value=current+1;
    $('#script-content').innerHTML=script.steps.map((step,i)=>`<article class="script-step" id="cue-${i}" data-cue="${i}"><div class="cue-heading"><span>${String(i+1).padStart(2,'0')}</span><h2>${esc(step.title)}</h2></div><div class="speaker-prose">${safeNotes(step.html)}</div><div class="cue-actions">${step.actions.map((a,j)=>`<button data-cue-action="${i}:${j}" ${j===0?'class="cue-primary"':''}><span aria-hidden="true">${j===0?'▶':'↗'}</span>${esc(a.label)}</button>`).join('')}</div></article>`).join('');
    $('#script-scroll').scrollTop=0;highlight(false);
    const next=course.slides[current+1];$('#advance-slide').disabled=!next;$('#previous-slide').disabled=current===0;
    $('#next-title').textContent=next?`${current+2}. ${next.title}`:"This is the final slide.";
    nextFrame.hidden=!next;
    if(next)nextFrame.srcdoc=frameHTML('next',current+1);
    history.replaceState(null,'','?'+new URLSearchParams({presenter:'1',session:config.sessionKey,v:'102'})+'#'+slide.id);
    document.title="Presenter Script · "+slide.title;
  }
  function transitionCue(index=active){
    const steps=scripts[current].steps;
    return index===steps.length-1&&steps[index]?.actions[0]?.action.kind==='slide';
  }
  function highlight(scroll=true){
    document.querySelectorAll('.script-step').forEach((n,i)=>{n.classList.toggle('active',i===active);if(i===active)n.setAttribute('aria-current','step');else n.removeAttribute('aria-current');});
    $('#cue-position').textContent=active<0?`Explanation ${scripts[current].steps.length} cues · Not started`:`Explanation ${active+1} / ${scripts[current].steps.length}`;
    $('#previous-cue').disabled=working||active<=0;
    $('#next-cue').disabled=working||(active>=scripts[current].steps.length-1&&!transitionCue());
    $('#next-cue').textContent=transitionCue()?"Next slide →":"Run next cue →";
    if(scroll&&active>=0){
      const card=$('#cue-'+active),box=scriptScroll.getBoundingClientRect(),rect=card?.getBoundingClientRect();
      if(rect){
        const inset=Math.max(16,scriptScroll.clientHeight*.4-rect.height/2);
        scriptScroll.scrollTo({top:scriptScroll.scrollTop+rect.top-box.top-inset,behavior:'smooth'});
      }
    }
  }
  function receive(data){
    state=data;
    if(Number.isInteger(data.current)&&data.current!==current){current=data.current;renderScript();}
    if(data.role==='display')lastDisplay=Date.now();
    const slide=course.slides[current],pane=slide.panes?.[data.activePane]||slide.rail_overview;
    $('#current-selection').textContent=pane?.label||pane?.source_title||slide.title;
    updateConnection();setTimeout(updateControls,60);
  }
  function updateConnection(){const connected=Date.now()-lastDisplay<7500;$('#presenter-connection').textContent=connected?"Presentation connected":"Preview · Waiting for presentation connection";$('#presenter-connection').classList.toggle('connected',connected);}
  async function run(action,cueIndex=null){
    if(working)return;working=true;highlight(false);$('#presenter-status').classList.remove('error');$('#presenter-status').textContent="Updating the presentation…";
    const at=current;
    try{
      const c=await controller();await c.run(action);
      const snap=previewAPI().captureState();receive(snap);
      if(at===current&&cueIndex!==null)active=cueIndex;
      $('#presenter-status').textContent="Presentation updated.";
    }catch(e){$('#presenter-status').textContent=e.message;$('#presenter-status').classList.add('error');}
    finally{working=false;highlight(cueIndex!==null);updateControls();}
  }
  function nextCue(delta){
    if(working)return;
    const steps=scripts[current].steps,i=Math.max(0,Math.min(steps.length-1,active+delta));
    if(i===active){
      if(delta>0&&transitionCue())return run(steps[i].actions[0].action,i);
      return;
    }
    // Read the final transition card before executing its slide-change action.
    if(transitionCue(i)){
      active=i;highlight();
      $('#presenter-status').classList.remove('error');
      $('#presenter-status').textContent="This is the last cue. Press again to move to the next slide.";
      return;
    }
    return run(steps[i].actions[0].action,i);
  }
  const toolActions={'timer-toggle':{kind:'timer',operation:'toggle'},'timer-reset':{kind:'timer',operation:'reset'},top:{kind:'scroll',fraction:0},up:{kind:'scroll',delta:-1},down:{kind:'scroll',delta:1},bottom:{kind:'scroll',fraction:1},'popup-close':{kind:'close'},'popup-up':{kind:'scroll',scope:'popup',delta:-1},'popup-down':{kind:'scroll',scope:'popup',delta:1}};
  function updateControls(){
    const c=currentFrame.contentWindow?.DLI_CONTROL,a=previewAPI();if(!c||!a||$('#live-controls').contains(document.activeElement))return;
    const root=currentFrame.contentDocument.querySelector('#stage'),frame=root.querySelector('iframe[data-diagram-key]');
    const terms=[...frame?.contentDocument?.querySelectorAll('.hotspot')||[]].map(n=>({term:n.dataset.term,label:n.getAttribute('aria-label')||n.dataset.term}));
    const w=c.widgetControls(),video=root.querySelector('video');
    const signature=JSON.stringify({index:current,pane:a.pane,media:a.media,w,terms,video:!!video});if(signature===toolsSignature)return;toolsSignature=signature;
    $('#live-controls').innerHTML=(terms.length?"<div class=\"live-control-group\"><h3>Diagram items</h3><div class=\"tool-row\">"+terms.map(t=>`<button data-term="${esc(t.term)}">${esc(t.label)}</button>`).join('')+"<button data-term=\"\">Clear selection</button></div></div>":'')+
      (video?"<div class=\"live-control-group\"><h3>Video</h3><div class=\"tool-row\"><button data-video=\"play\">Play</button><button data-video=\"pause\">Pause</button><button data-video=\"replay\">Restart</button></div><label>Seek time (seconds)<input type=\"number\" min=\"0\" step=\"1\" id=\"video-seek\"><button id=\"video-seek-go\">Go</button></label></div>":'')+
      (w?'<div class="live-control-group"><h3>Interactive Controls</h3><div class="tool-row">'+w.tabs.map(t=>`<button data-widget-tab="${esc(t.id)}" aria-pressed="${t.selected}">${esc(t.label)}</button>`).join('')+'</div>'+w.fields.map(f=>`<label>${esc(f.label)}${f.type==='select'?`<select data-widget-input="${esc(f.selector)}">${f.options.map(o=>`<option value="${esc(o.value)}" ${o.value===f.value?'selected':''}>${esc(o.label)}</option>`).join('')}</select>`:`<input data-widget-input="${esc(f.selector)}" type="${esc(f.type)}" value="${esc(f.value)}" min="${esc(f.min)}" max="${esc(f.max)}" step="${esc(f.step||1)}">`}</label>`).join('')+w.reset.map(r=>`<button data-widget-reset="${esc(r.selector)}">${esc(r.label)}</button>`).join('')+w.files.map(f=>`<label>${esc(f.label)}<input type="file" accept="image/png,image/jpeg,image/webp" data-widget-upload="${esc(f.selector)}"></label>`).join('')+'</div>':'');
  }
  document.addEventListener('click',event=>{
    const cue=event.target.closest('[data-cue-action]');if(cue){const [i,j]=cue.dataset.cueAction.split(':').map(Number);run(scripts[current].steps[i].actions[j].action,i);return;}
    const tool=event.target.closest('[data-tool]');if(tool){const action=tool.dataset.tool==='blank'?{kind:'blank',hidden:!!state?.control?.blank}:{...toolActions[tool.dataset.tool]};if(action.scope==='popup'&&state?.objectivesOpen)action.scope='objectives';run(action);return;}
    const term=event.target.closest('[data-term]');if(term){run({kind:'diagram',term:term.dataset.term});return;}
    const v=event.target.closest('[data-video]');if(v){run({kind:'video',operation:v.dataset.video});return;}
    const tab=event.target.closest('[data-widget-tab]');if(tab){run({kind:'widget',tab:tab.dataset.widgetTab});return;}
    const reset=event.target.closest('[data-widget-reset]');if(reset){run({kind:'widget',operation:'click',selector:reset.dataset.widgetReset});return;}
    const jump=event.target.closest('[data-slide]');if(jump){$('#presenter-outline').close();run({kind:'slide',index:Number(jump.dataset.slide)});return;}
    if(event.target.id==='video-seek-go')run({kind:'video',operation:'seek',time:Number($('#video-seek').value)});
  });
  document.addEventListener('change',e=>{if(e.target.dataset.widgetUpload){const file=e.target.files[0];if(file){const reader=new FileReader();reader.onload=()=>run({kind:'widget-file',selector:e.target.dataset.widgetUpload,file:{name:file.name,type:file.type,data:reader.result}});reader.readAsDataURL(file);}return;}if(e.target.dataset.widgetInput)run({kind:'widget',selector:e.target.dataset.widgetInput,value:e.target.value,checked:e.target.checked});});
  $('#next-cue').onclick=()=>nextCue(1);$('#previous-cue').onclick=()=>nextCue(-1);
  $('#advance-slide').onclick=()=>run({kind:'slide',index:current+1});$('#previous-slide').onclick=()=>run({kind:'slide',index:current-1});
  $('#presenter-page').onchange=e=>run({kind:'slide',index:Math.min(course.slides.length-1,Math.max(0,Number(e.target.value)-1))});
  $('.presenter-brand').onclick=e=>{e.preventDefault();run({kind:'slide',index:0});};
  function outline(query=''){const filtered=course.slides.filter(s=>s.title.toLowerCase().includes(query.toLowerCase()));$('#outline-items').innerHTML=filtered.map(s=>`<button data-slide="${s.index}" ${s.index===current?'aria-current="page"':''}><span>${String(s.index+1).padStart(2,'0')}</span>${esc(s.title)}</button>`).join('');}
  $('#presenter-agenda').onclick=()=>{outline();$('#presenter-outline').showModal();$('#outline-search').focus();};
  $('#outline-search').oninput=e=>outline(e.target.value);$('#close-outline').onclick=()=>$('#presenter-outline').close();
  $('#presenter-fullscreen').onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();
  $('#open-display').onclick=()=>{
    const url=new URL(config.base);url.searchParams.delete('presenter');url.searchParams.set('session',config.sessionKey);url.hash=course.slides[current].id;
    if(displayWindow&&!displayWindow.closed)displayWindow.focus();else displayWindow=window.open(url.href,'dli-display-'+(config.edition||'self_env')+'-'+config.sessionKey);
    if(!displayWindow){$('#presenter-status').textContent="Allow browser popups, then select Open presentation again.";return;}
    setTimeout(()=>previewAPI()?.sendState(),500);
  };
  function ignoresShortcut(e){
    const target=e.target;
    return e.ctrlKey||e.metaKey||e.altKey||target.isContentEditable||target.closest?.('input,textarea,select,[role="textbox"],[role="slider"],[role="spinbutton"],[role="combobox"]')||$('#presenter-outline').open;
  }
  function cueArrow(e){
    if(!['ArrowRight','ArrowLeft'].includes(e.key)||ignoresShortcut(e))return false;
    e.preventDefault();e.stopPropagation();
    if(!e.repeat)nextCue(e.key==='ArrowRight'?1:-1);
    return true;
  }
  // showModal() focuses the live preview's dialog even though the iframe is
  // excluded from Tab navigation. Forward its arrows before the deck handler.
  function wirePreviewKeys(){
    const preview=currentFrame.contentWindow;
    preview.removeEventListener('keydown',cueArrow,true);
    preview.addEventListener('keydown',cueArrow,true);
  }
  currentFrame.addEventListener('load',wirePreviewKeys);
  document.addEventListener('keydown',e=>{
    if(cueArrow(e)||ignoresShortcut(e)||e.target.closest?.('button,a'))return;
    if(e.key===' '){e.preventDefault();nextCue(1);}
    else if(e.key==='PageDown'){e.preventDefault();run({kind:'slide',index:current+1});}
    else if(e.key==='PageUp'){e.preventDefault();run({kind:'slide',index:current-1});}
    else if(e.key==='Escape')run({kind:'close'});
  });
  window.addEventListener('message',event=>{
    if(event.source!==currentFrame.contentWindow)return;
    if(event.data?.type==='dli:ready'){
      wirePreviewKeys();
      channel?.postMessage({type:'hello',role:'controller'});receive(previewAPI().captureState());
    }else if(event.data?.type==='dli:state')receive(event.data.state);
    else if(event.data?.type==='dli:media-error'){$('#presenter-status').textContent=event.data.message;$('#presenter-status').classList.add('error');}
  });
  if(channel)channel.onmessage=e=>{
    if(e.data.type==='hello'&&e.data.role==='display')previewAPI()?.sendState();
    if(e.data.type==='state')receive(e.data);
    if(e.data.type==='controller-pong'){lastDisplay=Date.now();updateConnection();}
  };
  const heartbeat=setInterval(()=>{const elapsed=Math.floor(((state?.timerSaved||0)+(state?.timerStart?Date.now()-state.timerStart:0))/1000);$('#presenter-elapsed').textContent=String(Math.floor(elapsed/60)).padStart(2,'0')+':'+String(elapsed%60).padStart(2,'0');channel?.postMessage({type:'controller-ping'});updateConnection();$('#presenter-clock').textContent=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date())+' KST';},2500);
  window.addEventListener('beforeunload',()=>{clearInterval(heartbeat);channel?.close();});
  renderScript();currentFrame.srcdoc=frameHTML('current',current);resizePreviews();
  window.DLI_PRESENTER={run,get index(){return current;},get cue(){return active;},get state(){return state;},nextCue,script:scripts};
})();
