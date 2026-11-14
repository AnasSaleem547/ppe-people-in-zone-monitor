// Canvas interaction and original-frame coordinate mapping.
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
  const config = data.config;

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
      if (points.length === config.corner_count) {
        ctx.closePath();
        ctx.fillStyle = config.fill_style;
        ctx.fill();
      }
      ctx.strokeStyle = config.stroke_style;
      ctx.lineWidth = config.line_width;
      ctx.stroke();
      ctx.font = config.font;
      points.forEach(([x,y], i) => {
        ctx.fillStyle = config.point_style;
        ctx.beginPath(); ctx.arc(x,y,config.point_radius,0,2*Math.PI); ctx.fill();
        ctx.fillText(String(i+1), x+config.label_offset_x, y+config.label_offset_y);
      });
    }

    note.textContent = points.length === config.corner_count ? 'Region ready. Review N/T below, then confirm and process.' : `Click ${config.corner_count} corners in order (${points.length}/${config.corner_count}).`;
  }
  image.onload = () => {
    if (disposed) return;
    canvas.width = image.width;
    canvas.height = image.height;
    draw();
  };
  image.src = data.first_frame;
  canvas.onpointerdown = event => {
    if (points.length === config.corner_count || !image.complete || !image.naturalWidth) return;
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
