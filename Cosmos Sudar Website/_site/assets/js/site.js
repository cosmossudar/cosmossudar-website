/* Cosmos Sudar — small helpers. No libraries, nothing to update. */
(function () {
  "use strict";

  /* Mobile menu */
  var toggle = document.getElementById("navToggle");
  var nav = document.getElementById("nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    });
    nav.addEventListener("click", function (e) {
      if (e.target.tagName === "A") {
        nav.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && nav.classList.contains("open")) {
        nav.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
        toggle.focus();
      }
    });
  }

  /* Copy-link button on articles */
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-copy]");
    if (!btn) return;
    var url = btn.getAttribute("data-copy");
    var done = function () {
      var original = btn.innerHTML;
      btn.innerHTML = "✓ Link copied";
      setTimeout(function () { btn.innerHTML = original; }, 1800);
    };
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(url).then(done, done);
    } else {
      var ta = document.createElement("textarea");
      ta.value = url;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch (err) {}
      document.body.removeChild(ta);
      done();
    }
  });

  /* Archive search — filters the story list as you type */
  var box = document.getElementById("siteSearch");
  var results = document.getElementById("searchResults");
  var defaultList = document.getElementById("defaultList");
  var count = document.getElementById("searchCount");

  if (box && results && defaultList) {
    var data = null;
    var loading = false;
    var here = location.pathname.replace(/[^/]*$/, "");

    var load = function () {
      if (data || loading) return Promise.resolve();
      loading = true;
      // The index sits at the site root; walk back up from wherever we are.
      var url = box.getAttribute("data-index").replace(/^\//, "");
      return fetch(here + "../" + url)
        .then(function (r) { return r.ok ? r.json() : fetch(here + url).then(function (x) { return x.json(); }); })
        .then(function (j) { data = j; loading = false; })
        .catch(function () { loading = false; });
    };

    var esc = function (s) {
      return String(s).replace(/[&<>"']/g, function (c) {
        return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
      });
    };

    var render = function (list, q) {
      if (!list.length) {
        results.innerHTML =
          '<div class="empty" style="grid-column:1/-1"><h3>Nothing found for “' +
          esc(q) + '”</h3><p>Try a place name, or a single word like water, road or school.</p></div>';
        return;
      }
      results.innerHTML = list.map(function (s) {
        var img = s.i || "assets/img/brand/social-card.jpg";
        if (img.charAt(0) === "/") img = here + ".." + img;
        var href = here + ".." + s.u + "index.html";
        return '<a class="card card-mid" href="' + esc(href) + '">' +
          '<div class="card-media"><img src="' + esc(img) + '" alt="" loading="lazy"></div>' +
          '<div class="card-body"><span class="kicker">' + esc(s.c) +
          '<span class="dot"></span><time>' + esc(s.d) + '</time></span>' +
          '<h3 class="card-title">' + esc(s.t) + '</h3>' +
          '<p class="card-excerpt">' + esc(s.s) + '</p></div></a>';
      }).join("");
    };

    var run = function () {
      var q = box.value.trim().toLowerCase();
      if (q.length < 2) {
        results.hidden = true;
        defaultList.hidden = false;
        if (count) count.hidden = true;
        return;
      }
      load().then(function () {
        if (!data) return;
        var terms = q.split(/\s+/);
        var hits = data.filter(function (s) {
          var hay = (s.t + " " + s.s + " " + s.c + " " + s.b).toLowerCase();
          return terms.every(function (t) { return hay.indexOf(t) !== -1; });
        });
        render(hits, box.value.trim());
        results.hidden = false;
        defaultList.hidden = true;
        if (count) {
          count.hidden = false;
          count.textContent = hits.length + (hits.length === 1 ? " story" : " stories") + " found";
        }
      });
    };

    var timer;
    box.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(run, 140);
    });
    box.addEventListener("focus", load);
  }

  /* Native share sheet on phones — replaces the copy button where supported */
  if (navigator.share) {
    var copyBtn = document.querySelector("[data-copy]");
    if (copyBtn && window.matchMedia("(max-width: 700px)").matches) {
      copyBtn.addEventListener("click", function (e) {
        e.stopImmediatePropagation();
        navigator.share({
          title: document.title,
          url: copyBtn.getAttribute("data-copy")
        }).catch(function () {});
      }, true);
    }
  }
})();
