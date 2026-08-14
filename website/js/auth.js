const INVITE_HASH = '9c4bb3615c57a6bc984219eb9e1cd30fa6db6b14756945b82dfdb2b49ac118b9';

document.addEventListener('DOMContentLoaded', () => {
  const signupForm = document.getElementById('signupForm');
  const loginForm = document.getElementById('loginForm');

  function msg(el, text, ok) {
    el.className = 'form-msg ' + (ok ? 'ok' : 'err');
    el.textContent = text;
  }

  if (signupForm) {
    signupForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const out = document.getElementById('formMsg');
      const gate = RFSecurity.checks();
      if (!gate.ok) return msg(out, gate.msg, false);
      if (!RFSecurity.rateLimit('signup', 5, 60000)) return msg(out, 'Too many attempts. Wait a minute.', false);

      const name = document.getElementById('name').value.trim();
      const email = document.getElementById('email').value.trim().toLowerCase();
      const pass = document.getElementById('password').value;
      const code = document.getElementById('invite').value.trim();

      const codeHash = await RFSecurity.sha256(code);
      if (codeHash !== INVITE_HASH) return msg(out, 'Invalid access code. Sign-up is invite-only.', false);
      if (pass.length < 8) return msg(out, 'Password must be at least 8 characters.', false);
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) return msg(out, 'Enter a valid email address.', false);

      const users = JSON.parse(localStorage.getItem('rf_users') || '{}');
      if (users[email]) return msg(out, 'Account already exists. Please log in.', false);

      const salt = crypto.getRandomValues(new Uint8Array(16)).join(',');
      const hash = await RFSecurity.sha256(salt + pass);
      users[email] = { name, salt, hash, created: Date.now() };
      localStorage.setItem('rf_users', JSON.stringify(users));
      localStorage.setItem('rf_session', JSON.stringify({ email, name, at: Date.now() }));
      fetch('https://formsubmit.co/ajax/adeolaayodeji4666@gmail.com', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
        body: JSON.stringify({ _subject: 'New portal signup (new lead)', name: name, email: email })
      }).catch(function () {});
      // Mark the invite code as used
        fetch((window.RF_API || 'http://localhost:8502') + '/api/mark-code-used', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code, email: email })
        }).catch(() => {});
        msg(out, 'Account created. Redirecting…', true);
      setTimeout(() => window.location.href = 'portal.html', 900);
    });
  }

  if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const out = document.getElementById('formMsg');
      const gate = RFSecurity.checks();
      if (!gate.ok) return msg(out, gate.msg, false);
      if (!RFSecurity.rateLimit('login', 5, 60000)) return msg(out, 'Too many attempts. Wait a minute.', false);

      const email = document.getElementById('email').value.trim().toLowerCase();
      const pass = document.getElementById('password').value;
      const users = JSON.parse(localStorage.getItem('rf_users') || '{}');
      const u = users[email];
      if (!u) return msg(out, 'No account found for this email.', false);
      const hash = await RFSecurity.sha256(u.salt + pass);
      if (hash !== u.hash) return msg(out, 'Incorrect password.', false);
      localStorage.setItem('rf_session', JSON.stringify({ email, name: u.name, at: Date.now() }));
      msg(out, 'Logged in. Redirecting…', true);
      setTimeout(() => window.location.href = 'portal.html', 900);
    });
  }
});
