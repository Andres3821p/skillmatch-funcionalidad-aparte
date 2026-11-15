// Modo claro / oscuro y tamaño de letra, igual que en SkillMatch.
// Va en un archivo (no dentro del HTML) porque la política de seguridad del servicio solo
// permite scripts propios. Se carga en el <head> para que la página no "parpadee".
(function () {
    'use strict';
    var raiz = document.documentElement;
    var tema;
    try { tema = localStorage.getItem('skillmatch_theme'); } catch (e) { tema = null; }
    if (tema !== 'dark' && tema !== 'light') {
        tema = window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    try {
        var letra = localStorage.getItem('skillmatch_letra');
        if (letra === 'grande' || letra === 'muy-grande') raiz.setAttribute('data-letra', letra);
    } catch (e) { /* sin almacenamiento */ }
    raiz.style.setProperty('--reloj', Date.now() % 864e5 + 'ms');

    function aplicar(t) {
        raiz.setAttribute('data-theme', t);
        var color = document.querySelector('meta[name="theme-color"]');
        if (color) color.setAttribute('content', t === 'dark' ? '#0B1B2C' : '#EDF2F8');
        var logo = document.querySelector('.logo img');
        if (logo) logo.src = 'assets/img/' + (t === 'dark' ? 'logo-oscuro.png' : 'logo.png');
        pintarBoton(t);
    }

    // Los mismos iconos que el principal (ui.js): la luna invita a ir al modo oscuro; el sol, a volver
    var ICONOS = {
        moon: '<path d="M20.5 14.5A8.5 8.5 0 1 1 9.5 3.5a7 7 0 0 0 11 11Z"/>',
        sun: '<circle cx="12" cy="12" r="4.5"/><path d="M12 3v2.2M12 18.8V21M4.2 12H2M22 12h-2.2M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6"/>'
    };
    function pintarBoton(t) {
        var boton = document.getElementById('cambiarTema');
        if (!boton) return;
        var oscuro = t === 'dark', nombre = oscuro ? 'sun' : 'moon';
        boton.innerHTML = '<svg class="ico ico-' + nombre + '" viewBox="0 0 24 24" aria-hidden="true">' + ICONOS[nombre] + '</svg>';
        boton.setAttribute('aria-pressed', String(oscuro));
        boton.setAttribute('aria-label', oscuro ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro');
    }

    // El tema nuevo se revela en círculo desde el botón (View Transitions), como en SkillMatch.
    // Sin soporte o con "reducir movimiento", cambia al instante.
    function cambiarConEfecto(boton, aplicarCambio) {
        var quieto = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (quieto || !document.startViewTransition) { aplicarCambio(); return; }
        var r = boton.getBoundingClientRect();
        var x = r.left + r.width / 2, y = r.top + r.height / 2;
        var radio = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
        raiz.classList.add('tema-cambiando');
        var transicion = document.startViewTransition(aplicarCambio);
        transicion.ready.then(function () {
            raiz.animate({ clipPath: ['circle(0px at ' + x + 'px ' + y + 'px)', 'circle(' + radio + 'px at ' + x + 'px ' + y + 'px)'] },
                         { duration: 650, easing: 'cubic-bezier(.4, 0, .2, 1)', pseudoElement: '::view-transition-new(root)' });
        }).catch(function () {});
        transicion.finished.finally(function () { raiz.classList.remove('tema-cambiando'); });
    }
    aplicar(tema);

    document.addEventListener('DOMContentLoaded', function () {
        aplicar(tema);
        var boton = document.getElementById('cambiarTema');
        if (!boton) return;
        boton.addEventListener('click', function () {
            tema = tema === 'dark' ? 'light' : 'dark';
            try { localStorage.setItem('skillmatch_theme', tema); } catch (e) { /* sin almacenamiento */ }
            var elegido = tema;
            cambiarConEfecto(boton, function () { aplicar(elegido); });
        });
    });
})();
