// One world page: nav, hero, film chapters, sections, footer. Server component.
// The markup follows the approved look pages in fludi-buddha-website/look/.

import Link from "next/link";
import type { Chapter, Section, Title, World } from "@/content/worlds/types";
import { PLANS } from "@/content/site";
import FilmScroll from "./FilmScroll";
import Scene from "./scenes";
import { GoWorld, LangSwitch, RoleBlock, WorldChip } from "./WorldClient";

const still = (name: string) => ({ ["--img" as string]: `url('/film/stills/${name}.jpg')` }) as React.CSSProperties;

function T({ t }: { t: Title }) {
  return <>{t[0]} <span className="gold">{t[1]}</span>{t[2] ? ` ${t[2]}` : ""}</>;
}

function Nav({ world }: { world: World }) {
  return (
    <header className="nav">
      <div className="wrap">
        <Link href={world.path} aria-label="FluidBuddha home">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={`/brand/logo-fluidbuddha-horizontal-${world.theme === "dark" ? "onblack" : "black"}.svg`} alt="FluidBuddha" width={150} height={26} />
        </Link>
        <ul>{world.nav.map((n) => <li key={n.label}><Link href={n.href}>{n.label}</Link></li>)}</ul>
        <span className="sp" />
        {world.hi && <LangSwitch world={world.id} />}
        {world.id !== "default" && <WorldChip current={world.id} name={world.name} />}
        <Link className="btn btn-primary" href={world.cta.href} data-hi={world.hi?.cta}>{world.cta.label}</Link>
      </div>
    </header>
  );
}

function Selector() {
  return (
    <>
      <div className="selector">What do you do?
        <GoWorld to="saas">SaaS</GoWorld><GoWorld to="education">Education</GoWorld><GoWorld to="enterprise">Bank or insurer</GoWorld>
      </div>
      <p className="note">Pick one and this site changes for you.</p>
    </>
  );
}

function HeroCopy({ world }: { world: World }) {
  const h = world.hero;
  return (
    <div className="copy">
      <span className="eyebrow">{h.eyebrow}</span>
      <h1 data-hi={world.hi?.title}><T t={h.title} /></h1>
      {h.langSwitch && world.hi && <LangSwitch world={world.id} variant="pill" />}
      {h.roles
        ? <RoleBlock world={world.id} roles={h.roles} primaryHref={world.cta.href} secondaryHref="#film" hi={world.hi && { sub: world.hi.sub, primary: world.hi.cta }} />
        : <>
            <p className="lead" data-hi={world.hi?.sub}>{h.sub}</p>
            <div className="ctas">
              {h.primary && <Link className="btn btn-primary" href={h.primary.href} data-hi={world.hi?.cta}>{h.primary.label}</Link>}
              {h.secondary && <a className="btn btn-secondary" href={h.secondary.href} data-hi={world.hi?.secondary}>{h.secondary.label}</a>}
            </div>
          </>}
      {h.selector && <Selector />}
    </div>
  );
}

function Hero({ world }: { world: World }) {
  const h = world.hero;
  const copy = <HeroCopy world={world} />;
  if (h.layout === "bleed") {
    const onDark = world.theme === "light" && h.tone === "dark";
    return (
      <div className={`hero bleed${onDark ? " on-dark" : ""}`} style={still(h.still!)}>
        <div className="wrap">{copy}</div>
        <span className="scrollcue" aria-hidden>Scroll</span>
      </div>
    );
  }
  return (
    <div className="hero">
      <div className="wrap">
        {copy}
        <div className="visual">{h.scene && <Scene id={h.scene} />}</div>
      </div>
    </div>
  );
}

function BleedChapter({ world, c, i, n }: { world: World; c: Chapter; i: number; n: number }) {
  const light = c.tone === "light";
  const onDark = world.theme === "light" && !light;
  const inner = (
    <>
      <span className="count">{String(i + 1).padStart(2, "0")} / {String(n).padStart(2, "0")} · {c.eyebrow}</span>
      {c.quote && <p className="quote" lang="hi">{c.quote}</p>}
      <h2><T t={c.title} /></h2>
      {c.body && <p className="lead">{c.body}</p>}
      {c.note && <p className="note">{c.note}</p>}
    </>
  );
  return (
    <section id={c.id} className={`bleed${light ? " light" : ""}${onDark ? " on-dark" : ""}`} style={still(c.still!)}>
      <div className="wrap">{world.id === "default" ? <div className="plate">{inner}</div> : <div className="copy">{inner}</div>}</div>
    </section>
  );
}

/** The hero and every chapter as slides over one scroll-driven film. */
function ScrubbedFilm({ world }: { world: World }) {
  const f = world.film;
  const heroAt = (f.frames ?? f.code)!.heroAt;
  const n = f.chapters.length;
  const plate = !f.code; // drawn films leave room beside the picture, so the copy needs no plate
  // a light world over a dark picture needs light text
  const dark = (tone?: "dark" | "light") => (world.theme === "light" && tone === "dark" ? " on-dark" : "");
  const focus = f.frames ? [f.frames.heroFocus ?? 0.5, ...f.chapters.map((c) => c.focus ?? f.frames!.heroFocus ?? 0.5)] : undefined;
  return (
    <FilmScroll frames={f.frames} code={f.code} focus={focus} ranges={[heroAt, ...f.chapters.map((c) => c.at!)]} labels={["Start", ...f.chapters.map((c) => c.label ?? c.eyebrow)]} ids={["film", ...f.chapters.map((c) => c.id)]}>
      {[
        <div className={`wrap${dark(world.hero.tone)}`} key="hero"><HeroCopy world={world} /></div>,
        ...f.chapters.map((c, i) => (
          <div className="wrap" key={c.id}>
            <div className={(plate ? "plate" : "copy") + dark(c.tone)}>
              <span className="count">{String(i + 1).padStart(2, "0")} / {String(n).padStart(2, "0")} · {c.eyebrow}</span>
              {c.quote && <p className="quote" lang="hi">{c.quote}</p>}
              <h2 data-hi={world.hi?.chapters?.[c.id]}><T t={c.title} /></h2>
              {c.body && <p className="lead">{c.body}</p>}
              {c.selector && <Selector />}
              {c.note && <p className="note">{c.note}</p>}
            </div>
          </div>
        )),
      ]}
    </FilmScroll>
  );
}

function Film({ world }: { world: World }) {
  const f = world.film;
  if (f.layout === "bleed") {
    return (
      <div id="film">
        {f.chapters.map((c, i) => <BleedChapter key={c.id} world={world} c={c} i={i} n={f.chapters.length} />)}
      </div>
    );
  }
  return (
    <section id="film">
      <div className="wrap">
        {f.intro && (
          <div className="head">
            {world.id === "enterprise" && <span className="num">00</span>}
            <span className="eyebrow">{f.intro.eyebrow}</span>
            <h2><T t={f.intro.title} /></h2>
            {f.intro.lead && <p className="lead">{f.intro.lead}</p>}
          </div>
        )}
        <div className="frames">
          {f.chapters.map((c) => (
            <figure key={c.id}>
              <div className="shot">{c.scene && <Scene id={c.scene} />}</div>
              <figcaption>
                <span className="eyebrow">{c.eyebrow}</span>
                <h3>{c.title.join(" ")}</h3>
                {c.body && <p>{c.body} {c.note && <span className="note">{c.note}</span>}</p>}
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}

type SectionHi = { title?: string; items?: Record<number, string> };

function Head({ s, hi }: { s: { num?: string; eyebrow: string; title: Title; lead?: string }; hi?: SectionHi }) {
  return (
    <div className="head">
      {s.num && <span className="num">{s.num}</span>}
      <span className="eyebrow">{s.eyebrow}</span>
      <h2 data-hi={hi?.title}><T t={s.title} /></h2>
      {s.lead && <p className="lead">{s.lead}</p>}
    </div>
  );
}

function SectionView({ s, hi }: { s: Section; hi?: SectionHi }) {
  switch (s.kind) {
    case "cards":
      return (
        <section id={s.id} className={[s.overFilm && "over-film", s.dots && "dots"].filter(Boolean).join(" ") || undefined} style={s.overFilm ? still(s.overFilm) : undefined}>
          <div className="wrap">
            <Head s={s} />
            <div className={`grid g${s.cols}`}>
              {s.items.map((it) => (
                <div className="card" key={it.title}>
                  {it.n && <span className={s.steps ? "step-n" : "n"}>{it.n}</span>}
                  <h3>{it.title}</h3><p>{it.body}</p>
                </div>
              ))}
            </div>
            {s.note && <p className="note after">{s.note}</p>}
          </div>
        </section>
      );
    case "talk":
      return (
        <section id={s.id}><div className="wrap">
          <Head s={s} hi={hi} />
          <div className="asks">{s.questions.map((q) => <Link key={q} href={s.cta.href} className="ask">{q}</Link>)}</div>
          <div className="ctas after"><Link className="btn btn-primary" href={s.cta.href}>{s.cta.label}</Link></div>
        </div></section>
      );
    case "list":
      return (
        <section id={s.id}><div className="wrap">
          <Head s={s} hi={hi} />
          <ul className="plain">{s.items.map((it, i) => <li key={it} data-hi={hi?.items?.[i]}>{it}</li>)}</ul>
          {s.note && <p className="note after">{s.note}</p>}
          {s.cta && <div className="ctas after"><Link className="btn btn-primary" href={s.cta.href}>{s.cta.label}</Link></div>}
        </div></section>
      );
    case "faq":
      return (
        <section id={s.id}><div className="wrap">
          <Head s={s} />
          <div className="faq">{s.items.map((it) => <details key={it.q}><summary>{it.q}</summary><p>{it.a}</p></details>)}</div>
        </div></section>
      );
    case "close":
      return (
        <section id={s.id} className="close"><div className="wrap">
          <h2><T t={s.title} /></h2>
          <p className="lead">{s.lead}</p>
          <div className="ctas"><Link className="btn btn-primary" href={s.primary.href}>{s.primary.label}</Link><Link className="btn btn-secondary" href={s.secondary.href}>{s.secondary.label}</Link></div>
        </div></section>
      );
    case "table":
      return (
        <section id={s.id}><div className="wrap">
          <Head s={s} />
          <table>
            <thead><tr><th>{s.head[0]}</th><th>{s.head[1]}</th></tr></thead>
            <tbody>{s.rows.map((r) => <tr key={r[0]}><td>{r[0]}</td><td>{r[1]}</td></tr>)}</tbody>
          </table>
          {s.note && <p className="note after">{s.note}</p>}
          {s.cta && <div className="ctas after"><Link className="btn btn-primary" href={s.cta.href}>{s.cta.label}</Link></div>}
        </div></section>
      );
    case "doors":
      return (
        <section id={s.id}><div className="wrap">
          <Head s={s} />
          <div className="doors">
            {s.doors.map((d) => (
              <GoWorld key={d.to} to={d.to} className="door" style={{ backgroundImage: `url('/film/stills/${d.still}.jpg')` }}>
                <span className="eyebrow">{d.eyebrow}</span><h3>{d.title}</h3>
              </GoWorld>
            ))}
          </div>
          {s.also && <p className="also">Also: {s.also.map((a) => <Link key={a.href} href={a.href}>{a.label}</Link>)}</p>}
        </div></section>
      );
    case "plans":
      return (
        <section id={s.id}><div className="wrap">
          <Head s={s} />
          <div className="plans">
            {PLANS.map((p) => {
              const named = p.name === "Free" || p.name === "Enterprise";
              const line = p.name === "Enterprise" ? "By arrangement" : `${named ? "" : `${p.name} · `}${p.included} a month`;
              return <div key={p.name}><b>{named ? p.name : p.price}</b><span>{line}</span></div>;
            })}
          </div>
          {s.link && <div className="ctas after"><Link className="btn btn-secondary" href={s.link.href}>{s.link.label}</Link></div>}
        </div></section>
      );
    case "lead-install":
      return (
        <section id={s.id}><div className="wrap"><div className="grid g2">
          <div className="card">
            <span className="eyebrow">The lead your team receives</span><h3>A lead you would want to call.</h3>
            <div className="kv">
              <i>score</i> ......... <b>78 / 100</b><br /><i>why</i> ........... email · 4 questions · asked about pricing<br />
              <i>asked</i> ......... ERP sync, cost for 60 seats, data location<br /><i>pages</i> ......... /pricing → /security<br />
              <i>summary opened</i>  <b>4 people</b><br /><i>sent to</i> ....... Slack, CRM webhook
            </div>
            <p className="note">Example lead.</p>
          </div>
          <div className="card">
            <span className="eyebrow">Install</span><h3>One line of code.</h3>
            <div className="code">{'<script src="…/widget/loader.js"\n        '}<b>{'data-key="fbk_…"'}</b>{" async></script>"}</div>
            <p>About 38.6 kB core script. Runs in its own isolated container, so it cannot change your styles.</p>
          </div>
        </div></div></section>
      );
    case "phone":
      return (
        <section id={s.id}><div className="wrap split">
          <div className="copy" style={{ display: "grid", gap: "var(--s-5)" }}>
            <span className="eyebrow">{s.eyebrow}</span><h2><T t={s.title} /></h2><p className="lead">{s.lead}</p>
            <ul className="ticks">{s.ticks.map((t) => <li key={t}>{t}</li>)}</ul>
          </div>
          <div className="phone"><div className="screen">
            <span className="eyebrow">Your summary</span>
            <h3>What you asked about the MBA programme</h3>
            <div className="row"><span>Tuition, first year</span><b>From your fee page</b></div>
            <div className="row"><span>Scholarship</span><b>From your fee page</b></div>
            <div className="row"><span>Eligibility</span><b>Graduate, any stream</b></div>
            <span className="src">Sources: /programmes/mba · /fees · /admissions</span>
            <span className="btn btn-primary">Apply now</span>
            <span className="note">Example summary. Figures come from your own pages.</span>
          </div></div>
        </div></section>
      );
    case "callout":
      return (
        <section id={s.id} className={s.dots ? "dots" : undefined}><div className="wrap"><div className="callout">
          <span className="eyebrow">{s.eyebrow}</span>
          {s.big && <p className="big">{s.big}</p>}
          <h3>{s.title}</h3><p className="note">{s.note}</p>
        </div></div></section>
      );
    case "controls":
      return (
        <section id={s.id}><div className="wrap">
          <Head s={s} />
          <ol className="controls">{s.items.map((it) => <li key={it.title}><span>{it.n}</span><div><b>{it.title}</b>{it.body}</div></li>)}</ol>
        </div></section>
      );
  }
}

function Footer({ world }: { world: World }) {
  return (
    <footer className="wfoot"><div className="wrap">
      <span>FluidBuddha · a Buddha Cognitive Lab product</span>
      <nav aria-label="Footer">
        <Link href="/pricing">Pricing</Link><Link href="/trust">Trust and security</Link>
        <Link href="/legal/privacy">Privacy</Link><Link href="/legal/terms">Terms</Link>
        {world.id !== "default" && <GoWorld to="default" how="chip">General version</GoWorld>}
      </nav>
    </div></footer>
  );
}

export default function WorldPage({ world }: { world: World }) {
  return (
    <div className="world" data-world={world.id} data-theme={world.theme === "light" ? "light" : undefined}>
      <Nav world={world} />
      {(world.film.kind === "frames" && world.film.frames) || (world.film.kind === "code" && world.film.code)
        ? <ScrubbedFilm world={world} />
        : <><Hero world={world} /><Film world={world} /></>}
      {world.sections.map((s, i) => <SectionView key={s.id ?? i} s={s} hi={s.id ? world.hi?.sections?.[s.id] : undefined} />)}
      <Footer world={world} />
    </div>
  );
}
