/* Минималистичные SVG-графики в стиле LADA Цифра. Без внешних зависимостей. */
(function (global) {
  "use strict";

  var PALETTE = ["#000000", "#ff5b06", "#757575", "#b8b8b8", "#ffb27a", "#3538cd", "#067647"];
  var MAX_DOTS = 40;

  function svgEl(name, attrs) {
    var el = document.createElementNS("http://www.w3.org/2000/svg", name);
    Object.keys(attrs || {}).forEach(function (key) {
      el.setAttribute(key, attrs[key]);
    });
    return el;
  }

  function niceMax(value) {
    if (!value || value <= 0) return 10;
    var exp = Math.pow(10, Math.floor(Math.log10(value)));
    var norm = value / exp;
    var step = norm <= 1.2 ? 1.2 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10;
    return step * exp;
  }

  function compact(value) {
    if (Math.abs(value) >= 1000000) return (value / 1000000).toFixed(1).replace(".0", "") + "M";
    if (Math.abs(value) >= 1000) return (value / 1000).toFixed(1).replace(".0", "") + "k";
    return String(Math.round(value * 100) / 100);
  }

  function emptyState(node, text) {
    node.innerHTML = '<p class="lc-loading">' + (text || "Нет данных") + "</p>";
  }

  function drawAxisGrid(svg, box, max, ticks) {
    for (var i = 0; i <= ticks; i += 1) {
      var y = box.top + (box.height * i) / ticks;
      svg.appendChild(
        svgEl("line", {
          x1: box.left,
          x2: box.left + box.width,
          y1: y,
          y2: y,
          stroke: "#ebebeb",
          "stroke-width": 1,
        })
      );
      var label = svgEl("text", {
        x: box.left - 8,
        y: y + 4,
        "text-anchor": "end",
        "font-size": 10,
        fill: "#b8b8b8",
        "font-family": "JetBrains Mono, Consolas, monospace",
      });
      label.textContent = compact(max - (max * i) / ticks);
      svg.appendChild(label);
    }
  }

  function collectX(series) {
    var seen = Object.create(null);
    var xs = [];
    series.forEach(function (s) {
      (s.points || []).forEach(function (point) {
        var key = String(point.x);
        if (seen[key]) return;
        seen[key] = true;
        xs.push(point.x);
      });
    });
    return xs;
  }

  function indexOfX(xs) {
    var map = Object.create(null);
    xs.forEach(function (value, index) {
      map[String(value)] = index;
    });
    return map;
  }

  function pathOf(points, xOf, yOf, closed) {
    var parts = points.map(function (point, index) {
      var x = xOf(point.x).toFixed(1);
      var y = yOf(point.y).toFixed(1);
      return (index === 0 ? "M" : "L") + x + " " + y;
    });
    return parts.join(" ") + (closed ? " Z" : "");
  }

  function lineChart(node, series, options) {
    var opts = options || {};
    var width = opts.width || 720;
    var height = opts.height || 280;
    var xs = collectX(series || []);
    if (!xs.length) return emptyState(node, opts.empty);

    var index = indexOfX(xs);
    var values = series.reduce(function (acc, s) {
      return acc.concat(s.points.map(function (point) { return point.y; }));
    }, []);
    var max = niceMax(Math.max.apply(null, values));
    var box = { left: 52, top: 12, width: width - 68, height: height - 44 };
    var stepX = xs.length > 1 ? box.width / (xs.length - 1) : 0;
    var xOf = function (value) {
      return xs.length > 1 ? box.left + index[String(value)] * stepX : box.left + box.width / 2;
    };
    var yOf = function (value) {
      return box.top + box.height - (value / max) * box.height;
    };

    var svg = svgEl("svg", { viewBox: "0 0 " + width + " " + height, role: "img" });
    drawAxisGrid(svg, box, max, 4);

    series.forEach(function (s, order) {
      var color = s.color || PALETTE[order % PALETTE.length];
      var closed = s.closed === true;
      svg.appendChild(
        svgEl("path", {
          d: pathOf(s.points, xOf, yOf, closed),
          fill: closed ? s.fill || "#ffe3d5" : "none",
          stroke: closed ? s.stroke || "none" : color,
          "stroke-width": closed ? 0 : 2.5,
          "stroke-linejoin": "round",
          "stroke-linecap": "round",
        })
      );
      if (s.dots === false || opts.dots === false || xs.length > MAX_DOTS || closed) return;
      s.points.forEach(function (point) {
        svg.appendChild(
          svgEl("circle", {
            cx: xOf(point.x),
            cy: yOf(point.y),
            r: 2.8,
            fill: "#ffffff",
            stroke: color,
            "stroke-width": 2,
          })
        );
      });
    });

    var labelStep = Math.ceil(xs.length / 8);
    xs.forEach(function (value, position) {
      if (position % labelStep !== 0 && position !== xs.length - 1) return;
      var text = svgEl("text", {
        x: xOf(value),
        y: box.top + box.height + 20,
        "text-anchor": "middle",
        "font-size": 10,
        fill: "#b8b8b8",
        "font-family": "JetBrains Mono, Consolas, monospace",
      });
      text.textContent = value;
      svg.appendChild(text);
    });

    node.innerHTML = "";
    node.appendChild(svg);
  }

  function barChart(node, items, options) {
    var opts = options || {};
    var width = opts.width || 720;
    var height = opts.height || 300;
    if (!items.length) return emptyState(node, opts.empty);

    var box = { left: 52, top: 10, width: width - 68, height: height - 56 };
    var max = niceMax(Math.max.apply(null, items.map(function (item) { return item.value; })));
    var svg = svgEl("svg", { viewBox: "0 0 " + width + " " + height, role: "img" });
    drawAxisGrid(svg, box, max, 4);

    var slot = box.width / items.length;
    var barWidth = Math.max(6, Math.min(48, slot * 0.56));

    items.forEach(function (item, position) {
      var barHeight = max === 0 ? 0 : (item.value / max) * box.height;
      var x = box.left + position * slot + (slot - barWidth) / 2;
      var y = box.top + box.height - barHeight;
      svg.appendChild(
        svgEl("rect", {
          x: x,
          y: y,
          width: barWidth,
          height: Math.max(barHeight, 2),
          rx: Math.min(6, barWidth / 2),
          fill: item.color || opts.color || "#000000",
        })
      );
      var label = svgEl("text", {
        x: box.left + position * slot + slot / 2,
        y: box.top + box.height + 20,
        "text-anchor": "middle",
        "font-size": 10,
        fill: "#757575",
      });
      label.textContent = item.label;
      svg.appendChild(label);
    });

    node.innerHTML = "";
    node.appendChild(svg);
  }

  function stackedBar(node, rows, options) {
    var opts = options || {};
    if (!rows.length) return emptyState(node, opts.empty);
    node.innerHTML = rows
      .map(function (row) {
        var segments = row.segments
          .map(function (segment) {
            return (
              '<span title="' + segment.label + ': ' + segment.value +
              '" style="width:' + segment.share.toFixed(2) + "%;background:" + (segment.color || "#000000") +
              ';display:block;height:100%"></span>'
            );
          })
          .join("");
        return (
          '<div style="margin-bottom:14px">' +
          '<div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px">' +
          "<span>" + row.label + "</span>" +
          '<span style="font-family:var(--mono);color:#757575">' + compact(row.total) + "</span></div>" +
          '<div style="display:flex;height:14px;border-radius:999px;overflow:hidden;background:#f5f5f5">' +
          segments +
          "</div></div>"
        );
      })
      .join("");
  }

  function heatScale(value, max) {
    var share = max > 0 ? Math.min(1, value / max) : 0;
    return "hsl(20, 88%, " + (96 - Math.round(share * 34)) + "%)";
  }

  global.LCCharts = {
    palette: PALETTE,
    line: lineChart,
    bar: barChart,
    stacked: stackedBar,
    heat: heatScale,
    compact: compact,
    empty: emptyState,
  };
})(window);
