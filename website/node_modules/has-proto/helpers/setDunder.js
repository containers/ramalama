'use strict';

var callBind = require('call-bind');
var gOPD = require('gopd');

// @ts-expect-error TS can't handle dunder proto
var desc = gOPD && gOPD(Object.prototype, '__proto__');

module.exports = !!desc && !!desc.set && callBind(desc.set);
