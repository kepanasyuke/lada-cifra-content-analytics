/* Общие утилиты страниц: запросы к API и форматирование. */
(function (global) {
  "use strict";

  function api(path, options) {
    var opts = options || {};
    var method = opts.method || "GET";
    var init = { method: method };
    if (method !== "GET") init.headers = { "Content-Type": "application/json" };
    return fetch(path, init).then(function (response) {
      if (!response.ok) {
        return response.text().then(function (body) {
          throw new Error("HTTP " + response.status + " · " + describe(body, path));
        });
      }
      return response.json();
    });
  }

  function describe(body, path) {
    try {
      var parsed = JSON.parse(body);
      if (parsed && parsed.detail) return parsed.detail;
    } catch (error) {
      /* тело не JSON — показываем путь */
    }
    return path;
  }

  function num(value) {
    if (value === null || value === undefined || isNaN(value)) return "—";
    return new Intl.NumberFormat("ru-RU").format(value);
  }

  function money(value, symbol) {
    if (value === null || value === undefined || isNaN(value)) return "—";
    var sign = symbol === undefined ? "₹" : symbol;
    return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(Math.round(value)) + " " + sign;
  }

  function millions(value, symbol) {
    if (value === null || value === undefined || isNaN(value)) return "—";
    var sign = symbol === undefined ? "₹" : symbol;
    return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 }).format(value) + " млн " + sign;
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

  function rows(target, items, render, emptyText) {
    if (!items || !items.length) {
      target.innerHTML = '<p class="lc-loading">' + (emptyText || "Нет данных") + "</p>";
      return;
    }
    target.innerHTML = items.map(render).join("");
  }

  function table(tbody, items, renderCells, options) {
    var opts = options || {};
    if (!items || !items.length) {
      var columns = opts.columns || 4;
      tbody.innerHTML =
        '<tr><td colspan="' + columns + '" class="lc-loading">' + (opts.empty || "Нет данных") + "</td></tr>";
      return;
    }
    tbody.innerHTML = items
      .map(function (item, index) {
        return "<tr>" + renderCells(item, index) + "</tr>";
      })
      .join("");
  }

  function text(value) {
    return String(value === null || value === undefined ? "—" : value);
  }

  function escapeHtml(value) {
    return String(value === null || value === undefined ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function fail(node, error) {
    node.innerHTML = '<p class="lc-loading">Ошибка загрузки: ' + escapeHtml(error.message) + "</p>";
  }

  global.LC = {
    api: api,
    num: num,
    money: money,
    millions: millions,
    pct: pct,
    ratio: ratio,
    badge: badge,
    rows: rows,
    table: table,
    text: text,
    escape: escapeHtml,
    fail: fail,
  };
})(window);
