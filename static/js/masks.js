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

  function maskDocumento(el) {
    // CPF (000.000.000-00) enquanto tiver ate 11 digitos; CNPJ
    // (00.000.000/0000-00) a partir do 12o digito digitado.
    el.addEventListener("input", function () {
      var d = el.value.replace(/\D/g, "").slice(0, 14);
      if (d.length <= 11) {
        el.value = d
          .replace(/(\d{3})(\d)/, "$1.$2")
          .replace(/(\d{3})(\d)/, "$1.$2")
          .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
      } else {
        el.value = d
          .replace(/(\d{2})(\d)/, "$1.$2")
          .replace(/(\d{3})(\d)/, "$1.$2")
          .replace(/(\d{3})(\d)/, "$1/$2")
          .replace(/(\d{4})(\d{1,2})$/, "$1-$2");
      }
    });
  }

  document.querySelectorAll('input[name$="_cep"]').forEach(maskCEP);
  document.querySelectorAll('input[name="pagador_documento"]').forEach(maskDocumento);
  var CURRENCY_FIELDS = [
    "valor_nf", "custos_adicionais",
    "custo_motorista", "custo_pedagio", "custo_impostos", "custo_seguro", "custo_outros_internos",
    "valor_diaria", "valor_ajudante", "valor_empilhadeira", "valor_guincho",
    "fe_manual",
  ];
  document
    .querySelectorAll(CURRENCY_FIELDS.map(function (n) { return 'input[name="' + n + '"]'; }).join(", "))
    .forEach(maskCurrency);
  document.querySelectorAll('input[name="qtd_volumes"], input[name="ajudante_qtd"]').forEach(maskInteger);

  // data minima = hoje para campos de coleta
  document.querySelectorAll('input[name="data_coleta"], input[name="data_entrega"]').forEach(function (el) {
    if (!el.min) {
      var t = new Date();
      el.min = t.toISOString().slice(0, 10);
    }
  });
})();
