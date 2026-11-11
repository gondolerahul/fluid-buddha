import "./worlds.css";
import "./worlds-app.css";
import WorldSwitch from "@/components/world/WorldSwitch";

/** Layout for the four worlds. Each world page renders its own nav inside its .world wrapper. */
export default function WorldsLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <main id="main">{children}</main>
      <WorldSwitch />
    </>
  );
}
