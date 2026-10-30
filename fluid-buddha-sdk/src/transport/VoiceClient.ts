// WebSocket client for the multiplexed voice transport. Connect/reconnect,
// typed envelope senders, graceful fallback to text on repeated failure.

import { Channel, Envelope, bytesToBase64 } from '../protocol';

export type ConnectionStatus = 'idle' | 'connecting' | 'open' | 'closed' | 'failed';

export interface VoiceClientHandlers {
  onEnvelope: (env: Envelope) => void;
  onStatus: (status: ConnectionStatus) => void;
}

export class VoiceClient {
  private ws: WebSocket | null = null;
  private readonly url: string;
  private readonly handlers: VoiceClientHandlers;
  private retries = 0;
  private readonly maxRetries = 4;
  private manualClose = false;

  constructor(url: string, handlers: VoiceClientHandlers) {
    this.url = url;
    this.handlers = handlers;
  }

  connect(): void {
    this.manualClose = false;
    this.handlers.onStatus('connecting');
    try {
      this.ws = new WebSocket(this.url);
    } catch {
      this.handlers.onStatus('failed');
      return;
    }
    this.ws.onopen = () => {
      this.retries = 0;
      this.handlers.onStatus('open');
    };
    this.ws.onmessage = (ev) => {
      try {
        this.handlers.onEnvelope(JSON.parse(ev.data as string) as Envelope);
      } catch {
        /* ignore malformed frames */
      }
    };
    this.ws.onclose = () => {
      this.handlers.onStatus('closed');
      if (!this.manualClose) this.retry();
    };
    this.ws.onerror = () => this.ws?.close();
  }

  private retry(): void {
    if (this.retries >= this.maxRetries) {
      this.handlers.onStatus('failed');
      return;
    }
    const delay = Math.min(8000, 500 * 2 ** this.retries);
    this.retries += 1;
    setTimeout(() => this.connect(), delay);
  }

  private send(env: Envelope): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(env));
    }
  }

  sendText(text: string): void {
    this.send({ channel: 'EVENTS', type: 'text', payload: { text } });
  }
  startAudio(): void {
    this.send({ channel: 'AUDIO', type: 'start', payload: {} });
  }
  sendAudioChunk(pcm: Uint8Array): void {
    this.send({ channel: 'AUDIO', type: 'chunk', payload: { data: bytesToBase64(pcm) } });
  }
  endAudio(transcript?: string): void {
    this.send({ channel: 'AUDIO', type: 'end', payload: transcript ? { transcript } : {} });
  }
  sendState(payload: Record<string, unknown>): void {
    this.send({ channel: 'STATE', type: 'sync', payload });
  }
  sendHello(payload: Record<string, unknown> = {}): void {
    this.send({ channel: 'EVENTS', type: 'hello', payload });
  }
  sendBargeIn(payload: Record<string, unknown> = {}): void {
    this.send({ channel: 'STATE', type: 'barge_in', payload });
  }
  sendRaw(channel: Channel, type: string, payload: Record<string, unknown>): void {
    this.send({ channel, type, payload });
  }

  close(): void {
    this.manualClose = true;
    this.ws?.close();
    this.ws = null;
  }

  get isOpen(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
