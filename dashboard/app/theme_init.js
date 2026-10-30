// Theme before the first paint: ?theme= (screenshots/tests) or the stored choice;
// without either the page follows the operating-system setting.
(function () {
  var t = null;
  try {
    var q = new URLSearchParams(location.search).get("theme");
    t = q || localStorage.getItem("theme");
    // a ?theme= link applies once: dropped from the address, so the theme button then decides
    if (q !== null) history.replaceState(null, "", location.pathname + location.hash);
  } catch (e) {}
  if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
})();
