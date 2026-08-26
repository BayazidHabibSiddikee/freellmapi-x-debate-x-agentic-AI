"use client";

import { useState } from "react";

export type Character = {
  id: string;
  name: string;
  image?: string;
  system_prompt?: string;
};

/** Auth token — no longer needed for localhost, returns empty string. */
export function tokenQS(): string {
  return "";
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
