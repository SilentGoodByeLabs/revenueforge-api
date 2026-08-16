// auth.js is now simple. Forms submit natively to Render.
(function(){
  var q = new URLSearchParams(location.search);
  var e = q.get('err');
  if (e) {
    var m = document.getElementById('li_msg') || document.getElementById('su_msg');
    if (m) m.textContent = e;
  }
})();
