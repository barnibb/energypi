const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const html=fs.readFileSync(path.join(__dirname,'../templates/index.html'),'utf8');
const js=fs.readFileSync(path.join(__dirname,'../static/dashboard.js'),'utf8');
for(const id of ['cost-ring','cost-ring-legend','cost-rate','benefit-ring','benefit-ring-legend','effective-rate','money-summary','money-note'])assert.match(html,new RegExp('id="'+id+'"'));
assert.match(js,/import_cost_eur/);assert.match(js,/pv_benefit_eur/);assert.match(js,/feed_revenue_eur/);assert.match(js,/battery_value_eur/);
assert.match(js,/style:'currency',currency:'EUR'/);
assert.match(js,/rechnerisch.*vermieden/);assert.match(js,/Einspeisevergütung/);assert.match(js,/nicht vollständig bestimmbar/);
assert.match(js,/actual_import_price_ct/);assert.match(js,/effective_house_price_ct/);assert.match(js,/tatsächlichen Bezugspreis/);
console.log('OK: Kosten- und Nutzenringe mit Eurobeträgen vorhanden');
