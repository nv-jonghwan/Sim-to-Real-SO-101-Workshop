/* Presentation controls. Lesson text and interactive assets remain in the copied guide. */
(() => {
  'use strict';
  const course = window.DLI_COURSE;
  const edition = course.edition || 'self_env';
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const stage = $('#stage');
  const embed = window.DLI_EMBED_CONFIG;
  const pageURL = embed?.base || location.href;
  const params = new URLSearchParams(embed?.query || location.search);
  const presenter = params.get('presenter') === '1';
  const sessionKey = params.get('session') || (crypto.randomUUID?.() ?? Date.now().toString(36)+Math.random().toString(36).slice(2));
  params.set('session', sessionKey);
  if(!embed)history.replaceState(null, '', '?' + params + location.hash);
  if(presenter&&!embed){window.DLI_CONTROLLER_CONFIG={sessionKey,base:pageURL,edition};return;}
  let channel = null;
  try { if (typeof BroadcastChannel !== 'undefined'&&embed?.role!=='next') channel = new BroadcastChannel('so101-dli-' + edition + '-' + sessionKey); } catch {}
  let stateMuted=0,receivingState=false;
  const slides = course.slides;
  const objectivesForPage = new Map(slides.filter(s=>s.learning_objectives).map(s=>[s.page,s.learning_objectives]));
  const sessionFor = id => course.sessions.find(s => s.id === id);
  let current = 0;
  let activePane = 0;
  let activeMedia = 0;
  let cardMediaSelections = {};
  let diagramSelections = {};
  let diagramScrollPositions = {};
  let explanationPositions = {};
  let accordionSelections = {};
  let explanationSyncTimer;
  let timerStart = 0;
  let timerSaved = 0;
  let toastTimeout;
  let layoutFrame;
  let displayWindow;
  let resizeObserver;
  let objectivesOpen = false;
  let objectivesLauncher = null;
  let activeSourcePopup = null;
  let readingState = null;
  let readingStack = [];
  let readingLauncher = null;
  const galleryImages = new Map(), galleryDiagrams = new Map();
  let focusGallerySelection = false;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  function toast(message) {
    $('#toast').textContent = message;
    $('#toast').classList.add('show');
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => $('#toast').classList.remove('show'), 2800);
  }

  function sourceURL(slide = slides[current]) {
    const pane=slide.panes?.[activePane]||slide.rail_overview;
    const anchor=slide===slides[current]&&(slide.layout==='visual'||hasStepRail(slide))?pane?.anchor:slide.anchor;
    return 'guide/' + (slide.page || 'index.html') + (anchor ? '#' + anchor : '');
  }

  function pauseMedia(root = stage) {
    root.querySelectorAll('video,audio').forEach(media => media.pause());
    root.querySelectorAll('iframe').forEach(frame => {
      try { frame.contentDocument?.querySelectorAll('video,audio').forEach(media => media.pause()); } catch {}
    });
  }

  function captureState(){return {type:'state',current,activePane,activeMedia,cardMediaSelections,diagramSelections,diagramScrollPositions,explanationPositions,accordionSelections,objectivesOpen,activeSourcePopup,role:embed?.role||'display',timerSaved,timerStart,control:window.DLI_CONTROL?.capture()};}
  function sendState() {
    if(stateMuted||receivingState||embed?.role==='next')return;
    const state=captureState();channel?.postMessage(state);
    if(embed)parent.postMessage({type:'dli:state',state},'*');
  }

  function navigate(index, broadcast = true) {
    index = Math.max(0, Math.min(slides.length - 1, index));
    if (!Number.isFinite(index)) return;
    setObjectivesOpen(false,false);
    setSourcePopup(null,false);
    pauseMedia();
    resizeObserver?.disconnect();
    current = index;
    activePane = slides[index].rail_overview?-1:0; activeMedia = 0; cardMediaSelections = {}; diagramSelections = {}; diagramScrollPositions = {};
    clearTimeout(explanationSyncTimer);
    explanationPositions={};
    accordionSelections={};
    const slide = slides[index];
    const session = sessionFor(slide.session);
    if(!embed)history.replaceState(null, '', '?' + params + '#' + slide.id);
    $('#page-number').value = index + 1;
    $('#page-number').max = slides.length;
    $('#page-total').textContent = '/ ' + slides.length;
    $('#previous-button').disabled = index === 0;
    $('#next-button').disabled = index === slides.length - 1;
    $('#session-label').textContent = session.title;
    $('#session-time').textContent = session.time || '필요할 때 열기';
    const instructor = session.instructor && session.instructor !== '—' ? session.instructor : '';
    $('#session-instructor').textContent = instructor;
    $('#session-instructor').hidden = !instructor;
    const sessionSummary = [session.title, session.time, instructor].filter(Boolean).join(' · ');
    $('#session-button').title = sessionSummary + ' · 일정 열기';
    $('#session-button').setAttribute('aria-label', sessionSummary + ' · 일정 열기');
    $('#source-link').href = sourceURL(slide);
    $('#progress').style.width = ((index + 1) / course.main_count * 100 > 100 ? 100 : (index + 1) / course.main_count * 100) + '%';
    stage.className = slide.kind === 'lesson' ? 'concept-screen '+slide.layout : '';
    stage.dataset.slide = slide.id;
    document.title = slide.title + ' · AI Days Seoul DLI';
    if (slide.kind === 'cover') renderCover();
    else if (slide.kind === 'agenda') renderAgendaSlide();
    else if (slide.kind === 'closing') renderClosing(slide);
    else if (['divider','pause'].includes(slide.kind)) renderDivider(slide, session);
    else renderLesson(slide, session);
    updateConsole(slide, session);
    requestAnimationFrame(fitStage);
    try { localStorage.setItem('so101-dli-last-slide',slide.id); } catch {}
    if (broadcast) sendState();
  }

  function renderCover() {
    stage.innerHTML = `<div class="cover"><img class="cover-photo" src="guide/_images/lightbox-sim-to-real.gif" alt="SO-101 simulation과 실제 Lightbox"><div class="cover-shade"></div><div class="cover-copy"><div class="eyebrow">AI DAYS SEOUL 2026 · DLI</div><h1>SO-101<span>Sim-to-Real</span></h1><p>NVIDIA Isaac으로<br>SO-101 Robot Sim-to-Real 학습하기</p><div class="cover-rule"></div><div class="cover-meta">09:00–17:15 KST · Jonghwan Lee · Hogun Kee · Jihyeon Ryu</div><button class="cover-start" data-go="agenda">오늘의 일정으로 시작</button></div><div class="cover-bottom"><span>Physical AI · LeRobot · Isaac GR00T</span><img src="guide/_static/nvidia-logo-horiz-rgb-wht-for-screen.svg" alt="NVIDIA"></div></div>`;
  }

  function renderAgendaSlide() {
    const morning = course.sessions.filter(s => s.time && s.time.slice(0,5) >= '09:00' && s.time.slice(0,5) < '12:45');
    const afternoon = course.sessions.filter(s => s.time && s.time.slice(0,5) >= '13:45');
    const column = (title,items) => `<div class="agenda-half"><h2>${title}</h2>${items.map(s=>`<button class="agenda-item" data-index="${s.first}"><time>${esc(s.time)}</time><span>${esc(s.title)}</span></button>`).join('')}</div>`;
    stage.innerHTML = `<div class="agenda-slide"><div class="eyebrow">AI DAYS SEOUL 2026 · KST</div><h1>오늘의 일정</h1><div class="agenda-columns">${column('Morning · Jonghwan Lee',morning)}${column('Afternoon · Hogun Kee / Jihyeon Ryu',afternoon)}</div><div class="agenda-foot">08:30–09:00 도착 및 착석 · 12:45–13:45 Lunch · 항목을 선택하면 해당 세션으로 이동합니다.</div></div>`;
  }

  function renderClosing(slide) {
    stage.innerHTML=`<section class="closing-screen" aria-labelledby="closing-title"><div class="closing-eyebrow">AI DAYS SEOUL 2026 · DLI</div><div class="closing-copy"><div class="closing-accent" aria-hidden="true"></div><h1 id="closing-title">${esc(slide.title)}</h1><p>${esc(slide.subtitle)}</p></div><div class="closing-footer"><span>Physical AI · SO-101 · Sim-to-Real</span><img src="guide/_static/nvidia-logo-horiz-rgb-wht-for-screen.svg" alt="NVIDIA"></div></section>`;
  }

  function renderDivider(slide,session) {
    const next = course.sessions[course.sessions.indexOf(session)+1];
    const notes = session.notes && session.notes !== '—' ? `<p class="divider-note">${esc(session.notes)}</p>` : '';
    stage.innerHTML = `<div class="divider ${slide.kind==='pause'?'pause':''}"><div class="divider-left"></div><div class="divider-body"><div class="eyebrow">${esc(session.type)}</div><h1>${esc(session.title)}</h1><div class="session-info"><span>${esc(session.time)} KST</span><span>${esc(session.duration)}</span>${session.instructor && session.instructor!=='—'?`<span>${esc(session.instructor)}</span>`:''}</div>${notes}</div><div class="divider-bottom">${slide.kind==='pause'&&next?`NEXT · ${esc(next.time)} · ${esc(next.title)}`:'AI DAYS SEOUL 2026 · DEEP LEARNING INSTITUTE'}</div></div>`;
  }

  function originalHTML(slide) {
    let previous = '';
    const objectives=objectivesForPage.get(slide.page);
    return slide.blocks.filter(b=>!objectives?.anchors.includes(b.anchor)).map(b=>{const h=b.heading!==previous?'<h3 id="'+esc(b.anchor)+'">'+esc(b.heading)+'</h3>':'';previous=b.heading;return h+'<div data-source-block="'+esc(b.id)+'">'+b.html+'</div>';}).join('');
  }

  function explanationHTML(pane,index,mediaHTML='',footer=''){
    const content=mediaHTML?'<div class="diagram-stage">'+mediaHTML+'</div>'+footer+'<div class="diagram-prose">'+paneHeading(pane)+pane.explanation+'</div>':pane.explanation;
    const brand=pane.brand_visual?'<figure class="brand-visual"><img src="'+esc(pane.brand_visual.src)+'" alt="'+esc(pane.brand_visual.alt)+'"></figure>':'';
    const key=mediaHTML?index+':media:'+activeMedia:String(index);
    return '<div class="pane-explanation '+(mediaHTML?'diagram-reading':'')+'" data-explanation-key="'+key+'" data-explanation-pane="'+index+'"><div class="explanation-scroll '+(mediaHTML?'diagram-flow':'')+(brand?' has-brand-visual':'')+'" tabindex="0" role="region" aria-label="'+esc(pane.source_title)+' 원문 설명">'+content+brand+'</div><nav class="explanation-navigation" aria-label="설명 이어 보기"><button data-explanation-step="-1" aria-label="이전 설명">↑</button><span class="explanation-position"></span><button data-explanation-step="1" aria-label="다음 설명">↓</button></nav></div>';
  }

  function updateExplanation(root){
    const box=root.querySelector('.explanation-scroll'),nav=root.querySelector('.explanation-navigation');
    const max=Math.max(0,box.scrollHeight-box.clientHeight),step=Math.max(1,box.clientHeight*.85);
    nav.classList.toggle('single-page',max<=3);
    root.querySelector('[data-explanation-step="-1"]').disabled=box.scrollTop<=2;
    root.querySelector('[data-explanation-step="1"]').disabled=box.scrollTop>=max-2;
    root.querySelector('.explanation-position').textContent=max>3?'설명 '+Math.min(Math.ceil(max/step)+1,Math.floor((box.scrollTop+2)/step)+1)+' / '+(Math.ceil(max/step)+1)+' · 스크롤로 이어 보기':'전체 설명';
  }

  function restoreExplanations(){
    $$('#stage .pane-explanation').forEach(root=>{
      const box=root.querySelector('.explanation-scroll');
      const diagram=root.querySelector('.diagram-stage');
      if(diagram)diagram.style.height=(innerWidth<=900?670:Math.max(360,box.clientHeight-(box.querySelector(':scope>.media-footer')?.offsetHeight||0)))+'px';
      box.scrollTop=(explanationPositions[root.dataset.explanationKey]||0)*Math.max(0,box.scrollHeight-box.clientHeight);
      updateExplanation(root);
    });
  }

  function hasStepRail(slide) {
    return ['steps','media-steps'].includes(slide.layout)||(['cards','reference'].includes(slide.layout)&&slide.panes.length>=4);
  }

  function restoreWorkflowAccordions() {
    stage.querySelectorAll('[data-workflow-key]').forEach(group=>{
      const selected=accordionSelections[group.dataset.workflowKey];
      group.querySelectorAll('[data-workflow-toggle]').forEach(button=>button.setAttribute('aria-expanded',String(button.dataset.workflowToggle===selected)));
      group.querySelectorAll('[data-workflow-content]').forEach(panel=>{panel.hidden=panel.dataset.workflowContent!==selected;});
      const region=group.closest('.pane-explanation');if(region)updateExplanation(region);
    });
  }

  function alignProseStart(root) {
    // Source sections can start with a paragraph, nested heading, list or
    // disclosure. Apply the same leading-margin rule to every prose layout.
    root.querySelectorAll('.explanation-scroll:not(.diagram-flow),.diagram-prose').forEach(scroll=>{
      const walker=document.createTreeWalker(scroll,NodeFilter.SHOW_TEXT);
      let first;
      while(first=walker.nextNode()){
        if(first.textContent.trim()&&first.parentElement.getClientRects().length)break;
      }
      for(let node=first?.parentElement;node&&node!==scroll;node=node.parentElement){
        node.dataset.proseLeading='';
      }
    });
  }

  function paneHeading(pane,extraClass='',id='') {
    if(pane.hide_source_title)return '';
    const slide=slides[current];
    const key=text=>String(text||'').normalize('NFKC').replace(/\s+/g,' ').trim().toLowerCase();
    const navigation=hasStepRail(slide)||(slide.layout==='visual'&&slide.panes.length>1);
    const repeated=key(pane.source_title)===key(slide.title)||(navigation&&key(pane.source_title)===key(pane.label));
    // Navigation already names this section. More specific source titles and
    // the unselected CODEX introduction retain their own heading.
    if(repeated&&!id)return '';
    return '<h2 class="source-section-title '+extraClass+'"'+(id?' id="'+esc(id)+'"':'')+'>'+esc(pane.source_title)+'</h2>';
  }

  function mediaCaption(media) {
    return '<div class="media-caption"'+(!media?.caption?' aria-hidden="true"':'')+'>'+esc(media?.caption||'')+'</div>';
  }

  function mediaPicker(pane,index=null) {
    if(pane.media.length<2)return '';
    const selected=index===null?activeMedia:(cardMediaSelections[index]||0);
    return '<div class="media-picker" aria-label="시각 자료 선택">'+pane.media.map((m,i)=>'<button class="'+(i===selected?'selected':'')+'" '+(index===null?'data-media="'+i+'"':'data-card-pane="'+index+'" data-card-media="'+i+'"')+' aria-pressed="'+(i===selected)+'" title="'+esc(m.title)+'">'+(m.selector_label?esc(m.selector_label):({iframe:'도표',widget:'Interactive',video:'영상',img:'이미지'}[m.kind])+' '+(i+1))+'</button>').join('')+'</div>';
  }

  function mediaFooter(pane,media,index=null) {
    return '<div class="media-footer">'+mediaCaption(media)+mediaPicker(pane,index)+'</div>';
  }

  function setObjectivesOpen(open,broadcast=true) {
    const slide=slides[current],dialog=$('#objectives-dialog');
    open=!!open&&!!slide.learning_objectives;
    if(open===objectivesOpen&&dialog.open===open)return;
    objectivesOpen=open;
    if(open){
      objectivesLauncher=stage.querySelector('[data-open-objectives]');
      pauseMedia();
      $('#objectives-chapter').textContent=slide.page_title;
      $('#objectives-body').innerHTML=slide.learning_objectives.html;
      enhanceContent($('#objectives-body'),true);
      dialog.showModal();
      $('#objectives-body').scrollTop=0;
      $('#objectives-title').focus({preventScroll:true});
    }else{
      dialog.close();
      if(objectivesLauncher?.isConnected)objectivesLauncher.focus({preventScroll:true});
    }
    stage.querySelector('[data-open-objectives]')?.setAttribute('aria-expanded',String(open));
    if(broadcast)sendState();
  }

  function renderLesson(slide,session) {
    const rail=hasStepRail(slide);
    const tabs=!rail&&!['cards','steps','compare','reference'].includes(slide.layout)&&slide.panes.length>1;
    const type=slide.teaching_type||'Reference';
    const badge=slide.teaching_badge_html||'<span class="teaching-type teaching-type--reference">'+esc(type)+'</span>';
    const objectives=slide.learning_objectives?'<button class="objectives-button" data-open-objectives aria-haspopup="dialog" aria-controls="objectives-dialog" aria-expanded="false"><svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4"/><path d="M12 1v4m0 14v4M1 12h4m14 0h4"/></svg><span>학습 목표</span></button>':'';
    const practice=(slide.practice_groups||[]).map(id=>'<button class="objectives-button" data-practice-group="'+esc(id)+'" aria-haspopup="dialog">'+(course.language==='ko'?'실습 ':'Exercise ')+esc(id)+'</button>').join('');
    stage.innerHTML = '<header class="slide-header"><div class="slide-heading-meta"><div class="slide-kicker">'+esc(slide.page_title)+'</div><div class="slide-header-actions">'+practice+objectives+badge+'</div></div><h1>'+esc(slide.title)+'</h1></header>'+
      (tabs?'<nav class="concept-tabs" aria-label="같은 주제의 설명" role="tablist">'+slide.panes.map((p,i)=>'<button role="tab" aria-selected="'+(i===activePane)+'" class="'+(i===activePane?'selected':'')+'" data-pane="'+i+'">'+esc(p.label)+'</button>').join('')+'</nav>':'')+
      '<div id="slide-content" class="lesson-content concept-canvas"></div>';
    stage.querySelectorAll('[data-practice-group]').forEach(button=>button.addEventListener('click',()=>window.DLI_CONTROL?.run({kind:'practice',group:button.dataset.practiceGroup})));
    renderConceptBody();
  }

  function renderConceptBody() {
    const slide=slides[current],root=$('#slide-content');
    if(!root||!slide.panes)return;
    const pane=slide.panes[activePane]||slide.rail_overview;
    const rail=hasStepRail(slide);
    const cardMode=!rail&&['cards','steps','compare','reference'].includes(slide.layout);
    if(rail){
      root.className='lesson-content concept-canvas rail-canvas';
      const overview=activePane===-1;
      const mediaRail=slide.layout==='media-steps',media=pane.media?.[activeMedia];
      const nav='<nav class="step-rail" role="tablist" aria-orientation="vertical" aria-label="실습 단계">'+slide.panes.map((p,i)=>'<button id="step-tab-'+i+'" role="tab" aria-controls="step-panel" tabindex="'+(i===(overview?0:activePane)?'0':'-1')+'" aria-selected="'+(i===activePane)+'" class="'+(i===activePane?'selected':'')+'" data-pane="'+i+'"><span class="rail-number">'+String(i+1).padStart(2,'0')+'.</span><span>'+esc(p.label)+'</span><span class="rail-arrow" aria-hidden="true">›</span></button>').join('')+'</nav>';
      const gallery=media?'<div class="visual-stage rail-gallery">'+media.html+mediaFooter(pane,media)+'</div>':'';
      root.innerHTML='<div class="step-layout '+(mediaRail?'has-rail-media':'')+'">'+(mediaRail?'<div class="step-sidebar">'+nav+gallery+'</div>':nav)+'<section id="step-panel" class="step-panel" role="'+(overview?'region':'tabpanel')+'" aria-labelledby="'+(overview?'step-overview-title':'step-tab-'+activePane)+'">'+paneHeading(pane,'',overview?'step-overview-title':'')+explanationHTML(pane,activePane)+'</section></div>';
    }else if(cardMode){
      const n=slide.panes.length;
      root.className='lesson-content concept-canvas cards-canvas '+slide.layout;
      root.innerHTML='<div class="teaching-grid count-'+n+'">'+slide.panes.map((p,i)=>{
        const media=p.media[cardMediaSelections[i]||0];
        const heading=paneHeading(p);
        return '<article class="teaching-card">'+(heading?'<div class="card-heading"><span class="step-number">'+String(i+1).padStart(2,'0')+'</span>'+heading+'</div>':'')+
          (media?'<div class="card-gallery"><div class="compare-media">'+media.html+'</div>'+mediaFooter(p,media,i)+'</div>':'')+
          '<div class="card-body">'+explanationHTML(p,i)+'</div></article>';
      }).join('')+'</div>';
    }else{
      const media=pane.media[activeMedia];
      const displayPane=media?.explanation!==undefined?{...pane,explanation:media.explanation}:pane;
      const interactive=media&&['iframe','widget'].includes(media.kind);
      const textOnly=!media;
      root.className='lesson-content concept-canvas '+(interactive?'diagram-canvas':textOnly?'text-canvas':'visual-canvas');
      if(interactive){
        const diagram=media.kind==='iframe'&&media.html.includes('assets/interactive/');
        const footer=mediaFooter(pane,media);
        root.innerHTML=diagram||media.widget_intro?'<div class="diagram-stage">'+media.html+'</div>'+footer:explanationHTML(displayPane,activePane,media.html,footer);
      }else if(textOnly){
        const heading=paneHeading(pane,'topic-label');
        root.innerHTML='<div class="text-focus">'+(heading?'<div class="explanation-heading">'+heading+'</div>':'')+explanationHTML(pane,activePane)+'</div>';
      }else{
        const hasNotes=!!pane.explanation;
        root.innerHTML='<div class="visual-layout '+(hasNotes?'':'visual-only')+'" data-media-layout="'+esc(media.layout_group)+'"><div class="visual-stage">'+media.html+mediaFooter(pane,media)+'</div>'+(hasNotes?'<aside class="concept-notes">'+paneHeading(pane,'topic-label')+explanationHTML(displayPane,activePane)+'</aside>':'')+'</div>';
      }
    }
    enhanceContent(root);
    alignProseStart(root);
    restoreWorkflowAccordions();
    root.querySelectorAll('.pane-explanation').forEach(region=>{
      region.querySelector('.explanation-scroll').addEventListener('scroll',()=>{
        if(!region.isConnected)return;
        const box=region.querySelector('.explanation-scroll');updateExplanation(region);
        const fraction=box.scrollTop/Math.max(1,box.scrollHeight-box.clientHeight),key=region.dataset.explanationKey;
        if(Math.abs((explanationPositions[key]||0)-fraction)>.002){explanationPositions[key]=fraction;clearTimeout(explanationSyncTimer);explanationSyncTimer=setTimeout(sendState,80);}
      });
    });
    $('#source-link').href=sourceURL();
    requestAnimationFrame(()=>fitConceptContent());
    document.fonts.ready.then(()=>{if(root===document.querySelector('#slide-content'))fitConceptContent();});
    root.querySelectorAll('img').forEach(img=>img.addEventListener('load',fitConceptContent,{once:true}));
    $$('[data-pane]').forEach(b=>{const yes=Number(b.dataset.pane)===activePane;b.classList.toggle('selected',yes);b.setAttribute('aria-selected',String(yes));});
  }

  function galleryAspectRatio(pane){
    // A common intrinsic height keeps selectors still without leaving a
    // letterbox between a wide image and its caption. Taller pictures use
    // less width, preserving their full content and the same top edge.
    const ratios=[];
    for(const item of pane.media){
      if(item.camera_grid)continue;
      const source=new DOMParser().parseFromString(item.html,'text/html');
      const diagram=source.querySelector('iframe[src*="assets/interactive/"]');
      if(diagram){
        const src=new URL(diagram.getAttribute('src'),pageURL).href;
        if(!galleryDiagrams.has(src)){
          galleryDiagrams.set(src,0);
          const bundled=window.DLI_PORTABLE_DIAGRAMS?.[diagram.getAttribute('src')];
          const sourceHTML=bundled?Promise.resolve(bundled):fetch(src).then(r=>{if(!r.ok)throw Error('Diagram unavailable');return r.text();});
          sourceHTML.then(html=>{
            const svg=new DOMParser().parseFromString(html,'text/html').querySelector('.diagram>svg');
            const viewBox=svg?.getAttribute('viewBox')?.trim().split(/[ ,]+/).map(Number);
            if(viewBox?.[3]>0)galleryDiagrams.set(src,viewBox[2]/viewBox[3]);
            requestAnimationFrame(fitConceptContent);
          }).catch(()=>{});
        }
        if(galleryDiagrams.get(src))ratios.push(galleryDiagrams.get(src));
      }
      const images=[...source.querySelectorAll('img')];
      for(const node of images){
        const src=new URL(node.getAttribute('src'),pageURL).href;
        if(!galleryImages.has(src)){
          const image=new Image();galleryImages.set(src,image);
          image.onload=()=>requestAnimationFrame(fitConceptContent);image.src=src;
        }
        const image=galleryImages.get(src);
        if(image.naturalHeight)ratios.push(image.naturalWidth/image.naturalHeight*images.length);
      }
      const video=source.querySelector('video');
      if(video){const w=Number(video.getAttribute('width')),h=Number(video.getAttribute('height'));if(w>0&&h>0)ratios.push(w/h);}
    }
    return ratios.length?Math.max(...ratios):1.6;
  }

  function fitConceptContent(){
    const root=$('#slide-content'),slide=slides[current],pane=slide.panes?.[activePane];
    if(!root||!pane){restoreExplanations();return;}
    const frame=root.querySelector('iframe[data-diagram-key]');
    const areas=[...root.querySelectorAll('.visual-stage')];
    const diagram=frame?.contentDocument?.querySelector('.diagram.has-media-footer');
    if(diagram)areas.push(diagram);
    for(const area of areas){
      const picker=area.querySelector('.media-picker');
      const style=getComputedStyle(area),width=area.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight);
      const media=area.querySelector(':scope>img,:scope>video,:scope>.media-pair,:scope>.diagram-picture');
      const ratio=galleryAspectRatio(pane);
      const captions=(slide.layout==='media-steps'?slide.panes.flatMap(p=>p.media):pane.media).map(m=>m.caption);
      const probe=area.ownerDocument.createElement('div');probe.className='media-caption';
      Object.assign(probe.style,{position:'absolute',visibility:'hidden',width:width+'px',height:'auto',minHeight:'21px',margin:'0',pointerEvents:'none'});
      area.append(probe);let captionHeight=21;
      for(const caption of captions){probe.textContent=caption||'';captionHeight=Math.max(captionHeight,probe.offsetHeight);}
      probe.remove();area.style.setProperty('--gallery-caption-height',captionHeight+'px');
      if(media){
        let available=pane.media[activeMedia]?.camera_grid?width/(innerWidth>900?1.2:.8):width/ratio;
        if(innerWidth>900){const controls=picker?(picker.offsetHeight+12):0;available=Math.min(available,area.clientHeight-parseFloat(style.paddingTop)-parseFloat(style.paddingBottom)-captionHeight-8-controls);}
        area.style.setProperty('--media-frame-height',Math.max(1,available)+'px');
      }
    }
    restoreExplanations();
  }

  function selectPane(index,broadcast=true){
    const slide=slides[current];if(index===-1?!slide.rail_overview:!slide.panes?.[index])return;
    pauseMedia();activePane=index;activeMedia=0;renderConceptBody();
    if(broadcast)sendState();
  }

  function selectMediaFocused(index){
    focusGallerySelection=true;
    selectMedia(index);
    const selected=stage.querySelector('.media-picker button.selected');
    if(selected&&!stage.querySelector('iframe[data-diagram-key]')){selected.focus({preventScroll:true});focusGallerySelection=false;}
  }

  function selectMedia(index,broadcast=true){
    if(!slides[current].panes?.[activePane]?.media[index])return;
    pauseMedia();activeMedia=index;renderConceptBody();
    if(broadcast)sendState();
  }

  function updateOverflowHint() {
    const content = $('#slide-content');
    stage.querySelector('.slide-content-scroll-hint')?.remove();
    if (content && content.scrollHeight > content.clientHeight + 6 && !stage.classList.contains('interactive')) {
      const hint = document.createElement('span');
      hint.className='slide-content-scroll-hint';hint.textContent='아래에 원문이 더 있습니다 · 스크롤';
      stage.append(hint);
    }
  }

  function restoreDiagram(frame){
    const doc=frame.contentDocument,key=frame.dataset.diagramKey;
    if(!key||!doc?.querySelector('.diagram-overview-prose'))return;
    const term=diagramSelections[key]||'',selected=doc.querySelector('.hotspot[aria-expanded="true"]')?.dataset.term||'';
    if(term!==selected){
      if(term){const target=[...doc.querySelectorAll('.hotspot')].find(n=>n.dataset.term===term);target?.dispatchEvent(new frame.contentWindow.MouseEvent('click',{bubbles:true,cancelable:true}));}
      else doc.querySelector('#clear-selection').click();
    }
    const prose=doc.querySelector('.diagram-overview-prose');
    prose.scrollTop=(diagramScrollPositions[key]||0)*Math.max(0,prose.scrollHeight-prose.clientHeight);
  }

  function installDiagramOverview(frame,pane,index){
    const doc=frame.contentDocument,empty=doc.getElementById('empty-prompt');
    if(!empty)return;
    const media=pane.media[Number(frame.dataset.diagramKey.split(':')[2])];
    doc.documentElement.dataset.mediaLayout=media?.layout_group||'reference';
    // Keep the caption and selectors in the diagram column, including when
    // the iframe stacks its explanation below the diagram on a small screen.
    const diagram=doc.querySelector('.layout>.diagram'),footer=frame.closest('.diagram-canvas')?.querySelector(':scope>.media-footer');
    if(diagram&&footer){
      if(pane.media.length>1||media.caption){
        diagram.classList.add('has-media-footer');
        const picture=doc.createElement('div');picture.className='diagram-picture';
        while(diagram.firstChild)picture.append(diagram.firstChild);
        diagram.append(picture,footer);
        footer.addEventListener('click',event=>{
          const button=event.target.closest('[data-media]');
          if(button)selectMediaFocused(Number(button.dataset.media));
        });
      }else footer.remove();
    }
    empty.innerHTML=paneHeading(pane)+'<div class="diagram-overview-prose" tabindex="0" role="region" aria-label="원문 설명">'+(media?.explanation??pane.explanation)+'</div><aside class="diagram-overview-note"><strong>Note</strong><p>각 도표의 아이템을 클릭하면 해당 설명을 확인할 수 있습니다.</p></aside>';
    const prose=empty.querySelector('.diagram-overview-prose');
    // Source URLs are relative to the presentation, not the iframe's guide base.
    prose.querySelectorAll('a[href]').forEach(a=>{
      const href=a.getAttribute('href');a.href=new URL(href.startsWith('#')?'guide/'+slides[current].page+href:href,pageURL).href;
    });
    prose.querySelectorAll('[id]').forEach(n=>{n.dataset.sourceAnchor=n.id;n.id='overview-'+n.id;});
    prose.addEventListener('click',event=>{
      const control=event.target.closest('a[href],[data-open-block],[data-source-dialog],[data-example-media]');
      if(!control)return;
      event.preventDefault();
      if(control.dataset.sourceDialog){
        control.focus({preventScroll:true});
        setSourcePopup(control.dataset.sourceDialog);
        readingLauncher=control;
        return;
      }
      const proxy=document.createElement('div');proxy.hidden=true;proxy.className='pane-explanation';proxy.dataset.explanationPane=index;
      const click=control.cloneNode(true);proxy.append(click);$('#slide-content').append(proxy);click.click();proxy.remove();
    });
    const key=frame.dataset.diagramKey;
    prose.addEventListener('scroll',()=>{
      const value=prose.scrollTop/Math.max(1,prose.scrollHeight-prose.clientHeight);
      if(Math.abs((diagramScrollPositions[key]||0)-value)>.002){diagramScrollPositions[key]=value;clearTimeout(explanationSyncTimer);explanationSyncTimer=setTimeout(sendState,80);}
    });
    const observer=new frame.contentWindow.MutationObserver(()=>{
      if(!frame.isConnected){observer.disconnect();return;}
      const value=doc.querySelector('.hotspot[aria-expanded="true"]')?.dataset.term||'';
      if((diagramSelections[key]||'')!==value){diagramSelections[key]=value;sendState();}
    });
    doc.querySelectorAll('.hotspot').forEach(n=>observer.observe(n,{attributes:true,attributeFilter:['aria-expanded']}));
    restoreDiagram(frame);
    requestAnimationFrame(fitConceptContent);
    doc.fonts.ready.then(fitConceptContent);
    if(focusGallerySelection){footer?.querySelector('button.selected')?.focus({preventScroll:true});focusGallerySelection=false;}
  }

  function enhanceContent(root, reading = false) {
    // Source headings such as #workspace must not inherit the application's
    // #workspace layout. Widgets are isolated in iframes and keep their IDs.
    const sourceIDs=new Map();
    root.querySelectorAll('[id]').forEach(node=>{
      if(node.closest('.step-rail')||node.id==='step-panel'||node.closest('.groot-explorers,.image-comparison')||node.dataset.sourceAnchor)return;
      const original=node.id;node.dataset.sourceAnchor=original;
      node.id='source-'+current+'-'+(root.id||'content')+'-'+original;
      sourceIDs.set(original,node.id);
    });
    root.querySelectorAll('[for],[aria-labelledby],[aria-describedby],[aria-controls]').forEach(node=>{
      if(node.closest('.groot-explorers,.image-comparison'))return;
      for(const attr of ['for','aria-labelledby','aria-describedby','aria-controls'])if(node.hasAttribute(attr))node.setAttribute(attr,node.getAttribute(attr).split(/\s+/).map(id=>sourceIDs.get(id)||id).join(' '));
    });
    root.querySelectorAll('.course-module-type').forEach(label=>label.remove());
    if (!reading) root.querySelectorAll('details').forEach(details=>{details.open=true;});
    root.querySelectorAll('.groot-explorers,.image-comparison').forEach(block=>{
      const html = block.outerHTML;
      const frame=document.createElement('iframe');frame.className='embedded-widget';frame.title='교재의 interactive controls';
      const base=new URL('.',pageURL).href;
      frame.srcdoc=`<!doctype html><html lang="ko" data-theme="light"><head><base href="${esc(base)}"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="guide/_static/groot-hyperparameters.css"><link rel="stylesheet" href="guide/_static/image-comparison.css"><link rel="stylesheet" href="assets/presentation.css"><link rel="stylesheet" href="assets/widget-presentation.css"></head><body class="lesson-content">${html}<script src="guide/_static/groot-hyperparameters.js"><\/script><script src="guide/_static/image-comparison.js"><\/script><script src="assets/widget-presentation.js"><\/script></body></html>`;
      block.replaceWith(frame);
    });
    root.querySelectorAll('iframe').forEach(frame=>{
      const sourceSlide=current,paneIndex=activePane,sourcePane=slides[current].panes?.[activePane];
      if(!reading&&frame.getAttribute('src')?.includes('assets/interactive/'))frame.dataset.diagramKey=current+':'+activePane+':'+activeMedia;
      frame.loading='eager';
      frame.addEventListener('load',()=>{
        try {
          const doc=frame.contentDocument;
          if (!doc) return;
          if(frame.dataset.diagramKey&&frame.isConnected&&sourceSlide===current)installDiagramOverview(frame,sourcePane,paneIndex);
          const link=doc.createElement('link');link.rel='stylesheet';link.href=new URL('assets/iframe-fonts.css',pageURL).href;doc.head.append(link);
          // A versioned stylesheet replaces stale diagram CSS in existing browsers.
          if(doc.getElementById('clear-selection')){
            const layout=doc.createElement('link');layout.rel='stylesheet';
            layout.href=new URL('assets/interactive-layout.css?v=close-layout-20261109',pageURL).href;
            doc.head.append(layout);
          }
          doc.documentElement.style.overflowY='auto';doc.body.style.overflowY='auto';
          if (frame.src.includes('/_static/interactive/') && innerWidth > 900) {
            const wrapper=doc.createElement('div');
            wrapper.className='presentation-embed-content';
            while(doc.body.firstChild)wrapper.append(doc.body.firstChild);
            doc.body.append(wrapper);
            Object.assign(doc.body.style,{margin:'0',padding:'0',overflow:'hidden',height:'100vh'});
            Object.assign(wrapper.style,{position:'absolute',width:'1100px',left:'50%',top:'8px',transformOrigin:'top center'});
            const fit=()=>{const height=wrapper.scrollHeight;const scale=Math.min((frame.clientWidth-16)/1100,(frame.clientHeight-16)/Math.max(height,1),1.32);wrapper.style.transform=`translateX(-50%) scale(${scale})`;};
            new frame.contentWindow.ResizeObserver(fit).observe(wrapper);
            doc.fonts.ready.then(fit);setTimeout(fit,100);
          }
        } catch {}
      });
      // srcdoc inherits the parent origin, so the packaged file:// presentation
      // can keep its source prose, diagram controls and gallery in one screen.
      const bundled=new URL(pageURL).protocol==='file:'&&window.DLI_PORTABLE_DIAGRAMS?.[frame.getAttribute('src')];
      if(bundled){
        const doc=new DOMParser().parseFromString(bundled,'text/html');
        const base=doc.querySelector('base')||doc.head.insertBefore(doc.createElement('base'),doc.head.firstChild);
        base.href=new URL('guide/_static/interactive/',pageURL).href;
        frame.removeAttribute('src');
        frame.srcdoc='<!doctype html>'+doc.documentElement.outerHTML;
      }
    });
    root.querySelectorAll('video').forEach(video=>{video.preload='metadata';video.controls=true;video.autoplay=false;video.muted=true;});
    root.querySelectorAll('pre').forEach(pre=>{
      const code=pre.textContent;
      const tools=document.createElement('div');tools.className='code-tools';
      const copy=document.createElement('button');copy.textContent="복사";copy.addEventListener('click',async()=>{
        if(navigator.clipboard?.writeText){
          try {await navigator.clipboard.writeText(code);toast("명령어를 복사했습니다.");return;}
          catch {}
        }
        // LAN HTTP can lack the Clipboard API; the fallback must stay inside an open modal.
        const input=document.createElement('textarea');input.value=code;input.readOnly=true;
        input.style.cssText='position:fixed;left:0;top:0;width:1px;height:1px;opacity:0;';
        (pre.closest('dialog[open]')||document.body).append(input);
        try {
          input.focus({preventScroll:true});input.select();input.setSelectionRange(0,input.value.length);
          if(!document.execCommand('copy'))throw new Error('Copy unavailable');
          toast("명령어를 복사했습니다.");
        } catch {
          const selection=getSelection();const range=document.createRange();range.selectNodeContents(pre);
          selection.removeAllRanges();selection.addRange(range);toast("명령어를 선택했습니다. Ctrl+C로 복사하세요.");
        } finally {input.remove();copy.focus({preventScroll:true});}
      });tools.append(copy);
      if(!reading){const expand=document.createElement('button');expand.textContent='크게 보기';expand.addEventListener('click',()=>openReading(slides[current].title,pre.outerHTML));tools.append(expand);}
      pre.before(tools);
    });
  }

  function setSourcePopup(id,broadcast=true){
    const popup=slides[current].popups?.find(p=>p.id===id&&p.presentation_dialog);
    id=popup?popup.id:null;
    if(id===activeSourcePopup)return;
    activeSourcePopup=id;
    if(popup){
      pauseMedia();
      openReading(popup.title,popup.html,{page:slides[current].page,anchor:popup.anchor,sourcePopup:id,tablePopup:popup.kind==='table',reportPopup:popup.kind==='report'});
    }else if($('#reading-dialog').classList.contains('source-detail-mode'))$('#reading-dialog').close();
    if(broadcast)sendState();
  }

  function openReading(title,html,context={page:slides[current].page,anchor:slides[current].anchor},push=true) {
    const dialog=$('#reading-dialog');
    dialog.classList.toggle('source-detail-mode',!!context.sourcePopup);
    dialog.classList.toggle('table-detail-mode',!!context.tablePopup);
    dialog.classList.toggle('report-detail-mode',!!context.reportPopup);
    if(dialog.open&&readingState&&push)readingStack.push({...readingState,scroll:$('#reading-body').scrollTop});
    if(!dialog.open){readingStack=[];readingLauncher=document.activeElement;}
    pauseMedia($('#reading-body'));
    readingState={title,html,context,scroll:0};
    $('#reading-title').textContent=title;
    $('#reading-body').innerHTML=html;
    enhanceContent($('#reading-body'),true);
    if(context.promptExamples){
      const pre=$('#reading-body pre'),list=document.createElement('ul');
      list.className='prompt-examples';
      for(const prompt of pre.textContent.trim().split(/\n\s*\n/)){
        const item=document.createElement('li');item.textContent=prompt.trim();list.append(item);
      }
      // The existing copy button retains the original plain-text examples.
      pre.parentElement.classList.remove('highlight');pre.replaceWith(list);
    }
    $('#reading-back').hidden=!readingStack.length;
    $('#reading-source').href='guide/'+(context.page||'index.html')+(context.anchor?'#'+context.anchor:'');
    if(!dialog.open)dialog.showModal();
    $('#reading-body').scrollTop=0;
    $('#reading-title').focus({preventScroll:true});
    sendState();
  }

  function scrollToReadingTarget(anchor){
    const target=[...$('#reading-body').querySelectorAll('[id]')].find(n=>n.id===anchor||n.dataset.sourceAnchor===anchor);
    if(!target)return false;
    for(let p=target;p&&p!==$('#reading-body');p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;
    target.scrollIntoView({block:'start'});
    return true;
  }

  function fitStage() {
    cancelAnimationFrame(layoutFrame);
    layoutFrame=requestAnimationFrame(()=>{
      const available=$('#workspace').getBoundingClientRect();
      if(embed){$('#stage-wrap').style.width='1600px';$('#stage-wrap').style.height='900px';stage.style.transform='none';return;}
      if (innerWidth<=900) {$('#stage-wrap').style.width='100%';$('#stage-wrap').style.height='auto';stage.style.transform='none';return;}
      const width=presenter?available.width-Math.min(520,Math.max(380,available.width*.33))-70:available.width-40;
      const scale=Math.min(width/1600,(available.height-(presenter?90:38))/900);
      $('#stage-wrap').style.width=`${1600*scale}px`;$('#stage-wrap').style.height=`${900*scale}px`;
      stage.style.transform=`scale(${scale})`;
    });
  }

  function showAgenda(reference=false) {
    $('#search').value='';renderAgendaList('',reference);$('#agenda-dialog').showModal();
    setTimeout(()=>$('#search').focus(),50);
  }

  function renderAgendaList(query='',reference=false) {
    const list=$('#agenda-list');
    if (query.trim()) {
      const term=query.toLocaleLowerCase();
      const matches=slides.filter(s=>(s.title+' '+(s.page_title||'')+' '+s.blocks.map(b=>b.html.replace(/<[^>]*>/g,' ')).join(' ')).toLocaleLowerCase().includes(term));
      list.innerHTML=matches.length?matches.slice(0,120).map(s=>`<button class="search-result" data-index="${s.index}"><small>${esc(sessionFor(s.session).title)} · ${s.index+1}</small>${esc(s.title)}</button>`).join(''):'<p>검색 결과가 없습니다.</p>';
      return;
    }
    const selected=reference?course.sessions.filter(s=>s.id==='reference'):course.sessions.filter(s=>s.id!=='arrival');
    list.innerHTML=selected.map(s=>{
      const pages=course.pages.filter(p=>p.session===s.id);
      return `<section class="session-entry ${slides[current].session===s.id?'current':''}"><button data-index="${s.first}"><time>${esc(s.time||'Reference')}</time><strong>${esc(s.title)}</strong><small>${esc(s.instructor)}</small></button>${pages.length?`<details ${reference?'open':''}><summary>교재별 이동 · ${pages.length}개</summary><div class="lesson-jumps">${pages.map(p=>`<button data-index="${p.first}">${esc(p.title)}</button>`).join('')}</div></details>`:''}</section>`;
    }).join('');
  }

  function updateConsole(slide,session) {
    if (!presenter) return;
    $('#console-title').textContent=slide.title;
    const next=slides[Math.min(slides.length-1,current+1)];
    $('#next-title').textContent=next.title;
    $('#next-session').textContent=(sessionFor(next.session).time||'Reference')+' · '+(next.index+1)+' / '+slides.length;
    const notes=$('#console-notes');
    notes.innerHTML=originalHTML(slide)||(slide.kind==='closing'?`<p>${esc(slide.subtitle)}</p>`:`<p>${esc(session.time)} · ${esc(session.instructor)}</p><p>${esc(session.notes)}</p>`);
    notes.querySelectorAll('.course-module-type').forEach(label=>label.remove());
    notes.querySelectorAll('video,iframe').forEach(node=>{const p=document.createElement('p');p.textContent=node.tagName==='VIDEO'?'영상은 발표 창에서 재생합니다.':'Interactive 도표는 발표 창에서 조작합니다.';node.replaceWith(p);});
  }

  function openPresenter() {
    const url=new URL(location.href);url.searchParams.set('presenter','1');
    displayWindow=window.open(url.href,'dli-presenter-'+edition+'-'+sessionKey,'width=1440,height=950');
    if(!displayWindow)toast('브라우저의 팝업 차단을 해제해 주세요.');
  }

  async function fullscreen() {
    try {if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}
    catch{toast('브라우저의 전체화면 버튼 또는 F11을 사용하세요.');}
  }

  function updateTimer() {
    const elapsed=timerSaved+(timerStart?Date.now()-timerStart:0);
    const seconds=Math.floor(elapsed/1000);
    $('#timer').textContent=String(Math.floor(seconds/60)).padStart(2,'0')+':'+String(seconds%60).padStart(2,'0');
    $('#timer-button').classList.toggle('running',!!timerStart);
    if (presenter) $('#wall-clock').textContent=new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Seoul',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date());
  }

  document.addEventListener('click',event=>{
    if(event.target.closest('[data-open-objectives]')){setObjectivesOpen(true);return;}
    if(event.target.closest('[data-close-objectives]')){setObjectivesOpen(false);return;}
    const sourceDialog=event.target.closest('[data-source-dialog]');
    if(sourceDialog){event.preventDefault();sourceDialog.focus({preventScroll:true});setSourcePopup(sourceDialog.dataset.sourceDialog);return;}
    const example=event.target.closest('[data-example-media]');
    if(example){
      const pane=Number(example.closest('.pane-explanation').dataset.explanationPane),media=Number(example.dataset.exampleMedia);
      if(slides[current].layout==='compare'){
        pauseMedia();cardMediaSelections[pane]=media;renderConceptBody();sendState();
      }else{
        if(activePane!==pane)selectPane(pane,false);
        selectMedia(media);
      }
      stage.querySelector('[data-example-media="'+media+'"]')?.focus({preventScroll:true});
      if(innerWidth<=900)requestAnimationFrame(()=>stage.querySelector('.visual-stage,.card-gallery')?.scrollIntoView({block:'start',behavior:'smooth'}));
      return;
    }
    const workflow=event.target.closest('[data-workflow-toggle]');
    if(workflow){
      const group=workflow.closest('[data-workflow-key]'),key=group.dataset.workflowKey,item=workflow.dataset.workflowToggle;
      accordionSelections[key]=accordionSelections[key]===item?null:item;
      restoreWorkflowAccordions();
      const box=group.closest('.explanation-scroll'),delta=workflow.getBoundingClientRect().top-box.getBoundingClientRect().top;
      if(delta<0||delta>box.clientHeight-60)box.scrollTop+=delta;
      sendState();return;
    }
    const explanationStep=event.target.closest('[data-explanation-step]');
    if(explanationStep){const box=explanationStep.closest('.pane-explanation').querySelector('.explanation-scroll');box.scrollBy({top:Number(explanationStep.dataset.explanationStep)*box.clientHeight*.85,behavior:'instant'});return;}
    const cardMedia=event.target.closest('[data-card-media]');
    if(cardMedia){pauseMedia();cardMediaSelections[cardMedia.dataset.cardPane]=Number(cardMedia.dataset.cardMedia);renderConceptBody();sendState();return;}
    const sourceBlock=event.target.closest('[data-open-block]');
    if(sourceBlock){
      const i=Number(sourceBlock.closest('.pane-explanation').dataset.explanationPane),pane=slides[current].panes[i],kind=sourceBlock.dataset.openBlock.split(':')[0],index=Number(sourceBlock.dataset.openBlock.split(':')[1]);
      if(kind==='pre'){
        const source=document.createElement('div');source.innerHTML=pane.full;
        const blocks=source.querySelectorAll('pre'),indices=(sourceBlock.dataset.openBlocks||String(index)).split(',').map(Number);
        const command=blocks[index]?.cloneNode(true);
        if(command&&indices.length>1){command.replaceChildren(...indices.flatMap(n=>[...blocks[n].cloneNode(true).childNodes]));}
        if(command){
          sourceBlock.focus({preventScroll:true});
          const promptExamples=slides[current].page==='01-codex.html'&&pane.anchor==='try-course-questions-and-hands-on-requests'&&index===0;
          openReading(promptExamples?'과정 Q&A와 실습 요청 예시':'명령·출력','<div class="highlight">'+command.outerHTML+'</div>',{page:slides[current].page,anchor:pane.anchor,promptExamples});
        }
        return;
      }
      openReading(pane.source_title,pane.full,{page:slides[current].page,anchor:pane.anchor});
      const target=$$('#reading-body '+kind)[index];
      if(target){for(let n=target;n&&n!==$('#reading-body');n=n.parentElement)if(n.tagName==='DETAILS')n.open=true;target.scrollIntoView({block:'start'});}
      return;
    }
    const pane=event.target.closest('[data-pane]');if(pane){const rail=!!pane.closest('.step-rail'),index=Number(pane.dataset.pane);selectPane(slides[current].rail_overview&&index===activePane?-1:index);if(rail)stage.querySelector('.step-rail [data-pane="'+index+'"]').focus({preventScroll:true});return;}
    const media=event.target.closest('[data-media]');if(media){const selected=Number(media.dataset.media);selectMediaFocused(selected);return;}
    const jump=event.target.closest('[data-index],[data-go]');
    if(jump){navigate(jump.dataset.index!==undefined?Number(jump.dataset.index):slides.findIndex(s=>s.id===jump.dataset.go));$('#agenda-dialog').close();return;}
    const close=event.target.closest('[data-close]');if(close){close.closest('dialog').close();return;}
    const img=event.target.closest('#slide-content img');
    if(img){event.preventDefault();openReading(img.alt||slides[current].title,`<img src="${esc(img.src)}" alt="${esc(img.alt)}">`);return;}
    const a=event.target.closest('#slide-content a[href],#reading-body a[href]');
    if(a){
      const url=new URL(a.getAttribute('href'),pageURL);
      const filename=url.pathname.split('/').pop();
      const page=a.getAttribute('href').startsWith('#')?(readingState?.context.page||slides[current].page):filename;
      if(url.origin===location.origin && (a.getAttribute('href').startsWith('#')||url.pathname.includes('/guide/'))){
        const anchor=decodeURIComponent(url.hash.slice(1));
        if($('#reading-dialog').open&&page===readingState?.context.page&&anchor&&scrollToReadingTarget(anchor)){event.preventDefault();return;}
        const objectiveIndex=anchor?slides.findIndex(s=>s.page===page&&s.learning_objectives?.targets.includes(anchor)):-1;
        if(objectiveIndex>=0){event.preventDefault();$('#reading-dialog').close();if(current!==objectiveIndex)navigate(objectiveIndex);setObjectivesOpen(true);return;}
        const match=slides.findIndex(s=>s.page===page&&(!anchor||s.readings?.some(r=>r.anchor===anchor||r.targets.includes(anchor))||s.popups?.some(p=>p.targets.includes(anchor))));
        if(match>=0){
          event.preventDefault();
          if(match!==current){$('#reading-dialog').close();navigate(match);}
          const slide=slides[current];
          const popup=slide.popups?.find(p=>p.targets.includes(anchor));
          const reading=slide.readings?.find(r=>r.anchor===anchor||r.targets.includes(anchor));
          const owner=popup?.pane??reading?.pane;
          $('#reading-dialog').close();
          if(owner!==null&&owner!==undefined){
            selectPane(owner);
            requestAnimationFrame(()=>{
              const box=stage.querySelector('[data-explanation-pane="'+owner+'"] .explanation-scroll');
              const target=[...(box?.querySelectorAll('[data-source-anchor]')||[])].find(n=>n.dataset.sourceAnchor===anchor);
              if(target&&box){box.scrollTop+=(target.getBoundingClientRect().top-box.getBoundingClientRect().top)/(innerWidth>900?stage.getBoundingClientRect().width/1600:1);}
              sendState();
            });
          }
        }else if(a.getAttribute('href').startsWith('#')){event.preventDefault();window.open('guide/'+page+url.hash,'_blank','noopener');}
      }
    }
  });

  $('#previous-button').onclick=()=>navigate(current-1);
  $('#next-button').onclick=()=>navigate(current+1);
  $('#console-next-button').onclick=()=>navigate(current+1);
  $('#page-number').addEventListener('change',()=>navigate(Number($('#page-number').value)-1));
  $('#agenda-button').onclick=()=>showAgenda();$('#session-button').onclick=()=>showAgenda();
  $('#reference-button').onclick=()=>renderAgendaList('',true);
  $('#search').addEventListener('input',()=>renderAgendaList($('#search').value));
  $('#fullscreen-button').onclick=fullscreen;$('#presenter-button').onclick=openPresenter;
  $('#help-button').onclick=()=>$('#help-dialog').showModal();
  $('#timer-button').onclick=()=>{if(timerStart){timerSaved+=Date.now()-timerStart;timerStart=0;}else timerStart=Date.now();updateTimer();sendState();};
  $('#reset-timer').onclick=()=>{timerSaved=0;timerStart=0;updateTimer();sendState();};
  $('#blank-screen').onclick=()=>{$('#blank-screen').hidden=true;};
  $('#reading-back').onclick=()=>{
    const previous=readingStack.pop();if(!previous)return;
    openReading(previous.title,previous.html,previous.context,false);
    $('#reading-body').scrollTop=previous.scroll;
  };
  $('#objectives-dialog').addEventListener('cancel',event=>{event.preventDefault();setObjectivesOpen(false);});
  $('#objectives-dialog').addEventListener('click',event=>{
    if(event.target!==event.currentTarget)return;
    const r=event.currentTarget.getBoundingClientRect();
    if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)setObjectivesOpen(false);
  });
  $('#reading-dialog').addEventListener('close',()=>{
    // A source link can close and immediately open a different reading.
    if($('#reading-dialog').open)return;
    pauseMedia($('#reading-body'));readingState=null;readingStack=[];
    if(activeSourcePopup){activeSourcePopup=null;sendState();}
    if(readingLauncher?.isConnected)readingLauncher.focus({preventScroll:true});
    sendState();
  });
  document.addEventListener('keydown',event=>{
    if (event.ctrlKey||event.metaKey||event.altKey) return;
    if(event.target.closest('input,textarea,select,[contenteditable="true"]'))return;
    if($$('dialog[open]').length)return;
    const key=event.key.toLowerCase();
    if(key==='escape'&&slides[current].rail_overview&&activePane>=0){event.preventDefault();const previous=activePane;selectPane(-1);stage.querySelector('.step-rail [data-pane="'+previous+'"]').focus();return;}
    if(event.target.closest('.step-rail')&&['arrowup','arrowdown','home','end'].includes(key)){
      event.preventDefault();const last=slides[current].panes.length-1;
      const next=key==='home'?0:key==='end'?last:Math.max(0,Math.min(last,Number(event.target.closest('[data-pane]').dataset.pane)+(key==='arrowdown'?1:-1)));
      selectPane(next);stage.querySelector('.step-rail [data-pane="'+next+'"]').focus();return;
    }
    if(event.target.closest('button,a')&&[' ','enter'].includes(key))return;
    if(event.target.closest('.explanation-scroll')&&['home','end','pageup','pagedown','arrowup','arrowdown',' '].includes(key))return;
    if (['arrowright','pagedown',' '].includes(key)){event.preventDefault();navigate(current+(event.shiftKey?-1:1));}
    else if(['arrowleft','pageup'].includes(key)){event.preventDefault();navigate(current-1);}
    else if(key==='home'){event.preventDefault();navigate(0);}
    else if(key==='end'){event.preventDefault();navigate(course.main_count-1);}
    else if(key==='d'){event.preventDefault();openReading(slides[current].title,originalHTML(slides[current]));}
    else if(key==='g'){event.preventDefault();showAgenda();}
    else if(key==='p'){event.preventDefault();openPresenter();}
    else if(key==='f'){event.preventDefault();fullscreen();}
    else if(key==='b'){$('#blank-screen').hidden=!$('#blank-screen').hidden;pauseMedia();}
    else if(key==='o'){window.open(sourceURL(),'_blank','noopener');}
    else if(key==='?'){$('#help-dialog').showModal();}
  });
  window.addEventListener('resize',()=>{fitStage();requestAnimationFrame(fitConceptContent);});
  window.addEventListener('hashchange',()=>{const i=slides.findIndex(s=>s.id===(course.aliases?.[decodeURIComponent(location.hash.slice(1))]||decodeURIComponent(location.hash.slice(1))));if(i>=0&&i!==current)navigate(i);});
  window.addEventListener('beforeunload',()=>pauseMedia());
  window.addEventListener('message',event=>{
    if(event.origin!==location.origin)return;
    const frame=[...stage.querySelectorAll('iframe')].find(f=>f.contentWindow===event.source);
    if(frame&&event.data?.type==='interactive-learning-diagram:ready')frame.contentWindow.postMessage({type:'interactive-learning-diagram:theme',theme:'light',tokens:{'--pst-color-primary':'#4e7d00','--nv-color-green':'#76b900'}},location.origin==='null'?'*':location.origin);
  });
  if (channel) channel.onmessage=event=>{
    const data=event.data;
    if(data.type==='controller-ping'){if(!embed)channel.postMessage({type:'controller-pong'});return;}
    if(data.type==='hello'){if(!embed)sendState();return;}
    if(data.type==='state'){
      if(stateMuted)return;
      receivingState=true;
      timerSaved=data.timerSaved;timerStart=data.timerStart;updateTimer();
      if(data.current!==current)navigate(data.current,false);
      if(data.activePane!==undefined&&data.activePane!==activePane)selectPane(data.activePane,false);
      if(data.activeMedia!==undefined&&data.activeMedia!==activeMedia)selectMedia(data.activeMedia,false);
      if(data.cardMediaSelections&&JSON.stringify(data.cardMediaSelections)!==JSON.stringify(cardMediaSelections)){cardMediaSelections=data.cardMediaSelections;renderConceptBody();}
      if(data.accordionSelections){accordionSelections=data.accordionSelections;restoreWorkflowAccordions();}
      if(data.explanationPositions){explanationPositions=data.explanationPositions;requestAnimationFrame(restoreExplanations);}
      if(data.diagramSelections)diagramSelections=data.diagramSelections;
      if(data.diagramScrollPositions)diagramScrollPositions=data.diagramScrollPositions;
      stage.querySelectorAll('iframe[data-diagram-key]').forEach(restoreDiagram);
      if(data.activeSourcePopup!==undefined)setSourcePopup(data.activeSourcePopup,false);
      if(data.objectivesOpen!==undefined)setObjectivesOpen(data.objectivesOpen,false);
      if(window.DLI_CONTROL)window.DLI_CONTROL.restore(data.control);else window.DLI_PENDING_CONTROL=data.control;
      receivingState=false;
      if(embed)parent.postMessage({type:'dli:state',state:data},'*');
      if(presenter)$('#connection').textContent='발표 창과 연결됨 · 같은 브라우저';
    }
  };
  if(presenter){document.body.classList.add('presenter-mode');$('#console').hidden=false;$('#presenter-button').hidden=true;}
  if(embed)document.body.classList.add('deck-preview');
  const initial=embed?embed.index:slides.findIndex(s=>s.id===(course.aliases?.[decodeURIComponent(location.hash.slice(1))]||decodeURIComponent(location.hash.slice(1))));
  navigate(initial>=0?initial:0,false);
  channel?.postMessage({type:'hello',role:embed?.role||'display'});
  updateTimer();setInterval(updateTimer,500);
  window.DLI_PRESENTATION={go:navigate,get index(){return current;},course,showAgenda,openReading,pauseMedia,selectPane,selectMedia,originalHTML,get pane(){return activePane;},get media(){return activeMedia;},
    captureState,sendState,setObjectivesOpen,setSourcePopup,
    // The close event can be delayed in an inactive window; publish visible state.
    get reading(){return $('#reading-dialog').open&&readingState?{...readingState,scroll:$('#reading-body').scrollTop}:null;},
    setCardMedia(pane,media){cardMediaSelections[pane]=media;renderConceptBody();},
    setDiagram(term){const frame=stage.querySelector('iframe[data-diagram-key]');if(frame){diagramSelections[frame.dataset.diagramKey]=term;diagramScrollPositions[frame.dataset.diagramKey]=0;restoreDiagram(frame);}},
    setAccordion(key,item){accordionSelections[key]=item;restoreWorkflowAccordions();},
    async batch(fn){stateMuted++;try{return await fn();}finally{stateMuted--;sendState();}},
    syncSilently(fn){receivingState=true;try{return fn();}finally{receivingState=false;}},
  };
})();
