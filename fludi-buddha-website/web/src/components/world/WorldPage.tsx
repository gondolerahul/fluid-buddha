// One world page: the film (with the hero as its first slide), then the world's sections.
// The header, footer and morph come from the root layout. Server component; the interactive parts
// are client islands. Redesign: docs/marketing-docs/website/audit-2026-11-11.md §5.

import { cloneElement, type ReactElement } from "react";
import Image from "next/image";
import Link from "next/link";
import type { Section, Title, World } from "@/content/worlds/types";
import { PLANS } from "@/content/site";
import { MEDIA } from "@/content/media";
import AskButton from "@/components/site/AskButton";
import FilmScroll from "./FilmScroll";
import FilmStill from "./FilmStill";
import { GoWorld, LangInit, RoleBlock } from "./WorldClient";
import { CopyButton, CostCompare, InstallTabs, SpecIndex, TrySite } from "./parts";
import AskStage from "./signature/AskStage";
import FitDemo from "./signature/FitDemo";
import LeadDesk from "./signature/LeadDesk";
import HindiAnswer from "./signature/HindiAnswer";
import RuleConsole from "./signature/RuleConsole";

const SNIPPET = "<script src=\"https://<server>/widget/loader.js\"\n        data-key=\"fbk_…\" async></script>";

function T({ t }: { t: Title }) {
  return <>{t[0]} <span className="em">{t[1]}</span>{t[2] ? ` ${t[2]}` : ""}</>;
}

function Head({ title, lead, hi, className = "" }: { title: Title; lead?: string; hi?: string; className?: string }) {
  return (
    <div className={`sh ${className}`}>
      <h2 className="t-h2" data-hi={hi}><T t={title} /></h2>
      {lead && <p className="t-lead">{lead}</p>}
    </div>
  );
}

// ------------------------------------------------------------------------------ hero and film

function Selector() {
  return (
    <div className="selector" role="group" aria-label="Choose the version of this site for you">
      <GoWorld to="saas" className="btn btn-quiet">B2B SaaS</GoWorld>
      <GoWorld to="education" className="btn btn-quiet">Education</GoWorld>
      <GoWorld to="enterprise" className="btn btn-quiet">Bank or insurer</GoWorld>
    </div>
  );
}

function HeroCopy({ world }: { world: World }) {
  const h = world.hero;
  return (
    <div className="hero-copy" data-enter>
      <h1 className="t-display" data-hi={world.hi?.title}><T t={h.title} /></h1>
      {h.roles
        ? <RoleBlock world={world.id} roles={h.roles} hi={world.hi && { sub: world.hi.sub, primary: world.hi.cta }} />
        : <>
            <p className="t-lead" data-hi={world.hi?.sub}>{h.sub}</p>
            <div className="ctas">
              {h.primary && <Link className="btn btn-primary btn-metal btn-lg" href={h.primary.href} data-hi={world.hi?.cta}>{h.primary.label}</Link>}
              {h.secondary && <a className="btn btn-quiet btn-lg" href={h.secondary.href} data-hi={world.hi?.secondary}>{h.secondary.label}</a>}
            </div>
          </>}
    </div>
  );
}

/** The hero and every chapter as slides beside one scroll-driven film. */
function Film({ world }: { world: World }) {
  const f = world.film;
  const heroAt = (f.frames ?? f.code)!.heroAt;
  const focus = f.frames ? [f.frames.heroFocus ?? 0.5, ...f.chapters.map((c) => c.focus ?? f.frames!.heroFocus ?? 0.5)] : undefined;
  return (
    <FilmScroll frames={f.frames} code={f.code} focus={focus}
                ranges={[heroAt, ...f.chapters.map((c) => c.at)]}
                labels={["Start", ...f.chapters.map((c) => c.label)]}
                ids={["start-film", ...f.chapters.map((c) => c.id)]}>
      {[
        <div className="wrap" key="hero"><HeroCopy world={world} /></div>,
        ...f.chapters.map((c) => (
          <div className="wrap" key={c.id}>
            <div className="slide-copy">
              {c.quote && <p className="quote" lang="hi">{c.quote}</p>}
              <h2 className="t-h2" data-hi={world.hi?.chapters?.[c.id]}><T t={c.title} /></h2>
              {c.body && <p className="t-lead">{c.body}</p>}
              {c.selector && <Selector />}
              {c.note && <p className="note">{c.note}</p>}
            </div>
          </div>
        )),
      ]}
    </FilmScroll>
  );
}

// ------------------------------------------------------------------------------ small visuals

/** The micro-visuals of the default world's "one conversation does all of this" cells. */
function BentoVisual({ k }: { k: string }) {
  switch (k) {
    case "talks":
      return (
        <div className="bv bv-talks" aria-hidden><FilmStill kind="wash" at={0.243} cam={TALK_CAM} /></div>
      );
    case "shows":
      return (
        <svg className="bv bv-shows" viewBox="0 0 220 120" aria-hidden>
          {[34, 52, 44, 70, 62, 88, 80].map((h, i) => <rect key={i} x={14 + i * 28} y={110 - h} width="16" height={h} rx="2" style={{ ["--i" as string]: i }} />)}
          <path d="M22 78 L50 62 L78 68 L106 44 L134 50 L162 28 L190 34" />
        </svg>
      );
    case "there":
      return (
        <div className="bv bv-there" aria-hidden>
          <span className="pg-nav" /><span className="pg-a" /><span className="pg-b" /><span className="pg-c on" /><span className="pg-d" />
          <span className="ring" />
        </div>
      );
    case "sources":
      return (
        <div className="bv bv-sources" aria-hidden>
          <span className="src-bubble">&ldquo;Growth is &#8377;33,000 a month for 2,000 conversations.&rdquo;</span>
          <span className="src-chip">Source: /pricing</span>
        </div>
      );
    case "books":
      return (
        <div className="bv bv-books" aria-hidden>
          <b>Demo, Thursday 11:00</b><span>Confirm the booking?</span>
          <span className="bk-row"><span className="bk-yes">Yes, book it</span><span className="bk-no">Not now</span></span>
        </div>
      );
    default:
      return (
        <svg className="bv bv-proves" viewBox="0 0 220 120" aria-hidden>
          {Array.from({ length: 10 }, (_, i) => <circle key={i} cx={20 + i * 20} cy="14" r="5" className={i === 9 ? "off" : undefined} />)}
          <path className="base" d="M12 100 C 60 96, 120 92, 208 86" />
          <path className="up" d="M12 100 C 60 88, 120 64, 208 38" />
        </svg>
      );
  }
}

function HoldoutChart() {
  return (
    <figure className="hold">
      <svg viewBox="0 0 520 300" role="img" aria-label="Example chart: visitors who met FluidBuddha convert more than the one in ten held back; the gap is the lift">
        <g className="hold-dots">{Array.from({ length: 10 }, (_, i) => <circle key={i} cx={40 + i * 26} cy="28" r="7" className={i === 9 ? "off" : undefined} />)}</g>
        <text x="312" y="33">one in ten held back</text>
        <path className="axis" d="M40 72 V262 H500" />
        <path className="band" d="M40 238 C 160 226, 300 190, 500 120 L 500 214 C 300 226, 160 234, 40 240 Z" />
        <path className="base" d="M40 240 C 160 234, 300 226, 500 214" />
        <path className="up" d="M40 238 C 160 226, 300 190, 500 120" />
        <text x="404" y="110">with FluidBuddha</text>
        <text x="420" y="236">held back</text>
        <text x="40" y="284">day 1</text><text x="452" y="284">day 30</text>
      </svg>
      <figcaption className="note">Example chart. Your own traffic produces the real one.</figcaption>
    </figure>
  );
}

function FlowDiagram() {
  return (
    <svg className="flow-dia" viewBox="0 0 760 340" role="img" aria-label="Diagram: the product and its data inside your network; your model and identity providers connected at the boundary; speech and search indexing leaving to Google Vertex AI">
      <rect className="dash" x="24" y="34" width="470" height="282" />
      <text className="cap" x="24" y="24">Your network</text>
      <rect className="ln" x="62" y="76" width="300" height="196" />
      <text className="ttl" x="82" y="108">FluidBuddha</text>
      {["Application and console", "Database", "Visitor conversations", "Leads", "Audit log"].map((t, i) => (
        <g key={t}><rect className="cell" x="82" y={124 + i * 28} width="260" height="20" /><text className="item" x="92" y={138 + i * 28}>{t}</text></g>
      ))}
      <path className="ln" d="M362 128 H494" /><circle className="plug" cx="494" cy="128" r="5" />
      <path className="ln" d="M362 196 H494" /><circle className="plug" cx="494" cy="196" r="5" />
      <path className="ln" d="M499 128 H560" /><rect className="ln" x="560" y="106" width="176" height="44" /><text className="item" x="574" y="133">Your model provider</text>
      <path className="ln" d="M499 196 H560" /><rect className="ln" x="560" y="174" width="176" height="44" /><text className="item" x="574" y="201">Your identity provider</text>
      <text className="cap" x="560" y="96">Your contracts</text>
      <path className="out" d="M362 252 H560" /><path className="out-head" d="M552 246 L562 252 L552 258" />
      <rect className="ln" x="562" y="230" width="176" height="44" /><text className="item" x="576" y="257">Google Vertex AI</text>
      <text className="cap" x="562" y="292">Speech and search indexing leave</text>
    </svg>
  );
}

// ------------------------------------------------------------------------------ sections

/** Where each of the three versions sits on the painted sheet (the film's chapter "you"): [x, y, zoom]. */
const DOOR_CAM: [number, number, number][] = [[2430, 12, 2.3], [2700, 12, 2.3], [2970, 12, 2.3]];
/** The painted page with its two sources gilded, a little closer than the film shows it. */
const TALK_CAM: [number, number, number] = [0, -17, 1.3];

/** A section on its ground: the main colour, or the secondary, or gold (content: `tone`). */
function SectionView({ world, s }: { world: World; s: Section }) {
  const el = sect(world, s) as ReactElement<{ className?: string }>;
  return s.tone ? cloneElement(el, { className: `${el.props.className ?? ""} tone-${s.tone}` }) : el;
}

function sect(world: World, s: Section) {
  const hiTitle = world.hi?.sections?.[s.id]?.title;
  switch (s.kind) {
    // ---------------------------------------------------------------- shared
    case "faq":
      return (
        <section id={s.id} className="section ws-faq">
          <div className="wrap faq-split">
            <div className="sh">
              <h2 className="t-h2"><T t={s.title} /></h2>
              {s.lead && <p className="t-lead">{s.lead}</p>}
              {s.ask && <div><AskButton question={s.ask} /></div>}
            </div>
            <div className="faq">{s.items.map((it) => <details key={it.q}><summary>{it.q}</summary><p>{it.a}</p></details>)}</div>
          </div>
        </section>
      );
    case "close":
      return (
        <section id={s.id} className="section ws-close">
          <div className="wrap">
            <h2 className="t-display close-h"><T t={s.title} /></h2>
            <p className="t-lead">{s.lead}</p>
            <div className="ctas">
              <Link className="btn btn-primary btn-lg" href={s.primary.href}>{s.primary.label}</Link>
              <Link className="btn btn-quiet btn-lg" href={s.secondary.href}>{s.secondary.label}</Link>
            </div>
          </div>
        </section>
      );
    case "limits":
      return (
        <section id={s.id} className="section ws-limits">
          <div className={`wrap limits${s.aside ? " with-aside" : ""}`}>
            <div className="limits-main">
              <h2 className="t-h2"><T t={s.title} /></h2>
              <ol className="limits-list">{s.items.map((it) => <li key={it}>{it}</li>)}</ol>
            </div>
            {s.aside && (
              <aside className="limits-aside tone-second">
                <h3>{s.aside.title}</h3>
                <p>{s.aside.body}</p>
              </aside>
            )}
          </div>
        </section>
      );

    // ---------------------------------------------------------------- default
    case "ask":
      return (
        <section id={s.id} className="section ws-ask">
          <div className="wrap">
            <Head title={s.title} lead={s.lead} hi={hiTitle} />
            <AskStage questions={s.questions} />
          </div>
        </section>
      );
    case "bento":
      return (
        <section id={s.id} className="section ws-bento">
          <div className="wrap">
            <Head title={s.title} />
            <div className="bento">
              {s.items.map((it) => (
                <div key={it.key} className={`bento-cell b-${it.key}${it.key === "books" ? " tone-gold" : it.key === "proves" ? " tone-second" : ""}`}>
                  <BentoVisual k={it.key} />
                  <div className="bento-copy"><h3 className="t-h3">{it.title}</h3><p>{it.body}</p></div>
                </div>
              ))}
            </div>
          </div>
        </section>
      );
    case "fit":
      return (
        <section id={s.id} className="section ws-fit">
          <div className="wrap">
            <Head title={s.title} lead={s.lead} />
            <FitDemo states={s.states} />
            <p className="note fit-note">{s.note}</p>
          </div>
        </section>
      );
    case "doors":
      return (
        <section id={s.id} className="section ws-doors">
          <div className="wrap">
            <Head title={s.title} lead={s.lead} />
            <div className="doors">
              {s.doors.map((d, i) => (
                <GoWorld key={d.to} to={d.to} className="door tone-second" label={`Show the version of this site for ${d.label}`}>
                  <span className="door-pic"><FilmStill kind="wash" at={0.866} cam={DOOR_CAM[i]} /></span>
                  <span className="door-copy">
                    <span className="door-label">{d.label}</span>
                    <b>{d.title}</b>
                    <span className="door-go">Show this version <span className="arrow" aria-hidden>&rarr;</span></span>
                  </span>
                </GoWorld>
              ))}
            </div>
            <p className="also"><span>Also for</span>{s.also.map((a) => <Link key={a.href} href={a.href} className="link">{a.label}</Link>)}</p>
          </div>
        </section>
      );
    case "start":
      return (
        <section id={s.id} className="section ws-start">
          <div className="wrap start">
            <div>
              <Head title={s.title} />
              <ol className="start-steps">{s.steps.map((st) => <li key={st.title}><h3 className="t-h3">{st.title}</h3><p>{st.body}</p></li>)}</ol>
            </div>
            <div className="ui-frame start-code">
              <div className="ui-bar"><span className="t-mono">your-site.html</span><span className="hdr-sp" /><CopyButton text={SNIPPET} /></div>
              <pre className="ui-code">{SNIPPET}</pre>
              <p className="start-fine">About 38.6 kB, loaded asynchronously, in its own isolated container.</p>
            </div>
          </div>
        </section>
      );
    case "plans":
      return (
        <section id={s.id} className="section ws-plans">
          <div className="wrap">
            <Head title={s.title} />
            <div className="plans-row">
              {PLANS.map((p) => (
                <Link key={p.name} href="/pricing" className={`plan-mini${p.lead ? " lead tone-gold" : ""}`}>
                  <span>{p.name}</span>
                  <b className="num">{p.price}</b>
                  <small>{p.name === "Enterprise" ? "By arrangement" : `${p.included} a month`}</small>
                </Link>
              ))}
            </div>
            <p className="plans-more"><Link href={s.link.href} className="link">{s.link.label} <span className="arrow" aria-hidden>&rarr;</span></Link></p>
          </div>
        </section>
      );

    // ---------------------------------------------------------------- saas
    case "lead-desk":
      return (
        <section id={s.id} className="section ws-lead">
          <div className="wrap">
            <Head title={s.title} lead={s.lead} />
            <LeadDesk />
          </div>
        </section>
      );
    case "try-site":
      return (
        <section id={s.id} className="section ws-try">
          <div className="wrap try-wrap">
            <Head title={s.title} lead={s.lead} />
            <TrySite />
          </div>
        </section>
      );
    case "questions":
      return (
        <section id={s.id} className="section ws-questions">
          <div className="wrap">
            <Head title={s.title} />
            <div className="qgrid">
              {s.rows.map((r) => (
                <div key={r.q} className="qcell">
                  <span className="qdoes">{r.does}</span>
                  <p className="qq">{r.q}</p>
                  <p className="qa">{r.a}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      );
    case "holdout":
      return (
        <section id={s.id} className="section ws-holdout">
          <div className="wrap holdout">
            <div>
              <Head title={s.title} />
              <ol className="hold-steps">{s.steps.map((st) => <li key={st.title}><b>{st.title}</b><span>{st.body}</span></li>)}</ol>
              <p className="note">{s.note}</p>
            </div>
            <HoldoutChart />
          </div>
        </section>
      );
    case "cost":
      return (
        <section id={s.id} className="section ws-cost">
          <div className="wrap cost">
            <div>
              <Head title={s.title} lead={s.body} />
              <p className="note">{s.note}</p>
            </div>
            <CostCompare />
          </div>
        </section>
      );
    case "install":
      return (
        <section id={s.id} className="section ws-install">
          <div className="wrap install">
            <Head title={s.title} lead={s.lead} />
            <InstallTabs tabs={s.tabs} />
          </div>
        </section>
      );
    case "facts":
      return (
        <section id={s.id} className="section ws-facts">
          <div className="wrap facts">
            <Head title={s.title} />
            <ul className="facts-list">
              {s.items.map((it) => (
                <li key={it.text} className={it.ok ? "ok" : "no"}><span className="mark" aria-hidden /><span className="sr-only">{it.ok ? "Yes:" : "Not covered:"}</span>{it.text}</li>
              ))}
            </ul>
          </div>
        </section>
      );

    // ---------------------------------------------------------------- education
    case "hindi-answer":
      return (
        <section id={s.id} className="section ws-hindi">
          <div className="wrap">
            <Head title={s.title} lead={s.lead} />
            <HindiAnswer />
          </div>
        </section>
      );
    case "visit":
      return (
        <section id={s.id} className="section ws-visit">
          <div className="wrap">
            <Head title={s.title} />
            <ol className="visit">
              {s.steps.map((st, i) => {
                const m = MEDIA[st.media];
                return (
                  <li key={st.title} className="visit-card">
                    <div className="visit-img"><Image unoptimized src={m.src} alt={m.alt} fill sizes="(max-width: 900px) 80vw, 25vw" style={{ objectPosition: `${m.focus ?? 50}% 50%` }} /></div>
                    <span className="visit-n num">{i + 1}</span>
                    <h3 className="t-h3">{st.title}</h3>
                    <p>{st.body}</p>
                  </li>
                );
              })}
            </ol>
          </div>
        </section>
      );
    case "phone":
      return (
        <section id={s.id} className="section ws-phone">
          <div className="wrap phone-split">
            <div>
              <Head title={s.title} lead={s.lead} />
              <ul className="cp-ticks">{s.ticks.map((t) => <li key={t}>{t}</li>)}</ul>
            </div>
            <div className="phone">
              <div className="phone-screen">
                <span className="phone-k">Your summary</span>
                <h3>What you asked about the MBA programme</h3>
                <div className="phone-row"><span>Tuition, first year</span><b>From the fee page</b></div>
                <div className="phone-row"><span>Scholarship</span><b>Up to 25%, automatic</b></div>
                <div className="phone-row"><span>Applications close</span><b>31 March</b></div>
                <span className="phone-src">Sources: /programmes/mba &middot; /fees &middot; /admissions</span>
                <span className="phone-btn">Apply now</span>
                <span className="phone-note">Example summary. Figures come from your own pages.</span>
              </div>
            </div>
          </div>
        </section>
      );
    case "counsellor": {
      const m = MEDIA[s.media];
      return (
        <section id={s.id} className="section ws-counsellor">
          <div className="wrap counsellor">
            <div className="counsellor-img"><Image unoptimized src={m.src} alt={m.alt} fill sizes="(max-width: 900px) 100vw, 50vw" style={{ objectPosition: `${m.focus ?? 50}% 50%` }} /></div>
            <div className="counsellor-copy">
              <Head title={s.title} lead={s.lead} />
              <div className="ui-frame lead-am tone-second">
                <div className="ui-bar"><span className="ui-orb" aria-hidden /><b>New lead</b><span className="hdr-sp" /><span className="t-mono">09:02</span></div>
                <dl className="ui-kv lead-am-kv">
                  {s.items.map((it, i) => (
                    <div key={it}><dt>{it}</dt><dd>{["Shared, hidden here", "MBA, 2026 intake · Nagpur", "Fees, scholarship, hostel (in Hindi)", "82 / 100: priced the course, opened the fee link", "Yes, twice"][i]}</dd></div>
                  ))}
                </dl>
                <p className="note">Example lead. {s.note}</p>
              </div>
            </div>
          </div>
        </section>
      );
    }
    case "pair": {
      const hi = world.hi?.sections?.[s.right.id];
      return (
        <section id={s.id} className="section ws-pair">
          <div className="wrap pair">
            <div className="pair-col">
              <h2 className="t-h2">{s.left.title}</h2>
              <ul className="cp-ticks">{s.left.items.map((it) => <li key={it}>{it}</li>)}</ul>
              {s.left.note && <p className="note">{s.left.note}</p>}
            </div>
            <div className="pair-col" id={s.right.id}>
              <h2 className="t-h2">{s.right.title}</h2>
              <ul className="cp-ticks">{s.right.items.map((it, i) => <li key={it} data-hi={hi?.items?.[i]}>{it}</li>)}</ul>
              {s.right.note && <p className="note">{s.right.note}</p>}
            </div>
          </div>
        </section>
      );
    }
    case "return":
      return (
        <section id={s.id} className="section ws-return">
          <div className="wrap ret">
            <h2 className="t-h2"><T t={s.title} /></h2>
            <p className="eq num" aria-label="2,00,000 rupees divided by 33,000 rupees a month is about six months">
              <span>&#8377;2,00,000</span><i aria-hidden>&divide;</i><span>&#8377;33,000 a month</span><i aria-hidden>&asymp;</i><span className="em">6 months</span>
            </p>
            <p className="t-lead">{s.body}</p>
            <p className="note">{s.note}</p>
          </div>
        </section>
      );

    // ---------------------------------------------------------------- enterprise (inside the specification)
    case "spec-table":
      return (
        <section id={s.id} className="spec-sec">
          <SpecHead num={s.num} title={s.title} />
          <div className="spec-table" role="table" aria-label={s.title.join(" ")}>
            <div className="spec-tr spec-th" role="row"><span role="columnheader">{s.head[0]}</span><span role="columnheader">{s.head[1]}</span></div>
            {s.rows.map((r) => <div key={r[0]} className="spec-tr" role="row"><b role="cell">{r[0]}</b><span role="cell">{r[1]}</span></div>)}
          </div>
          {s.note && <p className="note">{s.note}</p>}
          {s.cta && <div className="ctas"><Link className="btn btn-primary" href={s.cta.href}>{s.cta.label}</Link></div>}
        </section>
      );
    case "flow":
      return (
        <section id={s.id} className="spec-sec">
          <SpecHead num={s.num} title={s.title} />
          <div className="flow-fig tone-second"><FlowDiagram /></div>
          <div className="flow-zones">{s.zones.map((z) => <div key={z.n}><span className="label">{z.n}</span><b>{z.title}</b><p>{z.body}</p></div>)}</div>
          <p className="note">{s.note}</p>
        </section>
      );
    case "controls":
      return (
        <section id={s.id} className="spec-sec">
          <SpecHead num={s.num} title={s.title} />
          <ol className="controls">{s.items.map((it) => <li key={it.title}><span className="num">{it.n}</span><b>{it.title}</b><p>{it.body}</p></li>)}</ol>
        </section>
      );
    case "rules":
      return (
        <section id={s.id} className="spec-sec spec-wide">
          <SpecHead num={s.num} title={s.title} lead={s.lead} />
          <RuleConsole />
        </section>
      );
    case "spec-list":
      return (
        <section id={s.id} className="spec-sec">
          <SpecHead num={s.num} title={s.title} />
          <ol className="spec-list">{s.items.map((it, i) => <li key={it}><span className="num">{s.num}.{i + 1}</span><span>{it}</span></li>)}</ol>
          {s.note && <p className="note">{s.note}</p>}
          {s.cta && <div className="ctas"><Link className="btn btn-quiet" href={s.cta.href}>{s.cta.label}</Link></div>}
        </section>
      );
    case "visitors":
      return (
        <section id={s.id} className="spec-sec">
          <SpecHead num={s.num} title={s.title} />
          <div className="visitors">
            <ol className="spec-list">{s.items.map((it, i) => <li key={it}><span className="num">{s.num}.{i + 1}</span><span>{it}</span></li>)}</ol>
            <div className="ui-frame why" aria-label="An example of the visitor's Why this? panel">
              <div className="ui-bar"><b>Why this?</b><span className="hdr-sp" /><span>About this page</span></div>
              <div className="ui-body">
                <ol className="why-list"><li>You asked about home loans.</li><li>You chose tables over charts.</li><li>You prefer a compact layout.</li></ol>
                <dl className="ui-kv why-prefs"><dt>Density</dt><dd>Compact</dd><dt>Format</dt><dd>Tables</dd><dt>Detail</dt><dd>Short</dd><dt>Motion</dt><dd>Reduced</dd></dl>
                <p className="note">Example panel. The visitor can change or reset each setting.</p>
              </div>
            </div>
          </div>
        </section>
      );
    case "timeline":
      return (
        <section id={s.id} className="spec-sec">
          <SpecHead num={s.num} title={s.title} />
          <div className="gantt" role="table" aria-label="The pilot, week by week">
            <div className="gantt-scale" aria-hidden>{[0, 3, 6, 9, 12].map((w) => <span key={w} style={{ left: `${(w / 13) * 100}%` }}>week {w}</span>)}</div>
            {s.rows.map((r) => (
              <div key={r.stage} className="gantt-row" role="row">
                <b role="cell">{r.stage}</b>
                <span className="gantt-track" aria-hidden><span className={`gantt-bar${r.stage === "End" ? " end" : ""}`} style={{ left: `${(r.weeks[0] / 13) * 100}%`, width: `${((r.weeks[1] - r.weeks[0]) / 13) * 100}%` }} /></span>
                <p role="cell">{r.what}</p>
              </div>
            ))}
          </div>
          <div className="ctas"><Link className="btn btn-primary btn-lg" href={s.cta.href}>{s.cta.label}</Link></div>
        </section>
      );
  }
}

function SpecHead({ num, title, lead }: { num: string; title: Title; lead?: string }) {
  return (
    <div className="spec-head">
      <span className="spec-num num" aria-hidden>{num}</span>
      <div>
        <h2 className="t-h2"><T t={title} /></h2>
        {lead && <p className="t-lead">{lead}</p>}
      </div>
    </div>
  );
}

const SPEC_LABEL: Record<string, string> = {
  limits: "Limits, stated first", "data-flow": "Where data goes", controls: "Controls", console: "Try the rules",
  deployment: "Deployment", security: "Access and security", documents: "Security documents", visitors: "Your visitors", pilot: "The pilot",
};

/** The Enterprise world reads as a specification: a contents list beside numbered sections. */
function Spec({ world }: { world: World }) {
  const numbered = world.sections.filter((s) => "num" in s);
  const rest = world.sections.filter((s) => !("num" in s));
  return (
    <>
      <div className="spec wrap-wide">
        <SpecIndex items={numbered.map((s) => ({ id: s.id, num: (s as { num: string }).num, title: SPEC_LABEL[s.id] ?? s.id }))} />
        <div className="spec-body">{numbered.map((s) => <SectionView key={s.id} world={world} s={s} />)}</div>
      </div>
      {rest.map((s) => <SectionView key={s.id} world={world} s={s} />)}
    </>
  );
}

export default function WorldPage({ world }: { world: World }) {
  return (
    <div className="w" data-w={world.id}>
      <Film world={world} />
      {world.id === "enterprise" ? <Spec world={world} /> : world.sections.map((s) => <SectionView key={s.id} world={world} s={s} />)}
      {world.hi && <LangInit />}
    </div>
  );
}
