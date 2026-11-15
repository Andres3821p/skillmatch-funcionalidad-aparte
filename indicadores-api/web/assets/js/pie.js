// Pie de página grande, el mismo de SkillMatch (ui.js, sección 15), adaptado a este servicio:
// los enlaces llevan al sitio principal con su dirección completa y no se ofrece instalar la app.
// Va en un archivo (no dentro del HTML) porque la política de seguridad solo permite scripts propios.
// Si este archivo no carga, queda el texto corto que trae el <footer> del HTML.
(function () {
    'use strict';

    var SITIO = window.SKILLMATCH_SITIO || 'https://skillmatch-yz37.onrender.com';
    var QUIETO = !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches);

    // Las mismas columnas que ve una persona sin sesión en SkillMatch. Solo enlaces reales.
    var COLUMNAS = [
        { titulo: 'Busco trabajo', enlaces: [
            ['seleccionar-registro.html', 'Crear mi perfil'],
            ['oportunidades.html', 'Ver vacantes'],
            ['empresas.html', 'Conocer las empresas'],
            ['login.html', 'Iniciar sesión']
        ] },
        { titulo: 'Empresas', enlaces: [
            ['registro-empresa.html', 'Registrar mi empresa'],
            ['login.html?tipo=empresa', 'Acceso empresas']
        ] },
        { titulo: 'SkillMatch', enlaces: [
            ['index.html#como-funciona', 'Cómo funciona'],
            ['index.html#cerca', 'Vacantes cerca de ti'],
            ['dashboard.html', 'Indicadores del mercado'],
            ['como-aprende.html', 'Cómo aprende SkillMatch'],
            ['politica-datos.html', 'Política de datos']
        ] }
    ];

    // Tamaño de letra: mismas claves y valores que SkillMatch; tema.js lo aplica al cargar la página
    var LETRA_KEY = 'skillmatch_letra';
    var TAMANOS = [
        { id: 'normal', nombre: 'Normal' },
        { id: 'grande', nombre: 'Grande' },
        { id: 'muy-grande', nombre: 'Muy grande' }
    ];
    var FLECHA = '<svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h13M13 6l6 6-6 6"/></svg>';

    function tamanoActual() {
        return document.documentElement.getAttribute('data-letra') || 'normal';
    }

    function marcarTamano() {
        var actual = tamanoActual();
        document.querySelectorAll('.pie-letra-btn').forEach(function (b) {
            b.setAttribute('aria-pressed', String(b.dataset.letra === actual));
        });
    }

    function ponerTamano(id) {
        if (id === 'normal') document.documentElement.removeAttribute('data-letra');
        else document.documentElement.setAttribute('data-letra', id);
        try {
            if (id === 'normal') localStorage.removeItem(LETRA_KEY); else localStorage.setItem(LETRA_KEY, id);
        } catch (e) { /* sin almacenamiento: vale solo para esta página */ }
        marcarTamano();
    }

    function construirPie() {
        var pie = document.querySelector('body > footer');
        if (!pie || pie.classList.contains('pie')) return;
        pie.classList.add('pie');
        pie.innerHTML =
            '<div class="pie-ola" aria-hidden="true"></div>' +
            '<div class="container">' +
                '<div class="pie-grid">' +
                    '<div class="pie-marca">' +
                        '<a href="' + SITIO + '/" class="pie-logo"><img src="assets/img/logo-oscuro.png" alt="SkillMatch, ir al inicio" width="531" height="160" loading="lazy"></a>' +
                        '<p>La bolsa de empleo de Cartagena para todos los sectores: compara tus habilidades con cada vacante de la ciudad antes de postularte.</p>' +
                    '</div>' +
                    '<nav class="pie-columnas" aria-label="Enlaces del pie de página">' +
                        COLUMNAS.map(function (col) {
                            return '<div><h2 class="pie-titulo">' + col.titulo + '</h2><ul>' +
                                col.enlaces.map(function (e) { return '<li><a href="' + SITIO + '/pages/' + e[0] + '">' + e[1] + '</a></li>'; }).join('') +
                                '</ul></div>';
                        }).join('') +
                    '</nav>' +
                '</div>' +
                '<div class="pie-base">' +
                    '<p>&copy; ' + new Date().getFullYear() + ' SkillMatch Cartagena · Hecho en Cartagena de Indias para conectar a las personas y las empresas de la ciudad.</p>' +
                    '<div class="pie-letra" role="group" aria-label="Tamaño de letra">' +
                        '<span>Letra</span>' +
                        TAMANOS.map(function (t) {
                            return '<button type="button" class="pie-letra-btn" data-letra="' + t.id + '" aria-pressed="false" aria-label="' + t.nombre + '" title="' + t.nombre + '">A</button>';
                        }).join('') +
                    '</div>' +
                    '<div class="pie-acciones">' +
                        '<button type="button" class="pie-arriba">' + FLECHA + 'Volver arriba</button>' +
                    '</div>' +
                '</div>' +
            '</div>' +
            '<div class="pie-gigante" aria-hidden="true"><span>Skill</span><span>Match</span></div>';

        pie.querySelectorAll('.pie-letra-btn').forEach(function (b) {
            b.addEventListener('click', function () { ponerTamano(b.dataset.letra); });
        });
        marcarTamano();

        // Volver arriba: sube (suave si se permite movimiento) y deja el foco en el logo de la barra
        pie.querySelector('.pie-arriba').addEventListener('click', function () {
            window.scrollTo({ top: 0, behavior: QUIETO ? 'auto' : 'smooth' });
            var inicio = document.querySelector('header a');
            if (inicio) inicio.focus({ preventScroll: true });
        });

        // La palabra gigante sube al entrar en pantalla
        var gigante = pie.querySelector('.pie-gigante');
        if (QUIETO || !('IntersectionObserver' in window)) {
            gigante.classList.add('is-visible');
        } else {
            var obs = new IntersectionObserver(function (entradas) {
                if (!entradas[0].isIntersecting) return;
                gigante.classList.add('is-visible');
                obs.disconnect();
            }, { threshold: 0.2 });
            obs.observe(gigante);
        }
    }

    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', construirPie);
    else construirPie();
})();
