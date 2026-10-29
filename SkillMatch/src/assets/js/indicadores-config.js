// Direccion del servicio de indicadores (carpeta indicadores-api/).
//
// tendencias.js lee window.SKILLMATCH_INDICADORES_API y le agrega cada ruta
// (/resumen, /pronostico/vacantes...). Se carga ANTES de tendencias.js.
//
// - En tu PC (Live Server en localhost o 127.0.0.1) llama al servicio local:
//   http://localhost:8000  (arrancalo con indicadores-api/iniciar.ps1).
// - Publicado, llama a API_INDICADORES. CAMBIALA por la direccion real del
//   servicio cuando lo despliegues en Render (sin "/" al final).

(function () {
    'use strict';

    const API_INDICADORES = 'https://skillmatch-indicadores.onrender.com';
    const API_LOCAL = 'http://localhost:8000';

    const local = ['localhost', '127.0.0.1', ''].includes(window.location.hostname);
    const base = (local ? API_LOCAL : API_INDICADORES).replace(/\/+$/, '');

    window.SKILLMATCH_INDICADORES_API = base + '/api/indicadores';
})();
