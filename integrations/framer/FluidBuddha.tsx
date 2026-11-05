// FluidBuddha agent — Framer code component (M2-10).
//
// In Framer: Assets → Code → New component → paste this file. Drag
// "FluidBuddha" onto any page (or a shared layout) and paste your install code
// in the properties panel. The agent appears on the published site; on the
// canvas you see a placeholder instead.
//
// Self-contained on purpose (Framer code files can't import private packages):
// it adds the FluidBuddha server's /widget/loader.js, the same script the
// other install surfaces use.
import { useEffect } from "react"
import { addPropertyControls, ControlType, RenderTarget } from "framer"

type Props = {
    installCode: string
    position: "default" | "bottom-right" | "bottom-left"
    lang: "auto" | "en" | "hi"
}

const KEY = /^fbk_[A-Za-z0-9_-]{8,200}$/

/** "https://fbk_…@agent.example.com" → server + key, or null. */
export function parseInstallCode(code: string): { server: string; key: string } | null {
    const m = /^(https?):\/\/([^@/\s?#]+)@([^\s?#"<>]+)$/.exec((code || "").trim())
    if (!m || !KEY.test(m[2])) return null
    return { server: `${m[1]}://${m[3].replace(/\/+$/, "")}`, key: m[2] }
}

/**
 * @framerSupportedLayoutWidth any
 * @framerSupportedLayoutHeight any
 * @framerIntrinsicWidth 220
 * @framerIntrinsicHeight 48
 */
export default function FluidBuddha(props: Props) {
    const { installCode, position, lang } = props
    const target = parseInstallCode(installCode)
    const onCanvas = RenderTarget.current() === RenderTarget.canvas

    useEffect(() => {
        if (onCanvas || !target || typeof document === "undefined") return
        // One agent per page, even if the component is on several frames.
        if (document.querySelector("script[data-fluidbuddha-framer]")) return
        const s = document.createElement("script")
        s.src = `${target.server}/widget/loader.js`
        s.async = true
        s.setAttribute("data-fluidbuddha-framer", "")
        s.setAttribute("data-key", target.key)
        if (position !== "default") s.setAttribute("data-position", position)
        if (lang !== "auto") s.setAttribute("data-lang", lang)
        document.body.appendChild(s)
        // Framer keeps the page alive between routes, so the agent (and the
        // conversation) stays as visitors move around; nothing to clean up.
    }, [onCanvas, target?.server, target?.key, position, lang])

    if (!onCanvas) return null
    return (
        <div style={placeholder}>
            {target ? "FluidBuddha agent ✓" : "FluidBuddha: paste your install code"}
        </div>
    )
}

const placeholder: React.CSSProperties = {
    width: "100%",
    height: "100%",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    background: "rgba(201, 162, 74, 0.12)",
    border: "1px dashed #c9a24a",
    color: "#8a6d2b",
    fontSize: 13,
    fontFamily: "Inter, system-ui, sans-serif",
    padding: 8,
    textAlign: "center",
}

FluidBuddha.defaultProps = {
    installCode: "",
    position: "default",
    lang: "auto",
}

addPropertyControls(FluidBuddha, {
    installCode: {
        type: ControlType.String,
        title: "Install code",
        placeholder: "https://fbk_…@server",
        description: "From the FluidBuddha console: your website → Install → Framer.",
    },
    position: {
        type: ControlType.Enum,
        title: "Position",
        options: ["default", "bottom-right", "bottom-left"],
        optionTitles: ["Default", "Bottom right", "Bottom left"],
    },
    lang: {
        type: ControlType.Enum,
        title: "Language",
        options: ["auto", "en", "hi"],
        optionTitles: ["Auto", "English", "Hindi"],
    },
})
