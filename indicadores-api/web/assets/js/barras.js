// La barra de arriba se esconde al bajar y vuelve al subir un poco, igual que en SkillMatch
// (ui.js, barrasQueSeEsconden). Aquí solo se decide cuándo: la clase html.barras-escondidas y el
// movimiento ya están en app.css (sección 78).
//  - Arriba del todo (menos de 96 px) y al llegar al final de la página, siempre se ve.
//  - Para esconderse hay que bajar de verdad (24 px seguidos); para volver basta subir 8 px,
//    porque quien sube suele estar buscando la barra.
//  - No se esconde mientras se usa: con el foco dentro (teclado) o con un menú abierto.
//  - Una sola lectura por cuadro (requestAnimationFrame) y la clase solo cambia cuando hace falta.
(function () {
    'use strict';

    var header = document.querySelector('body > header');
    if (!header) return;
    var raiz = document.documentElement;
    var ARRIBA = 96, BAJAR = 24, SUBIR = 8;
    var ultimo = Math.max(0, window.scrollY);
    var recorrido = 0;          // lo recorrido seguido en la misma dirección (+ baja, - sube)
    var pendiente = false;

    function poner(esconder) {
        if (raiz.classList.contains('barras-escondidas') !== esconder) raiz.classList.toggle('barras-escondidas', esconder);
    }

    function enUso() {
        return header.contains(document.activeElement) || !!header.querySelector('[aria-expanded="true"]');
    }

    function revisar() {
        pendiente = false;
        var maximo = raiz.scrollHeight - window.innerHeight;
        var y = Math.min(Math.max(0, window.scrollY), Math.max(0, maximo));   // sin el rebote del iPhone
        var d = y - ultimo;
        ultimo = y;
        if (y < ARRIBA || y >= maximo - 4) { recorrido = 0; poner(false); return; }
        if (d === 0) return;
        if ((d > 0) !== (recorrido > 0)) recorrido = 0;   // cambio de dirección: se cuenta de nuevo
        recorrido += d;
        if (recorrido > BAJAR) { if (!enUso()) poner(true); }
        else if (recorrido < -SUBIR) poner(false);
    }

    window.addEventListener('scroll', function () {
        if (pendiente) return;
        pendiente = true;
        requestAnimationFrame(revisar);
    }, { passive: true });

    // El teclado (o el lector de pantalla) entra a la barra: vuelve
    document.addEventListener('focusin', function (e) {
        var t = e.target;
        if (t instanceof Element && t.closest('body > header')) poner(false);
    });

    // Al volver con "atrás", la página sale de la memoria tal cual: se revisa desde donde quedó
    window.addEventListener('pageshow', function (e) {
        if (!e.persisted) return;
        ultimo = Math.max(0, window.scrollY); recorrido = 0; poner(false);
    });
})();
