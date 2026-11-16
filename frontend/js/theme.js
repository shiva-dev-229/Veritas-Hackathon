/* theme.js: peas theme picker. Classic script, no modules.
   Exposes PT.theme.apply / list / current / isOpen. */
window.PT = window.PT || {};

PT.theme = (function () {
  var KEY = 'peas-theme';
  var THEMES = [
    { id: 'default', label: 'default' },
    { id: 'light', label: 'light' },
    { id: 'dracula', label: 'dracula' },
    { id: 'nord', label: 'nord' },
    { id: 'solarized-dark', label: 'solarized dark' },
    { id: 'solarized-light', label: 'solarized light' },
    { id: 'gruvbox-dark', label: 'gruvbox dark' },
    { id: 'catppuccin-mocha', label: 'catppuccin mocha' },
    { id: 'rose-pine', label: 'rose pine' },
    { id: 'monokai', label: 'monokai' },
    { id: 'forest', label: 'forest' },
    { id: 'high-contrast', label: 'high contrast' }
  ];

  var overlay = null;
  var listEl = null;

  function isKnown(id) {
    for (var i = 0; i < THEMES.length; i++) {
      if (THEMES[i].id === id) return true;
    }
    return false;
  }

  function safeId(id) {
    return isKnown(id) ? id : 'default';
  }

  function setAttr(id) {
    document.documentElement.setAttribute('data-theme', id);
  }

  function dispatch(id) {
    window.dispatchEvent(new CustomEvent('peas:themechange', { detail: { id: id } }));
  }

  // Sets the theme and saves it.
  function apply(name) {
    var id = safeId(name);
    setAttr(id);
    try { localStorage.setItem(KEY, id); } catch (e) { /* storage unavailable */ }
    dispatch(id);
    return id;
  }

  // Sets the theme for display only; nothing is saved.
  function preview(name) {
    var id = safeId(name);
    setAttr(id);
    dispatch(id);
    return id;
  }

  function list() {
    return THEMES.map(function (t) { return { id: t.id, label: t.label }; });
  }

  function current() {
    var v = null;
    try { v = localStorage.getItem(KEY); } catch (e) { /* storage unavailable */ }
    return isKnown(v) ? v : 'default';
  }

  function isOpen() {
    return !!overlay && !overlay.classList.contains('hidden');
  }

  function rows() {
    return listEl ? Array.prototype.slice.call(listEl.querySelectorAll('.theme-row')) : [];
  }

  function rowFor(id) {
    var rs = rows();
    for (var i = 0; i < rs.length; i++) {
      if (rs[i].getAttribute('data-id') === id) return rs[i];
    }
    return null;
  }

  function refreshCurrent() {
    var cur = current();
    rows().forEach(function (r) {
      var on = r.getAttribute('data-id') === cur;
      r.classList.toggle('current', on);
      if (on) r.setAttribute('aria-current', 'true');
      else r.removeAttribute('aria-current');
    });
  }

  function build() {
    overlay = document.createElement('div');
    overlay.id = 'themePicker';
    overlay.className = 'hidden';

    var box = document.createElement('div');
    box.className = 'theme-panel';
    box.setAttribute('role', 'dialog');
    box.setAttribute('aria-modal', 'true');
    box.setAttribute('aria-label', 'theme');

    var title = document.createElement('h2');
    title.className = 'theme-title';
    title.textContent = 'theme';

    listEl = document.createElement('div');
    listEl.className = 'theme-list';
    listEl.setAttribute('role', 'group');

    THEMES.forEach(function (t) {
      var row = document.createElement('button');
      row.type = 'button';
      row.className = 'theme-row';
      row.setAttribute('data-id', t.id);

      var name = document.createElement('span');
      name.className = 'theme-name';
      name.textContent = t.label;

      // The strip carries data-theme itself, so themes.css attribute
      // selectors give it that theme's palette regardless of the page theme.
      var swatch = document.createElement('span');
      swatch.className = 'theme-swatch';
      swatch.setAttribute('data-theme', t.id);
      swatch.setAttribute('aria-hidden', 'true');
      for (var i = 0; i < 4; i++) swatch.appendChild(document.createElement('i'));

      row.appendChild(name);
      row.appendChild(swatch);

      row.addEventListener('mouseenter', function () { preview(t.id); });
      row.addEventListener('focus', function () { preview(t.id); });
      row.addEventListener('click', function () { choose(t.id); });

      listEl.appendChild(row);
    });

    // Leaving the list reverts any hover preview to the saved theme.
    listEl.addEventListener('mouseleave', function () { preview(current()); });

    box.appendChild(title);
    box.appendChild(listEl);
    overlay.appendChild(box);

    // Clicking the backdrop (outside the panel) cancels.
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) close(true);
    });

    document.body.appendChild(overlay);
  }

  function open() {
    if (!overlay) build();
    refreshCurrent();
    overlay.classList.remove('hidden');
    var cur = rowFor(current());
    if (cur) cur.focus();
  }

  // revert: restore the saved theme (cancel). Otherwise the chosen theme stays.
  function close(revert) {
    if (!isOpen()) return;
    if (revert) preview(current());
    overlay.classList.add('hidden');
    if (document.activeElement && document.activeElement.blur) {
      document.activeElement.blur();
    }
  }

  function choose(id) {
    apply(id);
    close(false);
  }

  function focusedRow() {
    var ae = document.activeElement;
    return ae && ae.classList && ae.classList.contains('theme-row') ? ae : null;
  }

  function move(dir) {
    var rs = rows();
    var n = rs.length;
    if (!n) return;
    var idx = rs.indexOf(document.activeElement);
    var next;
    if (idx === -1) next = dir > 0 ? 0 : n - 1;
    else next = (idx + dir + n) % n;
    rs[next].focus();
  }

  // Capture phase on window so the page's typing handler never sees these keys while open.
  window.addEventListener('keydown', function (e) {
    if (!isOpen()) return;
    var k = e.key;
    if (k === 'Escape' || k === 'Esc') {
      e.preventDefault();
      e.stopPropagation();
      close(true);
    } else if (k === 'ArrowDown' || k === 'ArrowUp') {
      e.preventDefault();
      e.stopPropagation();
      move(k === 'ArrowDown' ? 1 : -1);
    } else if (k === 'Enter') {
      e.preventDefault();
      e.stopPropagation();
      var r = focusedRow();
      if (r) choose(r.getAttribute('data-id'));
    } else if (k !== 'Tab') {
      // Keep typing keys away from the test while the picker is open.
      e.stopPropagation();
    }
  }, true);

  function wire() {
    var btn = document.getElementById('themeBtn');
    if (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        open();
      });
    }
  }

  // On load: the inline head script sets data-theme before paint; fall back to default if unknown.
  if (!isKnown(document.documentElement.getAttribute('data-theme'))) {
    setAttr('default');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', wire);
  } else {
    wire();
  }

  return {
    apply: apply,
    list: list,
    current: current,
    isOpen: isOpen
  };
})();
