"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const FIELDS = [
  { key: "telegram_bot_token", label: "Telegram Bot Token", placeholder: "Enter bot token..." },
  { key: "gmail_api_key", label: "Gmail API Key", placeholder: "Enter Gmail API key..." },
  { key: "instagram_token", label: "Instagram Access Token", placeholder: "Enter Instagram token..." },
  { key: "youtube_token", label: "YouTube API Key", placeholder: "Enter YouTube API key..." },
  { key: "facebook_token", label: "Facebook Page Access Token", placeholder: "Enter Facebook token..." },
  { key: "x_token", label: "X (Twitter) Bearer Token", placeholder: "Enter X bearer token..." },
];

export default function SettingsForm({ initialConfig }: { initialConfig: any }) {
  const [keys, setKeys] = useState(() => {
    const init: Record<string, string> = {};
    FIELDS.forEach((f) => (init[f.key] = initialConfig[f.key] || ""));
    return init;
  });
  const [saving, setSaving] = useState<string | null>(null);

  async function save(key: string, value: string) {
    setSaving(key);
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, value }),
      });
      if (!res.ok) throw new Error();
    } catch {
      alert(`Failed to save ${key}`);
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="space-y-4">
      {FIELDS.map((f) => (
        <div key={f.key} className="grid gap-2">
          <label className="text-xs font-medium text-muted-foreground">{f.label}</label>
          <div className="flex gap-2">
            <Input
              type="password"
              value={keys[f.key]}
              onChange={(e) => setKeys({ ...keys, [f.key]: e.target.value })}
              placeholder={f.placeholder}
              className="font-mono text-xs"
            />
            <Button
              size="sm"
              onClick={() => save(f.key, keys[f.key])}
              disabled={saving === f.key}
            >
              {saving === f.key ? "..." : "Save"}
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}
