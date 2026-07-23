/* ── Gemeinsamer Sprach-Umschalter für die ganze Seite ──────────────────
   Jede Seite definiert vorher  window.I18N = { de:{...}, en:{...}, ... }
   und markiert Elemente mit  data-i18n / data-i18n-html / data-i18n-aria.
   Weitere Sprache = ein weiterer Block in window.I18N. Fertig.
   Optional: window.onLangChange(lang) für dynamisch gebauten Inhalt. */
(function(){
  'use strict';
  var I18N = window.I18N || {};
  var langs = Object.keys(I18N);
  if (!langs.length) return;
  var LS = 'cxo_lang';

  function detect(){
    try { var s = localStorage.getItem(LS); if (s && I18N[s]) return s; } catch(_){}
    var nav = (navigator.language || 'en').slice(0,2);
    return I18N[nav] ? nav : (I18N.en ? 'en' : langs[0]);
  }
  var lang = detect();

  window.getLang = function(){ return lang; };
  window.t = function(k){
    var d = I18N[lang] || I18N[langs[0]];
    return (k in d) ? d[k] : ((I18N.en && I18N.en[k]) || k);
  };

  /* Umschalter-Styles (nutzen die --gold/--dim/--cream der jeweiligen Seite) */
  var st = document.createElement('style');
  st.textContent =
    '.i18n-bar{position:fixed;top:1.05rem;right:1.05rem;z-index:60;display:flex;align-items:center;gap:.15rem;font-family:inherit}'+
    '.i18n-btn{background:none;border:none;color:var(--dim,#9d9188);font:inherit;font-size:.72rem;letter-spacing:.18em;text-transform:uppercase;cursor:pointer;padding:.4rem .5rem;line-height:1;transition:color .3s ease}'+
    '.i18n-btn[aria-pressed="true"]{color:var(--gold,#f0b45e)}'+
    '.i18n-btn:hover{color:var(--cream,#eef1f6)}'+
    '.i18n-btn:focus-visible{outline:1px solid var(--gold,#f0b45e);outline-offset:2px}'+
    '.i18n-sep{color:var(--dim,#9d9188);opacity:.45;font-size:.7rem}';
  document.head.appendChild(st);

  function applyStatic(){
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-i18n]').forEach(function(el){ el.textContent = window.t(el.getAttribute('data-i18n')); });
    document.querySelectorAll('[data-i18n-html]').forEach(function(el){ el.innerHTML = window.t(el.getAttribute('data-i18n-html')); });
    document.querySelectorAll('[data-i18n-aria]').forEach(function(el){ if (el.hasAttribute('aria-label')) el.setAttribute('aria-label', window.t(el.getAttribute('data-i18n-aria'))); });
    document.querySelectorAll('.i18n-btn').forEach(function(b){ b.setAttribute('aria-pressed', b.getAttribute('data-lang') === lang ? 'true' : 'false'); });
  }
  window.setLang = function(l){
    if (l !== lang && I18N[l]){ lang = l; try { localStorage.setItem(LS, l); } catch(_){} }
    applyStatic();
    if (typeof window.onLangChange === 'function') window.onLangChange(lang);
  };

  function build(){
    var bar = document.createElement('div');
    bar.className = 'i18n-bar';
    bar.setAttribute('role','group');
    bar.setAttribute('aria-label','Language / Sprache');
    langs.forEach(function(l, i){
      if (i){ var sep = document.createElement('span'); sep.className='i18n-sep'; sep.setAttribute('aria-hidden','true'); sep.textContent='·'; bar.appendChild(sep); }
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'i18n-btn'; b.setAttribute('data-lang', l); b.textContent = l.toUpperCase();
      b.addEventListener('click', function(){ window.setLang(l); });
      bar.appendChild(b);
    });
    document.body.appendChild(bar);
    applyStatic();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build);
  else build();
})();
