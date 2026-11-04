// Nothing lost (/audit, 2026-11-02): names and colours shared by the corpus view and the article flow.
// Colours: teal / indigo / green for what landed in a field, grey for ink that is not article text, red only for
// what fell through, orange only for what needs the owner (a prompt addition before gate 2).

export const KIND: Record<string, { label: string; short: string; color: string; note: string }> = {
  mapping: { label: 'Our code dropped it', short: 'code', color: '#dc2626',
    note: 'Gemini returned it; the code dropped or flattened it. Free to fix: rebuild from the saved answers.' },
  gemini_missed: { label: 'Gemini missed it', short: 'missed', color: '#f87171',
    note: 'The prompt asks for it, it is printed, and Gemini did not return it.' },
  not_asked: { label: 'Not asked for', short: 'not asked', color: '#f59e0b',
    note: 'No prompt version asks for it: it must go into the prompt before gate 2.' },
};
export const KIND_ORDER = ['mapping', 'gemini_missed', 'not_asked'];

export const STORED = '#0f766e';      // teal: landed in its own field
export const GREY = '#c4c9cf';        // not article text (running heads, page numbers, noise)
export const RED = '#dc2626';

export const FIELD: Record<string, string> = {
  position: "Author's post / rank", affiliation: 'Affiliation', author_name: 'Author name', email: 'E-mail',
  honorific: 'Honorific before a name', history_date: 'History dates', abstract: 'Abstract', keywords: 'Keywords',
  article_doi: "The article's own DOI", license: 'Licence / copyright', journal_info: 'Journal / volume / issue line',
  journal_section: 'Journal section (rubric)', other: 'Body text typed «other»', unclassified: 'Unclassified text',
  signature: 'Closing signature / place and date', phone_address: 'Phone / postal address', doi_url: 'Web address',
  funding_ack: 'Funding / thanks', author_id: 'ORCID / researcher id', corresp: 'Corresponding-author mark',
  date: 'A date (event, writing)', title: 'Title', trans_title: 'Translated title', subtitle: 'Subtitle',
  conference: 'Conference', author_note: 'Author note', role: 'Role phrase (by, prepared by)', table_note: 'Table note / source',
  paragraph: 'Paragraph', heading: 'Heading', footnote: 'Footnote', endnote: 'Endnote', reference: 'Reference',
  table_cell: 'Table cell', list_item: 'List item', caption: 'Caption', verse: 'Verse', quote: 'Quotation',
  abstract_label: 'Abstract heading', equation: 'Equation', figure_text: 'Text in a figure', boxed_text: 'Boxed text',
  appendix: 'Appendix', acknowledgements: 'Acknowledgements', table_note_: 'Table note', figure_note: 'Figure note',
  label: 'Label of a field', paragraph_added: 'Line Azure missed', pub_date: 'Publication date', reviewed_work: 'Reviewed book',
  thesis: 'Thesis', original: 'Original of a translation',
  'generic text': 'Fell through: generic text', nowhere: 'Fell through: nowhere', 'not article text': 'Not article text',
};
export const fieldLabel = (f?: string | null) => (f ? FIELD[f] || f.replace(/_/g, ' ') : '—');

export const GEMINI: Record<string, string> = {
  paragraph: 'Paragraph', heading: 'Heading', table: 'Table', reference: 'Reference', footnote: 'Footnote',
  endnote: 'Endnote', header: 'Running head', footer: 'Running foot', abstract: 'Abstract', byline: 'Byline',
  title: 'Title', 'title (translated)': 'Translated title', caption: 'Caption', list_item: 'List item', verse: 'Verse',
  quote: 'Quotation', figure: 'Figure', equation: 'Equation', keywords: 'Keywords', other: 'Other',
  other_article: 'Another article', noise: 'Noise', 'not placed': 'Not placed', boxed: 'Boxed text',
};
export const geminiLabel = (g: string) => GEMINI[g] || g;

export const PLATFORM: Record<string, string> = {
  'blocks (generic)': 'text, generic only', nowhere: 'nowhere', page_regions: 'page regions (not text)',
  blocks: 'text blocks', table_cells: 'table cells', citation_mentions: 'references', 'figures.caption': 'figure captions',
  sections: 'sections', notes: 'notes', authorships: 'authors', affiliation_mentions: 'affiliations',
  byline_mentions: 'bylines', metadata_assertions: 'metadata',
};
// plain names for the platform's tables (experiment 73); an unknown one keeps its name, underscores as spaces
export const platLabel = (p: string) => PLATFORM[p] || p.replace(/_/g, ' ');
