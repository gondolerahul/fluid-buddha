// A picture on a content page, drawn in the material of the world on screen (content/media.ts):
// painted in the default world, in characters in SaaS, a line drawing in Enterprise, a photograph in
// Education. All four are in the markup and CSS shows the one for <html data-world>, so the page
// never flashes another world's picture; only the one showing is drawn or downloaded.
import { ART, MEDIA, type ArtKey } from "@/content/media";
import FilmStill from "./FilmStill";

export default function WorldArt({ k, className = "" }: { k: ArtKey; className?: string }) {
  const a = ART[k], photo = MEDIA[a.photo];
  return (
    <div className={`art ${className}`} role="img" aria-label={a.alt}>
      <div className="art-in art-default"><FilmStill kind="wash" at={a.wash} /></div>
      <div className="art-in art-saas tone-second"><FilmStill kind="ascii" at={a.ascii} /></div>
      <div className="art-in art-enterprise tone-second"><FilmStill kind="line" at={a.line} /></div>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img className="art-in art-education" src={photo.src} alt="" loading="lazy" decoding="async" style={{ objectPosition: `${photo.focus ?? 50}% 50%` }} />
    </div>
  );
}
