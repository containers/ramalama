'use strict';

var callBind = require('call-bind');
var gOPD = require('gopd');

// eslint-disable-next-line no-extra-parens, no-proto
var hasProto = /** @type {{ __proto__?: typeof Array.prototype }} */ ([]).__proto__ === Array.prototype;

// eslint-disable-next-line no-extra-parens
var dunderGetter = hasProto && gOPD && gOPD(Object.prototype, /** @type {keyof typeof Object.prototype} */ ('__proto__'));

module.exports = dunderGetter && dunderGetter.get && callBind(dunderGetter.get);
