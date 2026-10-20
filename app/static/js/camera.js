// Camera access starts only after the user explicitly selects Take photo.
(() => {
  const dialog = $('cameraDialog'), video = $('cameraVideo'), canvas = $('cameraCanvas');
  const errorBox = $('cameraError'), capture = $('cameraCapture'), use = $('cameraUse'), retake = $('cameraRetake');
  let stream = null, revision = 0, captured = false;
  function stop() {
    revision++;
    if (stream) stream.getTracks().forEach(track => track.stop());
    stream = null; video.srcObject = null; captured = false;
    canvas.width = canvas.height = 0;
  }
  function live() {
    captured = false; canvas.hidden = true; video.hidden = false;
    capture.hidden = false; capture.disabled = !video.videoWidth;
    retake.hidden = use.hidden = true;
  }
  $('sourceFiles').onclick = () => { $('photoSourceDialog').close(); choose(); };
  $('sourceCamera').onclick = async () => {
    $('photoSourceDialog').close();
    if (state.busy) return;
    if (state.images.length >= 8) return toast('本次已達 8 張，請先送出或移除照片。');
    stop(); const request = revision;
    errorBox.textContent = '正在開啟相機…'; live(); dialog.showModal();
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      errorBox.textContent = '此瀏覽器無法開啟相機，請使用 HTTPS 網址或改為選擇照片。'; return;
    }
    try {
      const opened = await navigator.mediaDevices.getUserMedia({ audio: false, video: { facingMode: { ideal: 'environment' }, width: { ideal: 1920 }, height: { ideal: 1080 } } });
      if (request !== revision || !dialog.open) { opened.getTracks().forEach(track => track.stop()); return; }
      stream = opened; video.srcObject = opened;
      await video.play();
      if (request !== revision) return;
      errorBox.textContent = ''; capture.disabled = !video.videoWidth;
    } catch (error) {
      if (request !== revision) return;
      stop(); capture.disabled = true;
      errorBox.textContent = error.name === 'NotAllowedError' ? '相機權限未允許。請在瀏覽器的網站權限中允許相機，或改為選擇照片。' : error.name === 'NotFoundError' ? '找不到相機，請改為選擇照片。' : '相機無法開啟，請確認沒有被其他程式占用後重試。';
    }
  };
  video.onloadeddata = () => { if (stream && !captured) capture.disabled = !video.videoWidth; };
  capture.onclick = () => {
    if (!stream || !video.videoWidth) return;
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    captured = true; canvas.hidden = false; video.hidden = true;
    capture.hidden = true; retake.hidden = use.hidden = false;
  };
  retake.onclick = live;
  use.onclick = () => {
    if (!captured || state.busy) return;
    use.disabled = true; const request = revision;
    canvas.toBlob(blob => {
      use.disabled = false;
      if (request !== revision || !dialog.open) return;
      if (!blob) { errorBox.textContent = '照片產生失敗，請重拍。'; return; }
      addFiles([new File([blob], 'camera-' + Date.now() + '.jpg', { type: 'image/jpeg' })]);
      dialog.close();
    }, 'image/jpeg', 0.95);
  };
  dialog.addEventListener('close', stop);
  window.addEventListener('pagehide', () => { stop(); if (dialog.open) dialog.close(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden && dialog.open) { stop(); dialog.close(); } });
})();
