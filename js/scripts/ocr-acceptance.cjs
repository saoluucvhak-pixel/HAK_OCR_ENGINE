'use strict';
// Private input stays local. The report contains aggregate counts only.
const fs = require('node:fs');
const normalize = value => String(value == null ? '' : value).trim().replace('.', ',');
function evaluate(input) {
  if (!input || input.schema !== 1 || !Array.isArray(input.pages)) throw Error('Expected schema 1 and pages array');
  const ids = new Set(), groups = new Map();
  let total = 0, correct = 0, review = 0, wrongSuggestions = 0, suggestions = 0, alignmentErrors = 0, clear = 0, clearCorrect = 0;
  let testPages = 0; const counts = {};
  for (const page of input.pages) {
    if (!page.id || ids.has(page.id) || !page.group || !['train', 'validation', 'test'].includes(page.split) || !['clear', 'hard'].includes(page.quality) || !Array.isArray(page.cells)) throw Error('Invalid page metadata or duplicate page');
    ids.add(page.id);
    if (groups.has(page.group) && groups.get(page.group) !== page.split) throw Error('Document/writer group leaks across splits');
    groups.set(page.group, page.split);
    const keys = new Set();
    for (const cell of page.cells) {
      const key = cell.row + ':' + cell.day;
      if (typeof cell.row !== 'string' || !cell.row || !Number.isInteger(cell.day) || cell.day < 1 || cell.day > 31 || keys.has(key) || typeof cell.expected !== 'string' || typeof cell.read !== 'string' || typeof cell.needsReview !== 'boolean' || typeof cell.aligned !== 'boolean') throw Error('Invalid cell or duplicate row/day');
      keys.add(key);
      if (page.split !== 'test') continue;
      total++;
      const match = normalize(cell.read) === normalize(cell.expected);
      if (match && cell.aligned) correct++;
      if (!cell.aligned) alignmentErrors++;
      if (cell.needsReview) review++;
      if (page.quality === 'clear') { clear++; if (match && cell.aligned) clearCorrect++; }
      if (cell.suggestion != null) { if (typeof cell.suggestion !== 'string') throw Error('Invalid suggestion'); suggestions++; if (normalize(cell.suggestion) !== normalize(cell.expected) || !cell.aligned) wrongSuggestions++; }
    }
    if (page.split === 'test') { testPages++; counts[page.quality] = (counts[page.quality] || 0) + 1; }
  }
  const enough = testPages >= 30 && total >= 3000 && clear > 0 && (counts.hard || 0) > 0;
  return { schema: 1, kind: input.kind === 'real-private' ? 'real-private' : 'synthetic', testPages, cells: total, correct, accuracy: total ? correct / total : null,
    clearCells: clear, clearAccuracy: clear ? clearCorrect / clear : null, alignmentErrors, manualReviewCells: review, manualReviewRate: total ? review / total : null,
    suggestions, wrongSuggestions, suggestionAccuracy: suggestions ? (suggestions - wrongSuggestions) / suggestions : null,
    acceptance: input.kind === 'real-private' && enough && alignmentErrors === 0 && clearCorrect / clear >= 0.99 ? 'READY_FOR_HUMAN_SIGNOFF' : 'NOT_ACCEPTED',
    reasons: [input.kind !== 'real-private' && 'No private real-document evidence', !enough && 'Need >=30 test pages, >=3000 cells, clear and hard pages', alignmentErrors > 0 && 'Row/day alignment errors', clear > 0 && clearCorrect / clear < 0.99 && 'Clear-cell accuracy below 99%'].filter(Boolean),
    note: 'No automatic signoff. Operator, offline Windows, import preview and payroll regression checks remain required. Review rate and suggestion errors require human assessment.' };
}
if (require.main === module) {
  try {
    const [source, target] = process.argv.slice(2);
    if (!source || !target) throw Error('Usage: node scripts/ocr-acceptance.cjs PRIVATE_INPUT.json AGGREGATE_REPORT.json');
    const report = evaluate(JSON.parse(fs.readFileSync(source, 'utf8')));
    fs.writeFileSync(target, JSON.stringify(report, null, 2) + '\n');
    console.log('OCR acceptance: ' + report.acceptance + '; ' + report.correct + '/' + report.cells + ' cells; report written locally');
    process.exitCode = report.acceptance === 'READY_FOR_HUMAN_SIGNOFF' ? 0 : 2;
  } catch (error) { console.error('OCR acceptance input rejected: ' + error.message); process.exitCode = 1; }
}
module.exports = { evaluate };
