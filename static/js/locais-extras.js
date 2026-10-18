/* Mostra/esconde as coletas e destinos adicionais (ate 5 de cada, ver
   MAX_LOCAIS_POR_TIPO). As linhas extras ja existem no HTML (escondidas via
   atributo "hidden"); "+ Adicionar" revela a proxima linha oculta, e
   "Remover" esconde de novo e limpa o que foi digitado nela. */
(function () {
  "use strict";

  function setup(prefixo) {
    var addBtn = document.querySelector('[data-add-local="' + prefixo + '"]');
    if (!addBtn) return;
    var rows = Array.prototype.slice.call(
      document.querySelectorAll('[data-local-extra^="' + prefixo + '-"]')
    );
    if (!rows.length) return;

    function atualizarBotao() {
      addBtn.hidden = !rows.some(function (r) { return r.hidden; });
    }

    addBtn.addEventListener("click", function () {
      var proxima = rows.filter(function (r) { return r.hidden; })[0];
      if (!proxima) return;
      proxima.hidden = false;
      var primeiroInput = proxima.querySelector("input");
      if (primeiroInput) primeiroInput.focus();
      atualizarBotao();
    });

    rows.forEach(function (row) {
      var removerBtn = row.querySelector("[data-remove-local]");
      if (!removerBtn) return;
      removerBtn.addEventListener("click", function () {
        row.hidden = true;
        Array.prototype.forEach.call(row.querySelectorAll("input"), function (inp) {
          inp.value = "";
        });
        atualizarBotao();
      });
    });

    atualizarBotao();
  }

  setup("origem");
  setup("destino");
})();
