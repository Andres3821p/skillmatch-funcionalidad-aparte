// Tendencias y pronóstico (tendencias.html)
//
// Lee el servicio de indicadores (carpeta indicadores-api/), que es una API aparte del
// backend Java: lee MongoDB, calcula los indicadores y entrena el modelo de pronóstico.
// Cada tarjeta pide lo suyo: si una falla, muestra "No se pudo cargar este indicador.
// Reintentar" y las demás siguen funcionando.
//
// Sin librerías: las barras reutilizan las clases .ib-* de app.css y las gráficas son SVG
// dibujados aquí (la política CSP del sitio bloquea scripts externos).
// Requiere escaparHtml (base.js o api-config.js) y window.SKILLMATCH_INDICADORES_API
// (base.js cuando la pagina la sirve el propio servicio; indicadores-config.js si va dentro
// del sitio principal).

(function () {
    'use strict';

    // La direccion del servicio se configura en indicadores-config.js
    const BASE = window.SKILLMATCH_INDICADORES_API || '/api/indicadores';
    if (!window.SKILLMATCH_INDICADORES_API) console.warn('tendencias.js: falta window.SKILLMATCH_INDICADORES_API.');

    // En Render gratis pueden estar dormidos este servicio Y el sitio de SkillMatch del que
    // lee los datos: la primera visita puede tardar un par de minutos
    const ESPERA_MAXIMA_MS = 150000;
    const AVISO_LENTO_MS = 4000;

    // ---- Consultas ----

    // Datos que dos tarjetas comparten se piden una sola vez
    const memo = new Map();
    function pedir(ruta) {
        if (!memo.has(ruta)) {
            const p = (async () => {
                const control = new AbortController();
                const reloj = setTimeout(() => control.abort(), ESPERA_MAXIMA_MS);
                try {
                    const r = await fetch(BASE + ruta, { signal: control.signal });
                    if (!r.ok) throw new Error('El servicio respondió ' + r.status);
                    return await r.json();
                } finally { clearTimeout(reloj); }
            })();
            memo.set(ruta, p);
            p.catch(() => memo.delete(ruta));   // un fallo se puede reintentar
        }
        return memo.get(ruta);
    }

    // ---- Formato ----

    const numero = n => Number(n).toLocaleString('es-CO', { maximumFractionDigits: 1 });
    const pct = n => numero(n) + ' %';
    const millones = pesos => '$' + (pesos / 1e6).toLocaleString('es-CO', { maximumFractionDigits: 2 }) + ' millones';
    const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
    const fechaCorta = iso => { const [, mes, dia] = iso.split('-'); return Number(dia) + ' ' + MESES[Number(mes) - 1]; };
    const FLECHAS = {
        sube: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17 9.5 10.5l3.5 3.5L21 6.5"/><path d="M15 6.5h6v6"/></svg>',
        baja: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7l6.5 6.5 3.5-3.5L21 17.5"/><path d="M15 17.5h6v-6"/></svg>'
    };
    const suma = n => (n > 0 ? '+' : n < 0 ? '−' : '') + numero(Math.abs(n));

    // ---- Estados de una tarjeta ----

    const observador = 'IntersectionObserver' in window
        ? new IntersectionObserver(entradas => entradas.forEach(e => {
            if (!e.isIntersecting) return;
            e.target.classList.add('visible');
            observador.unobserve(e.target);
        }), { threshold: 0.15 })
        : null;
    const aparecer = el => { if (observador) observador.observe(el); else el.classList.add('visible'); };

    function esqueleto(el, filas = 4) {
        const item = el.tagName === 'UL' ? 'li' : 'div';
        el.innerHTML = Array.from({ length: filas }, (_, i) =>
            `<${item} class="ib-cargando" aria-hidden="true"><span class="skeleton skeleton-line ${['w-60', 'w-40', 'w-80', 'w-40'][i % 4]}"></span><span class="skeleton skeleton-line"></span></${item}>`
        ).join('');
        el.setAttribute('aria-busy', 'true');
    }

    function vacio(el, texto) {
        const item = el.tagName === 'UL' ? 'li' : 'p';
        el.innerHTML = `<${item} class="ib-vacio">${escaparHtml(texto)}</${item}>`;
        el.removeAttribute('aria-busy');
    }

    function falloTarjeta(el, reintentar) {
        const item = el.tagName === 'UL' ? 'li' : 'p';
        el.innerHTML = `<${item} class="ib-error" role="alert"><span>No se pudo cargar este indicador.</span> <button type="button" class="ib-reintentar">Reintentar</button></${item}>`;
        el.removeAttribute('aria-busy');
        el.querySelector('.ib-reintentar').addEventListener('click', reintentar);
    }

    // Pide, dibuja y, si algo falla, deja el botón de reintentar solo en esa tarjeta.
    // Si la tarjeta tiene varias listas (brecha, cambios), el esqueleto y el error van en un
    // contenedor aparte (id + "Estado") y las listas se esconden mientras tanto.
    function tarjeta(id, ruta, dibujar, filas, conEstado) {
        const el = document.getElementById(id);
        const estado = conEstado ? document.getElementById(id + 'Estado') : el;
        const cargar = async () => {
            if (conEstado) el.hidden = true;
            esqueleto(estado, filas);
            try {
                const datos = await pedir(ruta);
                if (conEstado) { estado.innerHTML = ''; estado.removeAttribute('aria-busy'); el.hidden = false; }
                dibujar(el, datos);
                el.removeAttribute('aria-busy');
            } catch (e) {
                console.error('tendencias.js:', ruta, e);
                falloTarjeta(estado, cargar);
            }
        };
        return cargar();
    }

    // ---- Barras (mismo marcado que indicadores.js) ----

    function barras(lista, filas, total) {
        if (!filas.length) return vacio(lista, 'Todavía no hay datos para este indicador.');
        const maximo = Math.max(1, ...filas.map(f => f.valor));
        lista.innerHTML = filas.map(f => {
            const nombre = f.enlace ? `<a href="${f.enlace}">${escaparHtml(f.nombre)}</a>` : escaparHtml(f.nombre);
            const sub = f.sub ? `<small>${escaparHtml(f.sub)}</small>` : '';
            const valor = f.texto ? escaparHtml(f.texto)
                : `${numero(f.valor)}<small>${total ? pct(f.porcentaje ?? f.valor / total * 100) : ''}</small>`;
            return `<li class="ib-fila${f.destacada ? ' destacada' : ''}">
                <span class="ib-nombre">${nombre}${sub}</span>
                <span class="ib-valor">${valor}</span>
                <span class="ib-barra" aria-hidden="true"><span></span></span></li>`;
        }).join('');
        lista.querySelectorAll('.ib-barra > span').forEach((b, i) => {
            b.style.setProperty('--p', filas[i].valor / maximo);
            b.style.setProperty('--i', i);
        });
        aparecer(lista);
    }

    // Fuera del sitio principal, los enlaces llevan a las vacantes de SkillMatch
    const SITIO = window.SKILLMATCH_SITIO || '';
    const enlaceHabilidad = nombre =>
        (SITIO ? SITIO + '/pages/' : '') + 'oportunidades.html?q=' + encodeURIComponent(nombre);

    // Un indicador que la fuente de datos no permite calcular trae { disponible: false, motivo }
    const noDisponible = (el, d) => {
        if (d && d.disponible === false) { vacio(el, d.motivo || 'Este indicador no está disponible.'); return true; }
        return false;
    };

    // ---- Cada tarjeta ----

    const dibujarDemandadas = (el, d) =>
        barras(el, d.items.map(i => ({ ...i, enlace: enlaceHabilidad(i.nombre) })), d.base);

    const dibujarUsuarios = (el, d) => noDisponible(el, d) || barras(el, d.items, d.base);

    const dibujarEmpresas = (el, d) =>
        barras(el, d.items.map(i => ({
            ...i,
            // null = la fuente no sabe cuántas postulaciones recibió cada empresa
            sub: i.postulaciones == null ? `${numero(i.abiertas)} abiertas hoy`
                : `${numero(i.postulaciones)} ${i.postulaciones === 1 ? 'postulación recibida' : 'postulaciones recibidas'}`
        })), d.base);

    const dibujarSalarios = (el, d) =>
        barras(el, d.items.map(i => ({ ...i, texto: millones(i.valor), sub: `${numero(i.vacantes)} vacantes` })));

    const dibujarEstados = (el, d) => noDisponible(el, d) || barras(el, d.items, d.base);

    // Gráfico de mancuerna: sobre una misma pista hay un punto para lo que piden las vacantes
    // y otro para lo que tienen las personas; la línea que los une ES la brecha. Los dos
    // lados de la tarjeta usan la misma escala (maxComun), así que se pueden comparar.
    // Solo se animan opacity y transform: la posición de los puntos es fija.
    function filasBrecha(lista, items, maxComun) {
        if (!items.length) return vacio(lista, 'Ninguna por ahora.');
        lista.innerHTML = items.map(f => {
            const d = f.demanda / maxComun, o = f.oferta / maxComun;
            const desde = Math.min(d, o), ancho = Math.abs(d - o);
            // La línea crece desde el punto de las personas hacia el de las vacantes
            const origen = o <= d ? 'left' : 'right';
            return `
            <li class="br-fila">
                <span class="ib-nombre"><a href="${enlaceHabilidad(f.nombre)}">${escaparHtml(f.nombre)}</a></span>
                <span class="br-datos">Piden ${pct(f.demanda)} · Tienen ${pct(f.oferta)}</span>
                <span class="mz-pista" aria-hidden="true">
                    <span class="mz-interior">
                        <span class="mz-union" style="left:${(desde * 100).toFixed(2)}%;width:${(ancho * 100).toFixed(2)}%;transform-origin:${origen} center"></span>
                        <span class="mz-punto oferta" style="left:${(o * 100).toFixed(2)}%" title="Personas que la tienen: ${pct(f.oferta)}"></span>
                        <span class="mz-punto demanda" style="left:${(d * 100).toFixed(2)}%" title="Vacantes que la piden: ${pct(f.demanda)}"></span>
                    </span>
                </span>
            </li>`;
        }).join('');
        lista.querySelectorAll('.br-fila').forEach((f, i) => f.style.setProperty('--i', i));
        aparecer(lista);
    }

    function dibujarBrecha(_, d) {
        const faltan = document.getElementById('tFaltan'), sobran = document.getElementById('tSobran');
        // Sin datos de las personas: un solo mensaje, sin la leyenda ni la segunda columna vacía
        const tarjeta = faltan.closest('.indicador');
        const leyenda = tarjeta && tarjeta.querySelector('.leyenda');
        const columnaSobran = sobran.parentElement;
        if (leyenda) leyenda.hidden = !d.disponible;
        columnaSobran.hidden = !d.disponible;
        faltan.previousElementSibling.hidden = !d.disponible;
        if (!d.disponible) { vacio(faltan, d.motivo); return; }
        const todos = [...d.faltan, ...d.sobran];
        const maxComun = Math.max(1, ...todos.flatMap(f => [f.demanda, f.oferta]));
        filasBrecha(faltan, d.faltan, maxComun);
        filasBrecha(sobran, d.sobran, maxComun);
    }

    // Mini-línea (sparkline): el % de vacantes que piden la habilidad, semana a semana.
    // Cada una usa su propia escala vertical: sirve para ver la forma (sube, baja, se agita),
    // no para comparar habilidades entre sí; para eso están los números del lado.
    function miniLinea(serie, nombre) {
        if (!Array.isArray(serie) || serie.length < 3) return '';   // API vieja o muy pocas semanas
        const W = 104, H = 36, P = 4;
        const min = Math.min(...serie), max = Math.max(...serie);
        const rango = max - min || 1;
        const px = i => P + i / (serie.length - 1) * (W - 2 * P);
        const py = v => H - P - (v - min) / rango * (H - 2 * P);
        const puntos = serie.map((v, i) => `${px(i).toFixed(1)} ${py(v).toFixed(1)}`);
        const ult = serie.length - 1;
        // Recta de tendencia (mínimos cuadrados): con pocas vacantes por semana la línea real
        // es dentada, y la recta deja ver hacia dónde va
        const n = serie.length, mx = ult / 2, my = serie.reduce((a, v) => a + v, 0) / n;
        const pendiente = serie.reduce((a, v, i) => a + (i - mx) * (v - my), 0) / serie.reduce((a, _, i) => a + (i - mx) ** 2, 0);
        const yRecta = i => Math.min(max, Math.max(min, my + pendiente * (i - mx)));
        const recta = `<line class="ts-recta" x1="${px(0).toFixed(1)}" y1="${py(yRecta(0)).toFixed(1)}" x2="${px(ult).toFixed(1)}" y2="${py(yRecta(ult)).toFixed(1)}"/>`;
        const texto = `${nombre}: de ${pct(serie[0])} a ${pct(serie[ult])} de las vacantes en ${serie.length} semanas`;
        return `<svg class="tn-spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="${escaparHtml(texto)}">
            <line class="ts-base" x1="${P}" x2="${W - P}" y1="${H - P}" y2="${H - P}"/>
            ${recta}
            <path class="ts-linea" d="M${puntos.join(' L')}"/>
            <circle class="ts-fin" cx="${px(ult).toFixed(1)}" cy="${py(serie[ult]).toFixed(1)}" r="3"/>
            <title>${escaparHtml(texto)}</title>
        </svg>`;
    }

    function filasTendencia(lista, items, vacioTexto) {
        if (!items.length) return vacio(lista, vacioTexto);
        lista.innerHTML = items.map(f => {
            const firme = f.evidencia === 'firme';
            const proyeccion = firme ? ` · En 4 semanas: ${pct(f.proyeccion_4_semanas)}` : '';
            const spark = miniLinea(f.serie, f.nombre);
            return `<li class="tn-fila ${f.tendencia}${spark ? ' con-spark' : ''}">
                <span class="tn-nombre"><a href="${enlaceHabilidad(f.nombre)}">${escaparHtml(f.nombre)}</a></span>
                <span class="tn-cambio">${FLECHAS[f.tendencia] || ''}${suma(f.cambio_pp_semana)} puntos por semana</span>
                ${spark}
                <span class="tn-detalle">Hoy en ${pct(f.porcentaje_actual)} de las vacantes${proyeccion} ·
                    <span class="tn-evidencia ${firme ? 'firme' : ''}">${firme ? 'Evidencia firme' : 'Podría ser azar'}</span></span>
            </li>`;
        }).join('');
        lista.removeAttribute('aria-busy');
        aparecer(lista);
    }

    function dibujarCambio(_, d) {
        const suben = document.getElementById('tSuben'), bajan = document.getElementById('tBajan');
        const nota = document.getElementById('tCambioNota');
        if (!d.disponible) { vacio(suben, d.motivo); vacio(bajan, ''); nota.textContent = ''; return; }
        filasTendencia(suben, d.suben, 'Ninguna habilidad subió lo suficiente en estas semanas.');
        filasTendencia(bajan, d.bajan, 'Ninguna habilidad bajó lo suficiente en estas semanas.');
        nota.textContent = `Se analizaron ${numero(d.vacantes_analizadas)} vacantes de las últimas ${d.semanas_analizadas} semanas completas ` +
            `y ${numero(d.habilidades_evaluadas)} habilidades. Con pocas vacantes por semana el azar pesa mucho: ` +
            'solo es «evidencia firme» el cambio que se sostiene tras descontar las casualidades. ' +
            'En cada mini-línea, los puntos marcan la tendencia.';
    }

    // ---- Gráfica de pronóstico (SVG propio) ----

    // Techo "redondo" para el eje: 8, 10, 12, 15, 20, 25, 30, 40, 50...
    function techo(maximo) {
        const bruto = Math.max(maximo * 1.08, 4) / 4;
        const magnitud = Math.pow(10, Math.floor(Math.log10(bruto)));
        const paso = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10].map(m => m * magnitud).find(p => p >= bruto);
        return paso * 4;
    }

    function svgPronostico(ancho, datos) {
        const hist = datos.historico, pron = datos.pronostico;
        const alto = ancho < 480 ? 220 : 264;
        const m = { i: 40, d: 14, s: 14, b: 30 };
        const w = ancho - m.i - m.d, h = alto - m.s - m.b;
        const SEMANA = 7 * 864e5;
        const t0 = Date.parse(hist[0].semana);
        const indice = iso => Math.round((Date.parse(iso) - t0) / SEMANA);
        const ultimoIndice = Math.max(1, indice(pron[pron.length - 1].semana));
        const x = iso => m.i + indice(iso) / ultimoIndice * w;
        const tope = techo(Math.max(...hist.map(p => p.valor), ...pron.map(p => p.maximo)));
        const y = v => m.s + h - v / tope * h;
        const completas = hist.filter(p => !p.parcial);
        const parcial = hist.find(p => p.parcial);
        const ultima = completas[completas.length - 1];
        const punto = (iso, v) => `${x(iso).toFixed(1)} ${y(v).toFixed(1)}`;

        const trazoHist = completas.map((p, i) => (i ? 'L' : 'M') + punto(p.semana, p.valor)).join(' ');
        const trazoPron = ['M' + punto(ultima.semana, ultima.valor), ...pron.map(p => 'L' + punto(p.semana, p.valor))].join(' ');
        const arriba = [ [ultima.semana, ultima.valor], ...pron.map(p => [p.semana, p.maximo]) ];
        const abajo = [ [ultima.semana, ultima.valor], ...pron.map(p => [p.semana, p.minimo]) ].reverse();
        const banda = 'M' + [...arriba, ...abajo].map(([s, v]) => punto(s, v)).join(' L') + ' Z';

        const rejilla = [0, 1, 2, 3, 4].map(k => {
            const v = tope / 4 * k, yy = y(v).toFixed(1);
            return `<line class="g-rejilla" x1="${m.i}" x2="${ancho - m.d}" y1="${yy}" y2="${yy}"/>` +
                   `<text class="g-eje" x="${m.i - 8}" y="${(+yy + 4).toFixed(1)}" text-anchor="end">${numero(v)}</text>`;
        }).join('');

        // En pantallas angostas, menos etiquetas para que no se pisen
        const marcas = ancho < 480 ? [0, .5, 1] : [0, .25, .5, .75, 1];
        const etiquetas = marcas.map((f, k) => {
            const i = Math.round(f * ultimoIndice);
            const iso = new Date(t0 + i * SEMANA).toISOString().slice(0, 10);
            const ancla = k === 0 ? 'start' : k === marcas.length - 1 ? 'end' : 'middle';
            return `<text class="g-eje" x="${(m.i + i / ultimoIndice * w).toFixed(1)}" y="${alto - 8}" text-anchor="${ancla}">${fechaCorta(iso)}</text>`;
        }).join('');

        const nombre = datos.unidad === 'postulaciones' ? 'postulaciones' : 'vacantes';
        const puntosPron = pron.map(p =>
            `<circle class="g-punto pron" cx="${x(p.semana).toFixed(1)}" cy="${y(p.valor).toFixed(1)}" r="4">` +
            `<title>Semana del ${fechaCorta(p.semana)}: se esperan ${numero(p.valor)} ${nombre} (entre ${numero(p.minimo)} y ${numero(p.maximo)})</title></circle>`).join('');
        const puntoParcial = parcial
            ? `<circle class="g-punto parcial" cx="${x(parcial.semana).toFixed(1)}" cy="${y(parcial.valor).toFixed(1)}" r="4.5"><title>Semana en curso, incompleta: ${numero(parcial.valor)} hasta ahora</title></circle>` : '';

        return `<svg viewBox="0 0 ${ancho} ${alto}" role="img" aria-label="${escaparHtml(datos.lectura)}">
            ${rejilla}${etiquetas}
            <path class="g-banda" d="${banda}"/>
            <path class="g-hist" d="${trazoHist}"/>
            <path class="g-pron" d="${trazoPron}"/>
            ${puntosPron}${puntoParcial}
            <circle class="g-punto" cx="${x(ultima.semana).toFixed(1)}" cy="${y(ultima.valor).toFixed(1)}" r="4.5"><title>Última semana completa: ${numero(ultima.valor)} ${nombre}</title></circle>
        </svg>`;
    }

    function dibujarPronostico(cont, datos) {
        if (!datos.disponible) { vacio(cont, datos.motivo); return; }
        const ev = datos.evaluacion;
        cont.innerHTML = `
            <div class="grafica-lienzo"></div>
            <ul class="leyenda" aria-hidden="true">
                <li><span class="leyenda-linea"></span>Semanas completas</li>
                <li><span class="leyenda-punto"></span>Semana en curso (incompleta)</li>
                <li><span class="leyenda-linea pron"></span>Pronóstico</li>
                <li><span class="leyenda-banda"></span>Rango probable (80 %)</li>
            </ul>
            <p class="grafica-lectura">${escaparHtml(datos.lectura)}</p>
            ${datos.nota ? `<p class="grafica-nota">${escaparHtml(datos.nota)}</p>` : ''}
            <details class="tend-detalle">
                <summary>Cómo le fue al modelo</summary>
                <p>Se probó cada modelo «adivinando» semanas ya conocidas. El error medio es cuántas ${escaparHtml(datos.unidad)} se equivocó por semana (menos es mejor), con ${ev.semanas_usadas} semanas de historia.</p>
                <ul>${ev.modelos.map(mo => `<li class="${mo.id === datos.modelo ? 'elegido' : ''}"><span>${escaparHtml(mo.nombre)}${mo.id === datos.modelo ? ' (el elegido)' : ''}</span><span>${numero(mo.mae)}</span></li>`).join('')}</ul>
            </details>`;
        const lienzo = cont.querySelector('.grafica-lienzo');
        let anchoPrevio = 0;
        const dibujar = () => {
            const ancho = Math.round(lienzo.clientWidth);
            if (!ancho || ancho === anchoPrevio) return;
            anchoPrevio = ancho;
            lienzo.innerHTML = svgPronostico(Math.max(ancho, 260), datos);
        };
        dibujar();
        if ('ResizeObserver' in window) new ResizeObserver(dibujar).observe(lienzo);
        aparecer(cont);
    }

    // ---- Cifras, avisos y hora ----

    function cifras(r) {
        // Sin tiempo de respuesta (fuente "api"), la cuarta cifra muestra las personas registradas
        if (r.dias_mediana_respuesta == null && typeof r.personas === 'number') {
            const cuarta = document.getElementById('cifraCuarta');
            const nombre = document.getElementById('cifraCuartaNombre');
            if (cuarta && nombre) { cuarta.dataset.cifra = 'personas'; nombre.textContent = 'Personas registradas'; }
        }
        document.querySelectorAll('[data-cifra]').forEach(el => {
            const v = r[el.dataset.cifra];
            el.textContent = typeof v === 'number' ? numero(v) : '–';
        });
        const fuente = document.getElementById('tendFuente');
        if (fuente) {
            fuente.textContent = r.fuente === 'api'
                ? 'Datos en vivo de SkillMatch: vacantes abiertas, empresas y totales que publica el sitio. ' +
                  'Los indicadores que necesitan información privada de las personas o de las postulaciones aparecen como no disponibles.'
                : '';
            fuente.hidden = r.fuente !== 'api';
        }
        const avisos = [];
        if (r.fuente === 'demo') avisos.push('Estás viendo datos de demostración, inventados para probar la página. No son las cifras reales de SkillMatch.');
        if (r.desactualizado) avisos.push('La fuente de datos no respondió: se muestran los últimos datos guardados.');
        const aviso = document.getElementById('tendAviso');
        aviso.textContent = avisos.join(' ');
        aviso.hidden = !avisos.length;
        // "5:52 p. m." ya termina en punto
        const hora = new Date(r.actualizado).toLocaleTimeString('es-CO', { hour: 'numeric', minute: '2-digit' }).replace(/\.?$/, '.');
        document.getElementById('tendHora').textContent = 'Datos de las ' + hora;
    }

    async function cargarCifras() {
        try { cifras(await pedir('/resumen')); } catch (e) { /* las tarjetas muestran su propio error */ }
    }

    // ---- Arranque ----

    document.addEventListener('DOMContentLoaded', async () => {
        const seccion = document.getElementById('tendencias');
        const espera = document.getElementById('tendEspera');
        // Un servicio gratuito dormido tarda en despertar: sin aviso la página parece rota
        const reloj = setTimeout(() => { espera.hidden = false; }, AVISO_LENTO_MS);

        await Promise.allSettled([
            cargarCifras(),
            tarjeta('tDemandadas', '/habilidades-demandadas?top=8', dibujarDemandadas, 6),
            tarjeta('tEmpresas', '/empresas-activas?top=8', dibujarEmpresas, 6),
            tarjeta('tUsuarios', '/habilidades-usuarios?top=8', dibujarUsuarios, 6),
            tarjeta('tBrecha', '/brecha-habilidades?top=5', dibujarBrecha, 4, true),
            tarjeta('tPronVacantes', '/pronostico/vacantes?semanas=4', dibujarPronostico, 5),
            tarjeta('tPronPostulaciones', '/pronostico/postulaciones?semanas=4', dibujarPronostico, 5),
            tarjeta('tCambio', '/tendencia-habilidades?top=5', dibujarCambio, 4, true),
            tarjeta('tSalarios', '/salarios', dibujarSalarios, 4),
            tarjeta('tEstados', '/postulaciones-estado', dibujarEstados, 4)
        ]);
        clearTimeout(reloj);
        espera.hidden = true;
        seccion.removeAttribute('aria-busy');
    });
})();
