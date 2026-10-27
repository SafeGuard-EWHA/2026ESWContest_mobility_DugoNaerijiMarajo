// Render the actual UI script with a minimal DOM; no browser or npm dependency.
// Run: node tests/test_dashboard_render.js
"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const nodes = new Map();
function node(tagName = "div") {
  return {
    tagName, textContent: "", className: "", style: {}, attributes: {}, children: [],
    setAttribute(name, value) { this.attributes[name] = value; },
    replaceChildren(...children) { this.children = children; },
    appendChild(child) { this.children.push(child); },
    append(...children) { this.children.push(...children); },
    addEventListener() {},
  };
}
const context = vm.createContext({
  document: {
    getElementById(id) {
      if (!nodes.has(id)) nodes.set(id, node());
      return nodes.get(id);
    },
    createElementNS(namespace, tagName) { return node(tagName); },
    createElement(tagName) { return node(tagName); },
  },
});
const page = fs.readFileSync(path.join(__dirname, "../scripts/dashboard.html"), "utf8");
const script = page.match(/<script>([\s\S]*?)<\/script>/)[1];
assert.match(script, /\brefresh\(\);\s*$/);
vm.runInContext(script.replace(/\brefresh\(\);\s*$/, ""), context);
const text = id => nodes.get(id).textContent;
const curve = [{t_s: 0, temp_c: 23}, {t_s: 300, temp_c: 24}];
const thermal = {valid: true, t35_s: null, reason: "no_reach_within_horizon", curve};

context.render({thermal});
assert.equal(text("thermalReady"), "예측 유효");
assert.equal(text("t35"), "예측 범위 내 미도달");
assert.equal(text("riskThresholdTitle"), "35°C 도달 예상 시간 · 모델 계산");
assert.ok(nodes.get("curve").children.some(child => child.textContent === "35°C"));

// Only the configured threshold changes: the existing curve must redraw too.
context.render({thermal, thresholds: {risk_temp_c: 37.5}});
assert.equal(text("riskThresholdTitle"), "37.5°C 도달 예상 시간 · 모델 계산");
assert.ok(nodes.get("curve").children.some(child => child.textContent === "37.5°C"));
assert.ok(!nodes.get("curve").children.some(child => child.textContent === "35°C"));

context.render({thermal: {...thermal, t35_s: 120}});
assert.equal(text("t35"), "120.0초 (2.0분)");
context.render({thermal: {...thermal, t35_s: 0}});
assert.equal(text("t35"), "0초 · 모델 계산");
context.render({thermal: {...thermal, valid: false}});
assert.equal(text("t35"), "WAITING");
assert.ok(!nodes.get("curve").children.some(child => child.tagName === "polyline"));
context.render({});
assert.equal(text("t35"), "WAITING");
console.log("PASS: forecast non-crossing, configured threshold redraw, valid crossing, invalid/missing prediction.");

const research={enabled:true,model:"literature_tau_observed_trend_v1",valid:false,reason:"warming_up",history_s:120,curve:[],t35_s:null,scenario:{valid:true,curve}};
context.render({thermal_observer:research});
assert.match(text("t35"), /120 \/ 600초/);
assert.match(text("riskThresholdTitle"), /현재 환경 예측 아님/);
assert.match(text("thermalResearchNote"), /자동 출력에 사용하지 않음/);
assert.ok(nodes.get("curve").children.some(child=>child.tagName==="polyline"));
context.render({thermal_observer:{...research,valid:true,reason:"estimated_crossing",t35_s:120,curve,ambient_in_study_range:false}});
assert.equal(text("t35"),"2.0분 · 연구용 추정");
assert.match(text("thermalResearchNote"), /원 연구 범위 밖/);
context.render({thermal_observer:{...research,reason:"temperature_invalid",scenario:{valid:false},curve:[]}});
assert.match(text("t35"),/온도 입력 끊김/);
assert.ok(!nodes.get("curve").children.some(child=>child.tagName==="polyline"));
context.render({thermal_observer:{...research,reason:"fan_active_or_feedback_unknown",scenario:{valid:false}}});
assert.match(text("t35"),/예측 중단/);
console.log("PASS: research label, conditional scenario, warmup, ETA, winter, stale curve removal, fan withholding");
