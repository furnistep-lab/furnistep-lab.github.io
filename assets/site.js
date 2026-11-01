// FurniStep website: click-to-play video, step seek links, guide filters, next publish slot. No tracking.
(function () {
  "use strict";

  // Video facade: the YouTube player (privacy-enhanced mode) loads only when the visitor presses play.
  function play(box, start) {
    var id = box.getAttribute("data-yt");
    var src = "https://www.youtube-nocookie.com/embed/" + encodeURIComponent(id) +
      "?autoplay=1&rel=0&modestbranding=1" + (start ? "&start=" + start : "");
    var old = box.querySelector("iframe");
    if (old) { old.src = src; return; }
    var f = document.createElement("iframe");
    f.src = src;
    f.title = box.getAttribute("data-title") || "Assembly video";
    f.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
    f.allowFullscreen = true;
    f.referrerPolicy = "strict-origin-when-cross-origin";
    box.appendChild(f);
    box.classList.add("is-playing");
  }
  var box = document.querySelector(".video[data-yt]");
  if (box) {
    box.querySelector(".play").addEventListener("click", function () { play(box, 0); });
    document.querySelectorAll("[data-seek]").forEach(function (a) {
      a.addEventListener("click", function (ev) {
        ev.preventDefault();
        play(box, parseInt(a.getAttribute("data-seek"), 10) || 0);
        box.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    });
  }

  // Guide filters (the list works without JS; the controls appear only when it runs).
  var filters = document.getElementById("filters");
  if (filters) {
    filters.hidden = false;
    var state = { brand: "", category: "", q: "" };
    var cards = Array.prototype.slice.call(document.querySelectorAll(".guide-card"));
    var empty = document.getElementById("no-results");
    var apply = function () {
      var shown = 0;
      cards.forEach(function (c) {
        var ok = (!state.brand || c.dataset.brand === state.brand) &&
          (!state.category || c.dataset.category === state.category) &&
          (!state.q || c.dataset.search.indexOf(state.q) !== -1);
        c.hidden = !ok;
        if (ok) shown++;
      });
      empty.hidden = shown !== 0;
    };
    filters.addEventListener("click", function (ev) {
      var b = ev.target.closest(".filter");
      if (!b) return;
      var kind = b.dataset.filter;
      state[kind] = b.dataset.value;
      filters.querySelectorAll('.filter[data-filter="' + kind + '"]').forEach(function (x) {
        x.classList.toggle("is-on", x === b);
      });
      apply();
    });
    document.getElementById("q").addEventListener("input", function (ev) {
      state.q = ev.target.value.trim().toLowerCase();
      apply();
    });
  }

  // Next publish slot (Tue, Thu, Sat 15:00 UTC) in the visitor's own time zone.
  var slot = document.getElementById("next-slot");
  if (slot) {
    var now = new Date();
    for (var i = 0; i < 8; i++) {
      var d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + i, 15, 0, 0));
      if ([2, 4, 6].indexOf(d.getUTCDay()) !== -1 && d > now) {
        try {
          var txt = d.toLocaleString("en-GB", { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" });
          slot.textContent = ". Next one: " + txt + " your time";
        } catch (e) { /* leave the static text */ }
        break;
      }
    }
  }
})();
