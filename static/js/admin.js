/* Painel: previews ao vivo de FC, FE e Valor Total da cotacao.
   O servidor sempre recalcula tudo de novo ao salvar — isto e so uma ajuda visual. */
(function () {
  "use strict";

  var form = document.getElementById("proposta-form");
  if (!form) return;

  var outFC = form.querySelector("[data-fc]");
  var outFE = form.querySelector("[data-fe]");
  var outFinal = form.querySelector("[data-total-final]");

  var CUSTO_FIELDS = ["custo_motorista", "custo_pedagio", "custo_impostos", "custo_seguro", "custo_outros_internos"];
  var ADICIONAL_FIELDS = ["valor_carga", "valor_descarga", "valor_diaria", "valor_ajudante", "valor_empilhadeira", "valor_guincho", "custos_adicionais"];

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

  function sumFields(names) {
    var total = 0;
    names.forEach(function (name) {
      if (form[name]) total += toNumber(form[name].value);
    });
    return total;
  }

  function recalc() {
    var fc = sumFields(CUSTO_FIELDS);
    var margem = form.margem_pct ? toNumber(form.margem_pct.value) : 0;
    var fe = fc * (1 + margem / 100);
    var adicionais = sumFields(ADICIONAL_FIELDS);
    var final_ = fe + adicionais;

    if (outFC) outFC.textContent = fmt(fc);
    if (outFE) outFE.textContent = fmt(fe);
    if (outFinal) outFinal.textContent = fmt(final_);
  }

  CUSTO_FIELDS.concat(ADICIONAL_FIELDS, ["margem_pct"]).forEach(function (name) {
    if (form[name]) form[name].addEventListener("input", recalc);
  });
  recalc();
})();
