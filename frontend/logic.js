/*
 Screening Room — live app logic (replaces the prototype's simulated logic).
 Template + styles are the design file's, unchanged except for a few live bindings.
 Backend: FastAPI in /backend. All AI calls return structured JSON; this file only renders it.
*/
class Component extends DCLogic {
  constructor(props) {
    super(props);
    this.D = Component.data();
    this.state = {
      stage: 'source', maxStage: 0, pid: null, cfg: null,
      source: '', culture: 'IN', lang: 'hi',
      workStep: 0, elapsed: 0, traceOpen: false, storyPhase: 'settled', trace: ['', '', '', '', '', ''], adaptErr: '', live: null,
      title: '', terms: {}, lines: [], story: null, names: {}, glossary: [], twists: [], bibleEdit: {},
      hoverTwist: null, activeBeat: null,
      sideTab: 'comments', sideOpen: true, sheet: null, sideW: 380, bibleHover: -1,
      prompt: '', route: null, aiBusy: false, draft: null, toasts: [],
      sel: null, composerOpen: false, composerText: '', comments: [],
      persona: 'ott', pace: 1, emoPop: null, voice: null, voicePicking: false, voiceListOpen: false, pvId: null,
      narr: 'idle', narrErr: '', stale: false, justReady: false, playing: false, t: 0, amp: 0, mini: false, genStep: 0, follow: true,
      audio: null, cmdOpen: false, cmdQ: '', cmdIdx: 0
    };
    this._timers = []; this._tid = 0; this._cid = 0;
  }

  static data() {
    const SAMPLE = 'Juliana returned to Ashcombe after six years abroad and found her late mother’s bridal gown laid upon the bed, as though it had been waiting. Her uncle, who had kept the estate since her mother’s death, would not meet her eye when she asked after the deeds.\n\nGerald had sworn, at the Michaelmas fair, that he would wait. Now he stood across the hall and would not hold her gaze. On the morning of the wedding, Clarissa fixed the veil with quick, cold fingers, and would not say why her hands shook.\n\nShe entered the cathedral in her mother’s gown and saw at once that the altar was not waiting for her. Gerald stood beside Clarissa. The family, it seemed, had chosen long before she arrived.\n\nIn the vestry, Juliana felt a stiffness in the bodice seam and drew out a letter in her mother’s hand. The letter was plain: Ashcombe had never been her uncle’s to keep. It was her mother’s, and now it was hers. Clarissa confessed she had hurried the veil so their uncle would not see the seam, and pressed the strongbox key into Juliana’s hand.\n\nJuliana walked to the altar not as a bride but as mistress of Ashcombe, and read the letter aloud to the congregation. By evening the cathedral was empty, and Juliana folded her mother’s gown away — this time in her own chest.';
    return {
      SAMPLE,
      STAGES: [{ id: 'source', label: 'Source' }, { id: 'adapt', label: 'Adapt' }, { id: 'story', label: 'Story' }, { id: 'edit', label: 'Edit' }, { id: 'narrate', label: 'Narrate' }],
      STEPS: ['Reading source', 'Extracting beats', 'Tagging twists', 'Adapting culture', 'Writing story', 'Checking twists'],
      LANGS: { hi: 'Hindi', bn: 'Bengali', or: 'Odia', ta: 'Tamil', te: 'Telugu', mr: 'Marathi', gu: 'Gujarati', kn: 'Kannada', ml: 'Malayalam', pa: 'Punjabi' },   // = qwen_prompts.LANGUAGE_PROFILES
      OTHER: ['ta', 'te', 'mr', 'gu', 'kn', 'ml', 'pa'],   // design order; hi, bn, or are the top options
      PERSONAS: [
        { id: 'ott', name: 'OTT storyteller', desc: 'Modern, natural Hinglish; cinematic, never overdone. Recommended.' },
        { id: 'grandma', name: 'Grandmother storyteller', desc: 'Warm and unhurried; leans into pauses.' },
        { id: 'radio', name: 'Radio-drama host', desc: 'Clear and theatrical; sets every scene.' },
        { id: 'trailer', name: 'Thriller trailer voice', desc: 'Low and clipped; builds tension.' }
      ],
      EMOS: ['whisper', 'pause', 'rising', 'shock'],
      CMDS: [{ cmd: '/rename', hint: 'Rename a character or place' }, { cmd: '/rewrite', hint: 'Redraft a line' }, { cmd: '/shorten', hint: 'Tighten a line' }, { cmd: '/tone', hint: 'Shift a line’s tone' }, { cmd: '/persona', hint: 'Change how the narrator sounds' }]
    };
  }

  /* ---------- api ---------- */
  async api(method, path, body, signal) {
    const r = await fetch(path, { method, headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined, signal });
    let data = null; try { data = await r.json(); } catch (e) { /* empty body */ }
    if (!r.ok) throw new Error((data && (typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail))) || ('HTTP ' + r.status));
    return data;
  }
  /* PUT a change ({story} | {names} | {cues} | {persona} | {pace}); the server re-runs swap_names + lint and
     returns the new view, which replaces what is on screen. */
  save(body) {
    const s = this.state; if (!s.pid) return Promise.resolve();
    return this.api('PUT', '/api/projects/' + s.pid + '/state', body).then(p => this.applyServer(p))
      .catch(e => this.toast('Couldn’t save: ' + e.message));
  }
  setAndSave(patch) {
    const local = {}; ['persona', 'pace'].forEach(k => { if (k in patch) local[k] = patch[k]; });
    if (Object.keys(local).length) this.setState(local);
    return this.save(patch);
  }
  applyServer(p) {
    if (!p || p.status !== 'ready') return;
    this.setState({ title: p.title || '', terms: p.terms || {}, lines: p.lines || [], story: p.story || null, names: p.names || {},
      glossary: p.glossary || [], twists: p.twists || [], persona: p.persona || this.state.persona, pace: p.pace || this.state.pace,
      voice: p.voice || this.state.voice });
  }

  /* ---------- lifecycle ---------- */
  later(fn, ms) { const id = setTimeout(fn, ms); this._timers.push(id); return id; }
  componentDidMount() {
    this.api('GET', '/api/config').then(cfg => this.setState({ cfg })).catch(() => {});
    // Listen on the whole document: a drag that starts in the story often ends outside the card.
    this._onSel = () => setTimeout(() => this.captureSelection(), 0);
    document.addEventListener('mouseup', this._onSel);
    document.addEventListener('keyup', this._onSel);
    const m = (location.hash || '').match(/p=([a-f0-9]+)/);
    if (m) this.resume(m[1]);
  }
  componentWillUnmount() { document.removeEventListener('mouseup', this._onSel); document.removeEventListener('keyup', this._onSel); this._timers.forEach(clearTimeout); clearInterval(this._el); clearInterval(this._poll); cancelAnimationFrame(this._raf); if (this.player) this.player.pause(); }
  componentDidUpdate() {
    const s = this.state;
    if (s.stage === 'adapt' && this.liveEl && this.liveEl.scrollHeight > this.liveEl.clientHeight) this.liveEl.scrollTop = this.liveEl.scrollHeight;
    if (s.stage !== 'narrate' || s.narr !== 'ready' || !s.playing || !s.follow) { this._lastSid = null; return; }
    const sid = this.sentAt(s.t);
    if (sid === this._lastSid) return;
    this._lastSid = sid;
    const el = document.getElementById('read-' + sid);
    if (el && el.scrollIntoView) {
      const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      el.scrollIntoView({ block: 'center', behavior: reduce ? 'auto' : 'smooth' });
    }
  }
  async resume(pid) {
    try {
      const p = await this.api('GET', '/api/projects/' + pid);
      if (p.status === 'ready') this.loadStory(p, false);
      else if (p.status === 'error') { this.setState({ pid }); }
      else { this.setState({ pid, stage: 'adapt', maxStage: 1, lang: p.lang }); this.startPolling(pid); }
    } catch (e) { history.replaceState(null, '', location.pathname); }
  }
  loadStory(p, stream) {
    if (p.status === 'error') { this.setState({ pid: p.id, stage: 'adapt', maxStage: 1, adaptErr: p.error || 'Something went wrong' }); return; }
    const patch = {
      pid: p.id, lang: p.lang, culture: p.culture, persona: p.persona || 'ott', pace: p.pace || 1, trace: p.trace || this.state.trace,
      stage: 'story', maxStage: 4, workStep: 6, storyPhase: stream ? 'stream' : 'settled', activeBeat: (p.lines && p.lines[0] && p.lines[0].beat) || null
    };
    this.applyServer(p);
    if (p.audio) Object.assign(patch, { audio: p.audio, narr: 'ready' });
    this.setState(patch);
    if (p.audio) this.makePlayer(p.audio);
    if (stream) {
      const words = this.sentences().reduce((a, x) => a + x.raw.split(/\s+/).length, 0);
      this.later(() => this.setState({ storyPhase: 'settled' }), Math.min(9000, words * 24 + 1400));
    }
  }

  /* ---------- text helpers ---------- */
  nm(k, terms) { terms = terms || this.state.terms; return terms[k] ? terms[k].val : k; }
  /* Display text is already swap_names()'d on the server; this only guards against a stray {ID}. */
  resolve(text) { return (text || '').replace(/\{([CE][0-9]+)\}/g, (_, k) => this.nm(k)); }
  sentences() { return (this.state.lines || []).map(l => ({ sid: l.sid, beat: l.beat, raw: l.text, line: l })); }
  segsStream(line, base) {
    const out = []; let wi = 0;
    ((line && line.parts) || [{ t: line ? line.text : '' }]).forEach(part => {
      if (!part.t) return;
      if (part.id) { out.push({ plain: false, mark: false, word: false, morph: true, src: part.src || part.t, t: part.t, d: base + wi * 24 }); wi++; }
      else (part.t.match(/\s*\S+\s*/g) || [part.t]).forEach(w => { out.push({ plain: false, mark: false, word: true, morph: false, t: w, d: base + wi * 24 }); wi++; });
    });
    return { segs: out, n: wi };
  }
  segsMarked(text, quotes) {
    let parts = [{ t: text, mark: false }];
    quotes.forEach(q => {
      if (!q) return;
      const next = [];
      parts.forEach(p => {
        if (p.mark || p.t.indexOf(q) < 0) { next.push(p); return; }
        const bits = p.t.split(q);
        bits.forEach((b, i) => { if (b) next.push({ t: b, mark: false }); if (i < bits.length - 1) next.push({ t: q, mark: true }); });
      });
      parts = next;
    });
    return parts.map(p => ({ plain: !p.mark, mark: p.mark, word: false, morph: false, t: p.t }));
  }
  estDur() { const chars = this.sentences().reduce((a, x) => a + this.resolve(x.raw).length, 0); return Math.max(10, Math.round(chars * 0.072 / this.state.pace)); }
  dur() { const a = this.state.audio; return a && this.state.narr === 'ready' ? a.duration : this.estDur(); }
  fmt(sec) { sec = Math.max(0, Math.round(sec)); return Math.floor(sec / 60) + ':' + String(sec % 60).padStart(2, '0'); }
  sentFracs() {
    const a = this.state.audio, ss = this.sentences();
    if (a && a.sents && a.duration) {
      const by = {}; a.sents.forEach(x => { by[x.sid] = x.start / a.duration; });
      return ss.map(x => ({ sid: x.sid, beat: x.beat, f: by[x.sid] !== undefined ? by[x.sid] : 0 }));
    }
    const lens = ss.map(x => this.resolve(x.raw).length + 12); const tot = lens.reduce((p, q) => p + q, 0) || 1;
    let acc = 0; return ss.map((x, i) => { const f = acc / tot; acc += lens[i]; return { sid: x.sid, beat: x.beat, f }; });
  }
  sentAt(t) {
    const a = this.state.audio;
    if (a && a.sents && a.sents.length) { let sid = a.sents[0].sid; a.sents.forEach(x => { if (t >= x.start - 0.05) sid = x.sid; }); return sid; }
    const f = t / this.dur(), fr = this.sentFracs(); if (!fr.length) return null; let sid = fr[0].sid; fr.forEach(x => { if (f >= x.f) sid = x.sid; }); return sid;
  }
  langName() { return this.D.LANGS[this.state.lang] || 'Hindi'; }
  termKeyFor(text) {
    const s = this.state, q = (text || '').trim().replace(/[।.,!?;:“”"'’]+$/g, '').toLowerCase();
    if (!q) return null;
    return Object.keys(s.terms).find(k => { const t = s.terms[k]; return [t.val, t.short, t.en, t.src].some(v => v && v.toLowerCase() === q); }) || null;
  }

  /* ---------- flow ---------- */
  goStage(id) {
    const s = this.state, idx = this.D.STAGES.findIndex(x => x.id === id);
    if (idx > s.maxStage) return;
    const patch = { stage: id, sheet: null, sel: null, composerOpen: false, cmdOpen: false };
    if (id === 'narrate') patch.sideTab = 'voice';
    else if (s.sideTab === 'voice') patch.sideTab = 'comments';
    if (id !== 'narrate') { this.pausePlayer(); patch.playing = false; patch.mini = false; }
    this.setState(patch);
    if (this.centerEl) this.centerEl.scrollTop = 0;
  }
  async craft() {
    const s = this.state;
    if (!s.source.trim()) return;
    this._timers.forEach(clearTimeout); this._timers = []; clearInterval(this._el); clearInterval(this._poll);
    this.pausePlayer();
    const t0 = Date.now();
    this.setState({ stage: 'adapt', maxStage: 1, workStep: 0, elapsed: 0, storyPhase: 'settled', comments: [], terms: {}, lines: [], story: null, names: {}, glossary: [], twists: [], audio: null, narr: 'idle', stale: false, sideTab: 'comments', adaptErr: '', trace: ['', '', '', '', '', ''], live: null });
    this._el = setInterval(() => this.setState({ elapsed: (Date.now() - t0) / 1000 }), 100);
    try {
      const r = await this.api('POST', '/api/projects', { source: s.source, culture: s.culture, lang: s.lang });
      history.replaceState(null, '', '#p=' + r.id);
      this.setState({ pid: r.id });
      this.startPolling(r.id);
    } catch (e) { clearInterval(this._el); this.setState({ adaptErr: e.message }); }
  }
  startPolling(pid) {
    clearInterval(this._poll);
    let busy = false;
    this._poll = setInterval(async () => {
      if (busy) return; busy = true;
      try {
        const p = await this.api('GET', '/api/projects/' + pid);
        if (p.status === 'error') { clearInterval(this._poll); clearInterval(this._el); this.setState({ adaptErr: p.error || 'Something went wrong', trace: p.trace || this.state.trace, workStep: p.step || 0 }); }
        else if (p.status === 'ready') { clearInterval(this._poll); clearInterval(this._el); this.setState({ workStep: 6, trace: p.trace, live: null }); this.later(() => this.loadStory(p, true), 700); }
        else this.setState({ workStep: p.step || 0, trace: p.trace || this.state.trace, live: p.live || this.state.live });
      } catch (e) { /* transient; keep polling */ }
      busy = false;
    }, 500);
  }
  toast(text, undo) {
    const id = ++this._tid;
    this.setState(st => ({ toasts: st.toasts.concat([{ id, text, undo }]).slice(-3) }));
    this.later(() => this.dismiss(id), 5200);
  }
  dismiss(id) { this.setState(st => ({ toasts: st.toasts.filter(x => x.id !== id) })); }
  snapshot() { const s = this.state; return { story: s.story, names: s.names, persona: s.persona, pace: s.pace }; }
  restore(snap) { this.markStale(); return this.setAndSave(snap); }
  markStale() { if (this.state.narr === 'ready') { this.pausePlayer(); this.setState({ narr: 'idle', stale: true, playing: false }); } }

  /* ---------- drafts (real model calls) ---------- */
  classify(t) {
    const x = t.toLowerCase().trim();
    if (x.startsWith('/persona')) return 'persona';
    if (/^\/(rename|rewrite|shorten|tone)/.test(x)) return 'story';
    if (/(voice|narrat|persona|slower|faster|louder|\bpace\b|sound like|grandmother|grandma|radio host|trailer voice)/.test(x)) return 'persona';
    return 'story';
  }
  async requestDraft(instruction, route, ctx, signal) {
    return this.api('POST', '/api/projects/' + this.state.pid + '/edit', { instruction, route, quote: (ctx && ctx.quote) || '', beat: (ctx && ctx.beat) || '' }, signal);
  }
  async send() {
    const s = this.state, text = s.prompt.trim();
    if (!text || s.aiBusy) return;
    const route = s.route || this.classify(text);
    this._abort = new AbortController();
    this.setState({ prompt: '', aiBusy: true });
    try {
      const d = await this.requestDraft(text.replace(/^\/persona\s*/i, ''), route, null, this._abort.signal);
      if (!d || d.kind === 'none' || d.kind === 'reply') { this.setState({ aiBusy: false }); this.toast(d && d.kind === 'reply' ? d.title : ((d && d.title ? d.title + ' — ' : '') + (d && d.sub ? d.sub : 'nothing to change'))); return; }
      if (d.also) this.toast(d.also);
      const patch = { aiBusy: false, draft: d };
      if (d.kind === 'story' && this.state.stage === 'story') patch.stage = 'edit';
      this.setState(patch);
    } catch (e) {
      this.setState({ aiBusy: false });
      if (e.name !== 'AbortError') this.toast('Couldn’t draft that: ' + e.message);
    }
  }
  applyDraft(d) {
    const snap = this.snapshot();
    this.markStale();
    this.setAndSave(Object.assign({}, d.apply));
    return snap;
  }
  keepDraft() {
    const d = this.state.draft; if (!d) return;
    const recast = d.apply && d.apply.persona && d.apply.persona !== this.state.persona;
    const snap = this.applyDraft(d);
    if (recast) this.later(() => this.recast(d.apply.persona), 300);
    this.setState({ draft: null, route: null });
    this.toast(d.kind === 'persona' ? 'Persona updated' : 'Edit applied', () => this.restore(snap));
  }
  undoDraft() { this.setState({ draft: null }); this.toast('Draft discarded'); }

  /* ---------- comments ---------- */
  captureSelection() {
    const s = this.state;
    if (!(s.stage === 'story' || s.stage === 'edit') || s.storyPhase === 'stream' || s.composerOpen) return;
    const sel = window.getSelection(); const txt = sel ? sel.toString().trim() : '';
    const art = document.querySelector('article.page');
    const inside = n => !!(n && art && art.contains(n.nodeType === 1 ? n : n.parentElement));
    if (!txt || !sel.rangeCount || !(inside(sel.anchorNode) || inside(sel.focusNode))) {
      if (s.sel && !s.composerOpen && !(document.activeElement && document.activeElement.closest && document.activeElement.closest('.cpill,.composer'))) this.setState({ sel: null });
      return;
    }
    if (txt.length > 600) { this.setState({ sel: null }); this.toast('Select a shorter passage (up to a few sentences) to comment on it'); return; }
    const r = sel.getRangeAt(0).getBoundingClientRect();
    const node = inside(sel.anchorNode) ? sel.anchorNode : sel.focusNode;
    const el = node && (node.nodeType === 1 ? node : node.parentElement); const be = el && el.closest('[data-beat]');
    const y = r.top < 210 ? r.bottom + 230 : r.top;                 // flip below the text near the top edge so the composer never clips
    this.setState({ sel: { x: Math.min(window.innerWidth - 190, Math.max(190, r.left + r.width / 2)), y: Math.min(window.innerHeight - 20, y), text: txt, beat: be ? be.getAttribute('data-beat') : '' }, composerText: '' });
  }
  /* A comment on selected text is a story edit unless it clearly talks about the narrator's voice. */
  commentRoute(t) {
    const x = t.toLowerCase().trim();
    if (x.startsWith('/persona')) return 'persona';
    return /(narrator|narration|voice|persona|\bpace\b|speak (slower|faster)|read (it )?(slower|faster))/.test(x) ? 'persona' : 'story';
  }
  async submitComment() {
    const s = this.state, text = s.composerText.trim(); if (!text || !s.sel) return;
    const id = ++this._cid, quote = s.sel.text, beat = s.sel.beat;
    const c = { id, quote, beat, text, status: 'drafting', draft: null };
    if (window.getSelection) window.getSelection().removeAllRanges();
    const narrow = window.innerWidth < 960;                         // side panel is a sheet on small windows: open it so the card is visible
    this.setState(st => ({ comments: [c].concat(st.comments), sel: null, composerOpen: false, composerText: '', sideTab: 'comments', sideOpen: true, sheet: narrow ? 'side' : st.sheet, stage: st.stage === 'story' ? 'edit' : st.stage }));
    this.toast('Comment added — drafting a change');
    try {
      const d = await this.requestDraft(text, this.commentRoute(text), { quote, beat });
      if (d && d.kind === 'reply') this.toast(d.title);
      this.setComment(id, d && d.kind !== 'none' && d.kind !== 'reply' ? { status: 'draft', draft: d } : { status: 'failed' });
    } catch (e) { this.setComment(id, { status: 'failed' }); this.toast('Couldn’t draft that comment: ' + e.message); }
  }
  setComment(id, patch) { this.setState(st => ({ comments: st.comments.map(x => x.id === id ? Object.assign({}, x, patch) : x) })); }
  keepComment(c) {
    const snap = this.applyDraft(c.draft);
    this.setComment(c.id, { status: 'applied' });
    this.toast('Comment resolved · edit applied', () => { this.restore(snap); this.setComment(c.id, { status: 'draft' }); });
  }

  /* ---------- bible ---------- */
  async commitBible(key) {
    const s = this.state, v = s.bibleEdit[key];
    if (v === undefined) return;
    const cur = this.nm(key);
    const be = Object.assign({}, s.bibleEdit); delete be[key];
    if (!v.trim() || v.trim() === cur) { this.setState({ bibleEdit: be }); return; }
    try {
      const r = await this.api('POST', '/api/projects/' + s.pid + '/transliterate', { key, value: v.trim() });
      const snap = this.snapshot();
      const be2 = Object.assign({}, this.state.bibleEdit); delete be2[key];
      this.markStale();
      this.setState({ bibleEdit: be2 });
      await this.save({ names: { [key]: r } });
      this.toast('Renamed ' + cur + ' → ' + r.name_native, () => this.restore(snap));
    } catch (e) { this.setState({ bibleEdit: be }); this.toast('Couldn’t rename: ' + e.message); }
  }

  /* ---------- narration (Cartesia via backend) ---------- */
  async generate() {
    const s = this.state;
    this.pausePlayer();
    this.setState({ narr: 'generating', narrErr: '', playing: false, stale: false, t: 0, genStep: 0, justReady: false });
    this.later(() => this.state.narr === 'generating' && this.setState({ genStep: 1 }), 1500);
    this.later(() => this.state.narr === 'generating' && this.setState({ genStep: 2 }), 3500);
    try {
      const audio = await this.api('POST', '/api/projects/' + s.pid + '/narrate', { persona: s.persona, pace: s.pace });
      this.makePlayer(audio);
      this.setState({ audio, narr: 'ready', justReady: true, t: 0 });
      this.later(() => this.setState({ justReady: false }), 1800);
    } catch (e) { this.setState({ narr: 'error', narrErr: e.message }); }
  }
  makePlayer(audio) {
    if (this.player) { this.player.pause(); this.player.src = ''; }
    const el = new Audio(audio.url); el.preload = 'auto';
    el.addEventListener('ended', () => { cancelAnimationFrame(this._raf); this.setState({ playing: false, t: audio.duration, amp: 0 }); });
    this.player = el;
  }
  pausePlayer() { cancelAnimationFrame(this._raf); if (this.player && !this.player.paused) this.player.pause(); }
  tick() {
    const el = this.player, a = this.state.audio; if (!el || !a) return;
    const t = el.currentTime, env = a.env || [];
    const e = env[Math.min(env.length - 1, Math.floor(t * 20))] || 0;
    this.setState({ t, amp: this.state.amp * 0.5 + e * 0.5 });
    this._raf = requestAnimationFrame(() => this.tick());
  }
  togglePlay() {
    const s = this.state; if (s.narr !== 'ready' || !this.player) return;
    if (s.playing) { this.pausePlayer(); this.setState({ playing: false, amp: 0 }); return; }
    if (s.t >= this.dur() - 0.3) this.player.currentTime = 0;
    this.player.play().then(() => { this.setState({ playing: true }); this.tick(); }).catch(e => this.toast('Can’t play audio: ' + e.message));
  }
  setPersona(id) {
    if (id === this.state.persona) return;
    this.markStale();
    this.setAndSave({ persona: id }).then(() => this.recast(id));   // a persona switch re-runs the casting
  }
  /* ---------- narrator casting (Cartesia catalog -> code filter -> Qwen pick) ---------- */
  async recast(persona) {
    const s = this.state; if (!s.pid) return;
    this.setState({ voicePicking: true });
    try {
      const v = await this.api('POST', '/api/projects/' + s.pid + '/voice/pick', { persona: persona || s.persona });
      this.setState({ voice: v, voicePicking: false });
      if (v && v.name) this.toast('Narrator: ' + v.name + (v.reason ? ' — ' + v.reason : ''));
    } catch (e) { this.setState({ voicePicking: false }); this.toast('Couldn’t pick a voice: ' + e.message); }
  }
  async chooseVoice(id) {
    const s = this.state; if (!s.pid || (s.voice && s.voice.voice_id === id)) return;
    try {
      const v = await this.api('POST', '/api/projects/' + s.pid + '/voice', { voice_id: id });
      this.markStale(); this.setState({ voice: v }); this.toast('Narrator changed to ' + v.name);
    } catch (e) { this.toast('Couldn’t change voice: ' + e.message); }
  }
  previewVoice(id) {
    if (!id) return;
    if (!this.pv) { this.pv = new Audio(); this.pv.addEventListener('ended', () => this.setState({ pvId: null })); this.pv.addEventListener('error', () => { this.setState({ pvId: null }); this.toast('No preview for this voice'); }); }
    if (this.state.pvId === id) { this.pv.pause(); this.setState({ pvId: null }); return; }
    this.pausePlayer(); if (this.state.playing) this.setState({ playing: false });
    this.pv.src = '/api/voices/' + encodeURIComponent(id) + '/preview';
    this.pv.play().then(() => this.setState({ pvId: id })).catch(() => {});
  }
  cmdAll() {
    const s = this.state, out = [];
    this.D.STAGES.forEach((st, i) => { if (i <= s.maxStage) out.push({ label: st.label, group: 'Stage', run: () => this.goStage(st.id) }); });
    if (s.maxStage >= 2) this.D.PERSONAS.forEach(p => out.push({ label: p.name, group: 'Persona', run: () => { this.goStage('narrate'); this.setPersona(p.id); } }));
    const q = s.cmdQ.trim().toLowerCase();
    return q ? out.filter(x => (x.label + ' ' + x.group).toLowerCase().indexOf(q) >= 0) : out;
  }

  voiceVals() {
    const s = this.state, v = s.voice;
    const g = x => x === 'feminine' ? 'Female' : x === 'masculine' ? 'Male' : x === 'gender_neutral' ? 'Neutral' : '';
    const meta = x => [g(x.gender), x.accent, x.native ? 'native speaker' : ''].filter(Boolean).join(' · ') || (x.tagline || '');
    const has = !!(v && v.voice_id && !s.voicePicking);
    return {
      hasVoice: has, voicePicking: s.voicePicking,
      voiceName: v ? (v.name || 'Voice from settings') : '', voiceMeta: v ? meta(v) : '', voiceReason: v ? (v.reason || '') : '',
      voiceBy: !v ? '' : v.by === 'qwen' ? 'Cast for this story' : v.by === 'writer' ? 'Your pick' : v.by === 'ranked' ? 'Best ranked match' : 'From settings',
      voicePlaying: !!(v && s.pvId === v.voice_id), voiceNotPlaying: !(v && s.pvId === v.voice_id), voicePlayCls: v && s.pvId === v.voice_id ? 'is-on' : '',
      previewVoice: () => v && this.previewVoice(v.voice_id),
      voiceListOpen: s.voiceListOpen, toggleVoiceList: () => this.setState({ voiceListOpen: !s.voiceListOpen }),
      voiceListLabel: s.voiceListOpen ? 'Hide voices' : 'Change voice', recastVoice: () => this.recast(s.persona),
      voiceOptions: ((v && v.finalists) || []).map(f => ({ name: f.name, meta: meta(f) + (f.tagline ? ' — ' + f.tagline : ''), on: f.id === v.voice_id, cls: f.id === v.voice_id ? 'is-on' : '',
        aria: 'Preview ' + f.name, preview: () => this.previewVoice(f.id), pick: () => this.chooseVoice(f.id) })),
      voicePoolNote: v ? ('Top ' + ((v.finalists || []).length) + ' of ' + (v.pool || 0) + ' ' + (this.D.LANGS[s.lang] || '') + ' voices for this persona' + (v.native_count !== undefined ? ' · ' + v.native_count + ' native speakers in the catalog' : '') + '.') : ''
    };
  }

  /* ---------- render ---------- */
  renderVals() {
    const s = this.state, D = this.D;
    const stIdx = D.STAGES.findIndex(x => x.id === s.stage);
    const isSource = s.stage === 'source', isAdapt = s.stage === 'adapt', isStoryish = s.stage === 'story' || s.stage === 'edit', isNarrate = s.stage === 'narrate';
    const lang = s.lang;
    const bodyCls = (lang === 'hi' || lang === 'mr') ? 'body-hi' : D.LANGS[lang] ? 'body-' + lang : 'body-en';
    const htmlLang = lang;
    const dur = this.dur();
    const ready = isNarrate && s.narr === 'ready';
    const readSid = ready ? this.sentAt(s.t) : null;
    const TW = s.twists || [];
    const hoverT = TW.find(t => t.id === s.hoverTwist);
    const streaming = s.storyPhase === 'stream' && isStoryish;
    const words = s.source.trim() ? s.source.trim().split(/\s+/).length : 0;
    const openQuotes = s.comments.filter(c => c.status === 'drafting' || c.status === 'draft').map(c => c.quote);
    const ss = this.sentences();
    const firstOfBeat = {}; ss.forEach(x => { if (!firstOfBeat[x.beat]) firstOfBeat[x.beat] = x.sid; });
    const nTw = TW.length, twLabel = nTw + (nTw === 1 ? ' twist' : ' twists') + ' kept in order';
    const cfg = s.cfg;

    let statusText = 'Ready when you are', statusDot = '', statusCls = '';
    if (isAdapt) {
      if (s.adaptErr) { statusText = 'Adaptation failed'; statusDot = 'err'; }
      else { statusText = D.STEPS[Math.min(s.workStep, 5)] + '…'; statusDot = 'ai'; statusCls = 'shim'; }
    } else if (isStoryish) {
      const drafting = s.aiBusy || s.comments.some(c => c.status === 'drafting');
      const pending = s.comments.filter(c => c.status === 'draft').length;
      if (drafting) { statusText = 'Drafting an edit…'; statusDot = 'ai'; statusCls = 'shim'; }
      else if (pending) { statusText = pending + (pending === 1 ? ' draft' : ' drafts') + ' waiting for Keep or Undo'; statusDot = 'ai'; }
      else { statusText = 'Story ready · ' + twLabel; statusDot = 'ok'; }
    } else if (isNarrate) {
      if (s.narr === 'generating') { statusText = 'Finding the voice…'; statusDot = 'ai'; statusCls = 'shim'; }
      else if (s.narr === 'error') { statusText = 'Narration failed — retry'; statusDot = 'err'; }
      else if (ready) { statusText = s.playing ? 'Narrating' : 'Narration ready'; statusDot = 'ok'; }
      else if (s.aiBusy) { statusText = 'Drafting a persona edit…'; statusDot = 'ai'; statusCls = 'shim'; }
      else statusText = 'Pick a voice, then narrate';
    } else if (cfg && !cfg.llm_ready) { statusText = 'Add the SiliconFlow key in backend/.env'; statusDot = 'err'; }

    /* story paragraph */
    let base = 0;
    const sents = ss.map(x => {
      const tw = TW.find(t => t.reveal_sid === x.sid);                    // line-level: this line IS the reveal
      let segs;
      if (streaming) { const r = this.segsStream(x.line, base); segs = r.segs; base += r.n * 24 + 60; }
      else segs = this.segsMarked(this.resolve(x.raw), openQuotes);
      const isSetup = !!(hoverT && hoverT.setup_sid === x.sid), isHot = !!(hoverT && hoverT.reveal_sid === x.sid);
      return {
        sid: x.sid, beat: x.beat, domId: 'story-' + x.sid, segs, spark: !!tw,
        cls: (isSetup ? 'is-setup ' : '') + (isHot ? 'is-hot' : ''),
        enter: () => { if (tw) this.setState({ hoverTwist: tw.id, activeBeat: x.beat }); else if (this.state.activeBeat !== x.beat) this.setState({ activeBeat: x.beat }); },
        leave: () => { if (this.state.hoverTwist) this.setState({ hoverTwist: null }); }
      };
    });

    /* working */
    const steps = D.STEPS.map((label, i) => {
      const done = i < s.workStep, run = i === s.workStep && isAdapt && !s.adaptErr;
      const failed = !!s.adaptErr && i === s.workStep;
      return { label, n: String(i + 1).padStart(2, '0'), done, run, queued: !done && !run, cls: done ? 'is-done' : run ? 'is-run' : '',
        showTrace: s.traceOpen && done && !!s.trace[i], trace: s.trace[i], stText: done ? 'Done' : run ? 'Running' : failed ? 'Failed' : 'Queued', stCls: done ? 'ok' : run ? 'ai' : failed ? 'err' : '' };
    });
    const thinkLines = D.STEPS.map((t, i) => ({ text: (s.adaptErr ? 'Stopped at: ' + t : t + '…'), on: i === Math.min(s.workStep, 5) }));

    /* side tabs */
    const tabDefs = isNarrate ? [{ id: 'voice', label: 'Voice' }, { id: 'bible', label: 'Bible' }] : [{ id: 'comments', label: 'Comments' }, { id: 'bible', label: 'Bible' }];
    let tabId = s.sideTab; if (!tabDefs.find(t => t.id === tabId)) tabId = tabDefs[0].id;
    const tabIdx = tabDefs.findIndex(t => t.id === tabId);
    const openCount = s.comments.filter(c => c.status === 'drafting' || c.status === 'draft').length;
    const sideTabs = tabDefs.map(t => ({ label: t.label, on: t.id === tabId, cls: t.id === tabId ? 'is-on' : '', hasCount: t.id === 'comments' && openCount > 0, count: String(openCount), pick: () => this.setState({ sideTab: t.id }) }));

    /* bible (editable) */
    const isEn = lang === 'en';
    const fcls = lang === 'hi' || lang === 'mr' ? 'f-hi' : D.LANGS[lang] ? 'f-' + lang : '';
    const bible = Object.keys(s.terms).map((k, i) => {
      const t = s.terms[k];
      const val = s.bibleEdit[k] !== undefined ? s.bibleEdit[k] : t.val;
      return { kind: t.kind, src: t.src, val, inId: 'bible-' + k, aria: 'Adapted ' + (t.kind || '').toLowerCase() + ' for ' + t.src,
        fcls, nlang: lang, gloss: [t.en, t.short && t.short !== t.val ? 'called ' + t.short : ''].filter(Boolean).join(' · '),
        enter: () => this.setState({ bibleHover: i }),
        onInput: e => { const v = e.target.value; this.setState(st => ({ bibleEdit: Object.assign({}, st.bibleEdit, { [k]: v }) })); },
        onKey: e => { if (e.key === 'Enter') { e.preventDefault(); e.target.blur(); } if (e.key === 'Escape') { e.stopPropagation(); const be = Object.assign({}, this.state.bibleEdit); delete be[k]; this.setState({ bibleEdit: be }); } },
        commit: () => this.commitBible(k) };
    });

    /* comments */
    const comments = s.comments.map(c => {
      const d = c.draft;
      const rows = d && d.rows ? d.rows.map(r => ({ where: r.where, before: r.before, after: r.after, cls: r.bodyRow ? bodyCls : '', lang: r.bodyRow ? htmlLang : 'en' })) : [];
      const label = { drafting: 'Drafting…', draft: 'Draft ready', applied: 'Resolved', discarded: 'Undone', failed: 'Couldn’t draft this' }[c.status];
      return { quote: '“' + c.quote + '”', text: c.text, statusLabel: label, drafting: c.status === 'drafting', hasDraft: c.status === 'draft',
        isPersona: !!d && d.kind === 'persona', isStory: !d || d.kind === 'story', cls: c.status === 'applied' || c.status === 'discarded' ? 'is-done' : '',
        rows, prows: d && d.prows ? d.prows : [], more: !!(d && d.more), moreLabel: d && d.more ? '+ ' + d.more + ' more lines change the same way' : '',
        keep: () => this.keepComment(c), undo: () => this.setComment(c.id, { status: 'discarded' }) };
    });

    /* prompt */
    const pr = s.prompt;
    const mentionM = pr.match(/@([^\s@]*)$/), slashM = pr.match(/^\/(\S*)$/);
    const ments = Object.keys(s.terms).map(k => ({ label: s.terms[k].en || s.terms[k].short, kind: s.terms[k].kind }));
    const mentionList = mentionM ? ments.filter(m => (m.label || '').toLowerCase().indexOf(mentionM[1].toLowerCase()) === 0).map(m => ({ label: m.label, kind: m.kind, pick: () => { this.setState({ prompt: pr.replace(/@([^\s@]*)$/, '@' + m.label + ' ') }); this.promptEl && this.promptEl.focus(); } })) : [];
    const slashList = slashM ? D.CMDS.filter(c => c.cmd.indexOf('/' + slashM[1]) === 0).map(c => ({ cmd: c.cmd, hint: c.hint, pick: () => { this.setState({ prompt: c.cmd + ' ' }); this.promptEl && this.promptEl.focus(); } })) : [];
    const liveRoute = s.route || (pr.trim() ? this.classify(pr) : null);

    /* narrate */
    const fr = this.sentFracs();
    const prog = dur ? Math.min(1, s.t / dur) : 0;
    const realBars = ready && s.audio && s.audio.bars;
    const bars = Array.from({ length: 64 }, (_, i) => ({ h: realBars ? s.audio.bars[i] : Math.round(26 + 64 * Math.abs(Math.sin(i * 0.61) * Math.cos(i * 0.23))), cls: i / 64 < prog ? 'on' : '' }));
    const tmarks = TW.map(t => { const x = fr.find(y => y.sid === t.reveal_sid); return { left: x ? (x.f * 100).toFixed(2) : '0' }; });
    const readIdx = readSid ? ss.findIndex(x => x.sid === readSid) : -1;
    const readSents = ss.map((x, i) => {
      const cue = (x.line && x.line.cue) || 'none';
      const isReveal = !!(x.line && x.line.twist_role === 'reveal');
      const emoHere = cue !== 'none';                                       // every cued line shows its cue chip
      return { domId: 'read-' + x.sid, text: this.resolve(x.raw), current: x.sid === readSid ? 'true' : 'false',
        cls: x.sid === readSid ? 'is-read' : (readIdx > i ? 'is-past' : ''),
        emoHere, emo: cue, emoOpen: s.emoPop === x.sid, emoAria: 'Narration cue: ' + cue + '. Change',
        openEmo: () => { this._emoFocused = false; this.setState({ emoPop: s.emoPop === x.sid ? null : x.sid }); },
        emoOpts: (isReveal ? ['shock'] : D.EMOS.concat(['none'])).map((e, j) => ({ label: e, on: e === cue, ref: j === 0 ? (el => { if (el && !this._emoFocused) { this._emoFocused = true; el.focus(); } }) : null,
          pick: () => { this.setState({ emoPop: null }); if (e === cue) return; this.markStale(); this.save({ cues: { [x.sid]: e } }); } })) };
    });
    const pIdx = Math.max(0, D.PERSONAS.findIndex(p => p.id === s.persona));
    const personas = D.PERSONAS.map(p => ({ name: p.name, desc: p.desc, on: p.id === s.persona, cls: p.id === s.persona ? 'is-on' : '', pick: () => this.setPersona(p.id) }));
    const orbCls = s.narr === 'generating' || (s.aiBusy && isNarrate) ? 'orb-think' : s.narr === 'error' ? 'orb-err orb-idle' : s.playing ? 'orb-speak' : 'orb-idle';
    const genLines = ['Reading the room…', 'Marking the twists…', 'Finding the voice…'].map((text, i) => ({ text, on: i === s.genStep }));
    const readNum = readIdx >= 0 ? readIdx + 1 : 0;

    const cmdAll = s.cmdOpen ? this.cmdAll() : [];
    const cIdx = Math.min(s.cmdIdx, Math.max(0, cmdAll.length - 1));
    const cmdItems = cmdAll.map((c, i) => ({ label: c.label, group: c.group, on: i === cIdx, cls: i === cIdx ? 'is-on' : '', run: () => { this.setState({ cmdOpen: false }); c.run(); }, hover: () => this.setState({ cmdIdx: i }) }));

    const d = s.draft;
    const draftRows = d && d.rows ? d.rows.map((r, i) => ({ where: r.where, before: r.before, after: r.after, d: i * 70, cls: r.bodyRow ? bodyCls : '', lang: r.bodyRow ? htmlLang : 'en' })) : [];
    const draftProws = d && d.prows ? d.prows.map((r, i) => Object.assign({}, r, { d: i * 70 })) : [];
    const sideOpen = s.sideOpen || s.sheet === 'side';

    return {
      stages: D.STAGES.map((st, i) => ({ label: st.label, num: String(i + 1), disabled: i > s.maxStage, current: i === stIdx ? 'step' : 'false', cls: i === stIdx ? 'is-on' : '', go: () => this.goStage(st.id) })),
      stepX: stIdx * 100, statusText, statusDot, statusCls,
      openCmd: () => this.setState({ cmdOpen: true, cmdQ: '', cmdIdx: 0 }),
      onRootKey: e => {
        if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); this.setState(st => ({ cmdOpen: !st.cmdOpen, cmdQ: '', cmdIdx: 0 })); return; }
        if (e.key === 'Escape') {
          if (s.cmdOpen) this.setState({ cmdOpen: false }); else if (s.draft) this.undoDraft(); else if (s.emoPop) this.setState({ emoPop: null }); else if (s.composerOpen || s.sel) this.setState({ sel: null, composerOpen: false }); else if (s.sheet) this.setState({ sheet: null });
        }
      },
      autoFocus: el => { if (el && el !== this._af) { this._af = el; el.focus(); } },
      isSource, isAdapt, isStoryish, isNarrate, isEdit: s.stage === 'edit', isWorkspace: !isSource,

      /* source */
      source: s.source, sourceEmpty: !s.source.trim(), sourceFilled: !!s.source.trim(),
      wordsLabel: words ? words.toLocaleString('en-IN') + ' words · ~' + Math.max(1, Math.round(words / 230)) + ' min read' : 'Nothing pasted yet',
      onSource: e => this.setState({ source: e.target.value }),
      useSample: () => this.setState({ source: D.SAMPLE }), clearSource: () => this.setState({ source: '' }),
      culture: s.culture, onCulture: e => this.setState({ culture: e.target.value }),
      langValue: lang,
      otherLangs: D.OTHER.map(o => ({ name: D.LANGS[o], value: o })),
      onLang: e => this.setState({ lang: e.target.value }),
      craft: () => this.craft(), craftDisabled: !s.source.trim() || words < 5,
      ctaNote: cfg && !cfg.llm_ready ? 'Writing model key missing — see backend/.env' : (s.source.trim() ? 'India · ' + this.langName() : 'Paste a story to begin'),

      /* adapt errors */
      adaptErr: !!s.adaptErr, adaptErrText: s.adaptErr, backToSource: () => { history.replaceState(null, '', location.pathname); this.setState({ stage: 'source', maxStage: 0, adaptErr: '' }); }, retryCraft: () => this.craft(),

      /* panes */
      centerRef: el => { this.centerEl = el; },
      sideW: s.sideW, sideSheetCls: s.sheet === 'side' ? 'is-sheet' : '',
      rzDown: e => { e.currentTarget.setPointerCapture(e.pointerId); this._drag = { x: e.clientX, w: s.sideW }; },
      rzMove: e => { const g = this._drag; if (!g) return; this.setState({ sideW: Math.min(560, Math.max(320, g.w - (e.clientX - g.x))) }); },
      rzUp: () => { this._drag = null; },
      rzKey: e => { if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); this.setState({ sideW: Math.min(560, Math.max(320, s.sideW + (e.key === 'ArrowLeft' ? 16 : -16))) }); } },
      sideOpen, sideClosed: !sideOpen, closeSide: () => this.setState({ sideOpen: false, sheet: null }), openSide: () => this.setState({ sideOpen: true }),
      openSideSheet: () => this.setState({ sheet: 'side' }), sheetOpen: !!s.sheet, closeSheet: () => this.setState({ sheet: null }),
      sideTitle: isAdapt ? 'Progress' : isNarrate ? 'Narration' : 'Review',

      /* story */
      skelLines: [100, 96, 100, 88, 100, 92, 100, 97, 84, 60].map(w => ({ w })),
      sents, bodyCls, htmlLang, langName: this.langName(), durLabel: this.fmt(dur), twistBadge: twLabel, storyTitle: s.title || 'Adapted story',
      isPlaceholderLang: false, placeholderNote: '',
      onStoryMouseUp: () => this.captureSelection(),

      /* comment composer */
      showCPill: !!s.sel && !s.composerOpen && isStoryish, showComposer: !!s.sel && s.composerOpen && isStoryish,
      selX: s.sel ? Math.round(s.sel.x) : 0, selY: s.sel ? Math.round(s.sel.y) : 0, selQuote: s.sel ? s.sel.text : '',
      keepSel: e => e.preventDefault(),
      openComposer: () => this.setState({ composerOpen: true }),
      composerText: s.composerText, onComposer: e => this.setState({ composerText: e.target.value }),
      composerEmpty: !s.composerText.trim(),
      composerPh: s.sel && this.termKeyFor(s.sel.text) ? 'New name, e.g. “Arjun”' : 'What should change here?',
      composerKey: e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.submitComment(); } if (e.key === 'Escape') { e.stopPropagation(); this.setState({ sel: null, composerOpen: false }); } },
      cancelComposer: () => this.setState({ sel: null, composerOpen: false, composerText: '' }),
      submitComment: () => this.submitComment(),

      /* working */
      steps, thinkLines, traceOpen: s.traceOpen, traceLabel: s.traceOpen ? 'Hide trace' : 'Show trace', toggleTrace: () => this.setState({ traceOpen: !s.traceOpen }),
      elapsedLabel: s.elapsed.toFixed(1) + 's', notAdaptErr: !s.adaptErr,
      hasLive: isAdapt && !s.adaptErr && !!(s.live && s.live.lines && s.live.lines.length),
      showSkel: isAdapt && !s.adaptErr && !(s.live && s.live.lines && s.live.lines.length),
      liveTitle: s.live ? s.live.label : '', liveMeta: s.live ? (s.live.chars || 0).toLocaleString('en-IN') + ' chars' : '',
      liveLines: (s.live && s.live.lines || []).map((l, i, a) => ({ text: l.text, cls: l.cls || '', lang: /story-/.test(l.cls || '') ? lang : 'en', open: !!l.open && i === a.length - 1 })),
      liveRef: el => { this.liveEl = el; },

      /* side */
      hasSideTabs: !isAdapt, sideTabs, tabX: tabIdx * 100,
      tabComments: tabId === 'comments', tabVoice: tabId === 'voice', tabBible: tabId === 'bible',
      comments, noComments: s.comments.length === 0,
      glossary: (s.glossary || []).map(g => ({ src: g.source_term, dst: g.target_term })), hasGlossary: !!(s.glossary && s.glossary.length),
      bible, glideY: Math.max(0, s.bibleHover) * 72, glideO: s.bibleHover < 0 ? 0 : 1, bibleLeave: () => this.setState({ bibleHover: -1 }),

      /* prompt */
      showPrompt: isStoryish || isNarrate, prompt: s.prompt, promptRows: Math.min(5, Math.max(1, pr.split('\n').length)),
      promptPh: isNarrate ? 'Ask for a different voice, pace or mood…' : 'Ask for an edit… @ a character, / for commands',
      onPrompt: e => this.setState({ prompt: e.target.value }),
      onPromptKey: e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); this.send(); } if (e.key === 'Escape' && s.prompt) { e.stopPropagation(); this.setState({ prompt: '', route: null }); } },
      promptRef: el => { this.promptEl = el; },
      send: () => this.send(), sendDisabled: !pr.trim(),
      stop: () => { if (this._abort) this._abort.abort(); this.setState({ aiBusy: false }); this.toast('Stopped'); },
      aiBusy: s.aiBusy, notBusy: !s.aiBusy, pbarCls: s.aiBusy ? 'is-busy' : '',
      showMention: mentionList.length > 0, mentionList, showSlash: slashList.length > 0, slashList,
      showRoute: !!liveRoute, routeX: liveRoute === 'persona' ? 100 : 0,
      routeIsStory: liveRoute === 'story', routeIsPersona: liveRoute === 'persona',
      routeStoryCls: liveRoute === 'story' ? 'is-on' : '', routePersonaCls: liveRoute === 'persona' ? 'is-on' : '',
      setRouteStory: () => this.setState({ route: 'story' }), setRoutePersona: () => this.setState({ route: 'persona' }),
      showGoNarrate: isStoryish, goNarrate: () => this.goStage('narrate'),

      /* draft modal */
      hasDraft: !!d, draftIsStory: !!d && d.kind === 'story', draftIsPersona: !!d && d.kind === 'persona',
      draftTitle: d ? d.title : '', draftSub: d ? d.sub : '', draftRows, draftProws,
      draftMore: !!(d && d.more), draftMoreLabel: d && d.more ? '+ ' + d.more + ' more lines change the same way' : '',
      keepDraft: () => this.keepDraft(), undoDraft: () => this.undoDraft(),
      keepRef: el => { if (el && el !== this._kf) { this._kf = el; el.focus(); } },
      modalKey: e => { if (e.key === 'Escape') { e.stopPropagation(); this.undoDraft(); } },
      toasts: s.toasts.map(t => ({ text: t.text, hasUndo: !!t.undo, undo: () => { t.undo(); this.dismiss(t.id); this.toast('Undone'); }, dismiss: () => this.dismiss(t.id) })),

      /* narrate */
      orbCls, orbScale: s.playing ? (1 + s.amp * 0.12).toFixed(3) : '1',
      narrGenerating: s.narr === 'generating', narrReady: ready, narrError: s.narr === 'error', narrErrText: s.narrErr || 'The voice service didn’t answer. Your story and settings are safe.',
      narrIdleLabel: s.narr === 'idle' || s.narr === 'error', genLines,
      showGenerate: s.narr === 'idle', generate: () => this.generate(), generateLabel: s.stale ? 'Hear it again' : 'Narrate',
      stale: s.stale, justReady: s.justReady,
      readyLabel: (s.playing ? 'Narrating · ' : 'Ready · ') + D.PERSONAS[pIdx].name,
      personaName: D.PERSONAS[pIdx].name, paceLabel: s.pace.toFixed(2) + '×',
      playing: s.playing, notPlaying: !s.playing, playerOff: !ready, playAria: s.playing ? 'Pause narration' : 'Play narration',
      togglePlay: () => this.togglePlay(),
      bars, tmarks, seekVal: Math.round(prog * 1000), seek: e => { const t = (+e.target.value / 1000) * dur; if (this.player) this.player.currentTime = t; this.setState({ t }); },
      timeLabel: this.fmt(s.t) + ' / ' + this.fmt(dur), progPct: (prog * 100).toFixed(1),
      nowLabel: ready ? 'Line ' + readNum + ' of ' + ss.length : 'Not generated yet',
      readSents, follow: s.follow, toggleFollow: e => this.setState({ follow: e.target.checked }),
      popKey: e => { if (e.key === 'Escape') { e.stopPropagation(); this.setState({ emoPop: null }); } },
      ...this.voiceVals(),
      personas, pglideY: pIdx * 84, pace: s.pace, paceFill: ((s.pace - 0.8) / 0.4 * 100).toFixed(1),
      paceTicks: Array.from({ length: 9 }, (_, i) => ({ left: (i / 8 * 100).toFixed(1) })),
      onPace: e => {
        const v = Math.round(+e.target.value * 20) / 20; if (v === s.pace) return;
        this.markStale(); this.setState({ pace: v });
        clearTimeout(this._paceT); this._paceT = setTimeout(() => this.save(['pace']), 400);
      },
      onCenterScroll: e => { if (!isNarrate) return; const m = e.target.scrollTop > 380; if (m !== this.state.mini) this.setState({ mini: m }); },
      showIsland: isNarrate && s.mini && ready,
      scrollTop: () => { if (this.centerEl) this.centerEl.scrollTop = 0; },

      cmdOpen: s.cmdOpen, cmdQ: s.cmdQ, cmdItems, cmdEmpty: s.cmdOpen && cmdAll.length === 0,
      closeCmd: () => this.setState({ cmdOpen: false }),
      onCmdQ: e => this.setState({ cmdQ: e.target.value, cmdIdx: 0 }),
      onCmdKey: e => {
        if (e.key === 'ArrowDown') { e.preventDefault(); this.setState({ cmdIdx: Math.min(cmdAll.length - 1, cIdx + 1) }); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); this.setState({ cmdIdx: Math.max(0, cIdx - 1) }); }
        else if (e.key === 'Enter') { e.preventDefault(); const c = cmdAll[cIdx]; if (c) { this.setState({ cmdOpen: false }); c.run(); } }
        else if (e.key === 'Escape') { e.stopPropagation(); this.setState({ cmdOpen: false }); }
      }
    };
  }
}
