/* Autopreenchimento de endereco a partir do CEP (ViaCEP, publico e gratuito).
   So preenche os campos que estiverem vazios -- nunca sobrescreve o que o
   cliente ja digitou. Falha silenciosamente (rede fora, CEP inexistente):
   o cliente so continua preenchendo manualmente, sem travar o formulario. */
(function () {
  "use strict";

  function soDigitos(v) {
    return (v || "").replace(/\D/g, "");
  }

  function ligarCep(prefixo) {
    var cepInput = document.querySelector('input[name="' + prefixo + '_cep"]');
    if (!cepInput) return;

    var enderecoInput = document.querySelector('input[name="' + prefixo + '_endereco"]');
    var bairroInput = document.querySelector('input[name="' + prefixo + '_bairro"]');
    var cidadeInput = document.querySelector('input[name="' + prefixo + '_cidade"]');

    var ultimoConsultado = "";

    function preencher(data) {
      if (enderecoInput && !enderecoInput.value && data.logradouro) {
        enderecoInput.value = data.logradouro;
      }
      if (bairroInput && !bairroInput.value && data.bairro) {
        bairroInput.value = data.bairro;
      }
      if (cidadeInput && !cidadeInput.value && data.localidade && data.uf) {
        cidadeInput.value = data.localidade + " - " + data.uf;
      }
    }

    function consultar() {
      var cep = soDigitos(cepInput.value);
      if (cep.length !== 8 || cep === ultimoConsultado) return;
      ultimoConsultado = cep;
      fetch("https://viacep.com.br/ws/" + cep + "/json/")
        .then(function (resp) { return resp.json(); })
        .then(function (data) {
          if (!data.erro) preencher(data);
        })
        .catch(function () {
          // sem internet/servico fora do ar -- cliente preenche na mao, sem erro visivel
        });
    }

    cepInput.addEventListener("blur", consultar);
    cepInput.addEventListener("input", function () {
      if (soDigitos(cepInput.value).length === 8) consultar();
    });
  }

  ligarCep("origem");
  ligarCep("destino");
})();
