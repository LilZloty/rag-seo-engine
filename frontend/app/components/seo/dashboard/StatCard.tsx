import React from 'react';
import { TrendingUpIcon, TrendingDownIcon } from '../../ui/Icons';

interface StatCardProps {
    title: string;
    value: string | number;
    subtitle?: string;
    trend?: { value: number; isPositive: boolean };
    icon: React.ReactNode;
    color: string;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, subtitle, trend, icon, color }) => (
    <div className="bg-[#111111] border border-[#222] p-6">
        <div className="flex items-start justify-between">
            <div>
                <p className="text-[#666666] text-sm mb-1">{title}</p>
                <p className="text-3xl font-bold text-white">{value}</p>
                {subtitle && <p className="text-[#555555] text-xs mt-1">{subtitle}</p>}
                {trend && (
                    <div className={`flex items-center gap-1 mt-2 text-sm ${trend.isPositive ? 'text-[#f7b500]' : 'text-[#888888]'}`}>
                        {trend.isPositive ? <TrendingUpIcon className="size-5" /> : <TrendingDownIcon className="size-5" />}
                        <span>{trend.isPositive ? '+' : ''}{trend.value}% vs last period</span>
                    </div>
                )}
            </div>
            <div className={`p-3 ${color}`}>
                {icon}
            </div>
        </div>
    </div>
);

export default StatCard;
