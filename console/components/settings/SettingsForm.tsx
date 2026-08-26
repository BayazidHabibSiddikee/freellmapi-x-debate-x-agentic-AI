"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

export default function SettingsForm({ initialConfig }: { initialConfig: any }) {
  const [keys, setKeys] = useState({
    telegram_bot_token: initialConfig.telegram_bot_token || "",
    gmail_api_key: initialConfig.gmail_api_key || "",
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
    } catch (e) {
      alert(`Failed to save ${key}`);
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-2">
        <label className="text-xs font-medium text-muted-foreground">Telegram Bot Token</label>
        <div className="flex gap-2">
          <Input
            value={keys.telegram_bot_token}
            onChange={(e) => setKeys({ ...keys, telegram_bot_token: e.target.value })}
            placeholder="Enter bot token..."
            className="font-mono text-xs"
          />
          <Button
            size="sm"
            onClick={() => save("telegram_bot_token", keys.telegram_bot_token)}
            disabled={saving === "telegram_bot_token"}
          >
            {saving === "telegram_bot_token" ? "..." : "Save"}
          </Button>
        </div>
      </div>

      <div className="grid gap-2">
        <label className="text-xs font-medium text-muted-foreground">Gmail API Key</label>
        <div className="flex gap-2">
          <Input
            value={keys.gmail_api_key}
            onChange={(e) => setKeys({ ...keys, gmail_api_key: e.target.value })}
            placeholder="Enter API key..."
            className="font-mono text-xs"
          />
          <Button
            size="sm"
            onClick={() => save("gmail_api_key", keys.gmail_api_key)}
            disabled={saving === "gmail_api_key"}
          >
            {saving === "gmail_api_key" ? "..." : "Save"}
          </Button>
        </div>
      </div>
    </div>
  );
}
