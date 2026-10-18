'use strict';
const { test } = require('node:test'), assert = require('node:assert/strict');
const P = require('../../core/timesheet-parse.js');
function grid(rows, widths, text) {
  const out=[];
  for(let r=0;r<rows;r++){let x=0;for(let c=0;c<widths.length;c++){const t=text(r,c);out.push({x0:x,x1:x+widths[c],y0:r*32,y1:r*32+30,cx:x+widths[c]/2,cy:r*32+15,text:t,num:/^\d+(?:[.,]\d+)?$/.test(t)?Number(t.replace(',','.')):null,conf:90});x+=widths[c]+2;}}
  return out;
}
test('layout: serial-number overtime summary never becomes calendar attendance',()=>{
  const result=P.parse(grid(18,[50,200,100,150,150],(r,c)=>r===0?['STT','Họ tên','Bộ phận','Tổng giờ tăng ca','Xác nhận'][c]:c===0?String(r):c===3&&r===1?'12,5':''));
  assert.equal(result.layout,null);assert.equal(result.lines.length,0);
});
test('layout: nonconsecutive explicit dates are retained with a nearby name header',()=>{
  const days=[5,6,7,8,9,21,22,23,24,25,26];
  const result=P.parse(grid(3,[200,...days.map(()=>40),70],(r,c)=>r===0?c===0?'Họ tên':c<=days.length?String(days[c-1]):'Tổng công':c===0?'Synthetic Person '+r:c<=days.length?'1':'11'));
  assert.equal(result.layout,'A');assert.deepEqual(result.days,days);assert.equal(result.lines[0].values[10],undefined);assert.equal(result.lines[0].values[21],1);
});
test('layout: five numbered fields without name-header evidence remain unsupported',()=>{
  const result=P.parse(grid(3,[40,40,40,40,40],(r,c)=>r===0?String(c+1):''));
  assert.equal(result.layout,null);
});
