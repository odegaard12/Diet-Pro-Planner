// Characterization tests for the offline queue in static/app.js (apiQueued, flushQueue, handle).
// app.js is a classic script, so it is evaluated whole inside a vm context with minimal stubs;
// its top-level let/const/function bindings are read back with vm.runInContext.
'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SRC = fs.readFileSync(path.join(__dirname, '..', '..', 'static', 'app.js'), 'utf8');

function makeEnv({online = true} = {}) {
  const store = new Map();
  const localStorage = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => { store.set(k, String(v)); },
    removeItem: (k) => { store.delete(k); },
  };
  const el = () => ({classList: {add() {}, remove() {}}, style: {}, dataset: {}, addEventListener() {}, set onclick(_) {}});
  const env = {
    calls: [],            // every fetch call: {path, opts}
    responder: null,      // (call) => response-like | throws
    reloads: 0,
    store,
  };
  const ctx = {
    localStorage,
    navigator: {onLine: online},
    location: {search: '', reload() { env.reloads += 1; }},
    history: {replaceState() {}},
    document: {
      readyState: 'loading', // keeps boot() from running: it only registers a DOMContentLoaded listener
      addEventListener() {},
      querySelector: el,
      querySelectorAll: () => [],
      getElementById: () => null,
      documentElement: {dataset: {}},
      body: {appendChild() {}},
    },
    fetch: async (p, opts) => {
      const call = {path: p, opts, body: opts && opts.body ? JSON.parse(opts.body) : undefined};
      env.calls.push(call);
      return env.responder(call);
    },
    console,
    setTimeout, clearTimeout,
    URLSearchParams, Date, JSON, Promise, Error, TypeError,
  };
  ctx.window = ctx;
  ctx.window.addEventListener = () => {};
  ctx.window.crypto = {randomUUID: (() => { let n = 0; return () => `uuid-${++n}`; })()};
  ctx.crypto = ctx.window.crypto;
  vm.createContext(ctx);
  vm.runInContext(SRC, ctx, {filename: 'static/app.js'});
  env.ctx = ctx;
  env.run = (code) => vm.runInContext(code, ctx);
  env.toasts = [];
  // toast() writes into #toast; record text instead through a dedicated element
  ctx.document.querySelector = (sel) => {
    const e = el();
    if (sel === '#toast') Object.defineProperty(e, 'textContent', {set: (t) => env.toasts.push(t), get: () => ''});
    return e;
  };
  env.queue = () => JSON.parse(store.get('dppQueue') || '[]');
  env.failed = () => JSON.parse(store.get('dppQueueFailed') || '[]');
  // load() runs after a successful flush: make it harmless by answering /api/state too.
  return env;
}

// Objects built inside the vm have another realm's prototypes: compare them as plain JSON.
const plain = (x) => JSON.parse(JSON.stringify(x));
const ok = (data = {ok: true}) => ({status: 200, ok: true, json: async () => data});
const err = (status, body) => ({status, ok: false, json: async () => { if (body === undefined) throw new Error('not json'); return body; }});
const offline = () => { throw new TypeError('Failed to fetch'); };

test('apiQueued adds a client_id and keeps the payload', async () => {
  const env = makeEnv();
  env.responder = () => ok({id: 7});
  const out = await env.run("apiQueued('/api/meals', {name: 'Comida', items: []})");
  assert.deepEqual(out, {id: 7});
  assert.equal(env.calls.length, 1);
  assert.equal(env.calls[0].path, '/api/meals');
  assert.equal(env.calls[0].opts.method, 'POST');
  assert.equal(env.calls[0].body.name, 'Comida');
  assert.equal(env.calls[0].body.client_id, 'uuid-1');
  assert.deepEqual(env.queue(), []);
});

test('apiQueued rejects paths that may not wait offline', async () => {
  const env = makeEnv();
  env.responder = () => ok();
  await assert.rejects(env.run("apiQueued('/api/settings', {})"), /Ruta no admitida/);
  assert.equal(env.calls.length, 0);
});

test('apiQueued queues the request when fetch throws TypeError', async () => {
  const env = makeEnv();
  env.responder = offline;
  const out = await env.run("apiQueued('/api/weights', {kg: 80})");
  assert.deepEqual(plain(out), {ok: true, queued: true});
  const q = env.queue();
  assert.equal(q.length, 1);
  assert.equal(q[0].path, '/api/weights');
  assert.equal(JSON.parse(q[0].body).client_id, 'uuid-1');
  assert.equal(typeof q[0].at, 'number');
  assert.ok(env.toasts.some((t) => t.startsWith('Sin conexión')));
});

test('apiQueued does not queue a real API error (4xx surfaces as Error)', async () => {
  const env = makeEnv();
  env.responder = () => err(400, {error: 'Falta nombre'});
  await assert.rejects(env.run("apiQueued('/api/meals', {})"), /Falta nombre/);
  assert.deepEqual(env.queue(), []);
});

test('apiQueued queues a 503 only when navigator is offline', async () => {
  const env = makeEnv({online: false});
  env.responder = () => err(503);
  const out = await env.run("apiQueued('/api/meals', {name: 'x'})");
  assert.equal(out.queued, true);
  assert.equal(env.queue().length, 1);

  const env2 = makeEnv({online: true});
  env2.responder = () => err(503);
  await assert.rejects(env2.run("apiQueued('/api/meals', {name: 'x'})"), /Error 503/);
  assert.deepEqual(env2.queue(), []);
});

test('flushQueue sends queued jobs in order and empties the queue', async () => {
  const env = makeEnv();
  env.responder = offline;
  for (const n of ['a', 'b', 'c']) await env.run(`apiQueued('/api/meals', {name: '${n}'})`);
  assert.equal(env.queue().length, 3);
  env.calls.length = 0;
  env.responder = (c) => (c.path === '/api/state' ? ok({}) : ok());
  await env.run('flushQueue()');
  const posts = env.calls.filter((c) => c.opts && c.opts.method === 'POST');
  assert.deepEqual(posts.map((c) => c.body.name), ['a', 'b', 'c']);
  assert.deepEqual(env.queue(), []);
  assert.deepEqual(env.failed(), []);
});

test('flushQueue does nothing while navigator is offline', async () => {
  const env = makeEnv({online: false});
  env.responder = offline;
  await env.run("apiQueued('/api/meals', {name: 'a'})");
  env.calls.length = 0;
  env.responder = () => ok();
  await env.run('flushQueue()');
  assert.equal(env.calls.length, 0);
  assert.equal(env.queue().length, 1);
});

test('flushQueue stops at the first network failure and keeps the rest', async () => {
  const env = makeEnv();
  env.responder = offline;
  for (const n of ['a', 'b']) await env.run(`apiQueued('/api/meals', {name: '${n}'})`);
  env.calls.length = 0;
  await env.run('flushQueue()');
  assert.equal(env.calls.length, 1);
  assert.equal(env.queue().length, 2);
});

test('flushQueue parks a 4xx in dppQueueFailed and does not retry it', async () => {
  const env = makeEnv();
  env.responder = offline;
  await env.run("apiQueued('/api/meals', {name: 'bad'})");
  await env.run("apiQueued('/api/meals', {name: 'good'})");
  env.calls.length = 0;
  env.responder = (c) => {
    if (c.path === '/api/state') return ok({});
    return c.body.name === 'bad' ? err(422, {error: 'Dato no válido'}) : ok();
  };
  await env.run('flushQueue()');
  assert.deepEqual(env.queue(), []);
  const failed = env.failed();
  assert.equal(failed.length, 1);
  assert.equal(failed[0].status, 422);
  assert.equal(failed[0].why, 'Dato no válido');
  assert.equal(JSON.parse(failed[0].body).name, 'bad');
  // second flush has nothing left: no retry of the parked job
  env.calls.length = 0;
  await env.run('flushQueue()');
  assert.equal(env.calls.length, 0);
});

test('flushQueue 4xx without JSON body falls back to "Error <status>"', async () => {
  const env = makeEnv();
  env.responder = offline;
  await env.run("apiQueued('/api/meals', {name: 'bad'})");
  env.responder = () => err(404);
  await env.run('flushQueue()');
  assert.equal(env.failed()[0].why, 'Error 404');
  assert.deepEqual(env.queue(), []);
});

test('flushQueue leaves the queue intact on 401', async () => {
  const env = makeEnv();
  env.responder = offline;
  await env.run("apiQueued('/api/meals', {name: 'a'})");
  const before = env.store.get('dppQueue');
  env.responder = () => err(401, {error: 'no auth'});
  await env.run('flushQueue()');
  assert.equal(env.store.get('dppQueue'), before);
  assert.deepEqual(env.failed(), []);
});

test('flushQueue keeps the record on 5xx and does not park it', async () => {
  const env = makeEnv();
  env.responder = offline;
  await env.run("apiQueued('/api/meals', {name: 'a'})");
  await env.run("apiQueued('/api/meals', {name: 'b'})");
  env.calls.length = 0;
  env.responder = () => err(500, {error: 'boom'});
  await env.run('flushQueue()');
  assert.equal(env.calls.length, 1); // stops at the first job
  assert.equal(env.queue().length, 2);
  assert.deepEqual(env.failed(), []);
});

test('handle: 401 reloads the page and throws, other errors use the JSON error', async () => {
  const env = makeEnv();
  await assert.rejects(env.run("handle({status: 401, ok: false})"), /Sesión caducada/);
  assert.equal(env.reloads, 1);
  await assert.rejects(env.run("handle({status: 500, ok: false, json: async () => ({error: 'caído'})})"), /caído/);
  await assert.rejects(env.run("handle({status: 500, ok: false, json: async () => { throw new Error('x'); }})"), /Error 500/);
  assert.deepEqual(plain(await env.run("handle({status: 200, ok: true, json: async () => ({a: 1})})")), {a: 1});
});
