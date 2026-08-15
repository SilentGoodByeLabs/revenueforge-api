var API = window.RF_API || 'http://localhost:8502';
(function(){
  var q = new URLSearchParams(location.search);
  var e = q.get('err');
  var m = document.getElementById('su_msg') || document.getElementById('li_msg');
  if (e && m) m.textContent = e;
  var f = document.getElementById('suForm') || document.getElementById('liForm');
  if (f) f.action = API + (f.id === 'suForm' ? '/api/join-form' : '/api/login-form');
})();

/* Safety net: old cached pages call these names — make them work via real POST navigation */
function capResp(){ return (window.grecaptcha && grecaptcha.getResponse) ? grecaptcha.getResponse() : ''; }
function postNav(url, fields){
  var f = document.createElement('form'); f.method = 'post'; f.action = url;
  for (var k in fields) { var i = document.createElement('input'); i.type = 'hidden'; i.name = k; i.value = fields[k]; f.appendChild(i); }
  document.body.appendChild(f); f.submit();
}
function rfSignup(){ postNav('https://revenueforge-api.onrender.com/api/join-form', { email: (document.getElementById('su_email')||{}).value||'', password: (document.getElementById('su_pass')||{}).value||'', 'g-recaptcha-response': capResp() }); }
function rfLogin(){ postNav('https://revenueforge-api.onrender.com/api/login-form', { email: (document.getElementById('li_email')||{}).value||'', password: (document.getElementById('li_pass')||{}).value||'', 'g-recaptcha-response': capResp() }); }
