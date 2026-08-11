/* =========================================================================
   CCNA Academy — Homepage interactivity (vanilla JS)
   - Mobile nav toggle
   - Sticky navbar shadow on scroll
   - Animated circular progress ring (runs when scrolled into view)
   ========================================================================= */
(function () {
  "use strict";

  document.addEventListener("DOMContentLoaded", function () {
    var page = document.querySelector(".home-page");
    if (!page) return; // only run on the landing page

    /* ---- Mobile nav toggle ---- */
    var toggle = page.querySelector(".nav-toggle");
    var links = page.querySelector(".home-nav__links");
    var actions = page.querySelector(".home-nav__actions");
    var openIcon = toggle ? toggle.querySelector(".nav-toggle__open") : null;
    var closeIcon = toggle ? toggle.querySelector(".nav-toggle__close") : null;

    function closeMenu() {
      if (links) links.classList.remove("open");
      if (actions) actions.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
      if (openIcon) openIcon.style.display = "block";
      if (closeIcon) closeIcon.style.display = "none";
    }

    if (toggle) {
      toggle.addEventListener("click", function () {
        var isOpen = links && links.classList.contains("open");
        if (isOpen) {
          closeMenu();
        } else {
          if (links) links.classList.add("open");
          if (actions) actions.classList.add("open");
          toggle.setAttribute("aria-expanded", "true");
          if (openIcon) openIcon.style.display = "none";
          if (closeIcon) closeIcon.style.display = "block";
        }
      });
      // Close menu when a link inside it is clicked
      page.querySelectorAll(".home-nav__links a, .home-nav__actions a").forEach(function (a) {
        a.addEventListener("click", closeMenu);
      });
    }

    /* ---- Sticky navbar shadow on scroll ---- */
    var nav = page.querySelector(".home-nav");
    if (nav) {
      var onScroll = function () {
        if (window.scrollY > 10) nav.classList.add("scrolled");
        else nav.classList.remove("scrolled");
      };
      window.addEventListener("scroll", onScroll, { passive: true });
      onScroll();
    }

    /* ---- Animated circular progress ---- */
    var ring = page.querySelector(".progress-ring-fg");
    if (ring) {
      var target = parseFloat(ring.getAttribute("data-progress")) || 0;
      var radius = parseFloat(ring.getAttribute("r")) || 52;
      var circ = 2 * Math.PI * radius;
      ring.style.strokeDasharray = circ;
      ring.style.strokeDashoffset = circ; // start fully hidden

      var elapsed = false;
      var onView = function () {
        if (elapsed) return;
        var rect = ring.getBoundingClientRect();
        if (rect.top < window.innerHeight && rect.bottom > 0) {
          elapsed = true;
          animateRing(target);
          window.removeEventListener("scroll", onView);
        }
      };

      function animateRing(value) {
        var start = null;
        var duration = 1400;
        function step(ts) {
          if (!start) start = ts;
          var progress = Math.min((ts - start) / duration, 1);
          var eased = 1 - Math.pow(1 - progress, 3); // easeOutCubic
          var offset = circ - (circ * value * eased) / 100;
          ring.style.strokeDashoffset = offset;
          var label = page.querySelector(".ring__label b");
          if (label) label.textContent = Math.round(value * eased) + "%";
          if (progress < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
      }

      window.addEventListener("scroll", onView, { passive: true });
      onView();
    }
  });
})();
