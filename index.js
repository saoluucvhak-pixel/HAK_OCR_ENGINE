"use strict";
module.exports={
 version:require('./package.json').version,
 documentReview:require('./js/core/timesheet-parse').documentReview,
 parseTable:require('./js/core/timesheet-parse').parse,
 analyze:require('./js/core/timesheet-ocr').analyze,
 grid:require('./js/core/table-grid'),
 rectify:require('./js/core/page-rectify').rectify,
 createOcrService:require('./js/main/ocr-service').createOcrService,
 sanitizeOcrItems:require('./js/main/ocr-service').sanitizeOcrItems
};
