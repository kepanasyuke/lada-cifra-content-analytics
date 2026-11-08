/* Минималистичные SVG-графики в стиле LADA Цифра. Без внешних зависимостей. */
(function (global) {
  "use strict";

  var PALETTE = ["#000000", "#ff5b06", "#757575", "#b8b8b8", "#ffb27a", "#3538cd", "#067647"];

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

  function compact(value) {
    if (Math.abs(value) >= 1000000) return (value / 1000000).toFixed(1).replace(".0", "") + "M";
    if (Math.abs(value) >= 1000) return (value / 1000).toFixed(1).replace(".0", "") + "k";
    return String(Math.round(value * 100) / 100);
  }

  function lineChart(node, series, options) {
    var opts = options || {};
    var width = opts.width || 720;
    var height = opts.height || 280;
    if (!series.length || !series[0].points.length) return emptyState(node, opts.empty);

    var box = { left: 52, top: 12, width: width - 68, height: height - 44 };
    var values = series.reduce(function (acc, s) {
      return acc.concat(s.points.map(function (p) { return p.y; }));
    }, []);
    var max = niceMax(Math.max.apply(null, values));
    var count = series[0].points.length;

    var svg = svgEl("svg", { viewBox: "0 0 " + width + " " + height, role: "img" });
    drawAxisGrid(svg, box, max, 4);

    var stepX = count > 1 ? box.width / (count - 1) : box.width;
    var xOf = function (i) { return box.left + (count > 1 ? i * stepX : box.width / 2); };
    var yOf = function (v) { return box.top + box.height - (v / max) * box.height; };

    series.forEach(function (s, si) {
      var color = s.color || PALETTE[si % PALETTE.length];
      var path = s.points
        .map(function (p, i) { return (i === 0 ? "M" : "L") + xOf(i).toFixed(1) + " " + yOf(p.y).toFixed(1); })
        .join(" ");
      svg.appendChild(svgEl("path", { d: path, fill: "none", stroke: color, "stroke-width": 2.5, "stroke-linejoin": "round" }));
      if (opts.dots !== false) {
        s.points.forEach(function (p, i) {
          svg.appendChild(svgEl("circle", { cx: xOf(i), cy: yOf(p.y), r: 2.8, fill: "#ffffff", stroke: color, "stroke-width": 2 }));
        });
      }
    });

    var labelStep = Math.ceil(count / 8);
    series[0].points.forEach(function (p, i) {
      if (i % labelStep !== 0 && i !== count - 1) return;
      var text = svgEl("text", {
        x: xOf(i),
        y: box.top + box.height + 20,
        "text-anchor": "middle",
        "font-size": 10,
        fill: "#b8b8b8",
        "font-family": "JetBrains Mono, Consolas, monospace",
      });
      text.textContent = p.x;
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
    var max = niceMax(Math.max.apply(null, items.map(function (i) { return i.value; })));
    var svg = svgEl("svg", { viewBox: "0 0 " + width + " " + height, role: "img" });
    drawAxisGrid(svg, box, max, 4);

    var slot = box.width / items.length;
    var barWidth = Math.max(6, Math.min(48, slot * 0.56));

    items.forEach(function (item, i) {
      var h = max === 0 ? 0 : (item.value / max) * box.height;
      var x = box.left + i * slot + (slot - barWidth) / 2;
      var y = box.top + box.height - h;
      svg.appendChild(
        svgEl("rect", {
          x: x,
          y: y,
          width: barWidth,
          height: Math.max(h, 2),
          rx: Math.min(6, barWidth / 2),
          fill: item.color || opts.color || "#000000",
        })
      );
      var label = svgEl("text", {
        x: box.left + i * slot + slot / 2,
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
          .map(function (s) {
            return (
              '<span title="' + s.label + ': ' + s.value + '" style="width:' + s.share.toFixed(2) +
              "%;background:" + (s.color || "#000000") + ';display:block;height:100%"></span>'
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
    var t = max > 0 ? Math.min(1, value / max) : 0;
    var light = 96 - Math.round(t * 34);
    return "hsl(20, 88%, " + light + "%)";
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
