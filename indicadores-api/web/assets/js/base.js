// Lo mínimo que tendencias.js necesita del sitio principal, sin traer todo api-config.js
// (que maneja sesiones y el resto de la API de SkillMatch).

// La página y la API de indicadores viven en el MISMO servicio: la ruta es relativa.
// Así funciona igual en tu PC (http://localhost:8000) y publicada en Render.
window.SKILLMATCH_INDICADORES_API = '/api/indicadores';

// Dirección del sitio principal, para los enlaces a vacantes y al resto de SkillMatch
window.SKILLMATCH_SITIO = 'https://skillmatch-yz37.onrender.com';

/** Convierte un texto en HTML seguro (igual que escaparHtml de api-config.js). */
function escaparHtml(texto) {
    return String(texto ?? '').replace(/[&<>"']/g, c => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
}
