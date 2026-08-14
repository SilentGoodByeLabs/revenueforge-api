const HEADER = `
<header class="site-header">
  <div class="container nav-wrap">
    <div style="display:flex;align-items:center;gap:14px">
      <button class="w-menu-btn" id="wMenuBtn" aria-label="Open menu"><span class="bar"></span><span class="bar"></span><span class="bar"></span></button>
      <a class="brand" href="index.html">
        <img src="assets/logo.png" alt="RevenueForge logo" class="logo">
        <span class="brand-name">Revenue<span>Forge</span></span>
      </a>
    </div>
    <div style="display:flex;align-items:center;gap:10px">
      <a href="book-call.html" class="btn btn-primary btn-sm">Book a Call</a>
      <a href="audit.html" class="btn btn-ghost btn-sm">Free Audit</a>
      <a href="login.html" id="portalLink" class="btn btn-ghost btn-sm">Client Login</a>
    </div>
  </div>
  <nav class="w-menu" id="wMenu">
    <div class="w-menu-inner">
      <a href="index.html"><i class="fa-solid fa-house"></i> Home</a>
      <a href="services.html"><i class="fa-solid fa-gears"></i> Services</a>
      <a href="case-studies.html"><i class="fa-solid fa-chart-line"></i> Case Studies</a>
      <a href="blog.html"><i class="fa-solid fa-newspaper"></i> Blog</a>
      <a href="about.html"><i class="fa-solid fa-circle-info"></i> About</a>
      <a href="testimonials.html"><i class="fa-solid fa-star"></i> Testimonials</a>
      <a href="pricing.html"><i class="fa-solid fa-tags"></i> Pricing</a>
      <a href="faq.html"><i class="fa-solid fa-circle-question"></i> FAQ</a>
      <a href="contact.html"><i class="fa-solid fa-envelope"></i> Contact</a>
      <a href="privacy.html"><i class="fa-solid fa-shield-halved"></i> Privacy</a>
      <a href="terms.html"><i class="fa-solid fa-file-contract"></i> Terms</a>
    </div>
  </nav>
</header>`;

const FOOTER = `
<footer class="site-footer">
  <div class="container footer-grid">
    <div>
      <div class="brand footer-brand">
        <img src="assets/logo.png" alt="RevenueForge logo" class="logo">
        <span class="brand-name">Revenue<span>Forge</span></span>
      </div>
      <p class="footer-text">Compliance-first AI revenue operations. We research, score, prepare and track — you approve every step.</p>
    </div>
    <div>
      <h4>Company</h4>
      <a href="about.html">About</a>
      <a href="testimonials.html">Testimonials</a>
      <a href="pricing.html">Pricing</a>
      <a href="contact.html">Contact</a>
      <a href="faq.html">FAQ</a>
      <a href="privacy.html">Privacy Policy</a>
      <a href="terms.html">Terms of Service</a>
    </div>
    <div>
      <h4>Services</h4>
      <a href="services.html">AI Sales Automation</a>
      <a href="services.html">CRM & Workflow Automation</a>
      <a href="services.html">Document & PDF Automation</a>
      <a href="services.html">AI Agent Development</a>
    </div>
    <div>
      <h4>Connect</h4>
      <a href="https://github.com/SilentGoodByeLabs" target="_blank" rel="noopener"><i class="fa-brands fa-github"></i> GitHub — SilentGoodByeLabs</a>
      <a href="mailto:adeolaayodeji4666@gmail.com"><i class="fa-solid fa-envelope"></i> adeolaayodeji4666@gmail.com</a>
      <a href="audit.html" class="btn btn-primary" style="margin-top:14px"><i class="fa-solid fa-rocket"></i> Run Free Audit</a>
      <p class="footer-text" style="margin-top:14px">No spam. No fake claims.<br>Human approval on every action.</p>
    </div>
  </div>
  <div class="footer-bottom"><div class="container">© 2016 – 2026 RevenueForge. All rights reserved.</div></div>
</footer>`;

document.addEventListener('DOMContentLoaded', () => {
  const h = document.getElementById('header');
  const f = document.getElementById('footer');
  if (h) h.innerHTML = HEADER;
  if (f) f.innerHTML = FOOTER;

  const b = document.getElementById('wMenuBtn');
  const m = document.getElementById('wMenu');
  if (b && m) {
    b.addEventListener('click', (e) => { e.stopPropagation(); m.classList.toggle('open'); b.classList.toggle('open'); });
    document.addEventListener('click', (e) => {
      if (m.classList.contains('open') && !m.contains(e.target) && !b.contains(e.target)) { m.classList.remove('open'); b.classList.remove('open'); }
    });
  }

  try {
    const sess = JSON.parse(localStorage.getItem('rf_session') || 'null');
    const pl = document.getElementById('portalLink');
    if (sess && pl) { pl.href = 'portal.html'; pl.innerHTML = '<i class="fa-solid fa-user"></i> My Portal'; }
  } catch (e) {}
});
