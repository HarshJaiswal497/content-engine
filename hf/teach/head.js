window.__timelines = window.__timelines || {};
const tl = gsap.timeline({ paused: true });
const D = %%D%%;
const B = D.beats, W = D.words, CH = D.chunks, NAME = D.name;
const IMP = [];
const CARDOF = D.cardof;
// a hit: shakes + flashes the card and shakes the caption, and drops a ripple into the background
function hit(card, t, amp, at) {
  const k = 8 * amp;
  tl.fromTo(card, { x: 0 }, { x: k, duration: .045, yoyo: true, repeat: 7, ease: "none" }, t);
  tl.fromTo(card + " .cf", { opacity: .55 * Math.min(amp, 1.2) }, { opacity: 0, duration: .28, ease: "power2.out" }, t);
  tl.fromTo(".caps", { x: 0 }, { x: k * .6, duration: .045, yoyo: true, repeat: 7, ease: "none" }, t);
  const p = at || [.5, .62];
  IMP.push([p[0], p[1], t, amp]);
}
const typeIn = (sel, t, per) => tl.to(sel + " .ch", { opacity: 1, duration: .01, stagger: per || .05 }, t);
const count = (sel, to, t, dur) => { const o = { v: 0 }; tl.to(o, { v: to, duration: dur, ease: "power2.out", onUpdate: () => { document.querySelector(sel).textContent = Math.round(o.v); } }, t); };
function card(id, t0, t1) {
  tl.fromTo(id, { opacity: 0, y: 170, rotationX: -38, rotationY: 28, scale: .86, transformPerspective: 1400 },
    { opacity: 1, y: 0, rotationX: 6, rotationY: -8, scale: 1, duration: .6, ease: "back.out(1.5)" }, t0);
  tl.to(id, { rotationY: 8, rotationX: -3, y: -14, duration: Math.max(.5, t1 - t0 - .95), ease: "sine.inOut" }, t0 + .6);
  tl.to(id, { opacity: 0, y: -150, rotationX: 24, scale: .9, duration: .35, ease: "power2.in" }, t1 - .35);
}
// HUD: segmented progress, tag chip, heading slam
B.forEach((b, i) => {
  tl.fromTo("#sg" + i, { scaleX: 0 }, { scaleX: 1, duration: b.e - b.s, ease: "none" }, b.s);
  tl.set("#tg" + i, { opacity: 1 }, b.s); if (i < B.length - 1) tl.set("#tg" + i, { opacity: 0 }, b.e);
  tl.fromTo("#tg" + i, { x: -60 }, { x: 0, duration: .3, ease: "power3.out" }, b.s);
  const hook = i === 0;
  tl.set("#hd" + i, { opacity: 1 }, b.s);
  tl.fromTo("#hd" + i + " .hw, #hd" + i + " .hl", { opacity: 0, scale: hook ? 2.6 : 1.6, y: hook ? -30 : 0 },
    { opacity: 1, scale: 1, y: 0, duration: hook ? .26 : .22, ease: "power4.in", stagger: .1, transformOrigin: "left center" }, b.s + .05);
  if (i < B.length - 1) tl.set("#hd" + i, { opacity: 0 }, b.e);
  const land = b.s + (D.land[i] ?? .65);
  hit(CARDOF[i], land, hook ? 1.5 : 1.0);
});
// captions: chunk by chunk, current word lit
CH.forEach((c, ci) => {
  const nxt = CH[ci + 1], prv = CH[ci - 1];
  const s = Math.max(W[c[0]].s - .04, prv ? W[prv[prv.length - 1]].e + .13 : 0);
  const e = Math.min(W[c[c.length - 1]].e + .12, nxt ? W[nxt[0]].s - .05 : 1e9);
  tl.set("#cc" + ci, { opacity: 1 }, s); tl.set("#cc" + ci, { opacity: 0 }, e);
  c.forEach((wi) => {
    tl.fromTo("#w" + wi, { y: 18, scale: .86 }, { y: 0, scale: 1, duration: .16, ease: "back.out(2)" }, W[wi].s);
    tl.set("#w" + wi, { color: "#000", backgroundColor: "#fff", webkitTextStrokeWidth: "0px" }, W[wi].s);
    tl.set("#w" + wi, { color: "#fff", backgroundColor: "rgba(255,255,255,0)", webkitTextStrokeWidth: "11px" }, W[wi].e);
  });
});
