/* Painel: previews ao vivo de FC, FE e Valor Total da cotacao.
   O servidor sempre recalcula tudo de novo ao salvar — isto e so uma ajuda visual.

   Margem (%) e FE (valor do frete) sao dois jeitos de mexer na mesma coisa,
   com FC sempre fixo (soma dos custos):
   - mudar um custo mantem a margem atual e recalcula o FE;
   - mover a barra ou digitar a margem recalcula o FE;
   - digitar o FE direto recalcula a margem (e move a barra) a partir do FC atual.
   Quem realmente vai pro servidor e sempre o campo margem_pct — o FE aqui e
   so uma forma auxiliar de ajustar esse numero. */
(function () {
  "use strict";

  var form = document.getElementById("proposta-form");
  if (!form) return;

  var outFC = form.querySelector("[data-fc]");
  var outFinal = form.querySelector("[data-total-final]");
  var margemInput = form.querySelector("#f_margem_pct");
  var margemSlider = document.getElementById("f_margem_slider");
  var feInput = document.getElementById("f_valor_frete");

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
    var n = parseFloat(v.replace(/[^0-9.-]/g, ""));
    return isNaN(n) ? 0 : n;
  }

  function fmt(n) {
    return "R$ " + fmtPlain(n);
  }

  function fmtPlain(n) {
    return n.toFixed(2).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  }

  function sumFields(names) {
    var total = 0;
    names.forEach(function (name) {
      if (form[name]) total += toNumber(form[name].value);
    });
    return total;
  }

  function getFC() {
    return sumFields(CUSTO_FIELDS);
  }

  function getMargem() {
    return margemInput ? toNumber(margemInput.value) : 0;
  }

  function syncSlider(margem) {
    if (!margemSlider) return;
    var max = parseFloat(margemSlider.max) || 100;
    var min = parseFloat(margemSlider.min) || 0;
    margemSlider.value = Math.min(Math.max(margem, min), max);
  }

  function setFeFromFC(fc, margem) {
    if (!feInput) return;
    feInput.value = fmtPlain(fc * (1 + margem / 100));
  }

  function recalc() {
    var fc = getFC();
    var margem = getMargem();
    var fe = fc * (1 + margem / 100);
    var adicionais = sumFields(ADICIONAL_FIELDS);
    var final_ = fe + adicionais;

    if (outFC) outFC.textContent = fmt(fc);
    if (outFinal) outFinal.textContent = fmt(final_);
  }

  // Custo mudou -> FC muda -> mantem a margem atual, recalcula o FE.
  CUSTO_FIELDS.forEach(function (name) {
    if (form[name]) {
      form[name].addEventListener("input", function () {
        setFeFromFC(getFC(), getMargem());
        recalc();
      });
    }
  });

  ADICIONAL_FIELDS.forEach(function (name) {
    if (form[name]) form[name].addEventListener("input", recalc);
  });

  // Digitou a margem -> move a barra e recalcula o FE.
  if (margemInput) {
    margemInput.addEventListener("input", function () {
      var margem = getMargem();
      syncSlider(margem);
      setFeFromFC(getFC(), margem);
      recalc();
    });
  }

  // Moveu a barra -> atualiza o numero da margem e o FE.
  if (margemSlider) {
    margemSlider.addEventListener("input", function () {
      var margem = toNumber(margemSlider.value);
      if (margemInput) margemInput.value = String(margem).replace(".", ",");
      setFeFromFC(getFC(), margem);
      recalc();
    });
  }

  // Digitou o FE direto -> recalcula a margem (e move a barra) a partir do FC atual.
  if (feInput) {
    feInput.addEventListener("input", function () {
      var fc = getFC();
      if (fc > 0) {
        var margem = (toNumber(feInput.value) / fc - 1) * 100;
        if (margem < 0) margem = 0; // servidor nao aceita margem negativa
        margem = Math.round(margem * 10) / 10;
        if (margemInput) margemInput.value = String(margem).replace(".", ",");
        syncSlider(margem);
      }
      recalc();
    });
  }

  // Estado inicial (inclusive ao reabrir uma proposta ja salva).
  syncSlider(getMargem());
  setFeFromFC(getFC(), getMargem());
  recalc();
})();
