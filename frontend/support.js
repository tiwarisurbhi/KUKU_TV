// GENERATED from dc-runtime/src/*.ts - do not edit. Rebuild with `bun build.ts` (see the package README for the source-only recipe).
"use strict";(()=>{var Mt=Object.defineProperty,Tt=(t,n,e)=>n in t?Mt(t,n,{enumerable:!0,configurable:!0,writable:!0,value:e}):t[n]=e,T=(t,n,e)=>Tt(t,typeof n!="symbol"?n+"":n,e);function L(){const t=window.React;if(!t)throw new Error("dc-runtime: window.React is not available yet");return t}function Lt(){const t=window.ReactDOM;if(!t)throw new Error("dc-runtime: window.ReactDOM is not available yet");return t}var A=((...t)=>L().createElement(...t));function Ot(t){const n=t.querySelector("x-dc");if(!n)return null;const e=t.querySelector("script[data-dc-script]"),{props:o,preview:r}=B(e?.getAttribute("data-props")??null);return{template:n.innerHTML,js:e&&e.textContent||"",props:o,preview:r}}function tt(t){const n=/<x-dc(?:\s[^>]*)?>/.exec(t);if(!n)return null;const e=t.lastIndexOf("</x-dc>");if(e===-1||e<n.index)return null;const o=t.slice(n.index+n[0].length,e),s=new DOMParser().parseFromString(t,"text/html").querySelector("script[data-dc-script]"),{props:i,preview:a}=B(s?.getAttribute("data-props")??null);return{template:o,js:s&&s.textContent||"",props:i,preview:a}}function B(t){if(!t)return{props:null,preview:null};let n;try{n=JSON.parse(t)}catch{return{props:null,preview:null}}if(!n||typeof n!="object"||Array.isArray(n))return{props:null,preview:null};const e=n,o=e.$preview&&typeof e.$preview=="object"?e.$preview:null,r={};for(const s of Object.keys(e))s[0]!=="$"&&(r[s]=e[s]);return{props:Object.keys(r).length?r:null,preview:o}}function Pt(t){let n=t||"";try{n=decodeURIComponent(n)}catch{}return(n.split("/").pop()||"Root").replace(/\.dc\.html$|\.html?$/,"")||"Root"}var Dt=`
    .sc-placeholder{background:color-mix(in srgb,currentColor 8%,transparent);
      border:1px solid color-mix(in srgb,currentColor 50%,transparent);
      border-radius:2px;box-sizing:border-box;overflow:hidden}
    @keyframes sc-shine{0%{background-position:100% 50%}100%{background-position:0% 50%}}
    html.sc-dc-streaming .sc-placeholder,
    html.sc-dc-streaming .sc-interp.sc-missing{position:relative;
      background:color-mix(in srgb,currentColor 5%,transparent);
      border-color:transparent}
    html.sc-dc-streaming .sc-placeholder::before,
    html.sc-dc-streaming .sc-interp.sc-missing::before{content:'';
      position:absolute;inset:0;pointer-events:none;
      background:linear-gradient(90deg,rgba(217,119,87,0) 25%,rgba(247,225,211,.95) 37%,rgba(217,119,87,0) 63%);
      background-size:400% 100%;animation:sc-shine 1.4s ease infinite}
    html.sc-dc-streaming .sc-placeholder:nth-child(n+9 of .sc-placeholder)::before,
    html.sc-dc-streaming .sc-interp.sc-missing:nth-child(n+9 of .sc-interp.sc-missing)::before{animation:none;
      background:color-mix(in srgb,currentColor 8%,transparent)}
    .sc-placeholder-error{padding:4px 8px;font:11px/1.4 ui-monospace,monospace;
      color:color-mix(in srgb,currentColor 70%,transparent);word-break:break-word}
    .sc-interp.sc-missing{display:inline-block;width:2em;height:1em;overflow:hidden;
      vertical-align:text-bottom;background:rgba(255,255,255,.3);border:1px solid rgba(0,0,0,.5);
      border-radius:2px;box-sizing:border-box;color:transparent;
      user-select:none}
    .sc-interp.sc-unresolved{font-family:ui-monospace,monospace;font-size:.85em;
      color:color-mix(in srgb,currentColor 50%,transparent);
      background:color-mix(in srgb,currentColor 10%,transparent);border-radius:3px;
      padding:0 3px}
    .sc-host.sc-has-error{position:relative}
    .sc-logic-error{position:absolute;top:8px;left:8px;z-index:2147483647;max-width:60ch;
      padding:6px 10px;background:#b00020;color:#fff;font:12px/1.4 ui-monospace,monospace;
      border-radius:4px;white-space:pre-wrap;pointer-events:none}
    /* Mirrors PRINT_BASELINE_CSS in apps/web deck-stage-export.ts \u2014 keep both
       in sync until dc-runtime regains a build step. */
    @media print {
      @page { margin: 0.5cm; }
      figure, table { break-inside: avoid; }
      #dc-root, #dc-root > .sc-host { height: auto; }
      *, *::before, *::after {
        print-color-adjust: exact; -webkit-print-color-adjust: exact;
        backdrop-filter: none !important; -webkit-backdrop-filter: none !important;
        animation-delay: -99s !important; animation-duration: .001s !important;
        animation-iteration-count: 1 !important; animation-fill-mode: both !important;
        animation-play-state: running !important; transition-duration: 0s !important;
      }
    }
  `,jt="html,body{height:100%;margin:0}#dc-root,#dc-root>.sc-host{height:100%}";function It(t,n){let e=n.pathname||"";if(!/\.dc\.html?$/i.test(zt(e)))try{e=new URL(t.baseURI||"/").pathname}catch{}return Pt(e)}function zt(t){try{return decodeURIComponent(t)}catch{return t}}function Ut(t,n=document){const e=Ot(n);if(!e)return null;const o=L(),r=It(n,location);t.markFetched(r),t.setRootName(r),t.adoptParsed(r,e),window.__resources||fetch(location.href).then(_=>_.ok?_.text():"").then(_=>{const u=_?tt(_):null;u?.template&&t.updateHtml(r,u.template)}).catch(()=>{});const s=n.querySelector("x-dc"),i=n.createElement("div");if(i.id="dc-root",s.replaceWith(i),!e.preview){const _=n.createElement("style");_.textContent=jt,n.head.appendChild(_)}const a=t.getDC(r),f=t.registry.get(r);function l(){const[,_]=o.useState(0);o.useEffect(()=>{const d=()=>_(g=>g+1);return f.subs.add(d),()=>{f.subs.delete(d)}},[]);const u=o.useMemo(()=>{const d={};for(const g in f.propsMeta||{}){const m=f.propsMeta?.[g]?.default;m!==void 0&&(d[g]=m)}return d},[f.propsMeta]);return A(a,{...u,...f.propOverrides||{}})}const c=Lt();return c.createRoot?c.createRoot(i).render(A(l)):c.render(A(l),i),r}var et=/^[A-Za-z_$][A-Za-z0-9_$]*/,Gt=/^-?\d+(\.\d+)?$/;function P(t,n){const e=String(n).trim();if(!e)return;if(e[0]==="("&&e[e.length-1]===")"&&Ft(e))return P(t,e.slice(1,-1));const o=Bt(e);if(o){const r=P(t,e.slice(0,o.index)),s=P(t,e.slice(o.index+o.op.length));switch(o.op){case"===":return r===s;case"!==":return r!==s;case"==":return r==s;default:return r!=s}}if(e[0]==="!")return!P(t,e.slice(1));if(e==="true")return!0;if(e==="false")return!1;if(e==="null")return null;if(e!=="undefined")return Gt.test(e)?Number(e):e.length>=2&&(e[0]==='"'||e[0]==="'")&&e[e.length-1]===e[0]?e.slice(1,-1):Wt(t,e)}function Ft(t){let n=0;for(let e=0;e<t.length-1;e++)if(t[e]==="(")n++;else if(t[e]===")"&&(n--,n===0))return!1;return!0}function Bt(t){let n=0;for(let e=0;e<t.length;e++){const o=t[e];if(o==="["||o==="(")n++;else if(o==="]"||o===")")n--;else if(n===0&&(o==="="||o==="!")&&t[e+1]==="="){if(e>0&&(t[e-1]==="="||t[e-1]==="!")||!t.slice(0,e).trim())continue;const r=t[e+2]==="="?o+"==":o+"=";return{index:e,op:r}}}return null}function Wt(t,n){const e=n.match(et);if(!e)return;let o=t?.[e[0]],r=e[0].length;for(;r<n.length;)if(n[r]==="."){const s=n.slice(r+1).match(et)||n.slice(r+1).match(/^\d+/);if(!s)return;o=o?.[s[0]],r+=1+s[0].length}else if(n[r]==="["){let s=1,i=r+1;for(;i<n.length&&s>0;){if(n[i]==="[")s++;else if(n[i]==="]"&&(s--,s===0))break;i++}if(s!==0)return;const a=P(t,n.slice(r+1,i));o=o?.[a],r=i+1}else return;return o}var W="sc-camel-",$t=new Set("a abbr b bdi bdo br cite code del dfn em i ins kbd mark q s samp small span strike strong sub sup u var wbr".split(" ")),nt={select:"sc-raw-select",table:"sc-raw-table",tbody:"sc-raw-tbody",thead:"sc-raw-thead",tfoot:"sc-raw-tfoot",tr:"sc-raw-tr",td:"sc-raw-td",th:"sc-raw-th",caption:"sc-raw-caption"},ot=Object.fromEntries(Object.entries(nt).map(([t,n])=>[n,t])),qt=new Set("allowFullScreen async autoFocus autoPlay checked controls default defer disabled disablePictureInPicture disableRemotePlayback formNoValidate hidden itemScope loop multiple muted noModule noValidate open playsInline readOnly required reversed scoped seamless selected".split(" ")),Ht={onclick:"onClick",onchange:"onChange",oninput:"onInput",onsubmit:"onSubmit",onkeydown:"onKeyDown",onkeyup:"onKeyUp",onkeypress:"onKeyPress",onmousedown:"onMouseDown",onmouseup:"onMouseUp",onmouseenter:"onMouseEnter",onmouseleave:"onMouseLeave",onfocus:"onFocus",onblur:"onBlur",ondoubleclick:"onDoubleClick",on