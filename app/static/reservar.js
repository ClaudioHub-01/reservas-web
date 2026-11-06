// Carga los horarios disponibles del día elegido sin recargar la página.
(() => {
  const form = document.getElementById("form-reserva");
  if (!form) return;
  const servicio = form.dataset.servicio;
  const contenedor = document.getElementById("horarios");
  const campoHora = document.getElementById("hora");
  const boton = document.getElementById("confirmar");

  const actualizarBoton = () => { boton.disabled = !campoHora.value; };

  async function cargar(fecha) {
    contenedor.innerHTML = '<p class="ayuda">Buscando horarios…</p>';
    try {
      const r = await fetch(`/api/horarios?servicio=${encodeURIComponent(servicio)}&fecha=${fecha}`);
      const { horarios = [] } = await r.json();
      if (!horarios.length) {
        contenedor.innerHTML = '<p class="ayuda">No quedan horarios para este día. Prueba con otro.</p>';
        campoHora.value = "";
        return actualizarBoton();
      }
      contenedor.innerHTML = "";
      horarios.forEach((h) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "hora" + (h === campoHora.value ? " activa" : "");
        b.textContent = h;
        b.addEventListener("click", () => {
          contenedor.querySelectorAll(".hora").forEach((x) => x.classList.remove("activa"));
          b.classList.add("activa");
          campoHora.value = h;
          actualizarBoton();
        });
        contenedor.appendChild(b);
      });
      if (!horarios.includes(campoHora.value)) campoHora.value = "";
      actualizarBoton();
    } catch {
      contenedor.innerHTML = '<p class="ayuda">No se pudieron cargar los horarios. Intenta de nuevo.</p>';
    }
  }

  form.querySelectorAll('input[name="fecha"]').forEach((r) =>
    r.addEventListener("change", () => { campoHora.value = ""; cargar(r.value); })
  );
  const elegido = form.querySelector('input[name="fecha"]:checked');
  if (elegido) cargar(elegido.value);
  actualizarBoton();
})();
