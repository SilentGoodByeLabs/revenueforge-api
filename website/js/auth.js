var API = window.RF_API || 'http://localhost:8502';
(function(){
  var q = new URLSearchParams(location.search);
  var e = q.get('err');
  var m = document.getElementById('su_msg') || document.getElementById('li_msg');
  if (e && m) m.textContent = e;
  var f = document.getElementById('suForm') || document.getElementById('liForm');
  if (f) f.action = API + (f.id === 'suForm' ? '/api/join-form' : '/api/login-form');
})();
