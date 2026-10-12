import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const playwrightPath = process.env.PLAYWRIGHT_MODULE || '/tmp/access-lab-browser-tools/node_modules/playwright/index.mjs';
const {chromium} = await import(playwrightPath);
const base = process.env.ACCESS_LAB_URL || 'http://127.0.0.1:8765';
assert(['127.0.0.1', 'localhost', '[::1]'].includes(new URL(base).hostname), 'Only test a local demo');
const artifacts = path.join(path.dirname(fileURLToPath(import.meta.url)), 'artifacts');
await mkdir(artifacts, {recursive:true});
const browser = await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',headless:true});
const context = await browser.newContext({viewport:{width:1440,height:1000}, reducedMotion:'reduce'});
const page = await context.newPage();
page.setDefaultTimeout(10000);
const errors = [];
page.on('pageerror', e => errors.push(e.message));
page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
const checks = [];
const contrastChecks = [];
let injectedNetworkFailures = 0;
const record = name => {checks.push({name,passed:true}); console.log('PASS ' + name);};
const api = async (endpoint, body, actor='maya') => {
  const response = await context.request.fetch(base + endpoint, {method:body === undefined ? 'GET' : 'POST',headers:{'X-Demo-User':actor}, ...(body === undefined ? {} : {data:body})});
  assert(response.ok(), `Setup/assertion API ${endpoint}: ${response.status()} ${await response.text()}`);
  return response.json();
};
const screenshot = name => page.screenshot({path:path.join(artifacts,name + '.png'),fullPage:true});
const visibleText = async text => { await page.getByText(text,{exact:false}).first().waitFor({state:'visible'}); };
const showDemo = async () => {
  await page.locator('.demo-strip [data-action="demo"]').click();
  await page.locator('#demo-dialog').waitFor({state:'visible'});
};
const persona = async id => {
  await showDemo();
  await page.locator('#persona-select').selectOption(id);
  await page.locator('#demo-dialog').waitFor({state:'hidden'});
  await page.waitForFunction(expected => document.querySelector('#persona-label').textContent.toLowerCase().includes(expected), id);
};
const payment = async result => {
  await showDemo();
  await page.locator('#payment-select').selectOption(result);
  await page.waitForFunction(() => !document.querySelector('#payment-select').disabled);
  await page.locator('[data-action="close-demo"]').click();
};
const reset = async scenario => {
  await showDemo();
  await page.locator('#scenario-select').selectOption(scenario);
  assert(await page.locator('#reset-button').isDisabled(), 'Reset requires confirmation');
  await page.locator('#reset-confirm').check();
  await page.locator('#reset-button').click();
  await page.locator('#demo-dialog').waitFor({state:'hidden'});
  await page.waitForFunction(() => document.querySelector('#persona-label').textContent.includes('Maya'));
};
const request = async () => {
  await page.locator('[data-action="request"]').click();
  await page.getByText('Your request is with an administrator.',{exact:true}).waitFor();
};
const review = async () => {
  await page.locator('[data-action="review"]').first().click();
  await page.locator('#review-dialog').waitFor({state:'visible'});
  await page.locator('#review-dialog [data-action="approve"]').waitFor({state:'visible'});
};
const approve = async () => {
  await page.locator('[data-action="approve"]').click();
  await page.locator('#review-dialog').waitFor({state:'hidden'});
};
const overflow = async () => {
  const dimensions = await page.evaluate(() => ({viewport:innerWidth,width:document.documentElement.scrollWidth}));
  assert(dimensions.width <= dimensions.viewport + 1, JSON.stringify(dimensions));
};
const contrast = async (selectors,label) => {
  const measurements = await page.evaluate(selectors => {
    const rgba = value => value.match(/[\d.]+/g).map(Number);
    const mix = (fg,bg) => fg.slice(0,3).map((v,i)=>v * (fg[3] ?? 1) + bg[i] * (1 - (fg[3] ?? 1)));
    const luminance = rgb => rgb.map(v=>v/255).map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4).reduce((total,v,i)=>total + v * [0.2126,0.7152,0.0722][i],0);
    return [...document.querySelectorAll(selectors)].filter(el=>el.getClientRects().length).map(el=>{
      const chain=[];
      for(let node=el;node;node=node.parentElement) chain.push(node);
      let bg=[255,255,255];
      for(const node of chain.reverse()) bg=mix(rgba(getComputedStyle(node).backgroundColor),bg);
      const style=getComputedStyle(el);
      const fg=rgba(style.color); fg[3]=(fg[3]??1)*Number(style.opacity);
      const a=luminance(mix(fg,bg)),b=luminance(bg);
      return {text:el.textContent.trim().slice(0,90),fontSize:parseFloat(style.fontSize),ratio:(Math.max(a,b)+0.05)/(Math.min(a,b)+0.05),foreground:style.color,background:bg};
    });
  },selectors);
  assert(measurements.length>0,'Contrast selector has visible matches: '+label);
  for(const m of measurements) {
    assert(m.fontSize>=12,`${label} essential text too small: ${JSON.stringify(m)}`);
    assert(m.ratio>=4.5,`${label} low text contrast: ${JSON.stringify(m)}`);
  }
  contrastChecks.push({label,measurements});
};
let failure;
try {
  await api('/api/demo/reset',{scenario:'full',confirm:'RESET DEMO'});
  await page.goto(base);
  await page.getByRole('button',{name:'Request access',exact:false}).waitFor();
  await visibleText('All 5 paid seats are currently assigned.');
  await screenshot('desktop-start');
  await overflow();
  await contrast('.page-subtitle,.summary-description,.summary-value small,.step-text p,.status-line p,.support-note p','desktop explanatory copy');
  await page.keyboard.press('Tab');
  const focused = await page.evaluate(() => ({tag:document.activeElement.tagName, text:document.activeElement.textContent.trim()}));
  assert(focused.tag === 'A' || focused.tag === 'BUTTON', 'A useful keyboard control receives focus');
  record('Desktop explains the blocker; primary controls are keyboard reachable');

  await request();
  const repeat = await api('/api/requests',{});
  assert.equal(repeat.created,false);
  assert.equal((await api('/api/workspace')).requests.length,1);
  record('Browser request is persisted and repeated request is deduplicated');
  await persona('eli');
  await screenshot('desktop-admin');
  await payment('failure');
  await review();
  const quoteText = await page.locator('#review-dialog').innerText();
  assert(quoteText.includes('$6.00') && quoteText.includes('$72.00') && quoteText.includes('15 / 30'));
  await contrast('#review-dialog .dialog-intro,#review-dialog .review-person p,#review-dialog .quote-main small,#review-dialog .quote-formula,#review-dialog .quote-next small,#review-dialog .simulation-note','cost explanation');
  await screenshot('desktop-cost-preview');
  await approve();
  await page.getByRole('button',{name:'Review & retry',exact:false}).waitFor();
  let admin = await api('/api/workspace',undefined,'eli');
  assert.equal(admin.organization.seat_count,5);
  assert.equal(admin.requests[0].status,'payment_failed');
  assert.equal(admin.payments.filter(p=>p.status==='succeeded').length,0);
  await screenshot('desktop-payment-failure');
  record('Failed payment is recoverable and creates no successful charge or access');
  await payment('success');
  await review();
  await approve();
  admin = await api('/api/workspace',undefined,'eli');
  assert.equal(admin.organization.seat_count,6);
  assert.equal(admin.organization.assigned_seats,6);
  assert.equal(admin.payments.filter(p=>p.status==='succeeded').length,1);
  await persona('maya');
  await page.locator('[data-action="open-workspace"]').waitFor();
  await page.locator('[data-action="open-workspace"]').click();
  await page.locator('.unlocked-workspace').waitFor();
  await screenshot('desktop-access-granted');
  record('Deliberate retry succeeds and developer opens server-gated workspace');
  await page.locator('#navigation [data-view="notifications"]').click();
  await visibleText('You’re ready to collaborate');
  await page.locator('[data-action="read-notifications"]').click();
  assert((await api('/api/workspace')).notifications.every(n=>n.read_at));
  record('Developer sees confirmation and can mark only own notifications as read');

  await reset('spare');
  await visibleText('A paid seat is available for you.');
  await request();
  await persona('eli');
  await review();
  await visibleText('Assign seat · $0.00');
  await approve();
  admin = await api('/api/workspace',undefined,'eli');
  assert.equal(admin.organization.seat_count,6);
  assert.equal(admin.payments.length,0);
  record('Existing paid seat is assigned for zero additional cost');

  await reset('full');
  await page.setViewportSize({width:390,height:844});
  await overflow();
  await contrast('.page-subtitle,.summary-description,.summary-value small,.step-text p,.status-line p,.support-note p','mobile explanatory copy');
  await screenshot('mobile-start');
  await request();
  await persona('eli');
  await review();
  await overflow();
  await contrast('#review-dialog .dialog-intro,#review-dialog .review-person p,#review-dialog .quote-main small,#review-dialog .quote-formula,#review-dialog .quote-next small,#review-dialog .simulation-note','mobile cost explanation');
  await screenshot('mobile-cost-preview');
  await approve();
  await persona('maya');
  await page.locator('[data-action="open-workspace"]').waitFor();
  await page.locator('[data-action="open-workspace"]').click();
  await page.locator('.unlocked-workspace').waitFor();
  await overflow();
  await screenshot('mobile-access-granted');
  record('Complete 390px mobile journey works without horizontal page overflow');

  await showDemo();
  for (const href of await page.locator('.evidence-links a').evaluateAll(links=>links.map(a=>a.getAttribute('href')))) {
    const response = await context.request.get(base + href);
    assert.equal(response.status(),200,href);
    assert((await response.text()).length > 50,href);
  }
  record('Evidence and decision links open real project documents');
  await page.locator('[data-action="close-demo"]').click();
  record('Selected essential text is at least 12px with measured contrast of at least 4.5:1');

  await reset('full');
  await page.setViewportSize({width:1440,height:1000});
  const requestPattern = '**/api/requests';
  await page.route(requestPattern, async route=>{
    injectedNetworkFailures++;
    await route.abort('connectionreset');
  },{times:1});
  await page.locator('[data-action="request"]').click();
  await page.getByRole('button',{name:'Request access',exact:true}).waitFor();
  assert(await page.locator('[data-action="request"]').isEnabled());
  assert.equal((await api('/api/workspace')).requests.length,0);
  record('Interrupted request restores the actionable button and can be retried');
  await request();
  await persona('eli');
  await review();
  const sentApprovalBodies=[];
  page.on('request',req=>{
    if(req.method()==='POST' && /\/api\/requests\/\d+\/approve$/.test(req.url())) sentApprovalBodies.push(req.postDataJSON());
  });
  await page.route('**/api/requests/*/approve',async route=>{
    const serverResponse=await route.fetch();
    assert.equal(serverResponse.status(),200);
    assert.equal((await serverResponse.json()).outcome,'approved');
    injectedNetworkFailures++;
    await route.abort('connectionreset');
  },{times:1});
  await page.locator('[data-action="approve"]').click();
  await page.getByRole('button',{name:'Retry same approval',exact:false}).waitFor();
  assert.equal((await api('/api/workspace',undefined,'eli')).payments.length,1);
  await approve();
  assert.equal(sentApprovalBodies.length,2);
  assert.deepEqual(sentApprovalBodies[0],sentApprovalBodies[1]);
  const afterLostResponse=await api('/api/workspace',undefined,'eli');
  assert.equal(afterLostResponse.payments.length,1);
  assert.equal(afterLostResponse.organization.seat_count,6);
  record('Lost approval response retries the same key and creates no second purchase');

  const expectedNetworkErrors=errors.filter(e=>e.includes('net::ERR_CONNECTION_RESET'));
  const unexpectedErrors=errors.filter(e=>!e.includes('net::ERR_CONNECTION_RESET'));
  assert.deepEqual(unexpectedErrors,[],'Unexpected browser console/page errors');
  assert.equal(expectedNetworkErrors.length,injectedNetworkFailures,'Only deliberately injected network errors are present');
  record('No unexpected browser errors; two deliberately injected connection resets were handled');
  await reset('full');
  await page.goto(base);
  await page.getByRole('button',{name:'Request access',exact:true}).waitFor();
  await screenshot('ready-to-review');
} catch (error) {
  failure = error;
  console.error(error.stack);
  await screenshot('failure').catch(()=>{});
} finally {
  await writeFile(path.join(artifacts,'browser-results.json'),JSON.stringify({checkedAt:new Date().toISOString(),url:base,browser:browser.version(),checks,contrastChecks,errors,injectedNetworkFailures,passed:!failure,failure:failure?.message || null},null,2)+'\n');
  await browser.close();
}
if (failure) process.exitCode=1;
