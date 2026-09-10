/* Painel: previews ao vivo do valor total do frete e do valor final da proposta. */
(function () {
  "use strict";

  var form = document.getElementById("proposta-form");
  if (!form) return;

  var outFrete = form.querySelector("[data-total-frete]");
  var outFinal = form.querySelector("[data-total-final]");

  function toNumber(v) {
    if (!v) return 0;
    v = String(v).replace(/R\$|\s/g, "");
    if (v.indexOf(",") !== -1) {
      // formato BR: ponto = milhar, virgula = decimal
      v = v.replace(/\./g, "").replace(",", ".");
    } else if ((v.match(/\./g) || []).length === 1) {
      var p = v.split(".");
      // "2.000" (3 casas) = milhar; "2000.00" / "2.5" = decimal
      if (p[1].length === 3 && p[0].length <= 3) v = p[0] + p[1];
    } else {
      v = v.replace(/\./g, "");
    }
    var n = parseFloat(v.replace(/[^0-9.]/g, ""));
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
