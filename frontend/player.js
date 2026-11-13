export async function playWithSound(video) {
  video.muted = false;
  video.volume = 1;
  await video.play();
}
export function alarmActive(time, alarms) {
  return alarms.some(a => time >= a.start_seconds && time < a.end_seconds);
}
export function fittedSize(width, height, availableWidth, availableHeight) {
  const scale = Math.min(availableWidth / width, availableHeight / height);
  return {width:width * scale, height:height * scale};
}
export default function({parentElement, data}) {
  const root = parentElement.querySelector('.result-player');
  const video = root.querySelector('video');
  const play = root.querySelector('[data-play]');
  const test = root.querySelector('[data-test]');
  const mode = root.querySelector('select');
  const status = root.querySelector('[data-status]');
  const Audio = window.AudioContext || window.webkitAudioContext;
  let context, oscillator, gain, ticker;
  let testUntil = 0, buffering = false;
  const sound = async () => {
    if (!Audio) throw new Error('Browser audio is unavailable.');
    if (!context) {
      context = new Audio(); gain = context.createGain();gain.gain.value=0;
      oscillator=context.createOscillator();oscillator.frequency.value=880;
      oscillator.connect(gain);gain.connect(context.destination);oscillator.start();
    }
    await context.resume();
  };
  const sync = () => {
    const checking = context && context.currentTime < testUntil;
    const active = mode.value==='browser' && !buffering && !video.paused && !video.ended && !video.seeking && alarmActive(video.currentTime,data.alarms);
    if(gain) gain.gain.setTargetAtTime((checking || active) ? .25 : 0,context.currentTime,.005);
  };
  const resize = () => {
    if(!video.videoWidth) return;
    const fit=fittedSize(video.videoWidth,video.videoHeight,root.clientWidth,Math.max(180,window.innerHeight-190));
    video.style.width=fit.width+'px';video.style.height=fit.height+'px';
  };
  // Keep one DOM/media instance on Python reruns. No media URL reload during playback.
  if(video.getAttribute('src')!==data.url)video.src=data.url;
  video.onloadedmetadata=resize;
  play.onclick=async()=>{
    try {
      if(mode.value==='browser') {
        await sound(); video.muted=true; await video.play();
      } else await playWithSound(video);
      status.textContent=mode.value==='browser'?'Browser alarm enabled; follows video time.':'Video sound enabled at full player volume.';
    }catch(e){status.textContent='Playback could not start: '+e.message;}
  };
  test.onclick=async()=>{
    try {
      await sound();testUntil=context.currentTime+.35;gain.gain.setValueAtTime(.25,context.currentTime);
      gain.gain.setValueAtTime(0,context.currentTime+.35);
      status.textContent='Sound check played. If silent, check this site/tab and device volume.';
    }catch(e){status.textContent=e.message;}
  };
  mode.onchange=()=>{video.pause();video.muted=mode.value==='browser';sync();status.textContent='Press Play with sound to use the selected audio.';};
  const onWaiting=()=>{buffering=true;sync();};
  const onPlaying=()=>{buffering=false;sync();};
  video.addEventListener('waiting',onWaiting);video.addEventListener('playing',onPlaying);
  for(const event of ['pause','ended','seeking','seeked','timeupdate','play','waiting']) video.addEventListener(event,sync);
  ticker=setInterval(sync,30);
  const observer=new ResizeObserver(resize);observer.observe(root);window.addEventListener('resize',resize);resize();
  return ()=>{
    // A rerun closes the audio graph: pause too, so fallback never runs silently.
    video.pause();
    status.textContent='Press Play with sound to resume after a page update.';
    clearInterval(ticker);observer.disconnect();window.removeEventListener('resize',resize);
    for(const event of ['pause','ended','seeking','seeked','timeupdate','play','waiting'])video.removeEventListener(event,sync);
    video.removeEventListener('waiting',onWaiting);video.removeEventListener('playing',onPlaying);
    if(context)context.close();
    play.onclick=null;test.onclick=null;mode.onchange=null;video.onloadedmetadata=null;
  };
}
