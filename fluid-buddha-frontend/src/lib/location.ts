"use client";
import { useSyncExternalStore } from "react";

const noop = () => () => {};

/** A query parameter of the current URL, read on the client only (avoids
 *  `useSearchParams`, which needs a Suspense boundary on prerendered pages). */
export function useQueryParam(name: string): string | null {
  return useSyncExternalStore(noop, () => new URLSearchParams(window.location.search).get(name), () => null);
}

/** A parameter of the URL fragment (`#token=…`). */
export function useHashParam(name: string): string | null {
  return useSyncExternalStore(noop, () => new URLSearchParams(window.location.hash.slice(1)).get(name),
    () => null);
}
