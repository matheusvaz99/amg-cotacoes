/* Painel: total da proposta ao vivo (frete + pedagio + seguro). */
(function () {
  "use strict";

  var form = document.getElementById("proposta-form");
  if (!form) return;

  var out = form.querySelector("[data-total]");

  function toNumber(v) {
    if (!v) return 0;
    v = String(v).replace(/\./g, "").replace(",", ".").replace(/[^0-9.]/g, "");
    var n = parseFloat(v);
    return isNaN(n) ? 0 : n;
  }

  function fmt(n) {
    return "R$ " + n.toFixed(2).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function recalc() {
    var total =
      toNumber(form.frete.value) +
      toNumber(form.pedagio.value) +
      toNumber(form.seguro.value);
    if (out) out.textContent = fmt(total);
  }

  ["frete", "pedagio", "seguro"].forEach(function (name) {
    if (form[name]) form[name].addEventListener("input", recalc);
  });
  recalc();
})();
