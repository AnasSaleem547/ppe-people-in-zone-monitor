// Same four-corner canvas interaction and coordinate mapping as notebook cell 11.
export function eventPoint(event, rect, width, height) {
  return [
    Math.min(width - 1, Math.max(0, (event.clientX - rect.left) * width / rect.width)),
    Math.min(height - 1, Math.max(0, (event.clientY - rect.top) * height / rect.height)),
  ];
}

export function toOriginal(points, previewWidth, previewHeight, width, height) {
  return points.map(([x, y]) => [x * width / previewWidth, y * height / previewHeight]);
}

export default function({data, parentElement, setStateValue}) {
  const root = parentElement.querySelector('.zone-annotation');
  const canvas = root.querySelector('canvas');
  const reset = root.querySelector('[data-reset]');

  const note = root.querySelector('[data-note]');
  const ctx = canvas.getContext('2d');
  const image = new Image();
  let points = (data.selection?.preview_points || []).map(p => [...p]);
  let confirmed = Boolean(data.selection?.confirmed);
  let disposed = false;

  function publish() {
    setStateValue('selection', {
      preview_points: points.map(p => [...p]),
      points: toOriginal(points, canvas.width, canvas.height, data.width, data.height),
      confirmed,
    });
  }
  function draw() {
    if (disposed || !image.complete || !image.naturalWidth) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0);
    if (points.length) {
      ctx.beginPath();
      points.forEach(([x,y], i) => i ? ctx.lineTo(x,y) : ctx.moveTo(x,y));
      if (points.length === 4) {
        ctx.closePath();
        ctx.fillStyle = 'rgba(0,255,100,0.25)';
        ctx.fill();
      }
      ctx.strokeStyle = '#00ff66';
      ctx.lineWidth = 3;
      ctx.stroke();
      ctx.font = '18px sans-serif';
      points.forEach(([x,y], i) => {
        ctx.fillStyle = '#ffff00';
        ctx.beginPath(); ctx.arc(x,y,5,0,2*Math.PI); ctx.fill();
        ctx.fillText(String(i+1), x+8, y+5);
      });
    }

    note.textContent = points.length === 4 ? 'Region ready. Review N/T below, then confirm and process.' : `Click four corners in order (${points.length}/4).`;
  }
  image.onload = () => {
    if (disposed) return;
    canvas.width = image.width;
    canvas.height = image.height;
    draw();
  };
  image.src = data.first_frame;
  canvas.onpointerdown = event => {
    if (points.length === 4 || !image.complete || !image.naturalWidth) return;
    event.preventDefault();
    points.push(eventPoint(event, canvas.getBoundingClientRect(), canvas.width, canvas.height));
    confirmed = false;
    draw();
    publish();
  };
  reset.onclick = () => { points = []; confirmed = false; draw(); publish(); };

  return () => {
    disposed = true;
    image.onload = null;
    canvas.onpointerdown = null;
    reset.onclick = null;

  };
}
