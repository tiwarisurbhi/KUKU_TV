"""Build frontend/index.html = design template (design/Main.dc.html) + live bindings + logic.js.

The design file stays untouched so a new export from the design tool can be dropped in and rebuilt.
Run: python3 frontend/build.py
"""
from pathlib import Path

HERE = Path(__file__).parent
CSS_EXTRA = r"""
/* ===== Scripts beyond the design file: Gurmukhi, Gujarati, Tamil, Telugu, Kannada, Malayalam ===== */
:root{--guru:'Noto Sans Gurmukhi','Geist',sans-serif;--gujr:'Noto Sans Gujarati','Geist',sans-serif;--taml:'Noto Sans Tamil','Geist',sans-serif;--telu:'Noto Sans Telugu','Geist',sans-serif;--knda:'Noto Sans Kannada','Geist',sans-serif;--mlym:'Noto Sans Malayalam','Geist',sans-serif}
.body-pa,.body-gu,.body-ta,.body-te,.body-kn,.body-ml{margin:0;letter-spacing:0;text-transform:none;font-style:normal;word-break:keep-all;overflow-wrap:normal;font-size:18px;line-height:1.85}
.body-ta,.body-ml{word-break:normal;overflow-wrap:anywhere;font-size:17px}
.body-pa{font-family:var(--guru)}.body-gu{font-family:var(--gujr)}.body-ta{font-family:var(--taml)}.body-te{font-family:var(--telu)}.body-kn{font-family:var(--knda)}.body-ml{font-family:var(--mlym)}
.mdiff .b [class^="body-"],.mdiff .a [class^="body-"]{font-size:15px;line-height:1.75}
.dtext [class^="body-"]{font-size:16px;line-height:1.75}
.dt-in.f-pa{font-family:var(--guru)}.dt-in.f-gu{font-family:var(--gujr)}.dt-in.f-ta{font-family:var(--taml)}.dt-in.f-te{font-family:var(--telu)}.dt-in.f-kn{font-family:var(--knda)}.dt-in.f-ml{font-family:var(--mlym)}
.ll.story-pa,.ll.story-gu,.ll.story-mr,.ll.story-ta,.ll.story-te,.ll.story-kn,.ll.story-ml{font-size:16px;line-height:1.85}
.ll.story-pa{font-family:var(--guru)}.ll.story-gu{font-family:var(--gujr)}.ll.story-mr{font-family:var(--deva)}.ll.story-ta{font-family:var(--taml)}.ll.story-te{font-family:var(--telu)}.ll.story-kn{font-family:var(--knda)}.ll.story-ml{font-family:var(--mlym)}
.gl{display:flex;flex-direction:column;border:1px solid var(--line);border-radius:12px;overflow:hidden;margin-bottom:12px}
.gl-row{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:9px 14px;border-top:1px solid var(--line);font-size:13px}
.gl-row:first-child{border-top:0}
.gl-dst{font-size:15px!important;line-height:1.4!important;text-align:right}

/* ===== Narrator voice (Voice tab) ===== */
.vcard{display:flex;gap:12px;align-items:flex-start;padding:14px;border:1px solid var(--line2);border-radius:var(--r-card);background:var(--raised)}
.vplay{width:36px;height:36px;flex:none;border-radius:50%;display:grid;place-items:center;background:var(--accent);color:var(--on-accent);transition:transform 150ms var(--spring)}
.vplay:hover{transform:scale(1.06)}.vplay.is-on{box-shadow:0 0 0 4px var(--accent-soft)}
.vplay.sm{width:28px;height:28px;background:var(--raised2);color:var(--text);border:1px solid var(--line2)}
.vmeta{min-width:0}.vmeta b{display:block;font-size:14px}.vmeta small{display:block;color:var(--muted);font-size:12px;margin-top:2px}
.vmeta p{margin:8px 0 0;font-size:13px;line-height:1.5;color:var(--text);opacity:.85}
.vlist{margin-top:10px;border:1px solid var(--line);border-radius:12px;max-height:320px;overflow:auto}
.vrow{display:flex;align-items:center;gap:10px;padding:8px 12px;border-top:1px solid var(--line)}
.vrow:first-child{border-top:0}.vrow.is-on{background:var(--accent-soft)}
.vpick{flex:1;text-align:left;min-width:0}.vpick b{display:block;font-size:13px}.vpick small{display:block;color:var(--muted);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.vrow .pk{color:var(--accent)}

/* ===== Live model stream (Adapt) ===== */
.live{background:var(--surface);border:1px solid var(--line);border-radius:var(--r-card);padding:16px 20px 18px;margin-bottom:16px;animation:fadeUp 260ms var(--ease) both}
.live-h{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--ai);margin-bottom:12px}
.live-m{margin-left:auto;color:var(--muted);font-size:12px}
.ldot{width:8px;height:8px;border-radius:50%;background:var(--ai);flex:none;animation:lpulse 1.4s ease-out infinite}
@keyframes lpulse{0%{box-shadow:0 0 0 0 rgba(142,123,255,.6)}70%{box-shadow:0 0 0 9px rgba(142,123,255,0)}100%{box-shadow:0 0 0 0 rgba(142,123,255,0)}}
.live-body{max-height:min(46vh,420px);overflow:auto;display:flex;flex-direction:column;gap:8px;padding-right:4px;-webkit-mask-image:linear-gradient(to bottom,transparent 0,#000 24px);mask-image:linear-gradient(to bottom,transparent 0,#000 24px);scroll-behavior:smooth}
.ll{font-size:14px;line-height:1.6;color:var(--text)}
.ll.ll-think{color:var(--ai);font-style:italic;opacity:.85}
.ll.meta{color:var(--muted);font-size:13px}
.ll.twist{color:#D8CBB0;padding-left:10px;border-left:2px solid rgba(242,180,65,.32)}
.ll.story-hi{font-family:var(--deva);font-size:16px;line-height:1.85}
.ll.story-bn{font-family:var(--beng);font-size:16px;line-height:1.85}
.ll.story-or{font-family:var(--orya);font-size:16px;line-height:1.85}
.ll.story-en{font-family:var(--serif);font-size:17px;line-height:1.7}
.ll.title{font-size:19px;font-weight:600}
.caret{display:inline-block;width:2px;height:1.1em;margin-left:2px;vertical-align:text-bottom;background:var(--ai);border-radius:1px;animation:blink 1s steps(1) infinite}
@keyframes blink{50%{opacity:0}}

/* ===== "Story looks good — Narrate": a slow violet light running along the border only ===== */
@property --gx{syntax:'<angle>';inherits:false;initial-value:0deg}
.go-narr{position:relative;border:1.5px solid transparent;color:var(--text);
  background:linear-gradient(var(--surface),var(--surface)) padding-box,
             conic-gradient(from var(--gx),#4C3A9E,#8E7BFF,#C4B5FD,#8E7BFF,#4C3A9E 50%,#2E2566 75%,#4C3A9E) border-box;
  animation:gspin 4s linear infinite}
.go-narr:hover{color:#fff;border-color:transparent;transform:translateY(-1px);
  background:linear-gradient(var(--raised),var(--raised)) padding-box,
             conic-gradient(from var(--gx),#6D5AE6,#A594FF,#DDD6FE,#A594FF,#6D5AE6 50%,#4C3A9E 75%,#6D5AE6) border-box}
@keyframes gspin{to{--gx:360deg}}
@media (prefers-reduced-motion:reduce){.go-narr{animation:none}}
"""
src = (HERE / "design" / "Main.dc.html").read_text(encoding="utf-8")
tpl = src[:src.index('<script type="text/x-dc"')]


def rep(old, new):
    global tpl
    assert tpl.count(old) == 1, f"design changed, patch not found: {old[:70]!r}"
    tpl = tpl.replace(old, new)


start = tpl.index('<select id="lang"')
end = tpl.index("</select>", start) + len("</select>")
rep(tpl[start:end], '''<select id="lang" class="sel" value="{{langValue}}" onChange="{{onLang}}">
          <option value="hi">Hindi</option>
          <option value="bn">Bengali</option>
          <option value="or">Odia</option>
          <optgroup label="More languages">
            <sc-for list="{{otherLangs}}" as="ol" hint-placeholder-count="6"><option value="{{ol.value}}">{{ol.name}}</option></sc-for>
          </optgroup>
        </select>''')
rep('<span class="badge ok">6 twists kept in order</span>', '<span class="badge ok">{{twistBadge}}</span>')
rep('<h2>Adapted story</h2>', '<h2>{{storyTitle}}</h2>')
rep('<span>The voice service didn’t answer. Your story and settings are safe.</span>', '<span>{{narrErrText}}</span>')
rep('''          </section>
          <div class="skel-page" aria-hidden="true">
            <sc-for list="{{skelLines}}" as="k" hint-placeholder-count="10"><span class="skel" style="height: 14px; width: {{k.w}}%"></span></sc-for>
          </div>''', '''          </section>
          <sc-if value="{{adaptErr}}" hint-placeholder-val="{{ false }}">
            <div class="errcard" role="alert" style="margin-top: 16px">
              <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" style="flex: none"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v6M12 16.5v.5"></path></svg>
              <span style="flex: 1">{{adaptErrText}}</span>
              <button class="btn btn-g btn-sm" onClick="{{backToSource}}">Edit source</button>
              <button class="btn btn-g btn-sm" onClick="{{retryCraft}}">Retry</button>
            </div>
          </sc-if>
          <s