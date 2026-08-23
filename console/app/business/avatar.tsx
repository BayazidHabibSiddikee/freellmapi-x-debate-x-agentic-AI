"use client";

import { useState } from "react";

export type Character = {
  id: string;
  name: string;
  image?: string;
  system_prompt?: string;
};

let _t: string | null = null;

/** Auth token from ?t= query or cookie, for <img> URLs that can't send headers. */
export function tokenQS(): string {
  if (_t === null) {
    const m =
      typeof window !== "undefined"
        ? window.location.search.match(/[?&]t=([a-f0-9]+)/)
        : null;
    _t = m ? m[1] : "";
    if (!_t && typeof document !== "undefined") {
      const c = document.cookie.match(/agentic_os_token=([a-f0-9]+)/);
      _t = c ? c[1] : "";
    }
  }
  return encodeURIComponent(_t);
}

export function Avatar({
  name,
  id,
  className = "h-10 w-10",
  textClass = "text-xs",
}: {
  name: string;
  id?: string;
  className?: string;
  textClass?: string;
}) {
  const [failed, setFailed] = useState(false);
  if (failed || !id) {
    return (
      <div
        className={`flex shrink-0 items-center justify-center rounded-full bg-muted font-mono ${className} ${textClass}`}
      >
        {name.slice(0, 2).toUpperCase()}
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={`/api/business/avatar/${encodeURIComponent(id)}.card.png?t=${tokenQS()}`}
      alt={name}
      onError={() => setFailed(true)}
      className={`${className} shrink-0 rounded-full object-cover`}
    />
  );
}
