"use strict";
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const root=path.resolve(__dirname,'../..'),dest=path.join(root,'dist','HAK_OCR_ENGINE');
const files=['index.js','package.json','README.md','DOCUMENT_REVIEW.md','HANDWRITTEN_DIGITS.md',
'js/core/table-grid.js','js/core/page-rectify.js','js/core/timesheet-ocr.js','js/core/timesheet-parse.js','js/core/ocr-learning/attendance-validation.js',
'js/main/ocr-service.js','js/main/handwritten-digits.js','js/ocr/models/mnist-cnn.json','js/ocr/models/NOTICE.md'];
fs.mkdirSync(dest,{recursive:true});const entries=[];
for(const file of files){const bytes=fs.readFileSync(path.join(root,file)),out=path.join(dest,file);fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,bytes);entries.push({path:file,size:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex')});}
const manifest={format:'HAK_OCR_DISTRIBUTION',version:require(path.join(root,'package.json')).version,files:entries,hostRequirements:['tesseract.js 5.1.1 for image recognition','ocr/worker.js and offline vie/eng tessdata assets supplied by host; see README'],safety:{autoImport:false,formFieldsRequireReview:true}};
fs.writeFileSync(path.join(dest,'manifest.json'),JSON.stringify(manifest,null,2)+'\n');
// The distribution must load on its own, with no dependency on the payroll checkout.
const api=require(path.join(dest,'index.js'));
if(api.documentReview('GIẤY XÁC NHẬN VÂN TAY').kind!=='FINGERPRINT_EXCEPTION')throw Error('Distribution smoke test failed');
console.log('PASS standalone distribution '+api.version+' ('+entries.length+' files)');
