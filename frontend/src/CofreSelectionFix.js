/* Refuerzo táctil para mantener visible la elección de cofre en navegadores móviles. */
if (typeof document !== "undefined") {
  document.addEventListener("click", (evento) => {
    const cofre = evento.target.closest("[data-testid^='cofre-']");
    if (!cofre) return;
    document.querySelectorAll("[data-testid^='cofre-']").forEach((elemento) => elemento.classList.remove("elegido"));
    cofre.classList.add("elegido");
  }, true);
}