const menuBtn=document.querySelector('.menu-toggle');
const nav=document.querySelector('.nav-panel');
if(menuBtn&&nav){
menuBtn.addEventListener('click',()=>nav.classList.toggle('open'));
nav.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>nav.classList.remove('open')))
}
const topBtn=document.getElementById('scrollTop');
window.addEventListener('scroll',()=>{
if(window.scrollY>650){
topBtn?.classList.add('show')
}
else{
topBtn?.classList.remove('show')
}
}
);
topBtn?.addEventListener('click',()=>window.scrollTo({
top:0,behavior:'smooth'
}
));
const dateInput=document.querySelector('input[name="appointment_date"]');
if(dateInput){
const d=new Date();
d.setDate(d.getDate()+1);
dateInput.min=d.toISOString().split('T')[0];
}
// Premium stats counter: slower, smoother, and only starts when the stats are visible.
const statNumbers=document.querySelectorAll('.trust-row strong');
const prefersReducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function animateStat(el){
  if(el.dataset.counted==='true') return;
  el.dataset.counted='true';
  const original=el.textContent.trim();
  const target=parseInt(original.replace(/[^0-9]/g,''),10);
  const suffix=original.replace(/[0-9]/g,'');
  if(!target || prefersReducedMotion){
    el.textContent=original;
    return;
  
}
  const duration=2600;
  const start=performance.now();
  el.textContent=`0${
suffix
}
`;
  function tick(now){
    const progress=Math.min((now-start)/duration,1);
    const eased=1-Math.pow(1-progress,3);
    const value=Math.round(target*eased);
    el.textContent=`${
value
}
${
suffix
}
`;
    if(progress<1){
requestAnimationFrame(tick)
}
else{
el.textContent=original
}
  
}
  requestAnimationFrame(tick);
}
if('IntersectionObserver' in window){
  const statsObserver=new IntersectionObserver((entries)=>{
    entries.forEach(entry=>{
      if(entry.isIntersecting){
        statNumbers.forEach((el,index)=>setTimeout(()=>animateStat(el),index*180));
        statsObserver.disconnect();
      
}
    
}
);
  
}
,{
threshold:.45
}
);
  const trustRow=document.querySelector('.trust-row');
  if(trustRow){
statsObserver.observe(trustRow)
}
}
else{
  statNumbers.forEach((el,index)=>setTimeout(()=>animateStat(el),index*180));
}

// Load videos and Facebook only when their activity area is close to view.
const lazyMedia=document.querySelectorAll('.lazy-video, .lazy-embed');
function loadMedia(el){
  if(el.dataset.loaded==='true') return;
  el.dataset.loaded='true';
  if(el.matches('video')&&el.dataset.src){
    el.src=el.dataset.src;
    el.load();
    if(el.closest('.activity-slide.is-active')) el.play().catch(()=>{});
  }
  if(el.classList.contains('lazy-embed')&&el.dataset.embedSrc){
    const frame=document.createElement('iframe');
    frame.src=el.dataset.embedSrc;
    frame.title='ORCA Facebook activity';
    frame.loading='lazy';
    frame.allow='autoplay; clipboard-write; encrypted-media; picture-in-picture; web-share';
    frame.allowFullscreen=true;
    el.replaceChildren(frame);
  }
}
if('IntersectionObserver' in window){
  const mediaObserver=new IntersectionObserver(entries=>{
    entries.forEach(entry=>{
      if(entry.isIntersecting){
        loadMedia(entry.target);
        mediaObserver.unobserve(entry.target);
      }
    });
  },{rootMargin:'300px 0px'});
  lazyMedia.forEach(el=>mediaObserver.observe(el));
}else{
  lazyMedia.forEach(loadMedia);
}

// Reusable touch-friendly sliders for social posts and new project images.
document.querySelectorAll('[data-slider]').forEach(slider=>{
  const slides=[...slider.querySelectorAll('.activity-slide')];
  const count=slider.querySelector('[data-count]');
  let current=0;
  let startX=0;
  let timer;
  const show=index=>{
    slides[current]?.classList.remove('is-active');
    slides[current]?.querySelector('video')?.pause();
    current=(index+slides.length)%slides.length;
    const active=slides[current];
    active.classList.add('is-active');
    const video=active.querySelector('video');
    if(video){
      loadMedia(video);
      video.play().catch(()=>{});
    }
    active.querySelectorAll('.lazy-embed').forEach(loadMedia);
    if(count) count.textContent=`${current+1} / ${slides.length}`;
  };
  slider.querySelector('[data-prev]')?.addEventListener('click',()=>show(current-1));
  slider.querySelector('[data-next]')?.addEventListener('click',()=>show(current+1));
  slider.addEventListener('touchstart',event=>{startX=event.changedTouches[0].clientX},{passive:true});
  slider.addEventListener('touchend',event=>{
    const distance=event.changedTouches[0].clientX-startX;
    if(Math.abs(distance)>45) show(current+(distance<0?1:-1));
  },{passive:true});
  if(slider.dataset.autoplay==='true'&&!prefersReducedMotion){
    const start=()=>{timer=setInterval(()=>show(current+1),5000)};
    const stop=()=>clearInterval(timer);
    slider.addEventListener('mouseenter',stop);
    slider.addEventListener('mouseleave',start);
    start();
  }
  show(0);
});
