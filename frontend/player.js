export function fittedSize(width, height, availableWidth, availableHeight) {
  const scale = Math.min(availableWidth / width, availableHeight / height);
  return {width:width * scale, height:height * scale};
}
export default function({parentElement, data}) {
  const root = parentElement.querySelector('.result-player');
  const video = root.querySelector('video');
  const resize = () => {
    if(!video.videoWidth) return;
    const fit=fittedSize(video.videoWidth,video.videoHeight,root.clientWidth,Math.max(180,window.innerHeight-190));
    video.style.width=fit.width+'px';video.style.height=fit.height+'px';
  };
  if(video.getAttribute('src')!==data.url) {
    video.src=data.url;
    video.muted=false;
    video.volume=1;
  }
  video.onloadedmetadata=resize;
  const observer=new ResizeObserver(resize);
  observer.observe(root);window.addEventListener('resize',resize);resize();
  return ()=>{
    observer.disconnect();window.removeEventListener('resize',resize);
    video.onloadedmetadata=null;
  };
}
