/* No audio subprocess. The dedicated systemd user audio service survives UI switching. */
const NodeHelper = require('node_helper');
const http = require('node:http');
module.exports = NodeHelper.create({
  socketNotificationReceived(type) {
    if (type !== 'SPOTIFY_APPLIANCE_ENTER') return;
    const req = http.request({
      hostname: '127.0.0.1', port: 16181, path: '/enter', method: 'POST',
      timeout: 2500, headers: {'X-Spotify-Appliance':'1'}
    }, res => {
      res.resume();
      if (res.statusCode !== 202) this.sendSocketNotification('SPOTIFY_APPLIANCE_ERROR', `Switch service returned ${res.statusCode}`);
    });
    req.on('timeout', () => req.destroy(new Error('Switch service timed out')));
    req.on('error', err => this.sendSocketNotification('SPOTIFY_APPLIANCE_ERROR', err.message));
    req.end();
  }
});