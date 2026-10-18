"use strict";
const test=require('node:test'),assert=require('node:assert/strict'),P=require('../../core/timesheet-parse');
test('fingerprint form routes to mandatory review; name/date/time remain unapproved',()=>{
 const r=P.documentReview('GIẤY XÁC NHẬN VÂN TAY\nTôi tên là: Synthetic Person\n7h00 ngày 6/7/2026');
 assert.equal(r.kind,'FINGERPRINT_EXCEPTION');assert.equal(r.canAutoImport,false);assert.equal(r.requiresReview,true);
 assert.ok(r.candidates.some(c=>c.field==='name'));assert.ok(r.candidates.some(c=>c.value==='07:00'));
 assert.ok(r.candidates.every(c=>c.status==='PENDING_REVIEW'));
});
test('overtime slip preserves two times and does not compute paid hours',()=>{
 const r=P.documentReview('GIẤY XÁC NHẬN TĂNG CA\n28/7 11h30 13h00');assert.equal(r.kind,'OVERTIME_SLIP');
 assert.deepEqual(r.candidates.filter(c=>c.field==='time').map(c=>c.value),['11:30','13:00']);assert.equal(r.totalHours,undefined);
});
test('summary distinguished from individual slip; unknown stays unknown',()=>{
 assert.equal(P.documentReview('DANH SÁCH NHÂN VIÊN TĂNG CA THÁNG\nTổng giờ tăng ca').kind,'OVERTIME_SUMMARY');
 assert.equal(P.documentReview('random text').kind,'UNKNOWN');
});
test('invalid dates/times rejected; missing year is not invented; repeated tokens deduplicate',()=>{
 const r=P.documentReview('31/2/2026 29/2/2025 25h99 8h65\n28/7 28/7 23h10 01h20');
 assert.deepEqual(r.candidates.filter(c=>c.field==='date').map(c=>c.value),['28/7']);
 assert.deepEqual(r.candidates.filter(c=>c.field==='time').map(c=>c.value),['23:10','01:20']);
});
