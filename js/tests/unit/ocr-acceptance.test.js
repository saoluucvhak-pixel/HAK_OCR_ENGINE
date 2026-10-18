'use strict';
const { test } = require('node:test'), assert = require('node:assert/strict');
const { evaluate } = require('../../scripts/ocr-acceptance.cjs');
const cell = (extra = {}) => ({ row: 'anonymous-1', day: 1, expected: '0,5', read: '0.5', aligned: true, needsReview: false, ...extra });
const fixture = cells => ({ schema: 1, kind: 'synthetic', pages: [{ id: 'p1', group: 'g1', split: 'test', quality: 'clear', cells }] });
test('acceptance: decimals normalize, blank differs from zero, suggestion does not overwrite OCR', () => {
  const r = evaluate(fixture([cell(), cell({ day: 2, expected: '', read: '0', needsReview: true, suggestion: '' })]));
  assert.equal(r.correct, 1); assert.equal(r.manualReviewRate, 0.5); assert.equal(r.suggestionAccuracy, 1); assert.equal(r.acceptance, 'NOT_ACCEPTED');
});
test('acceptance: misplaced correct values are alignment failures and names never enter report', () => {
  const r = evaluate(fixture([cell({ row: 'private employee name', aligned: false, suggestion: '1' })]));
  assert.equal(r.alignmentErrors, 1); assert.equal(r.correct, 0); assert.equal(r.wrongSuggestions, 1);
  assert.ok(!JSON.stringify(r).includes('private employee name'));
});
test('acceptance: rejects duplicate cells, missing review status and document/writer leakage', () => {
  assert.throws(() => evaluate(fixture([cell(), cell()])));
  assert.throws(() => evaluate(fixture([cell({ needsReview: undefined })])));
  const placeholder = fixture([cell()]); placeholder.pages[0].group = 'SET_DOCUMENT_WRITER_GROUP';
  assert.throws(() => evaluate(placeholder));
  const f = fixture([cell()]); f.pages.push({ ...f.pages[0], id: 'p2', split: 'train' });
  assert.throws(() => evaluate(f), /leaks/);
});
test('acceptance: training pages excluded and empty set never passes', () => {
  const f = fixture([cell()]); f.pages[0].split = 'train'; const r = evaluate(f);
  assert.equal(r.cells, 0); assert.equal(r.accuracy, null); assert.equal(r.acceptance, 'NOT_ACCEPTED');
});
test('acceptance: large synthetic set cannot masquerade as signed real-document acceptance', () => {
  const f = { schema: 1, kind: 'synthetic', pages: Array.from({ length: 30 }, (_, i) => ({ id: 'p' + i, group: 'g' + i, split: 'test', quality: i ? 'clear' : 'hard', cells: Array.from({ length: 100 }, (_, j) => cell({ row: 'r' + j })) })) };
  assert.equal(evaluate(f).acceptance, 'NOT_ACCEPTED'); f.kind = 'real-private';
  assert.equal(evaluate(f).acceptance, 'READY_FOR_HUMAN_SIGNOFF');
});
