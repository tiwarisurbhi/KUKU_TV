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
    if (p.audio) Object.assign(patch, { audio: p.a