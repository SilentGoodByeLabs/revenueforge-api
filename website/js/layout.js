(function () {
  var sess = null; try { sess = JSON.parse(localStorage.getItem('rf_session') || 'null'); } catch (e) {}
  var T = Date.now();
  function L(p){ return p + '?t=' + T; }
  var pages = [['index.html','Home'],['pricing.html','Pricing'],['audit.html','Free Audit'],['portal.html','My Portal']];
  function links(cls){ return pages.map(function(p){ return '<a class="'+cls+'" href="'+L(p[0])+'">'+p[1]+'</a>'; }).join(''); }
  var cta = sess
    ? '<a class="rf-btn ghost" href="'+L('portal.html')+'">My Portal</a><a class="rf-btn solid" id="rfLogout" href="index.html">Log out</a>'
    : '<a class="rf-btn ghost" href="'+L('signin.html')+'">Log in</a><a class="rf-btn solid" href="'+L('register.html')+'">Get started</a>';
  var mcta = sess
    ? '<a class="rf-btn ghost" href="'+L('portal.html')+'">My Portal</a><a class="rf-btn solid" id="rfLogoutM" href="index.html">Log out</a>'
    : '<a class="rf-btn ghost" href="'+L('signin.html')+'">Log in</a><a class="rf-btn solid" href="'+L('register.html')+'">Get started</a>';
  var header = document.getElementById('header');
  if (header) header.innerHTML =
    '<header class="rf-header"><div class="rf-wrap">' +
    '<a class="rf-logo" href="'+L('index.html')+'"><img src="assets/logo.png" alt=""><span>Revenue<b>Forge</b></span></a>' +
    '<nav class="rf-nav">' + links('rf-link') + '</nav>' +
    '<div class="rf-cta">' + cta + '</div>' +
    '<button class="rf-burger" id="rfBurger" aria-label="Open menu"><i></i><i></i><i></i></button>' +
    '</div><div class="rf-menu" id="rfMenu">' + links('rf-m-link') +
    '<div class="rf-m-cta">' + mcta + '</div></div></header>';
  function wire(id){ var b = document.getElementById(id); if (b) b.addEventListener('click', function(){ localStorage.removeItem('rf_session'); }); }
  wire('rfLogout'); wire('rfLogoutM');
  var b = document.getElementById('rfBurger');
  if (b) b.addEventListener('click', function () { document.querySelector('.rf-header').classList.toggle('open'); });
  var footer = document.getElementById('footer');
  if (footer) footer.innerHTML =
    '<footer class="rf-footer"><div class="rf-wrap rf-f-grid">' +
    '<div><span class="rf-logo">Revenue<b>Forge</b></span><p>The autonomous revenue engine for freelancers and agencies.</p></div>' +
    '<div><strong style="color:#fff">Explore</strong>' + links('rf-f-link') + '</div>' +
    '<div><p>© ' + new Date().getFullYear() + ' RevenueForge · Silent Goodbye Labs</p></div>' +
    '</div></footer>';
})();
