(() => {
  const comparison=document.querySelector('.image-comparison');
  if(comparison){
    const stage=comparison.querySelector('.image-comparison-stage');
    const fit=()=>{
      const side=stage.dataset.mode==='side';
      const siblings=[...stage.parentElement.children];
      const tail=siblings.slice(siblings.indexOf(stage)+1).reduce((height,node)=>{
        const style=getComputedStyle(node);
        return height+node.getBoundingClientRect().height+parseFloat(style.marginTop||0)+parseFloat(style.marginBottom||0);
      },0);
      const remaining=Math.max(120,innerHeight-stage.getBoundingClientRect().top-tail-(side?45:14));
      stage.style.maxWidth=(remaining*4/3*(side?2:1))+'px';
    };
    comparison.querySelectorAll('input,select,button').forEach(el=>el.addEventListener('change',()=>requestAnimationFrame(fit)));
    new ResizeObserver(fit).observe(comparison);
    fit();
  }
  const root=document.querySelector('.groot-explorers');
  if(!root)return;
  const panels=[...root.querySelectorAll('.groot-explorer')];
  root.querySelectorAll('.groot-caption').forEach(caption=>{
    const detail=document.createElement('details');detail.className='widget-note';
    const summary=document.createElement('summary');summary.textContent='Timing 예시의 조건';
    caption.before(detail);detail.append(summary,caption);
  });
  const toolbar=document.createElement('div');toolbar.className='widget-toolbar';
  const tabs=document.createElement('nav');
  tabs.className='widget-tabs';
  tabs.setAttribute('aria-label','Intro, Training과 Inference');
  tabs.setAttribute('role','tablist');
  const resets=document.createElement('div');resets.className='widget-resets';
  const resetButtons=panels.map(panel=>panel.querySelector('.groot-reset'));
  resetButtons.forEach(reset=>{
    if(!reset)return;
    const description=reset.textContent.trim();
    reset.title=description;reset.setAttribute('aria-label',description);
    reset.textContent='Reset';resets.append(reset);
  });
  const buttons=[];
  function selectPanel(index,focus=false){
    panels.forEach((panel,i)=>{
      panel.hidden=i!==index;
      buttons[i].setAttribute('aria-selected',String(i===index));
      buttons[i].tabIndex=i===index?0:-1;
      if(resetButtons[i])resetButtons[i].hidden=i!==index;
    });
    resets.hidden=!resetButtons[index];
    if(focus)buttons[index].focus();
  }
  panels.forEach((panel,index)=>{
    const button=document.createElement('button');
    button.type='button';button.id=panel.id+'-tab';
    button.textContent={'groot-intro':'Intro','groot-training':'Training','groot-inference':'Inference'}[panel.id];
    button.setAttribute('role','tab');
    button.setAttribute('aria-controls',panel.id);
    panel.setAttribute('role','tabpanel');panel.setAttribute('aria-labelledby',button.id);
    button.addEventListener('click',()=>selectPanel(index));
    button.addEventListener('keydown',event=>{
      const next={ArrowRight:(index+1)%panels.length,ArrowLeft:(index+panels.length-1)%panels.length,Home:0,End:panels.length-1}[event.key];
      if(next!==undefined){event.preventDefault();selectPanel(next,true);}
    });
    buttons.push(button);tabs.append(button);
  });
  toolbar.append(tabs,resets);root.before(toolbar);
  selectPanel(0);
})();
