/* Wizard de 3 etapas + rascunho em localStorage. Sem JS o form ainda envia. */
(function () {
  "use strict";

  var form = document.getElementById("cotacao-form");
  if (!form) return;

  var steps = Array.prototype.slice.call(form.querySelectorAll(".step"));
  var markers = Array.prototype.slice.call(document.querySelectorAll(".stepper li"));
  var banner = document.getElementById("draft-banner");
  var DRAFT_KEY = "amg_draft_v1";
  var current = 0;
  var hasServerErrors = !!form.querySelector(".field--error");

  function show(index) {
    current = Math.max(0, Math.min(index, steps.length - 1));
    steps.forEach(function (s, i) { s.hidden = i !== current; });
    markers.forEach(function (m, i) {
      m.classList.toggle("is-active", i === current);
      m.classList.toggle("is-done", i < current);
    });
    var y = form.getBoundingClientRect().top + window.scrollY - 80;
    window.scrollTo({ top: y, behavior: "smooth" });
  }

  function validateStep(index) {
    var fields = steps[index].querySelectorAll("input, select, textarea");
    for (var i = 0; i < fields.length; i++) {
      if (!fields[i].checkValidity()) {
        fields[i].reportValidity();
        return false;
      }
    }
    return true;
  }

  // Navegacao livre entre etapas: "Continuar"/"Voltar" e os marcadores do
  // stepper vao direto pra qualquer aba, sem exigir que a etapa atual esteja
  // preenchida -- os campos-chave so sao checados no envio final (salvar),
  // nao a cada troca de aba.
  form.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-nav]");
    if (!btn) return;
    e.preventDefault();
    show(current + (btn.dataset.nav === "next" ? 1 : -1));
  });

  markers.forEach(function (marker, index) {
    marker.classList.add("is-clickable");
    marker.setAttribute("tabindex", "0");
    marker.setAttribute("role", "button");
    marker.addEventListener("click", function () { show(index); });
    marker.addEventListener("keydown", function (e) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        show(index);
      }
    });
  });

  // Envio final: ai sim verifica os campos-chave de TODAS as etapas (nao so
  // a atual) antes de deixar salvar -- se alguma faltar, mostra a etapa com
  // o problema em vez de deixar o servidor rejeitar as cegas.
  form.addEventListener("submit", function (e) {
    for (var i = 0; i < steps.length; i++) {
      if (!validateStep(i)) {
        e.preventDefault();
        show(i);
        return;
      }
    }
    clearDraft();
  });

  // ----- rascunho -----
  function collect() {
    var data = {};
    new FormData(form).forEach(function (v, k) {
      if (k === "csrf_token" || k === "base_code") return;
      data[k] = v;
    });
    return data;
  }

  function saveDraft() {
    try { localStorage.setItem(DRAFT_KEY, JSON.stringify(collect())); } catch (e) {}
  }

  function applyDraft(data) {
    Object.keys(data).forEach(function (k) {
      var els = form.elements[k];
      if (!els) return;
      if (els.length && els[0] && els[0].type === "radio") {
        Array.prototype.forEach.call(els, function (r) { r.checked = r.value === data[k]; });
      } else {
        els.value = data[k];
      }
    });
  }

  function clearDraft() {
    try { localStorage.removeItem(DRAFT_KEY); } catch (e) {}
  }

  var saved = null;
  try { saved = JSON.parse(localStorage.getItem(DRAFT_KEY) || "null"); } catch (e) {}

  var isBased = !!(form.querySelector('input[name="base_code"]') || {}).value;
  if (saved && !isBased && !hasServerErrors && banner) {
    banner.hidden = false;
    banner.addEventListener("click", function (e) {
      var act = (e.target.dataset || {}).draft;
      if (act === "restore") { applyDraft(saved); banner.hidden = true; }
      else if (act === "discard") { clearDraft(); banner.hidden = true; }
    });
  }

  var t;
  form.addEventListener("input", function () {
    clearTimeout(t);
    t = setTimeout(saveDraft, 400);
  });

  // se veio com erros do servidor, comeca na primeira etapa que tem erro
  if (hasServerErrors) {
    for (var i = 0; i < steps.length; i++) {
      if (steps[i].querySelector(".field--error")) { show(i); return; }
    }
  }
  show(0);
})();
