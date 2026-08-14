fetch('js/testimonials.json').then(r => r.json()).then(data => {
  const grid = document.getElementById('tGrid');
  if (!grid) return;
  const list = (data.testimonials || []).filter(t => t.approved);
  if (list.length === 0) {
    for (let i = 1; i <= 3; i++) {
      grid.insertAdjacentHTML('beforeend',
        '<div class="card"><div class="icon"><i class="fa-solid fa-lock"></i></div>' +
        '<h3>Reserved slot ' + i + '</h3>' +
        '<p>Waiting for a verified, client-approved result with photo and written permission. No fake reviews — ever.</p></div>');
    }
  } else {
    list.forEach(t => {
      grid.insertAdjacentHTML('beforeend',
        '<div class="card"><img class="t-photo" src="' + t.photo + '" alt="' + t.name + '">' +
        '<p class="t-quote">"' + t.quote + '"</p>' +
        '<div class="t-who">' + t.name + '<span>' + t.role + ' · ' + t.country + '</span></div></div>');
    });
  }
});
