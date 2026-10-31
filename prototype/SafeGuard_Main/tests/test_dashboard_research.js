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

context.render({thermal_observer:{enabled:true,model:"literature_tau_observed_trend_v1",control_enabled:true,valid:true,t35_s:51,curve,history_s:600}});
assert.match(text("thermalReady"), /선제 보호 제어/);
assert.match(text("thermalResearchNote"), /자동 출력/);
assert.doesNotMatch(text("thermalResearchNote"), /자동 출력에 사용하지 않음/);
console.log("PASS: enabled predictive control label");

context.render({thermal_observer:{enabled:true,model:"ambient_heat_balance_observer_v2",control_enabled:true,valid:false,reason:"ambient_invalid",history_s:0}});
assert.equal(nodes.get("thermalResearchNote").hidden,false);
assert.match(text("thermalResearchNote"), /실내·외기온/);
assert.match(text("thermalResearchNote"), /차량 정확도 미검증/);
assert.match(text("t35"), /위치·외기온 입력 사용 불가/);
context.render({thermal_observer:{enabled:true,model:"ambient_heat_balance_observer_v2",control_enabled:true,valid:false,reason:"warming_up",history_s:100}});
assert.match(text("t35"), /100 \/ 600초/);
console.log("PASS: ambient heat-balance model label, missing ambient and warmup");

vm.runInContext('online=true',context);
context.render({profile:'CONNECTION_CHECK',mode:'CONNECTION_CHECK',read_only:true,
  manual_control:{enabled:true,resume_available:true},
  thermal_observer:{enabled:true,model:'ambient_heat_balance_observer_v2',valid:false,reason:'hardware_not_connected'}});
assert.match(text('profile'),/접속 점검/);
assert.match(text('t35'),/실내 센서 미연결/);
for(const id of ['stopButton','resumeButton','clearButton','rearmButton'])assert.equal(nodes.get(id).disabled,true);
console.log('PASS: connection-only label and all hardware controls disabled');

// A Pi-based update must retain the mmWave panel already published by the team.
for(const id of ['mmwaveSource','mmwaveEvidence','mmwaveKind','mmwaveHealth','mmwaveProcessing'])
  assert.ok(page.includes(`id="${id}"`), `Missing real HTML node: ${id}`);
context.render({inputs:{mmwave:{valid:true,evidence:true,evidence_kind:'presence',source:'REAL_MMWAVE',health:'ok'}}});
assert.equal(text('mmwaveEvidence'),'존재 증거 있음');
context.render({inputs:{mmwave:{valid:true,evidence:false,evidence_kind:'presence',source:'REAL_MMWAVE',health:'ok'}}});
assert.equal(text('mmwaveEvidence'),'존재 증거 없음');
context.render({inputs:{mmwave:{valid:false,evidence:false,source:'MISSING'}}});
assert.equal(text('mmwaveEvidence'),'WAITING');
console.log('PASS: preserved mmWave panel distinguishes presence, absence and unavailable input');
