const RFSecurity = {
  captchaAnswer: null,
  loadTime: Date.now(),

  newCaptcha() {
    const a = Math.floor(Math.random() * 9) + 2;
    const b = Math.floor(Math.random() * 9) + 2;
    this.captchaAnswer = a + b;
    const el = document.getElementById('captchaQ');
    if (el) el.textContent = a + ' + ' + b + ' =';
    const input = document.getElementById('captchaA');
    if (input) input.value = '';
  },

  checkCaptcha() {
    const input = document.getElementById('captchaA');
    if (!input) return false;
    return parseInt(input.value, 10) === this.captchaAnswer;
  },

  checks() {
    const hp = document.getElementById('website');
    if (hp && hp.value !== '') return { ok: false, msg: 'Spam protection triggered.' };
    if (!this.checkCaptcha()) return { ok: false, msg: 'CAPTCHA answer is incorrect.' };
    if (Date.now() - this.loadTime < 3000) return { ok: false, msg: 'Too fast. Please wait a moment and retry.' };
    return { ok: true };
  },

  async sha256(text) {
    const data = new TextEncoder().encode(text);
    const buf = await crypto.subtle.digest('SHA-256', data);
    return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('');
  },

  rateLimit(key, max, windowMs) {
    const now = Date.now();
    const store = JSON.parse(localStorage.getItem('rf_rl_' + key) || '[]');
    const recent = store.filter(t => now - t < windowMs);
    recent.push(now);
    localStorage.setItem('rf_rl_' + key, JSON.stringify(recent));
    return recent.length <= max;
  }
};
document.addEventListener('DOMContentLoaded', () => RFSecurity.newCaptcha());
