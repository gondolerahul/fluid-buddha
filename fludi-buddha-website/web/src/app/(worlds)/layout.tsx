import "./film.css";
import "./world-sections.css";
import "./world-default.css";
import "./world-saas.css";
import "./world-education.css";
import "./world-enterprise.css";

/** The four worlds. The header, footer and morph come from the root layout; each world styles them through its tokens. */
export default function WorldsLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <main id="main" className="world-main">{children}</main>;
}
