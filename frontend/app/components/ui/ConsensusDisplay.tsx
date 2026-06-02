'use client';

import React from 'react';
import { Badge } from './Badge';
import { ProgressBar } from './ProgressBar';

interface ConsensusMetadata {
  mode: string;
  agents_used: string[];
  consensus_score: number;
  task_type?: string;
}

interface ConsensusDisplayProps {
  metadata: ConsensusMetadata;
  variant?: 'full' | 'compact' | 'inline';
  showAgents?: boolean;
}

export function ConsensusDisplay({ 
  metadata, 
  variant = 'full',
  showAgents = true 
}: ConsensusDisplayProps) {
  const { mode, agents_used, consensus_score, task_type } = metadata;

  // Color based on consensus score
  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-400';
    if (score >= 60) return 'text-yellow-400';
    return 'text-red-400';
  };

  const getBadgeVariant = (score: number): 'success' | 'warning' | 'default' => {
    if (score >= 80) return 'success';
    if (score >= 60) return 'warning';
    return 'default';
  };

  if (variant === 'inline') {
    return (
      <span className="inline-flex items-center gap-2 text-xs">
        <Badge variant={getBadgeVariant(consensus_score)}>
          {consensus_score}% consensus
        </Badge>
        <span className="text-zinc-500">
          ({agents_used.length} agents)
        </span>
      </span>
    );
  }

  if (variant === 'compact') {
    return (
      <div className="flex items-center gap-2 flex-wrap">
        <Badge variant="default" className="text-xs">
          {mode}
        </Badge>
        <Badge variant={getBadgeVariant(consensus_score)}>
          {consensus_score}%
        </Badge>
      </div>
    );
  }

  return (
    <div className="bg-[#1a1a1a] border border-[#3a3a3a] rounded p-3">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-zinc-500 uppercase tracking-wider">
          Multi-Agent Consensus
        </span>
        <Badge variant="default">{mode}</Badge>
      </div>

      <div className="flex items-center gap-4 mb-3">
        <div className="flex-1">
          <ProgressBar 
            value={consensus_score} 
            color={consensus_score >= 70 ? 'green' : 'yellow'}
            className="h-2"
          />
        </div>
        <span className={`text-lg font-bold ${getScoreColor(consensus_score)}`}>
          {consensus_score}%
        </span>
      </div>

      {showAgents && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-zinc-500">Agents:</span>
          {agents_used.map((agent) => (
            <Badge key={agent} variant="default" className="text-xs">
              {agent.charAt(0).toUpperCase() + agent.slice(1)}
            </Badge>
          ))}
        </div>
      )}

      {task_type && (
        <div className="mt-2 text-xs text-zinc-500">
          Task: {task_type}
        </div>
      )}
    </div>
  );
}

// Agent breakdown display for detailed analysis
interface AgentBreakdown {
  harper: { verified?: boolean; notes?: string };
  benjamin: { logical_valid?: boolean; score?: number };
  lucas: { style_score?: number; suggestions?: string };
}

interface AgentBreakdownDisplayProps {
  breakdown: AgentBreakdown;
}

export function AgentBreakdownDisplay({ breakdown }: AgentBreakdownDisplayProps) {
  const agents = [
    { 
      name: 'Harper', 
      role: 'Research', 
      status: breakdown.harper?.verified ? 'verified' : 'pending',
      detail: breakdown.harper?.notes 
    },
    { 
      name: 'Benjamin', 
      role: 'Logic', 
      status: breakdown.benjamin?.logical_valid ? 'verified' : 'pending',
      score: breakdown.benjamin?.score,
      detail: `Score: ${breakdown.benjamin?.score || 'N/A'}`
    },
    { 
      name: 'Lucas', 
      role: 'Creative', 
      status: 'verified',
      score: breakdown.lucas?.style_score,
      detail: breakdown.lucas?.suggestions 
    },
  ];

  return (
    <div className="grid grid-cols-3 gap-2 mt-2">
      {agents.map((agent) => (
        <div 
          key={agent.name}
          className="bg-[#0a0a0a] border border-[#3a3a3a] rounded p-2 text-center"
        >
          <div className="text-xs font-semibold text-zinc-300">{agent.name}</div>
          <div className="text-xs text-zinc-500">{agent.role}</div>
          {agent.score && (
            <div className="text-sm font-bold text-[#F7B500] mt-1">
              {agent.score}%
            </div>
          )}
          <Badge 
            variant={agent.status === 'verified' ? 'success' : 'default'}
            className="text-xs mt-1"
          >
            {agent.status}
          </Badge>
        </div>
      ))}
    </div>
  );
}
