// Design Level 2 message stack (req iii/iv). Messages stack just above the text
// box: the newest sits at the bottom (most opaque) and older ones drift upward
// with increasing transparency until the topmost is fully transparent. No chat
// panel, no scrollback — a fading column of recent turns.

const MAX_VISIBLE = 6;

export class MessageStack {
  constructor(private readonly container: HTMLElement) {}

  /** Append a turn. The new line becomes the most-opaque bottom entry; older
   *  lines fade as they rise. */
  push(text: string, who: 'user' | 'agent'): void {
    if (!text.trim()) return;
    const line = document.createElement('div');
    line.className = `l2-msg ${who}`;
    line.textContent = text;
    this.container.appendChild(line);
    while (this.container.childElementCount > MAX_VISIBLE) {
      this.container.firstElementChild?.remove();
    }
    this.restyle();
  }

  clear(): void {
    this.container.replaceChildren();
  }

  /** Bottom (newest) = opaque; each step up loses opacity; topmost ~0. */
  private restyle(): void {
    const items = Array.from(this.container.children) as HTMLElement[];
    const total = items.length;
    items.forEach((el, i) => {
      const fromBottom = total - 1 - i;           // 0 = newest
      const opacity = Math.max(0, 1 - fromBottom / (MAX_VISIBLE - 1));
      el.style.opacity = opacity.toFixed(3);
      // Slight upward scale-down for depth.
      el.style.transform = `translateY(${-fromBottom * 1}px)`;
    });
  }
}
