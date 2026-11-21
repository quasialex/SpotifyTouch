/* Optional MagicMirror button: asks the persistent kiosk controller to show Spotify.
   The MagicMirror Node.js server stays running; the viewer navigates pages. */
Module.register('MMM-SpotifyTouch', {
  defaults: { anchorSelector: '.kuma-summary' },
  start() {
    this.launcher = null;
    this.positionTimer = setInterval(() => this.reposition(), 2000);
  },
  getStyles() { return ['MMM-SpotifyTouch.css']; },
  getDom() {
    const anchor = document.createElement('div');
    anchor.className = 'spotify-touch-anchor';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'spotify-touch-launch';
    btn.title = 'Open Spotify';
    btn.setAttribute('aria-label', 'Open Spotify');
    const img = document.createElement('img');
    img.src = this.file('spotify-glyph.svg');
    img.alt = 'Spotify';
    btn.append(img);
    btn.addEventListener('click', e => {
      e.preventDefault(); e.stopPropagation();
      if (btn.disabled) return;
      btn.disabled = true;
      this.sendSocketNotification('SPOTIFY_APPLIANCE_ENTER');
      setTimeout(() => { if (btn.isConnected) btn.disabled = false; }, 6000);
    });
    anchor.append(btn);
    this.launcher = btn;
    window.requestAnimationFrame(() => this.reposition());
    return anchor;
  },
  reposition() {
    if (!this.launcher?.isConnected) return;
    const kuma = document.querySelector(this.config.anchorSelector);
    if (!kuma) {
      // Generic MagicMirror setups may not have the author's Kuma widget.
      // Fall back to a top-right launcher; keep the touch target visible.
      const size = 72;
      this.launcher.style.width = size + 'px';
      this.launcher.style.height = size + 'px';
      this.launcher.style.left = Math.max(6, window.innerWidth-size-14) + 'px';
      this.launcher.style.top = '14px';
      this.launcher.style.visibility = 'visible';
      return;
    }
    const r = kuma.getBoundingClientRect();
    if (r.width < 10 || r.height < 10) { this.launcher.style.visibility = 'hidden'; return; }
    // Scale with the Kuma status block but avoid obscuring it or the viewport.
    const desired = Math.round(Math.max(62, Math.min(92, r.height * 0.644)));
    const gap = 18;
    const side = Math.max(56, Math.min(desired, r.left - gap - 10));
    this.launcher.style.width = side + 'px';
    this.launcher.style.height = side + 'px';
    this.launcher.style.left = Math.max(6, r.left-side-gap)+'px';
    this.launcher.style.top = Math.max(6, Math.min(window.innerHeight-side-6, r.top+(r.height-side)/2))+'px';
    this.launcher.style.visibility = 'visible';
  },
  socketNotificationReceived(type, message) {
    if (type === 'SPOTIFY_APPLIANCE_ERROR') {
      console.error('[Spotify Appliance]', message);
      if (this.launcher) {
        this.launcher.disabled = false;
        this.launcher.title = 'Spotify unavailable: ' + String(message).slice(0, 120);
      }
    }
  },
  suspend() { clearInterval(this.positionTimer); this.positionTimer = null; },
  resume() { if (!this.positionTimer) this.positionTimer = setInterval(() => this.reposition(), 2000); }
});