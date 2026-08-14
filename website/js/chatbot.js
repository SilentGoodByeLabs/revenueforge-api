const CONTACT_EMAIL = 'adeolaayodeji4666@gmail.com';

const BOT_KB = [
  { k: ['price', 'pricing', 'cost', 'quote', 'how much'], a: 'Pricing is transparent: a free automation audit, fixed-quote build sprints, and monthly retainers. Every quote is fixed before work begins. See the Pricing page for details.' },
  { k: ['service', 'what do you do', 'offer', 'build'], a: 'We build AI sales outreach systems, CRM & workflow automation, document/PDF automation, chatbots, and custom AI agents — all compliance-first with human approval on every action.' },
  { k: ['spam', 'safe', 'legal', 'compliance', 'rule'], a: 'Yes — we only use official APIs and permitted channels. No spam, no scraping bans, no fake accounts. Every message waits for human approval, and opt-outs are always respected.' },
  { k: ['time', 'long', 'deadline', 'fast'], a: 'Most build sprints run 1–3 weeks depending on scope. You get a fixed timeline with the quote before any work starts.' },
  { k: ['human', 'person', 'email', 'contact', 'talk'], a: 'You can email the founder directly — the button below opens your mail app pre-filled.', human: true }
];

(function () {
  const fab = document.createElement('button');
  fab.className = 'bot-fab';
  fab.innerHTML = '<i class="fa-solid fa-comments"></i>';
  fab.setAttribute('aria-label', 'Open chat');

  const panel = document.createElement('div');
  panel.className = 'bot-panel';
  panel.innerHTML =
    '<div class="bot-head"><span><i class="fa-solid fa-robot"></i> Forge Assistant</span>' +
    '<button id="botClose" style="background:none;border:none;color:#fff;font-size:16px;cursor:pointer" aria-label="Close chat"><i class="fa-solid fa-xmark"></i></button></div>' +
    '<div class="bot-body" id="botBody"></div>' +
    '<div class="bot-chips" id="botChips"></div>';

  document.body.appendChild(fab);
  document.body.appendChild(panel);

  const body = panel.querySelector('#botBody');
  const chips = panel.querySelector('#botChips');

  function addMsg(text, who) {
    const d = document.createElement('div');
    d.className = 'msg ' + who;
    d.textContent = text;
    body.appendChild(d);
    body.scrollTop = body.scrollHeight;
  }

  function humanButton() {
    const b = document.createElement('button');
    b.className = 'btn btn-primary btn-sm bot-mail';
    b.innerHTML = '<i class="fa-solid fa-envelope"></i> Email the founder';
    b.onclick = function () {
      window.location.href = 'mailto:' + CONTACT_EMAIL +
        '?subject=' + encodeURIComponent('Question from website chat') +
        '&body=' + encodeURIComponent('Hi RevenueForge,\n\n(Paste your question here)\n\n— sent from the website chat');
    };
    panel.appendChild(b);
  }

  function answer(q) {
    const t = q.toLowerCase();
    for (const item of BOT_KB) {
      if (item.k.some(k => t.includes(k))) {
        addMsg(item.a, 'bot');
        if (item.human) humanButton();
        return;
      }
    }
    addMsg('Good question. The fastest way to get an exact answer is to email the founder directly — the button below opens your mail app pre-filled.', 'bot');
    humanButton();
  }

  ['Services', 'Pricing', 'Is this spam-safe?', 'Talk to a human'].forEach(q => {
    const b = document.createElement('button');
    b.textContent = q;
    b.onclick = function () { addMsg(q, 'user'); answer(q); };
    chips.appendChild(b);
  });

  fab.onclick = function () {
    panel.classList.toggle('open');
    if (!panel.dataset.greeted) {
      panel.dataset.greeted = '1';
      addMsg('Hi! I am the Forge Assistant. Ask me about services, pricing or compliance — or jump straight to a human email.', 'bot');
    }
  };
  panel.querySelector('#botClose').onclick = function () { panel.classList.remove('open'); };
})();
