(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("data").textContent);
  var STATUS = { planned: "planowany", auction: "przetarg", rokowania: "rokowania", cancelled: "odwołany" };
  var TYPE = { flat: "mieszkanie", house: "dom" };
  var state = { tab: "active", key: "auction_date", dir: 1 };
  var nf = new Intl.NumberFormat("pl-PL");

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (text != null) e.textContent = text;
    return e;
  }
  function link(href, text) { return el("a", { href: href, target: "_blank", rel: "noopener" }, text); }
  function money(v) { return v == null ? "—" : nf.format(v); }
  function dash(td) { td.textContent = "—"; td.classList.add("muted"); return td; }
  function fmtDate(iso) { return iso ? iso.slice(8, 10) + "." + iso.slice(5, 7) + "." + iso.slice(0, 4) : "—"; }

  function sortValue(r, key) {
    var v = r[key];
    if (key === "status") v = STATUS[v];
    if (key === "type") v = TYPE[v];
    return v;
  }

  function compare(a, b) {
    var x = sortValue(a, state.key), y = sortValue(b, state.key);
    if (x == null && y == null) return 0;
    if (x == null) return 1;  // empty values always last
    if (y == null) return -1;
    if (typeof x === "number" && typeof y === "number") return (x - y) * state.dir;
    return String(x).localeCompare(String(y), "pl") * state.dir;
  }

  function filters() {
    return {
      city: document.getElementById("f-city").value,
      type: document.getElementById("f-type").value,
      status: document.getElementById("f-status").value,
      onlyNew: document.getElementById("f-new").checked
    };
  }

  function row(r) {
    var tr = el("tr", r["new"] ? { "class": "is-new" } : {});
    var td = el("td"); td.appendChild(el("span", { "class": "pill " + r.status }, STATUS[r.status]));
    if (r["new"]) td.appendChild(el("span", { "class": "newtag" }, "nowe"));
    tr.appendChild(td);
    tr.appendChild(el("td", {}, fmtDate(r.auction_date)));

    td = el("td", { "class": "addr" });
    td.appendChild(link(r.maps, r.address || r.raw_title || "—"));
    var sv = el("small");
    sv.appendChild(link(r.streetview || r.maps, r.streetview ? "Street View" : "mapa"));
    if (r.raw_title && r.raw_title !== r.address) sv.appendChild(document.createTextNode(" · " + r.raw_title.slice(0, 60)));
    td.appendChild(sv);
    tr.appendChild(td);

    tr.appendChild(el("td", {}, r.city));
    tr.appendChild(el("td", {}, TYPE[r.type]));
    td = el("td", { "class": "num" }); r.area_m2 == null ? dash(td) : (td.textContent = String(r.area_m2).replace(".", ",")); tr.appendChild(td);

    td = el("td", { "class": "num" }, money(r.start_price));
    if (r.price_drop) {
      var hist = (r.price_history || []).map(function (h) { return fmtDate(h.date) + ": " + money(h.start_price) + " zł (" + STATUS[h.status] + ")"; }).join("\n");
      td.appendChild(el("span", { "class": "drop", title: "Obniżka ceny\n" + hist }, "↓"));
    }
    tr.appendChild(td);
    tr.appendChild(el("td", { "class": "num" }, money(r.price_per_m2)));

    td = el("td", { "class": "num" });
    if (r.market_gap_pct == null) {
      dash(td);
      if (r.type === "house") td.title = "Brak danych rynkowych dla domów";
    } else {
      var g = r.market_gap_pct;
      td.textContent = (r.market_low_confidence ? "≈ " : "") + (g > 0 ? "+" : g < 0 ? "−" : "") + Math.abs(Math.round(g)) + "%";
      td.className += g < 0 ? " gap-neg" : " gap-pos";
      td.title = (r.market_basis === "nearby" ? "Wycena z transakcji w okolicy (" : "Mediana ceny transakcyjnej miasta (") +
        r.market_period + ")" + (r.market_low_confidence ? ", mało transakcji porównawczych" : "");
    }
    tr.appendChild(td);
    tr.appendChild(el("td", { "class": "num" }, money(r.deposit)));

    td = el("td");
    if (r.photo_url) {
      var a = link(r.photo_url, "");
      a.appendChild(el("img", { "class": "thumb", src: r.photo_url, alt: "Zdjęcie: " + r.address, loading: "lazy" }));
      td.appendChild(a);
    } else if (r.streetview) {
      td.appendChild(link(r.streetview, "Street View"));
    } else dash(td);
    tr.appendChild(td);

    td = el("td");
    td.appendChild(r.notice_url ? link(r.notice_url, r.source_label + " ↗") : document.createTextNode(r.source_label));
    tr.appendChild(td);
    return tr;
  }

  function draw() {
    var f = filters();
    var rows = DATA.offers.filter(function (r) {
      return (state.tab === "archive") === r.archived &&
        (!f.city || r.city === f.city) && (!f.type || r.type === f.type) &&
        (!f.status || r.status === f.status) && (!f.onlyNew || r["new"]);
    }).sort(compare);
    var body = document.querySelector("#offers tbody");
    body.textContent = "";
    rows.forEach(function (r) { body.appendChild(row(r)); });
    document.getElementById("empty").hidden = rows.length > 0;
    document.querySelectorAll("th[data-key]").forEach(function (th) {
      th.setAttribute("aria-sort", th.dataset.key === state.key ? (state.dir > 0 ? "ascending" : "descending") : "none");
    });
  }

  var cities = Array.from(new Set(DATA.offers.map(function (r) { return r.city; }))).sort(function (a, b) { return a.localeCompare(b, "pl"); });
  var sel = document.getElementById("f-city");
  cities.forEach(function (c) { sel.appendChild(el("option", { value: c }, c)); });

  document.querySelectorAll("th[data-key]").forEach(function (th) {
    th.tabIndex = 0;
    function sort() {
      if (state.key === th.dataset.key) state.dir = -state.dir; else { state.key = th.dataset.key; state.dir = 1; }
      draw();
    }
    th.addEventListener("click", sort);
    th.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sort(); } });
  });
  document.querySelectorAll("[data-tab]").forEach(function (b) {
    b.addEventListener("click", function () {
      state.tab = b.dataset.tab;
      document.querySelectorAll("[data-tab]").forEach(function (x) { x.setAttribute("aria-selected", String(x === b)); });
      draw();
    });
  });
  ["f-city", "f-type", "f-status", "f-new"].forEach(function (id) { document.getElementById(id).addEventListener("change", draw); });
  draw();
})();
