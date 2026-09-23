/* Mascaras de entrada: CEP, moeda BRL e numeros. Progressive enhancement. */
(function () {
  "use strict";

  function maskCEP(el) {
    el.addEventListener("input", function () {
      var d = el.value.replace(/\D/g, "").slice(0, 8);
      el.value = d.length > 5 ? d.slice(0, 5) + "-" + d.slice(5) : d;
    });
  }

  function maskCurrency(el) {
    function format() {
      var d = el.value.replace(/\D/g, "");
      if (!d) { el.value = ""; return; }
      d = d.replace(/^0+/, "") || "0";
      while (d.length < 3) d = "0" + d;
      var cents = d.slice(-2);
      var intp = d.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
      el.value = intp + "," + cents;
    }
    el.addEventListener("input", format);
    el.addEventListener("blur", format);
  }

  function maskInteger(el) {
    el.addEventListener("input", function () {
      el.value = el.value.replace(/\D/g, "");
    });
  }

  // Peso em kg: agrupa milhar com ponto, aceita uma virgula com ate 2 casas.
  function maskWeight(el) {
    function format() {
      var v = el.value.replace(/[^\d,]/g, "");
      var parts = v.split(",");
      var intp = parts[0].replace(/^0+(?=\d)/, "").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
      el.value = parts.length > 1 ? intp + "," + parts[1].slice(0, 2) : intp;
    }
    el.addEventListener("input", format);
    el.addEventListener("blur", format);
  }

  document.querySelectorAll('input[name$="_cep"]').forEach(maskCEP);
  var CURRENCY_FIELDS = [
    "valor_nf", "custos_adicionais",
    "custo_motorista", "custo_pedagio", "custo_impostos", "custo_seguro", "custo_outros_internos",
    "valor_diaria", "valor_ajudante", "valor_empilhadeira", "valor_guincho",
    "fe_manual",
  ];
  document
    .querySelectorAll(CURRENCY_FIELDS.map(function (n) { return 'input[name="' + n + '"]'; }).join(", "))
    .forEach(maskCurrency);
  document.querySelectorAll('input[name="peso_total_kg"]').forEach(maskWeight);
  document.querySelectorAll('input[name="qtd_volumes"], input[name="ajudante_qtd"]').forEach(maskInteger);

  // data minima = hoje para campos de coleta
  document.querySelectorAll('input[name="data_coleta"], input[name="data_entrega"]').forEach(function (el) {
    if (!el.min) {
      var t = new Date();
      el.min = t.toISOString().slice(0, 10);
    }
  });
})();
