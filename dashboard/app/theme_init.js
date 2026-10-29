// Theme before the first paint: ?theme= (screenshots/tests) or the stored choice;
// without either the page follows the operating-system setting.
(function () {
  var t = null;
  try { t = new URLSearchParams(location.search).get("theme") || localStorage.getItem("theme"); } catch (e) {}
  if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
})();
