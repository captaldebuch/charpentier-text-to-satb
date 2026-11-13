const field = id => document.getElementById(id);
const form = field('compose'), phrase = field('phrase'), statusText = field('compose-status');
const controls = Array.from(form.querySelectorAll('button,input,select'));
const draw = () => crypto.getRandomValues(new Uint32Array(1))[0] & 0x7fffffff;
let seed = draw(), urls = [];
function resource(content, type) {
    const url = URL.createObjectURL(new Blob([content], {type}));
    urls.push(url);
    return url;
}
function clearComposition() {
    field('performance').pause();
    field('composition').hidden = true;
    for (const url of urls) URL.revokeObjectURL(url);
    urls = [];
    statusText.textContent = '';
}
phrase.oninput = clearComposition;
const compoundOption = field('meter').querySelector('option[value="6/8"]');
const coreHint = field('meter-hint').textContent;
function syncMeter() {
    const core = field('pool').value === 'core';
    const reset = core && field('meter').value === '6/8';
    if (reset) field('meter').value = '4/4';
    compoundOption.disabled = core;
    field('meter-hint').hidden = !core;
    field('meter-hint').textContent = reset
        ? ui('Retour en 4/4. ', 'Switched to 4/4. ', 'عاد الميزان إلى 4/4. ') + coreHint
        : coreHint;
}
for (const select of form.querySelectorAll('select')) select.onchange = () => {
    clearComposition();
    syncMeter();
};
syncMeter();

function cadenceName(value) {
    return field('cadence').querySelector('option[value="' + value + '"]').textContent;
}
function describeStudy(a) {
    const note = a.tonic.replace('-', '♭').replace('#', '♯');
    const solfege = {C:['do','دو'],D:['ré','ري'],E:['mi','مي'],F:['fa','فا'],G:['sol','صول'],A:['la','لا'],B:['si','سي']};
    const syllable = solfege[note[0]];
    const tonic = ui(syllable[0],note[0],syllable[1]) + note.slice(1);
    const mode = a.mode === 'minor' ? ui('mineur', 'minor', 'الصغير') : ui('majeur', 'major', 'الكبير');
    const cadence = cadenceName(a.cadence);
    const peak = a.peakBars.join(', ');
    return ui(
        `En ${tonic} ${mode} (${a.meter}), la première phrase se suspend sur la dominante à la mesure 4. La seconde se termine à la mesure 8 par la cadence « ${cadence} » (${a.penultimate} → ${a.final}). Le soprano va de ${a.low} à ${a.high} et atteint son sommet ${a.peakBars.length === 1 ? 'à la mesure' : 'aux mesures'} ${peak}.`,
        `In ${tonic} ${mode} (${a.meter}), the first phrase pauses on the dominant in measure 4. The second ends in measure 8 with the selected cadence, ${cadence} (${a.penultimate} → ${a.final}). The soprano ranges from ${a.low} to ${a.high} and reaches its highest note in ${a.peakBars.length === 1 ? 'measure' : 'measures'} ${peak}.`,
        `في سلم ${tonic} ${mode} (ميزان ${a.meter}) تستقر العبارة الأولى على الدرجة الخامسة في المازورة ٤. وتنتهي الثانية في المازورة ٨ بالقفلة المختارة «${cadence}» (${a.penultimate} → ${a.final}). يمتد صوت السوبرانو من ${a.low} إلى ${a.high} ويبلغ أعلى نغمة في الموازير ${a.peakBars.join('، ')}.`
    );
}

field('reroll').onclick = () => { seed = draw(); form.requestSubmit(); };
form.onsubmit = async event => {
    event.preventDefault();
    clearComposition();
    controls.forEach(control => { control.disabled = true; });
    statusText.textContent = ui("Composition des quatre voix en cours…","Composing the four voices…","جارٍ تأليف الأصوات الأربعة…");
    try {
        const key = field('shift').value;
        const minor = key.startsWith('minor:');
        const query = new URLSearchParams({
            seed, pool:field('pool').value, meter:field('meter').value, cadence:field('cadence').value,
            mode:minor ? 'minor' : 'major', shift:minor ? key.split(':')[1] : key
        });
        const response = await fetch('/api/text-to-charpentier?' + query, {method:'POST', headers:{'Content-Type':'text/plain;charset=UTF-8'}, body:phrase.value.trim()});
        if (!response.ok) {
            const error = await response.json().catch(() => ({}));
            throw new Error(ui(error.detail || 'Génération indisponible. Réessayez.', response.status === 422 ? 'Enter 1–32 words (up to 160 characters).' : 'Generation is unavailable. Please retry.', response.status === 422 ? 'أدخل من كلمة إلى ٣٢ كلمة (١٦٠ حرفاً كحد أقصى).' : 'تعذّر التوليد. حاول مجدداً.'));
        }
        const data = await response.json();
        field('study-analysis').textContent = describeStudy(data.analysis);
        const audit = data.analysis.counterpoint;
        field('counterpoint').hidden = !audit;
        if (audit) {
            const numbers = new Intl.NumberFormat(document.documentElement.lang);
            for (const cell of field('counterpoint').querySelectorAll('[data-counterpoint]')) {
                cell.textContent = numbers.format(audit[cell.dataset.counterpoint]);
            }
        }
        field('notation').src = resource(data.svg, 'image/svg+xml');
        field('performance').src = resource(Uint8Array.from(atob(data.audio), c => c.charCodeAt(0)), 'audio/wav');
        field('export').href = resource(data.xml, 'application/vnd.recordare.musicxml+xml');
        field('trace').replaceChildren(...data.trace.map(({source, cadence, measure, sourceMeter, startQuarter, contour, rhythm}) => {
            const row = document.createElement('li');
            if (!source) {
                row.textContent = ui('Cadence composée', 'Composed cadence', 'قفلة مؤلّفة') + ' · ' + cadenceName(cadence);
                return row;
            }
            const name = document.createElement('a');
            if (/^https?:\/\//i.test(source.url)) name.href = source.url;
            name.textContent = source.composer + ' · ' + source.title;
            const excerpt = startQuarter == null ? '' : ' · ' + ui('début à la noire', 'start offset in quarter notes', 'موضع البداية بوحدة النوار') + ' ' + startQuarter;
            row.append(name, ' · ' + source.collection + ' · ' + source.part + ' · ' + ui('mes.', 'm.', 'مازورة') + ' ' + measure + ' · ' + ui('mesure source', 'source meter', 'الميزان الأصلي') + ' ' + sourceMeter + excerpt,
                document.createElement('br'), ui('Degrés', 'Steps', 'الدرجات') + ': ' + contour.join(' → ') +
                ' · ' + ui('Durées', 'Durations', 'المدد') + ': ' + rhythm.join(' + '));
            return row;
        }));
        field('composition').hidden = false;
        field('reroll').hidden = false;
        statusText.textContent = ui("Vos huit mesures sont prêtes.","Your eight measures are ready.","الموازير الثماني جاهزة.");

    } catch (error) {
        statusText.textContent = error.message;
    } finally {
        controls.forEach(control => { control.disabled = false; });
    }
};

field('catalog').ontoggle = async () => {
    if (!field('catalog').open || field('library-list').childElementCount) return;
    const status = field('library-count');
    try {
        const res = await fetch('/api/text-to-charpentier/library');
        if (!res.ok) throw Error();
        const {sources, shapes} = await res.json();
        status.textContent = sources.length + ' ' + ui('partitions', 'scores', 'مدونات') + ' · ' +
            shapes + ' ' + ui('motifs distincts', 'distinct patterns', 'أنماط متميزة');
        field('library-list').replaceChildren(...sources.map(source => {
            const row = document.createElement('li');
            const link = document.createElement('a');
            link.textContent = source.title;
            if (/^https?:\/\//i.test(source.url)) link.href = source.url;
            row.append(source.composer + ' · ', link, ' · ' + source.collection + ' · ' + source.part,
                document.createElement('br'), source.attribution + ' · ' + source.license);
            return row;
        }));
    } catch {
        status.textContent = ui('Catalogue indisponible.', 'Catalogue unavailable.', 'الفهرس غير متاح.');
    }
};
