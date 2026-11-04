// How a page is read (/pipeline, 2026-10-30): the stages, their timing, their one-sentence captions and the colour
// of every role. Facts as in docs/overview.md, experiment 43's README and the technical documentation (sections 2,
// 4, 6, 7). Calm palette (the owner's rules of thumb): teal / indigo / green accents on light ground; orange only for
// "needs you", red only for problems.

export type StageKey = 'scan' | 'azure' | 'gemini' | 'rules' | 'judge' | 'platform' | 'index';

export const STAGES: { key: StageKey; n: number; title: string; short: string; ms: number; caption: string; detail: string }[] = [
  { key: 'scan', n: 1, title: 'The scan', short: 'Scan', ms: 4000,
    caption: 'Everything starts from the page as Mandumah scanned it, and every value we extract points back to this image.',
    detail: 'The page image comes from Mandumah\'s S3 archive (1,013,912 documents with a PDF and Azure\'s OCR). Nothing printed on it is ever overwritten.' },
  { key: 'azure', n: 2, title: 'Azure reads the words', short: 'Azure OCR', ms: 7500,
    caption: 'Azure\'s OCR finds every word and its box. We number each line, page:line, so the next step can name it.',
    detail: 'Azure\'s reading is already in the archive. It is the text: from here on, nobody retypes a word.' },
  { key: 'gemini', n: 3, title: 'Gemini says what each line is', short: 'Gemini', ms: 11000,
    caption: 'Gemini doesn\'t retype anything. It only says what each numbered line is, and in what order to read them.',
    detail: 'Gemini 4 Argon (prompt v3.5b) sees the page image and Azure\'s numbered lines, and answers in line ids only. Every value it gives is a line id, a word from a closed list, or an exact copy of Azure\'s text (D30).' },
  { key: 'rules', n: 4, title: 'Code builds the article', short: 'Code rules', ms: 8000,
    caption: 'Code builds the blocks, repairs only what is safe, keeps running heads out of the text, and raises flags.',
    detail: 'Everything decidable by code is decided by code, the same way every time. The result is two master files per article, JATS 1.4 (the article) and ALTO 4.4 (every word on the page), checked against their official schemas on every build.' },
  { key: 'judge', n: 5, title: 'A second look', short: 'Judge', ms: 5500,
    caption: 'Pages with flags get a second look from a judge model. It never changes a word itself: it can only propose a patch.',
    detail: 'A patch is applied only with two keys: confidence of at least 0.85 and a check in code against the scan and Azure. Patches are logged and reversible; a person\'s patch outranks the judge\'s (D34).' },
  { key: 'platform', n: 6, title: 'Into the platform', short: 'Fields & ids', ms: 14000,
    caption: 'Each field leaves the page with its ink, then joins a record with a permanent id: a person, an institution, a cited work, a journal.',
    detail: 'What is printed stays a mention, tied to the ink by its Azure word numbers. The entities above it carry ids that never break: A… persons, I… institutions, C… cited works, J… journals.' },
  { key: 'index', n: 7, title: 'In the index', short: 'Index', ms: 9000,
    caption: 'The article takes its place in the index: who wrote it, where they work, what it cites, and who cites it.',
    detail: 'Counts such as times cited are never stored on a record: they are computed fresh from the links at every release.' },
];

export const SPEEDS = [0.5, 1, 1.5, 2];

// role → colour (fill and stroke on the scan, the dot in the legend)
export const ROLE_COLOR: Record<string, string> = {
  title: '#4338ca',          // indigo
  byline: '#0f766e',         // teal
  abstract: '#0369a1',       // sky
  keywords: '#0e7490',       // cyan
  heading: '#7c3aed',        // violet
  paragraph: '#15803d',      // green
  list: '#4d7c0f',           // olive
  quote: '#65a30d',
  verse: '#65a30d',
  footnote: '#a21caf',       // plum
  reference: '#0891b2',      // cyan
  table: '#2563eb',          // blue
  caption: '#1d4ed8',
  figure: '#475569',
  running: '#94a3b8',        // grey: page furniture
  page_number: '#94a3b8',
  noise: '#cbd5e1',
  other_article: '#cbd5e1',
  note_call: '#a21caf',
};
export const roleColor = (r?: string | null) => ROLE_COLOR[r || ''] || '#64748b';

// field kind → card title and colour
export const FIELD_KIND: Record<string, { title: string; color: string }> = {
  title: { title: 'Title', color: ROLE_COLOR.title },
  author: { title: 'Authors', color: ROLE_COLOR.byline },
  affiliation: { title: 'Affiliations', color: '#0d9488' },
  abstract: { title: 'Abstract', color: ROLE_COLOR.abstract },
  keywords: { title: 'Keywords', color: ROLE_COLOR.keywords },
  heading: { title: 'Headings', color: ROLE_COLOR.heading },
  footnote: { title: 'Footnotes', color: ROLE_COLOR.footnote },
  table: { title: 'Tables', color: ROLE_COLOR.table },
  reference: { title: 'References', color: ROLE_COLOR.reference },
  figure: { title: 'Figures', color: ROLE_COLOR.figure },
};
export const KIND_ORDER = ['title', 'author', 'affiliation', 'abstract', 'keywords', 'heading', 'footnote', 'table', 'figure', 'reference'];

export const ENTITY_KIND: Record<string, { label: string; color: string; bg: string }> = {
  person: { label: 'Person', color: '#0f766e', bg: '#f0fdfa' },
  institution: { label: 'Institution', color: '#0d9488', bg: '#f0fdfa' },
  work: { label: 'Cited work', color: '#0891b2', bg: '#ecfeff' },
  journal: { label: 'Journal', color: '#4338ca', bg: '#eef2ff' },
  publication: { label: 'This article', color: '#4338ca', bg: '#eef2ff' },
};

export const PART_LABEL: Record<string, string> = {
  position: 'position', faculty: 'faculty', department: 'department', organisation: 'organisation', city: 'city',
  country: 'country', author: 'author', title: 'title', source: 'in', year: 'year', publisher: 'publisher', place: 'place',
};

export const DEFAULT_STEM = '0130-018-072-003';

export type Box = { x: number; y: number; w: number; h: number };
