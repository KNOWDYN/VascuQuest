(() => {
  const header = document.querySelector("[data-header]");
  const menuButton = document.querySelector("[data-menu-button]");
  const nav = document.querySelector("[data-nav]");

  const setHeader = () => {
    header?.classList.toggle("scrolled", window.scrollY > 18);
  };
  setHeader();
  window.addEventListener("scroll", setHeader, { passive: true });

  if (menuButton && nav) {
    const closeMenu = () => {
      menuButton.setAttribute("aria-expanded", "false");
      nav.classList.remove("open");
      document.body.style.overflow = "";
    };

    menuButton.addEventListener("click", () => {
      const isOpen = menuButton.getAttribute("aria-expanded") === "true";
      menuButton.setAttribute("aria-expanded", String(!isOpen));
      nav.classList.toggle("open", !isOpen);
      document.body.style.overflow = isOpen ? "" : "hidden";
    });

    nav.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
    window.addEventListener("resize", () => {
      if (window.innerWidth > 780) closeMenu();
    });
  }

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const revealItems = [...document.querySelectorAll("[data-reveal]")];

  if (reducedMotion || !("IntersectionObserver" in window)) {
    revealItems.forEach((item) => item.classList.add("revealed"));
  } else {
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("revealed");
        obs.unobserve(entry.target);
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    revealItems.forEach((item) => observer.observe(item));
  }
})();