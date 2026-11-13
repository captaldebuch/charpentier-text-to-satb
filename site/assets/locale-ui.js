// Shared by the composition and arrangement forms.
const uiLanguage = document.documentElement.lang;
function ui(fr, en, ar) {
    return ({en, ar})[uiLanguage] ?? fr;
}
const ensembleNames = [
    ['violon','violins?','كمانات|كمانين|كمان'],
    ['alto','violas?','فيولات|فيولا'],
    ['violoncelle','cellos?','تشيلوهات|تشيلو'],
    ['contrebasse','double bass(?:es)?','كونترباص'],
    ['flûte','flutes?','آلات فلوت|فلوت'],
    ['hautbois','oboes?','أوبوا'],
    ['clarinette','clarinets?','كلارينيت'],
    ['basson','bassoons?','فاغوت'],
    ['cor','(?:french )?horns?','هورن|كورنو'],
    ['trompette','trumpets?','آلات ترومبيت|ترومبيت|أبواق|بوق'],
    ['trombone','trombones?','ترومبون'],
    ['piano','pianos?','بيانو']
];
function requestEnsemble(text) {
    if (uiLanguage === 'fr') return text;
    let target = text.toLowerCase().replace(/[٠-٩]/g, c => '٠١٢٣٤٥٦٧٨٩'.indexOf(c))
        .replace(/[\u064b-\u065f\u0670]/g, '').trim();
    if (/^(?:a |for (?:a )?)?string quartet$|^رباعي وتري$/.test(target)) return 'quatuor à cordes';
    if (/^(?:a |for (?:a )?)?wind quartet$|^رباعي (?:هوائي|نفخي)$/.test(target)) return 'quatuor à vents';
    target = target.replace(/^(?:(?:i (?:would like|want) (?:an arrangement )?)?for |لـ)/,'')
        .replace(/\band\b|،|\s+و\s*/g, ',')
        .replace(/\b(one|a|an|two|three|four)\b/g, s=>({one:1,a:1,an:1,two:2,three:3,four:4})[s])
        .replace(/ثلاث(?:ة)?|أربع(?:ة)?|اثنان|اثنين|واحد(?:ة)?/g,s=>s.startsWith('ثلاث')?3:s.startsWith('أربع')?4:s.startsWith('اثن')?2:1);
    return target.split(/[,;+]/).map(s => {
        s = s.trim();
        if (s === 'كمانين') return '2 violon';
        for (const [fr,en,ar] of ensembleNames) {
            const match = s.match(new RegExp('^(?:(\\d+)\\s+)?(?:'+en+'|'+ar+')$'));
            if (match) return (match[1] || 1) + ' ' + fr;
        }
        return s;
    }).join(', ');
}
