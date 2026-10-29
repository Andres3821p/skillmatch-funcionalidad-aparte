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
        var boton = document.getElementById('cambiarTema');
        if (boton) {
            boton.textContent = t === 'dark' ? 'Modo claro' : 'Modo oscuro';
            boton.setAttribute('aria-pressed', String(t === 'dark'));
        }
    }
    aplicar(tema);

    document.addEventListener('DOMContentLoaded', function () {
        aplicar(tema);
        var boton = document.getElementById('cambiarTema');
        if (!boton) return;
        boton.addEventListener('click', function () {
            tema = tema === 'dark' ? 'light' : 'dark';
            try { localStorage.setItem('skillmatch_theme', tema); } catch (e) { /* sin almacenamiento */ }
            aplicar(tema);
        });
    });
})();
