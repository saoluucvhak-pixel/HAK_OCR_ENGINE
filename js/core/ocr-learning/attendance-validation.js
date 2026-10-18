// HAK shared attendance validation. Pure, offline; never fills cells or approves payroll.
(function (root) {
  'use strict';
  function number(value) {
    var text = String(value == null ? '' : value).trim();
    if (!text) return null;
    if (!/^[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)$/.test(text)) return NaN;
    var result = Number(text.replace(',', '.'));
    return isFinite(result) ? result : NaN;
  }
  function daysIn(period) {
    var match = /^(\d{4})-(0[1-9]|1[0-2])$/.exec(String(period || ''));
    if (!match || +match[1] < 1900 || +match[1] > 9999) return 0;
    return new Date(+match[1], +match[2], 0).getDate();
  }
  function check(page, opts) {
    page = page || {}; opts = opts || {};
    var issues = [], dim = daysIn(page.ky), labels = Object.create(null), seen = Object.create(null);
    var normal = !page.mode || page.mode === 'so', maximum = opts.maxPerDay == null ? 3 : opts.maxPerDay;
    var summary = { numericCells: 0, blankCells: 0, invalidCells: 0, readSum: 0 };
    function add(level, code, line, day, msg, struct) { issues.push({ level: level, code: code, line: line, day: day == null ? null : day, msg: msg, struct: !!struct }); }
    function validDay(day) { return /^\d+$/.test(String(day)) && Number.isInteger(+day) && +day >= 1 && +day <= dim; }
    if (!dim) add('ERROR', 'KY_SAI', null, null, 'Kỳ của trang không hợp lệ (cần YYYY-MM, tháng 01–12)', true);
    if (!(page.days || []).length) add('ERROR', 'KHONG_COT_NGAY', null, null, 'Không có cột ngày để đối chiếu', true);
    (page.days || []).forEach(function (day) {
      if (dim && !validDay(day)) add('ERROR', 'NGAY_NGOAI_KY', null, day, 'Cột ngày ' + day + ' không có trong tháng ' + page.ky, true);
      var key = String(+day);
      if (labels[key]) add('ERROR', 'TRUNG_COT_NGAY', null, day, 'Trùng cột ngày ' + day + ' — cần kiểm tra bố cục', true);
      labels[key] = true;
    });
    if (!(page.lines || []).length) add('ERROR', 'KHONG_DONG', null, null, 'Không có dòng nào', true);
    (page.lines || []).forEach(function (line, index) {
      if (!line.kind) return;
      var values = line.vals || {};
      if (!line.ma) add('WARN', 'CHUA_CHON_NV', index, null, 'Dòng ' + (index + 1) + ' chưa chọn nhân viên');
      else {
        if (opts.maSet && !Object.prototype.hasOwnProperty.call(opts.maSet, line.ma)) add('ERROR', 'MA_NV_LA', index, null, 'Mã NV ' + line.ma + ' không có trong danh mục');
        var key = line.ma + '|' + line.kind;
        if (seen[key] != null) {
          add('ERROR', 'TRUNG_NV', index, null, 'Mã NV ' + line.ma + ' (' + line.kind + ') trùng dòng ' + (seen[key] + 1));
          add('ERROR', 'TRUNG_NV', seen[key], null, 'Mã NV ' + line.ma + ' có nhiều dòng cùng loại — cần đối chiếu');
        } else seen[key] = index;
      }
      Object.keys(values).forEach(function (day) {
        var value = number(values[day]);
        if (dim && (!validDay(day) || !labels[String(+day)])) add('ERROR', 'O_NGOAI_BO_CUC', index, +day, 'Ô ngày ' + day + ' không thuộc bố cục đã nhận diện', true);
        if (value !== null && isNaN(value)) add('ERROR', 'O_KHONG_PHAI_SO', index, +day, 'Dòng ' + (index + 1) + ' ngày ' + day + ': "' + values[day] + '" không phải số hợp lệ');
        else if (value !== null && value < 0) add('ERROR', 'GIA_TRI_AM', index, +day, 'Dòng ' + (index + 1) + ' ngày ' + day + ': giá trị âm chưa được phép ghi');
        else if (normal && value !== null && value > maximum) add('WARN', 'CONG_NGOAI_KHOANG', index, +day, 'Dòng ' + (index + 1) + ' ngày ' + day + ': ' + value + ' công ngoài khoảng 0–' + maximum);
      });
      (page.days || []).forEach(function (day) {
        var value = number(values[day]);
        if (value === null) summary.blankCells++;
        else if (isNaN(value)) summary.invalidCells++;
        else { summary.numericCells++; summary.readSum += value; }
      });
      var totals = line.src && line.src.totals || {};
      Object.keys(totals).forEach(function (name) {
        var total = number(totals[name]);
        if (total !== null && isNaN(total)) add('WARN', 'TONG_KHONG_PHAI_SO', index, null, 'Dòng ' + (index + 1) + ': tổng trên giấy chưa đọc được');
      });
      // Existing callers choose how to sum work/shift cells. Keep their semantics.
      var total = Object.keys(totals).map(function (key) { return number(totals[key]); }).filter(function (value) { return value !== null && !isNaN(value); })[0];
      if (total != null && opts.sumOf) {
        var sum = opts.sumOf(line);
        if (!Number.isFinite(sum)) add('ERROR', 'TONG_TINH_KHONG_HOP_LE', index, null, 'Không đối chiếu được tổng dòng ' + (index + 1));
        else if (Math.abs(sum - total) > 0.01) add('WARN', 'LECH_TONG_DONG', index, null, 'Dòng ' + (index + 1) + ': tổng tính ' + sum + ' ≠ tổng trên giấy ' + total);
      }
    });
    summary.readSum = Math.round(summary.readSum * 10000) / 10000;
    return { issues: issues, errors: issues.filter(function (item) { return item.level === 'ERROR'; }).length, warns: issues.filter(function (item) { return item.level === 'WARN'; }).length, layoutSuspect: issues.some(function (item) { return item.struct; }), summary: summary, payrollReady: false };
  }
  var API = { check: check, daysIn: daysIn, number: number, version: '1.1.0' };
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
  else { root.HAKCore = root.HAKCore || {}; root.HAKCore.ocrRules = API; }
})(typeof self !== 'undefined' ? self : this);
