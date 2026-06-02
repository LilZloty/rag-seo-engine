/**
 * Multi-Agent Toggle - Example Store Design System
 * 
 * Toggle for enabling 4-agent consensus mode (Harper, Benjamin, Lucas, Captain)
 * Uses: Brand colors, subtle styling, matches existing Badge/Button patterns
 */

'use client';

import React from 'react';
import { Badge } from './Badge';

interface MultiAgentToggleProps {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  variant?: 'default' | 'compact';
  disabled?: boolean;
}

export function MultiAgentToggle({ 
  enabled, 
  onChange, 
  variant = 'default',
  disabled = false
}: MultiAgentToggleProps) {
  if (variant === 'compact') {
    return (
      <label className={`flex items-center gap-2 cursor-pointer ${disabled ? 'opacity-50 pointer-events-none' : ''}`}>
        <input
          type="checkbox"
          className="size-4 accent-[#F7B500] rounded-sm"
          checked={enabled}
          onChange={(e) => onChange(e.target.checked)}
          disabled={disabled}
        />
        <span className="text-sm text-zinc-300">Multi-Agent</span>
        {enabled && (
          <Badge variant="brand" className="text-[10px]">4A</Badge>
        )}
      </label>
    );
  }

  return (
    <label className={`flex items-center gap-3 bg-[#1a1a1a] border border-[#3a3a3a] px-4 py-2.5 cursor-pointer hover:border-[#F7B500] transition-colors rounded-sm ${disabled ? 'opacity-50 pointer-events-none' : ''}`}>
      <input
        type="checkbox"
        className="size-4 accent-[#F7B500] rounded-sm"
        checked={enabled}
        onChange={(e) => onChange(e.target.checked)}
        disabled={disabled}
      />
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-white">
          Multi-Agent
        </span>
        {enabled ? (
          <Badge variant="brand">4 AGENTS</Badge>
        ) : (
          <Badge variant="outline">OFF</Badge>
        )}
      </div>
    </label>
  );
}
