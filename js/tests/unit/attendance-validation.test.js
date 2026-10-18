'use strict';
const test = require('node:test'), assert = require('node:assert/strict');
const V = require('../../core/ocr-learning/attendance-validation.js');
const page = overrides => Object.assign({ ky: '2026-02', mode: 'so', days: [1, 2], lines: [{ ma: 'NV1', kind: 'Công', vals: { 1: '0,5', 2: '0' } }] }, overrides);
const codes = result => result.issues.map(item => item.code);
test('shared OCR: blanks remain distinct from zero; source is immutable', () => {
  const p = page({ lines: [{ ma: 'NV1', kind: 'Công', vals: { 1: ' ', 2: '0' } }] }), before = JSON.stringify(p);
  const r = V.check(p); assert.deepEqual(r.summary, { numericCells: 1, blankCells: 1, invalidCells: 0, readSum: 0 });
  assert.equal(JSON.stringify(p), before); assert.equal(r.payrollReady, false);
});
test('shared OCR: strict month, leap year, duplicate and fractional day labels', () => {
  assert.equal(V.daysIn('2026-13'), 0); assert.equal(V.daysIn('2026-00'), 0); assert.equal(V.daysIn('2024-02'), 29);
  for (const days of [[1, 1], [1, '01'], [1, 1.5], [1, 30]]) assert.equal(V.check(page({ days })).layoutSuspect, true);
});
test('shared OCR: extra values outside the identified grid block learning', () => {
  const r = V.check(page({ lines: [{ ma: 'NV1', kind: 'Công', vals: { 1: '1', 3: '2' } }] }));
  assert.ok(codes(r).includes('O_NGOAI_BO_CUC')); assert.equal(r.layoutSuspect, true);
});
test('shared OCR: both duplicate employee rows need review', () => {
  const r = V.check(page({ lines: [page().lines[0], page().lines[0]] }));
  assert.deepEqual(r.issues.filter(x => x.code === 'TRUNG_NV').map(x => x.line).sort(), [0, 1]);
});
test('shared OCR: reject ambiguous numeric strings instead of Number coercion', () => {
  for (const value of ['0x10', '1e2', 'Infinity', '1,2,3', 'x']) assert.ok(Number.isNaN(V.number(value)));
  assert.equal(V.number('0,5'), 0.5); assert.equal(V.number('0'), 0); assert.equal(V.number('   '), null);
});
test('shared OCR: negative shift hours are errors, positive shift hours are not work-day warnings', () => {
  assert.ok(codes(V.check(page({ mode: 'ca', lines: [{ ma: 'NV1', kind: 'Công', vals: { 1: '-1', 2: '8' } }] }))).includes('GIA_TRI_AM'));
  assert.equal(V.check(page({ mode: 'ca', lines: [{ ma: 'NV1', kind: 'Công', vals: { 1: '8' } }] })).warns, 0);
});
test('shared OCR: zero paper total is checked and invalid computed totals are errors', () => {
  const p = page(); p.lines[0].src = { totals: { cong: 0 } };
  assert.ok(codes(V.check(p, { sumOf: () => 0.5 })).includes('LECH_TONG_DONG'));
  assert.ok(codes(V.check(p, { sumOf: () => NaN })).includes('TONG_TINH_KHONG_HOP_LE'));
});
test('shared OCR: unknown employee and bad glyphs do not receive silent approval', () => {
  const r = V.check(page({ lines: [{ ma: 'UNKNOWN', kind: 'Công', vals: { 1: '?' } }] }), { maSet: { NV1: true } });
  assert.ok(codes(r).includes('MA_NV_LA')); assert.ok(codes(r).includes('O_KHONG_PHAI_SO')); assert.equal(r.payrollReady, false);
});
