/* Painel: previews ao vivo do valor total do frete e do valor final da proposta. */
(function () {
  "use strict";

  var form = document.getElementById("proposta-form");
  if (!form) return;

  var outFrete = form.querySelector("[data-total-frete]");
  var outFinal = form.querySelector("[data-total-final]");

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
    var frete =
      toNumber(form.frete.value) +
      toNumber(form.pedagio.value) +
      toNumber(form.seguro.value);
    var adicionais = form.custos_adicionais ? toNumber(form.custos_adicionais.value) : 0;
    if (outFrete) outFrete.textContent = fmt(frete);
    if (outFinal) outFinal.textContent = fmt(frete + adicionais);
  }

  ["frete", "pedagio", "seguro", "custos_adicionais"].forEach(function (name) {
    if (form[name]) form[name].addEventListener("input", recalc);
  });
  recalc();
})();
