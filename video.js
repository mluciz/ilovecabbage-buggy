'use strict';
// The supplied portrait-encoded clip was physically rotated to landscape.
// Deployment splits the MP4 into small byte chunks for reliable publishing;
// bytes are concatenated before playback, preserving the complete video/audio.
(async () => {
  const video = document.getElementById('team-video');
  if (!video) return;
  if (location.protocol === 'file:') {
    // Offline backup includes the complete original converted video.
    video.src = './assets/ilovecabbage-feature.mp4';
    return;
  }
  const parts = Array.from({length: 8}, (_, i) =>
    `./assets/ilovecabbage-feature.p${String(i + 1).padStart(2, '0')}`);
  try {
    const data = await Promise.all(parts.map(async path => {
      const response = await fetch(path, {cache: 'force-cache'});
      if (!response.ok) throw new Error(`Video segment unavailable (${response.status})`);
      return await response.arrayBuffer();
    }));
    const playable = new Blob(data, {type: 'video/mp4'});
    const objectUrl = URL.createObjectURL(playable);
    video.src = objectUrl;
    video.load();
    const safePlay = () => video.play().catch(() => {});
    if (video.autoplay) video.addEventListener('loadeddata', safePlay, {once:true});
    window.addEventListener('pagehide', () => URL.revokeObjectURL(objectUrl), {once:true});
  } catch(error) {
    video.setAttribute('aria-label','Video is temporarily unavailable');
    console.warn('Team video did not load:', error);
  }
})();
