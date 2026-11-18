/* FacultyNxtGen — progressive enhancement. No inline handlers required. */
(function () {
  "use strict";

  var COOKIE_KEY = "fng_cookie_choice";

  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function getCookie(name) {
    var match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[2]) : "";
  }

  ready(function () {
    /* Sticky header shadow */
    var header = document.querySelector(".site-header");
    if (header) {
      var onScroll = function () {
        header.classList.toggle("is-scrolled", window.scrollY > 6);
      };
      onScroll();
      window.addEventListener("scroll", onScroll, { passive: true });
    }

    /* Cookie consent banner */
    var banner = document.querySelector("[data-cookie-banner]");
    if (banner) {
      var choice = "";
      try { choice = window.localStorage.getItem(COOKIE_KEY) || ""; } catch (e) { choice = ""; }
      if (!choice) banner.classList.add("is-visible");
      banner.addEventListener("click", function (event) {
        var btn = event.target.closest("[data-cookie-choice]");
        if (!btn) return;
        var value = btn.getAttribute("data-cookie-choice");
        try { window.localStorage.setItem(COOKIE_KEY, value); } catch (e) {}

        /* Persist consent in the Django HttpOnly cookie without navigating away. */
        var url = btn.getAttribute("data-cookie-url");
        var csrfInput = document.querySelector("[data-cookie-csrf] input[name=csrfmiddlewaretoken]");
        var csrfToken = csrfInput ? csrfInput.value : "";
        if (url && csrfToken) {
          var body = new URLSearchParams();
          body.set("analytics", value === "all" ? "on" : "");
          body.set("marketing", value === "all" ? "on" : "");
          fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "Content-Type": "application/x-www-form-urlencoded",
              "X-CSRFToken": csrfToken
            },
            body: body.toString()
          }).catch(function () {
            /* Local storage still prevents the banner reappearing in this browser. */
          });
        }
        banner.classList.remove("is-visible");
      });;
    }

    /* Dismissible server messages */
    document.querySelectorAll("[data-dismiss-message]").forEach(function (el) {
      el.addEventListener("click", function () {
        var wrap = el.closest(".alert-fng");
        if (wrap) wrap.remove();
      });
    });

    /* Mobile job filters */
    var filterToggle = document.querySelector("[data-filter-toggle]");
    var filterCard = document.querySelector("[data-filter-card]");
    if (filterToggle && filterCard) {
      filterToggle.addEventListener("click", function () {
        var open = filterCard.classList.toggle("is-open");
        filterToggle.setAttribute("aria-expanded", open ? "true" : "false");
      });
    }

    /* Dependent state -> city selects: compare the actual database IDs. */
    document.querySelectorAll("select[data-state-select]").forEach(function (stateSelect) {
      var target = stateSelect.getAttribute("data-city-target") || "#id_city";
      var citySelect = document.querySelector(target.charAt(0) === "#" ? target : "#" + target);
      if (!citySelect) return;

      var cityOptions = Array.prototype.slice.call(citySelect.options).filter(function (option) {
        return option.value !== "";
      });
      var placeholder = new Option("Select a state first", "");

      function updateCityOptions() {
        var stateId = stateSelect.value;
        var previousCityId = citySelect.value;
        citySelect.replaceChildren(placeholder.cloneNode(true));

        cityOptions.forEach(function (option) {
          if (option.getAttribute("data-state") === stateId) {
            var clone = option.cloneNode(true);
            clone.selected = clone.value === previousCityId;
            citySelect.add(clone);
          }
        });

        citySelect.disabled = !stateId || citySelect.options.length === 1;
        if (stateId && citySelect.options.length === 1) {
          citySelect.options[0].textContent = "No cities available for this state";
        }
      }

      stateSelect.addEventListener("change", updateCityOptions);
      updateCityOptions();
    });

    /* Type-ahead suggestions */
    document.querySelectorAll("[data-suggest]").forEach(function (input) {
      var wrap = input.closest(".suggest-wrap");
      if (!wrap) return;
      var menu = wrap.querySelector("[data-suggest-menu]");
      if (!menu) return;
      var timer = null;
      var lastQuery = "";
      var hide = function () {
        menu.classList.remove("is-open");
        input.setAttribute("aria-expanded", "false");
      };
      var show = function () {
        menu.classList.add("is-open");
        input.setAttribute("aria-expanded", "true");
      };
      var escapeText = function (text) {
        var div = document.createElement("div");
        div.appendChild(document.createTextNode(text == null ? "" : String(text)));
        return div.innerHTML;
      };
      var render = function (data) {
        var html = "";
        if (data.jobs && data.jobs.length) {
          html += '<div class="suggest-label">Vacancies</div>';
          data.jobs.forEach(function (job) {
            html += '<a class="suggest-item" href="' + job.url + '"><strong>' +
              escapeText(job.title) + "</strong><small>" +
              escapeText(job.institution) + " · " + escapeText(job.location) + "</small></a>";
          });
        }
        if (data.institutions && data.institutions.length) {
          html += '<div class="suggest-label">Institutions</div>';
          data.institutions.forEach(function (item) {
            html += '<a class="suggest-item" href="' + item.url + '">' + escapeText(item.name) + "</a>";
          });
        }
        if (data.departments && data.departments.length) {
          html += '<div class="suggest-label">Departments</div>';
          data.departments.forEach(function (item) {
            html += '<a class="suggest-item" href="' + item.url + '">' + escapeText(item.name) + "</a>";
          });
        }
        if (!html) html = '<div class="suggest-item text-muted-fng">No matches yet. Press Enter to search all vacancies.</div>';
        menu.innerHTML = html;
        show();
      };
      input.addEventListener("input", function () {
        var query = input.value.trim();
        if (query.length < 2) { hide(); return; }
        if (query === lastQuery) return;
        lastQuery = query;
        window.clearTimeout(timer);
        timer = window.setTimeout(function () {
          fetch("/search/suggest/?q=" + encodeURIComponent(query), {
            headers: { "X-Requested-With": "XMLHttpRequest" },
            credentials: "same-origin"
          })
            .then(function (response) {
              if (!response.ok) throw new Error("Search unavailable");
              return response.json();
            })
            .then(render)
            .catch(hide);
        }, 220);
      });
      input.addEventListener("keydown", function (event) {
        if (event.key === "Escape") hide();
      });
      document.addEventListener("click", function (event) {
        if (!wrap.contains(event.target)) hide();
      });
      input.addEventListener("focus", function () {
        if (menu.innerHTML.trim()) show();
      });
    });

    /* File input size feedback */
    document.querySelectorAll("input[type=file]").forEach(function (input) {
      input.addEventListener("change", function () {
        var help = input.parentElement ? input.parentElement.querySelector(".form-text") : null;
        if (!help) return;
        if (input.files && input.files.length > 1) {
          help.textContent = input.files.length + " files selected.";
        } else if (input.files && input.files[0]) {
          help.textContent = input.files[0].name + " · " + Math.ceil(input.files[0].size / 1024) + " KB";
        }
      });
    });

    /* Conditional field groups (checkboxes, selects) */
    document.querySelectorAll("[data-toggle-target]").forEach(function (control) {
      var target = document.querySelector(control.getAttribute("data-toggle-target"));
      if (!target) return;
      var allowed = (control.getAttribute("data-toggle-value") || "")
        .split(",")
        .map(function (value) { return value.trim(); })
        .filter(function (value) { return value !== ""; });
      var sync = function () {
        if (control.type === "checkbox" || control.type === "radio") {
          target.hidden = !control.checked;
        } else if (allowed.length) {
          target.hidden = allowed.indexOf(control.value) === -1;
        } else {
          target.hidden = !control.value;
        }
        target.querySelectorAll("input, select, textarea").forEach(function (input) {
          input.disabled = target.hidden;
        });
      };
      control.addEventListener("change", sync);
      sync();
    });

    /* Current-role end date helper */
    document.querySelectorAll("[data-current-role]").forEach(function (checkbox) {
      var form = checkbox.closest("form");
      var end = form ? form.querySelector("input[name=end_date]") : null;
      if (!end) return;
      var sync = function () {
        end.disabled = checkbox.checked;
        if (checkbox.checked) end.value = "";
      };
      checkbox.addEventListener("change", sync);
      sync();
    });

    /* Confirmation for destructive or irreversible actions */
    document.addEventListener("click", function (event) {
      var trigger = event.target.closest("[data-confirm]");
      if (!trigger) return;
      var message = trigger.getAttribute("data-confirm");
      if (message && !window.confirm(message)) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    });

    /* Auto-submit filter controls without inline handlers */
    document.querySelectorAll("[data-auto-submit]").forEach(function (control) {
      control.addEventListener("change", function () {
        var form = control.closest("form");
        if (!form) return;
        if (typeof form.requestSubmit === "function") form.requestSubmit();
        else form.submit();
      });
    });
  });
})();
