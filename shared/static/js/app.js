/* Общие утилиты страниц: запросы к API и форматирование. */
(function (global) {
  "use strict";

  function api(path, options) {
    var opts = options || {};
    return fetch(path, {
      method: opts.method || "GET",
      headers: { "Content-Type": "application/json" },
    }).then(function (response) {
      if (!response.ok) throw new Error("HTTP " + response.status + " · " + path);
      return response.json();
    });
  }

  function num(value) {
    if (value === null || value === undefined || isNaN(value)) return "—";
    return new Intl.NumberFormat("ru-RU").format(value);
  }

  function money(value) {
    if (value === null || value === undefined || isNaN(value)) return "—";
    return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(Math.round(value)) + " ₽";
  }

  function pct(value, digits) {
    if (value === null || value === undefined || isNaN(value)) return "—";
    return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: digits === undefined ? 1 : digits }).format(value) + "%";
  }

  function ratio(value) {
    if (value === null || value === undefined || isNaN(value)) return "—";
    return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(value);
  }

  function badge(level, text) {
    var map = { ok: "lc-badge--ok", warn: "lc-badge--warn", bad: "lc-badge--bad", info: "lc-badge--info" };
    return '<span class="lc-badge ' + (map[level] || "") + '">' + text + "</span>";
  }

  function rows(target, items, render) {
    if (!items || !items.length) {
      target.innerHTML = '<p class="lc-loading">Нет данных</p>';
      return;
    }
    target.innerHTML = items.map(render).join("");
  }

  function rowsIntoTable(tbody, items, renderCells) {
    rows(tbody, items, function (item, index) {
      return "<tr>" + renderCells(item, index) + "</tr>";
    });
  }

  function text(value) {
    return String(value === null || value === undefined ? "—" : value);
  }

  function fail(node, error) {
    node.innerHTML = '<p class="lc-loading">Ошибка загрузки: ' + error.message + "</p>";
  }

  global.LC = { api: api, num: num, money: money, pct: pct, ratio: ratio, badge: badge, rows: rows, table: rowsIntoTable, text: text, fail: fail };
})(window);
