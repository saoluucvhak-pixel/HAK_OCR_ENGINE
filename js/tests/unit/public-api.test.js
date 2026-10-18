"use strict";
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
test('public engine entry point loads without the payroll app or Tesseract installed',()=>{
 const api=require('../../..');assert.equal(typeof api.analyze,'function');assert.equal(typeof api.grid.findCells,'function');assert.equal(api.documentReview('GIẤY XÁC NHẬN VÂN TAY').canAutoImport,false);
});
test('browser modules load in documented order and expose the same form review contract',()=>{
 const context={Uint8Array,Uint8ClampedArray,Uint32Array,Int32Array,Float32Array};context.window=context;vm.createContext(context);
 for(const file of ['table-grid.js','timesheet-parse.js','timesheet-ocr.js'])vm.runInContext(fs.readFileSync(path.resolve(__dirname,'../../core',file),'utf8'),context);
 assert.equal(typeof context.HAKCore.tsocr.analyze,'function');const r=context.HAKCore.tsparse.documentReview('GIẤY XÁC NHẬN TĂNG CA\n7h');assert.equal(r.candidates[0].value,'07:00');assert.equal(r.canAutoImport,false);
});
